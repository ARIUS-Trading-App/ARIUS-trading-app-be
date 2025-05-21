# app/services/rag_service.py
from app.services.llm_provider_service import llm_service
from app.services.web_search_service import web_search_service # Ensure this is used
from app.services.financial_data_service import financial_data_service
from app.services.vector_db_service import vector_db_service
from app.models.user import User as UserModel
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
# ollama.Response for type hinting if using it directly
from ollama import ChatResponse as OllamaChatResponseType
from ollama import Message as OllamaMessageType

class RAGService:
    def _summarize_user_profile(self, user: UserModel) -> str:
        # ... (your existing code for this method) ...
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
        # ... (your existing code, ensure llm_service is used correctly) ...
        user_profile_summary = self._summarize_user_profile(current_user)
        
        understanding_prompt = f"""
        You are an expert query analyzer for a financial chatbot.
        Analyze the following user query in the context of their user profile and determine their intent and key entities.

        User Profile:
        {user_profile_summary}

        User Query: "{user_query}"

        Possible Intents:
        - "get_stock_price": User wants the current price of one or more stocks.
        - "get_stock_news": User wants recent news about specific stocks or the market.
        - "get_company_info": User wants general information or overview about a company/stock.
        - "get_crypto_price": User wants the current price of one or more cryptocurrencies.
        - "get_crypto_news": User wants recent news about specific cryptocurrencies.
        - "investment_suggestion": User is asking for advice or opinion on whether to invest, buy, or sell.
        - "portfolio_analysis": User is asking about their portfolio (requires portfolio data - future feature).
        - "market_outlook": User is asking for general market trends or predictions.
        - "compare_assets": User wants to compare two or more assets.
        - "general_chat": User is having a general conversation, not specifically financial.
        - "clarification_needed": If the query is too vague or ambiguous.

        Entities to extract:
        - "stock_symbols": List of stock ticker symbols (e.g., ["AAPL", "MSFT"]). If multiple, list all.
        - "crypto_symbols": List of cryptocurrency symbols (e.g., ["BTC", "ETH"]).
        - "timeframe": Any mention of time (e.g., "today", "this week", "last month", "since 2022").
        - "topics": Other key topics or keywords (e.g., ["AI research", "dividend yield"]).
        - "sentiment_query": If the user is asking about positive/negative sentiment.

        If the query is ambiguous or requires clarification, set "clarification_needed" to true and formulate a "clarification_question".

        Output your analysis as a JSON object only, with no other text before or after.
        Example JSON output format:
        {{
            "intent": "get_stock_news",
            "entities": {{
                "stock_symbols": ["TSLA"],
                "crypto_symbols": [],
                "timeframe": "this week",
                "topics": ["production numbers"]
            }},
            "clarification_needed": false,
            "clarification_question": null
        }}
        If no specific symbols are found but the intent implies them (e.g., "tell me about tech stocks"), leave symbols list empty.
        """
        
        # Corrected: Use llm_service.generate_response which returns a string
        response_str_from_llm = await llm_service.generate_response(prompt=understanding_prompt) 
        
        print(f"RAGService._understand_query_with_llm: Raw string from LLM for JSON parsing: '''{response_str_from_llm}'''")

        try:
            clean_response_str = response_str_from_llm.strip()
            if clean_response_str.startswith("```json"):
                # More robustly remove potential leading/trailing backticks and "json" keyword
                clean_response_str = clean_response_str.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            
            parsed_understanding = json.loads(clean_response_str)
            
            if not isinstance(parsed_understanding, dict) or "intent" not in parsed_understanding or "entities" not in parsed_understanding:
                print("RAGService._understand_query_with_llm: Parsed JSON, but missing required keys ('intent', 'entities').")
                raise ValueError("LLM understanding output structure invalid after parsing.")
            return parsed_understanding
        except (json.JSONDecodeError, ValueError) as e:
            print(f"RAGService._understand_query_with_llm: Error parsing LLM string as JSON: {e}")
            print(f"String attempted for parsing: '''{clean_response_str if 'clean_response_str' in locals() else response_str_from_llm}'''")
            # Fallback if JSON parsing fails
            return {
                "intent": "general_chat", 
                "entities": {"stock_symbols": [], "crypto_symbols": [], "timeframe": None, "topics": [user_query]},
                "clarification_needed": True,
                "clarification_question": "I'm sorry, I had difficulty understanding the details of your request. Could you please try rephrasing?"
            }

    async def generate_intelligent_response(self, user_query: str, current_user: UserModel, chat_history: Optional[List[Dict[str, str]]] = None):
        understanding = await self._understand_query_with_llm(user_query, current_user) # Corrected: self._understand_query_with_llm
        
        print(f"LLM Understanding: {understanding}")

        if understanding.get("clarification_needed"):
            return understanding.get("clarification_question", "I'm not sure I understood. Could you rephrase?")
        
        intent = understanding.get("intent", "general_chat")
        entities = understanding.get("entities", {})
        stock_symbols = entities.get("stock_symbols", [])
        crypto_symbols = entities.get("crypto_symbols", [])
        timeframe = entities.get("timeframe")
        topics = entities.get("topics", []) # Corrected: entities.get
        
        context_parts = []
        user_profile_summary = self._summarize_user_profile(current_user)
        context_parts.append(f"User Profile Context:\n{user_profile_summary}")
        
        web_search_performed_for_intent = False # NEW flag

        if intent == "get_stock_price" and stock_symbols:
            for symbol in stock_symbols:
                quote = await financial_data_service.get_stock_quote(symbol)
                if quote and 'Global Quote' in quote and quote['Global Quote'].get('05. price'):
                    price = quote['Global Quote']['05. price']
                    context_parts.append(f"Current Price for {symbol}: ${price}")
            # Supplemental web search for analysis/news
            news_query = f"latest news or analysis for {', '.join(stock_symbols)}"
            supplemental_news = await web_search_service.get_search_context(news_query, max_results=1)
            if supplemental_news and "No relevant information" not in supplemental_news:
                context_parts.append(f"Supplemental Web Info for {', '.join(stock_symbols)}:\n{supplemental_news}")
            web_search_performed_for_intent = True


        elif intent == "get_crypto_price" and crypto_symbols: # Ensure this block is complete
            for symbol in crypto_symbols:
                # Alpha Vantage crypto daily might not be "current price". Web search might be better.
                quote_data = await financial_data_service.get_crypto_quote(symbol)
                # The key from AV for daily close can be specific, e.g., '4a. close (USD)'
                # Let's make this more robust or rely more on web search for current crypto price
                price_found_api = False
                if quote_data:
                    # Try to find a close price key, it might vary
                    for key in quote_data:
                        if 'close' in key.lower() and (settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT or "USD").lower() in key.lower():
                            price = quote_data[key]
                            context_parts.append(f"Latest Daily Close Price for {symbol.upper()} (from API): ${price}")
                            price_found_api = True
                            break
                if not price_found_api:
                    crypto_price_search_result = await web_search_service.get_search_context(f"current price of {symbol.upper()} crypto", max_results=1)
                    if crypto_price_search_result and "No relevant information" not in crypto_price_search_result:
                        context_parts.append(f"Web Search for {symbol.upper()} Price:\n{crypto_price_search_result}")
            news_query = f"latest news or analysis for {', '.join(crypto_symbols)} crypto"
            supplemental_news = await web_search_service.get_search_context(news_query, max_results=1)
            if supplemental_news and "No relevant information" not in supplemental_news:
                context_parts.append(f"Supplemental Web Info for {', '.join(crypto_symbols)} crypto:\n{supplemental_news}")
            web_search_performed_for_intent = True

        elif intent == "get_stock_news" and stock_symbols:
            news_query = f"latest financial news for {', '.join(stock_symbols)}"
            if timeframe: news_query += f" covering timeframe {timeframe}"
            stock_news_results = await web_search_service.get_search_context(news_query, max_results=3, include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"])
            if stock_news_results and "No relevant information" not in stock_news_results:
                context_parts.append(f"Stock News for {', '.join(stock_symbols)}:\n{stock_news_results}")
            web_search_performed_for_intent = True
            for symbol in stock_symbols:
                overview = await financial_data_service.get_company_overview(symbol)
                if overview and overview.get('Description'):
                    context_parts.append(f"Overview for {symbol}: {overview.get('Description', '')[:200]}...")

        elif intent == "get_company_info" and stock_symbols:
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

        elif intent == "investment_suggestion" and (stock_symbols or crypto_symbols or topics):
            assets_involved = stock_symbols + crypto_symbols
            context_parts.append("Note to LLM: User is seeking an investment suggestion.")
            for asset_symbol in assets_involved: # Ensure you handle stock vs crypto here if services differ
                if asset_symbol in stock_symbols: # Crude check, improve if symbols can overlap
                    overview = await financial_data_service.get_company_overview(asset_symbol) 
                    if overview and overview.get('Description'): context_parts.append(f"Overview {asset_symbol}: {overview.get('Description', '')[:200]}...")
                    quote_data = await financial_data_service.get_stock_quote(asset_symbol) 
                    if quote_data and 'Global Quote' in quote_data and quote_data['Global Quote'].get('05. price'):
                        context_parts.append(f"Price {asset_symbol}: ${quote_data['Global Quote']['05. price']}")
                # Add similar logic for crypto if needed, using get_crypto_quote and web search for price

            news_query = f"investment analysis, risks, and outlook for {', '.join(assets_involved + topics)}"
            if timeframe: news_query += f" (considering timeframe: {timeframe})"
            web_news_results = await web_search_service.get_search_context(news_query, max_results=3)
            if web_news_results and "No relevant information" not in web_news_results:
                context_parts.append(f"Web Search Context for Suggestion:\n{web_news_results}")
            web_search_performed_for_intent = True
        
        if not web_search_performed_for_intent and (intent == "general_chat" or (not context_parts or len(context_parts) <= 1)): # Check if context_parts is empty beyond user profile
            general_search_query = user_query
            if topics: general_search_query = f"{user_query} related to {', '.join(topics)}"
            
            print(f"RAGService: Performing general web search for: {general_search_query}")
            general_web_search_context = await web_search_service.get_search_context(general_search_query, max_results=2)
            if general_web_search_context and "No relevant information" not in general_web_search_context:
                context_parts.append(f"General Web Search Context:\n{general_web_search_context}")

        pinecone_query_text = user_query
        if topics: pinecone_query_text += " " + " ".join(topics)
        if stock_symbols: pinecone_query_text += " " + " ".join(stock_symbols) # Also add crypto_symbols if relevant
        if crypto_symbols: pinecone_query_text += " " + " ".join(crypto_symbols)
        
        if "strategy" in user_query.lower() or "analysis report" in user_query.lower() or "deep dive" in user_query.lower() or intent in ["investment_suggestion", "market_outlook", "compare_assets"]:
            print(f"RAGService: Querying Pinecone with: {pinecone_query_text}")
            pinecone_context_results = await vector_db_service.get_pinecone_context(pinecone_query_text, top_k=2)
            if pinecone_context_results and "No relevant documents found" not in pinecone_context_results:
                context_parts.append(f"Information from Knowledge Base (Vector DB):\n{pinecone_context_results}")
        
        # --- End Context Gathering ---

        final_context = "\n\n---\n\n".join(filter(None, context_parts))
        if not final_context.replace(f"User Profile Context:\n{user_profile_summary}", "").strip(): # Check if only user profile is there
             final_context = "No specific external context was retrieved for this query. Please answer based on general knowledge or the user's profile if relevant."
        
        system_prompt_for_answer = f"""You are an expert financial assistant chatbot.
        User Profile: {user_profile_summary}
        Today's Date: {datetime.now().strftime('%Y-%m-%d')}

        Your task is to answer the user's query based on the provided context.
        User's Original Query: "{user_query}"
        Understood Intent: {intent}
        Extracted Entities: {entities}

        Carefully consider the user's profile when formulating any advice.
        If providing investment opinions, ALWAYS include a disclaimer: "This is not financial advice. Consult a qualified professional."
        If context is insufficient or empty (beyond user profile), state that you couldn't find specific information but can try to answer generally, or ask for clarification. Do not make up information.
        Be clear, concise, and helpful.
        """

        final_answer_messages = [{"role": "system", "content": system_prompt_for_answer}]
        if chat_history:
            final_answer_messages.extend(chat_history)
        
        # Ensure the prompt for the final LLM call isn't overly repetitive if context is minimal
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