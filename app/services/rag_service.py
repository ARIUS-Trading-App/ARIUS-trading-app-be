from app.services.llm_provider_service import llm_service
from app.services.web_search_service import web_search_service 
from app.services.financial_data_service import financial_data_service
from app.services.vector_db_service import vector_db_service
from app.core.config import settings
from app.models.user import User as UserModel
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
from ollama import ChatResponse as OllamaChatResponseType
from ollama import Message as OllamaMessageType

class RAGService:
    def _summarize_user_profile(self, user: UserModel) -> str:
        summary = f"User: {user.username} (Email: {user.email})\n"
        if user.trading_experience:
            summary += f"Trading Experience: {user.trading_experience.value}\n"
        if user.risk_appetite:
            summary += f"Risk Appetite: {user.risk_appetite.value}\n"
        if user.investment_goals:
            summary += f"Investment Goals: {user.investment_goals.value}\n"
        if user.preferred_asset_classes:
            summary += f"Preferred Assets: {', '.join(user.preferred_asset_classes)}\n"
        if user.interests_for_feed:
            summary += f"Interests: {', '.join(user.interests_for_feed)}\n"
        return summary.strip()

    async def _understand_query_with_llm(self, user_query: str, current_user: UserModel) -> Dict[str, Any]:
        user_profile_summary = self._summarize_user_profile(current_user)
        
        understanding_prompt = f"""
        You are an expert query analyzer for a financial chatbot. Your primary goal is to meticulously analyze user queries, identify ALL intents expressed, and extract ALL relevant financial entities.

        User Profile:
        {user_profile_summary}

        User Query: "{user_query}"

        **Core Task:**
        Decompose the user query into one or more distinct intents. For each intent, identify all associated entities. Aggregate all unique intents into a list and all unique entities into their respective lists/fields in the final JSON output.

        **Possible Intents (the "intent" field in the output JSON should be a LIST of these):**
        - "get_stock_price": User wants the current price of one or more stocks.
        - "get_stock_news": User wants recent news about specific stocks or the market.
        - "get_company_info": User wants general information, an overview, or specific stats (like performance, fundamentals) about a company/stock.
        - "get_crypto_price": User wants the current price of one or more cryptocurrencies.
        - "get_crypto_news": User wants recent news about specific cryptocurrencies.
        - "get_crypto_info": User wants general information, an overview, or specific stats (like performance, fundamentals) about a cryptocurrency.
        - "investment_suggestion": User is asking for advice or opinion on whether to invest, buy, or sell an asset.
        - "portfolio_analysis": User is asking about their portfolio (requires portfolio data - future feature).
        - "market_outlook": User is asking for general market trends or predictions.
        - "compare_assets": User wants to compare two or more assets.
        - "general_chat": User is having a general conversation, not specifically financial.
        - "clarification_needed": If the query is too vague, ambiguous, or essential information is missing.

        **Entities to Extract (ensure all relevant entities from the query are captured):**
        - "stock_symbols": List of stock ticker symbols (e.g., ["AAPL", "MSFT"]). Extract ALL mentioned. Map company names (e.g., "Apple", "Nvidia") to their likely ticker symbols.
        - "crypto_symbols": List of cryptocurrency symbols (e.g., ["BTC", "ETH"]). Extract ALL mentioned. Map cryptocurrency names (e.g., "Bitcoin", "Ethereum") to their likely symbols.
        - "timeframe": Any mention of time (e.g., "today", "this week", "last month", "since 2022"). If multiple distinct timeframes are mentioned that apply globally or to significant parts of the query, try to capture the most encompassing or list them if appropriate for a single string field (e.g., "today and last week"). For now, provide a single string.
        - "topics": Other key topics, keywords, or specific data points requested (e.g., ["AI research", "dividend yield", "production numbers", "performance", "stats"]). Capture ALL relevant topics as a list.
        - "sentiment_query": (Boolean) True if the user is asking about positive/negative sentiment or market feeling, false otherwise.

        **Output Instructions:**
        - Respond ONLY with a single JSON object. Do NOT include any text before or after the JSON.
        - The "intent" field in the JSON output MUST be a list of strings, even if only one intent is detected.
        - Ensure ALL stock symbols, crypto symbols, and relevant topics mentioned in the query are included in their respective lists within the "entities" object. Do not limit to just one per entity type.
        - If no specific symbols are found but an intent implies them (e.g., "tell me about tech stocks news"), leave the relevant symbols list empty but still include the intent.
        - If the query is ambiguous or requires clarification to proceed, set "clarification_needed" to true and formulate a concise "clarification_question" to ask the user. Otherwise, "clarification_needed" is false and "clarification_question" is null.
        - Always return a JSON object adhering to the specified structure. If no information is extractable for a field, use an appropriate empty representation, [].      
        **Example of desired JSON output format for a complex query:**

        Query: "What's the price of Tesla stock and Bitcoin? Also, find news about Apple's new products this month and tell me if I should buy Ethereum. How is Google performing lately?"

        ```json
        {{
            "intent": [
                "get_stock_price",
                "get_crypto_price",
                "get_stock_news",
                "investment_suggestion",
                "get_company_info"
            ],
            "entities": {{
                "stock_symbols": ["TSLA", "AAPL", "GOOGL"],
                "crypto_symbols": ["BTC", "ETH"],
                "timeframe": "this month",
                "topics": ["new products", "performance"]
            }},
            "clarification_needed": false,
            "clarification_question": null
            
            Your Turn: Analyze the User Query based on the User Profile and the instructions above.
        }}
        """
        
        response_str_from_llm = await llm_service.generate_response(prompt=understanding_prompt, is_json = True) 
        
        print(f"RAGService._understand_query_with_llm: Raw string from LLM for JSON parsing: '''{response_str_from_llm}'''")

        try:
            clean_response_str = response_str_from_llm.strip()
            if clean_response_str.startswith("```json"):
                clean_response_str = clean_response_str.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            
            parsed_understanding = json.loads(clean_response_str)
            
            if not isinstance(parsed_understanding, dict) or "intent" not in parsed_understanding or "entities" not in parsed_understanding:
                print("RAGService._understand_query_with_llm: Parsed JSON, but missing required keys ('intent', 'entities').")
                raise ValueError("LLM understanding output structure invalid after parsing.")
            return parsed_understanding
        except (json.JSONDecodeError, ValueError) as e:
            print(f"RAGService._understand_query_with_llm: Error parsing LLM string as JSON: {e}")
            print(f"String attempted for parsing: '''{clean_response_str if 'clean_response_str' in locals() else response_str_from_llm}'''")
            return {
                "intent": "general_chat", 
                "entities": {"stock_symbols": [], "crypto_symbols": [], "timeframe": None, "topics": [user_query]},
                "clarification_needed": True,
                "clarification_question": "I'm sorry, I had difficulty understanding the details of your request. Could you please try rephrasing?"
            }

    async def generate_intelligent_response(self, user_query: str, current_user: UserModel, chat_history: Optional[List[Dict[str, str]]] = None):
        understanding = await self._understand_query_with_llm(user_query, current_user) 
        
        print(f"LLM Understanding: {understanding}")

        if understanding.get("clarification_needed"):
            return understanding.get("clarification_question", "I'm not sure I understood. Could you rephrase?")
        
        intent = understanding.get("intent", "general_chat")
        entities = understanding.get("entities", {})
        stock_symbols = entities.get("stock_symbols", [])
        crypto_symbols = entities.get("crypto_symbols", [])
        timeframe = entities.get("timeframe")
        topics = entities.get("topics", []) 
        
        context_parts = []
        user_profile_summary = self._summarize_user_profile(current_user)
        context_parts.append(f"User Profile Context:\n{user_profile_summary}")
        
        web_search_performed_for_intent = False 

        if "get_stock_price" in intent and stock_symbols:
            for symbol in stock_symbols:
                quote = await financial_data_service.get_stock_quote(symbol)
                if quote and quote.get('05. price'):
                    price = quote.get('05. price')
                    context_parts.append(f"Current Price for {symbol}: ${price}")
            news_query = f"latest news or analysis for {', '.join(stock_symbols)}"
            supplemental_news = await web_search_service.get_search_context(news_query, max_results=1)
            if supplemental_news and "No relevant information" not in supplemental_news:
                context_parts.append(f"Supplemental Web Info for {', '.join(stock_symbols)}:\n{supplemental_news}")
            web_search_performed_for_intent = True


        if "get_crypto_price" in intent and crypto_symbols: 
            for symbol in crypto_symbols:
                crypto_price = await financial_data_service.get_crypto_quote(symbol)
                print("!!!!!!!")
                print(crypto_price)
                price_found_api = False
                if crypto_price:
                    print("???")
                    context_parts.append(f"Latest Daily Close Price for {symbol.upper()} (from API): ${crypto_price}")
                    price_found_api = True
                if not price_found_api:
                    crypto_price_search_result = await web_search_service.get_search_context(f"current price of {symbol.upper()} crypto", max_results=1)
                    if crypto_price_search_result and "No relevant information" not in crypto_price_search_result:
                        context_parts.append(f"Web Search for {symbol.upper()} Price:\n{crypto_price_search_result}")
            news_query = f"latest news or analysis for {', '.join(crypto_symbols)} crypto"
            supplemental_news = await web_search_service.get_search_context(news_query, max_results=1)
            if supplemental_news and "No relevant information" not in supplemental_news:
                context_parts.append(f"Supplemental Web Info for {', '.join(crypto_symbols)} crypto:\n{supplemental_news}")
            web_search_performed_for_intent = True

        if "get_stock_news" in intent and stock_symbols:
            news_query = f"latest financial news for {', '.join(stock_symbols)}"
            if timeframe: news_query += f" covering timeframe {timeframe}"
            stock_news_results = await web_search_service.get_search_context(news_query, max_results=5, include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"])
            if stock_news_results and "No relevant information" not in stock_news_results:
                context_parts.append(f"Stock News for {', '.join(stock_symbols)}:\n{stock_news_results}")
            web_search_performed_for_intent = True
            for symbol in stock_symbols:
                overview = await financial_data_service.get_company_overview(symbol)
                if overview and overview.get('Description'):
                    context_parts.append(f"Overview for {symbol}: {overview.get('Description', '')[:200]}...")

        if "get_company_info" in intent and stock_symbols:
            for symbol in stock_symbols:
                overview = await financial_data_service.get_company_overview(symbol)
                if overview and overview.get('Description'):
                    overview_summary = f"Overview for {symbol}: Name: {overview.get('Name', 'N/A')}, Sector: {overview.get('Sector', 'N/A')}, Industry: {overview.get('Industry', 'N/A')}. Description: {overview.get('Description', '')[:500]}..."
                    context_parts.append(f"Company Info for {symbol}:\n{overview_summary}")
            news_query = f"recent developments and analysis for {', '.join(stock_symbols)}"
            supplemental_news = await web_search_service.get_search_context(news_query, max_results=2)
            if supplemental_news and "No relevant information" not in supplemental_news:
                context_parts.append(f"Recent Developments (Web Search) for {', '.join(stock_symbols)}:\n{supplemental_news}")
            web_search_performed_for_intent = True

        if "investment_suggestion" in intent and (stock_symbols or crypto_symbols or topics):
            assets_involved = stock_symbols + crypto_symbols
            context_parts.append("Note to LLM: User is seeking an investment suggestion.")
            for asset_symbol in assets_involved: 
                if asset_symbol in stock_symbols: 
                    overview = await financial_data_service.get_company_overview(asset_symbol) 
                    if overview and overview.get('Description'): context_parts.append(f"Overview {asset_symbol}: {overview.get('Description', '')[:200]}...")
                    quote_data = await financial_data_service.get_stock_quote(asset_symbol) 
                    if quote_data and 'Global Quote' in quote_data and quote_data['Global Quote'].get('05. price'):
                        context_parts.append(f"Price {asset_symbol}: ${quote_data['Global Quote']['05. price']}")

            news_query = f"investment analysis, risks, and outlook for {', '.join(assets_involved + topics)}"
            if timeframe: news_query += f" (considering timeframe: {timeframe})"
            web_news_results = await web_search_service.get_search_context(news_query, max_results=3)
            if web_news_results and "No relevant information" not in web_news_results:
                context_parts.append(f"Web Search Context for Suggestion:\n{web_news_results}")
            web_search_performed_for_intent = True
        
        if not web_search_performed_for_intent and (intent == "general_chat" or (not context_parts or len(context_parts) <= 1)): 
            general_search_query = user_query
            if topics: general_search_query = f"{user_query} related to {', '.join(topics)}"
            
            print(f"RAGService: Performing general web search for: {general_search_query}")
            general_web_search_context = await web_search_service.get_search_context(general_search_query, max_results=2)
            if general_web_search_context and "No relevant information" not in general_web_search_context:
                context_parts.append(f"General Web Search Context:\n{general_web_search_context}")

        pinecone_query_text = user_query
        if topics: pinecone_query_text += " " + " ".join(topics)
        if stock_symbols: pinecone_query_text += " " + " ".join(stock_symbols) 
        if crypto_symbols: pinecone_query_text += " " + " ".join(crypto_symbols)
        
        if "strategy" in user_query.lower() or "analysis report" in user_query.lower() or "deep dive" in user_query.lower() or intent in ["investment_suggestion", "market_outlook", "compare_assets"]:
            print(f"RAGService: Querying Pinecone with: {pinecone_query_text}")
            pinecone_context_results = await vector_db_service.get_pinecone_context(pinecone_query_text, top_k=2)
            if pinecone_context_results and "No relevant documents found" not in pinecone_context_results:
                context_parts.append(f"Information from Knowledge Base (Vector DB):\n{pinecone_context_results}")
        

        final_context = "\n\n---\n\n".join(filter(None, context_parts))
        if not final_context.replace(f"User Profile Context:\n{user_profile_summary}", "").strip(): 
             final_context = "No specific external context was retrieved for this query. Please answer based on general knowledge or the user's profile if relevant."
        
        
        system_prompt_for_answer = f"""
        You are a highly capable, trustworthy, and articulate financial assistant chatbot.
        Your primary goal is to provide clear, comprehensive, and helpful answers to the user.

        **Context for Your Response:**
        1.  **User Profile:** {user_profile_summary}
        2.  **Today's Date:** {datetime.now().strftime('%Y-%m-%d')}
        3.  **User's Original Query:** "{user_query}"
        4.  **Understood Intent(s) & Entities (from previous analysis):**
            *   Intents: {intent} 
            *   Entities: {entities}

        **Your Task: Generate a comprehensive and helpful response to the user.**

        **Key Guidelines for Your Response:**

        *   **Directly Address the Query:** Ensure your answer directly addresses all aspects of the "User's Original Query" and covers all "Understood Intent(s)". If multiple intents or questions are present, address each one logically.
        *   **Utilize Retrieved Information:** Base your answer *primarily* on the "Retrieved Information". If specific data points, numbers, or news summaries are available in the "Retrieved Information", incorporate them directly into your answer.
        *   **Natural & Knowledgeable Tone:**
            *   Speak as if you possess the knowledge directly. **AVOID** phrases like "According to the data I received," "The API returned," "Based on the information provided to me," or "I searched the web and found...",  "Based on the provided web search context and user request for an investment suggestion".
            *   Do NOT mention knowledge cutoffs. The "Retrieved Information" is assumed to be real-time or relevant.
        *   **Handling Insufficient Information:**
            *   If the "Retrieved Information" is empty, insufficient for a specific part of the query, or explicitly states "no data found," gracefully state that you couldn't find the specific information for that part. For example: "I couldn't find specific production numbers for Tesla this week, but I can share recent news about their stock."
            *   Do NOT invent information or speculate beyond the provided data. It's better to say you don't know than to be wrong.
        *   **Clarity and Conciseness:**
            *   Provide specific and actionable answers where appropriate.
            *   If you must use a technical term, briefly explain it.
            *   Avoid unnecessary fluff or overly verbose explanations ("yapping"). Get to the point and be comprehensive and in depth while still being polite and helpful.
        *   **Investment Opinions/Advice:**
            *   If the query asks for an investment opinion ("should I buy X?", "is Y a good investment?"), and you are providing one based on the "Retrieved Information" or general market principles:
                *   Frame it cautiously (e.g., "Some analysts suggest...", "Considering its recent performance...", "Factors to consider include...").
                *   ALWAYS include the disclaimer: "This is not financial advice. Always do your own research and consult with a qualified financial professional before making investment decisions."
        *   **User Profile Consideration:** Subtly tailor the language and depth of explanation based on the "User Profile," if relevant information is present (e.g., beginner vs. experienced investor).
        *   **Structure:** If answering multiple points, consider using short paragraphs or bullet points for readability if it makes sense for the flow of the conversation.
                
        **Now, generate the response for the user.**
        """

        final_answer_messages = [{"role": "system", "content": system_prompt_for_answer}]
        if chat_history:
            final_answer_messages.extend(chat_history)
        
        prompt_for_final_llm = f"User Query: {user_query}\n\nRelevant Context (if any):\n{final_context}\n\nPlease provide your answer."
        final_answer_messages.append({"role": "user", "content": prompt_for_final_llm})
        
        print(f"RAGService: Messages for final LLM call: {json.dumps(final_answer_messages, indent=2)}") # DEBUG
       
        llm_final_response_obj = await llm_service.chat(final_answer_messages)
        
        print(f"RAGService: Raw final LLM response object: type={type(llm_final_response_obj)}, content='{llm_final_response_obj}'") # DEBUG

        if isinstance(llm_final_response_obj, OllamaChatResponseType):
            if hasattr(llm_final_response_obj, 'message') and \
               isinstance(llm_final_response_obj.message, OllamaMessageType) and \
               hasattr(llm_final_response_obj.message, 'content') and \
               isinstance(llm_final_response_obj.message.content, str):
                return llm_final_response_obj.message.content
            else:
                print(f"RAGService: Final answer LLM response (OllamaChatResponseType) structure issue.")
                return "There was an issue processing the LLM's final response structure."
        elif isinstance(llm_final_response_obj, dict) and "error" in llm_final_response_obj:
            print(f"RAGService: Error from llm_service.chat (final answer): {llm_final_response_obj.get('error')}")
            return llm_final_response_obj.get("llm_message_content", "An error occurred with the final LLM call.")
        
        print(f"RAGService: Unexpected final answer LLM response type after all checks.")
        return "I'm sorry, I couldn't generate a final response due to an unexpected issue."

rag_service = RAGService()