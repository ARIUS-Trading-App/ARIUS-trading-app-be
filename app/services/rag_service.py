from app.services.llm_provider_service import llm_service
from app.services.web_search_service import web_search_service
from app.services.financial_data_service import financial_data_service
from app.services.vector_db_service import vector_db_service
from app.models.user import User as UserModel
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

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
        """
        Uses an LLM to understand user intent and extract entities.
        Returns a dictionary like:
        {
            "intent": "get_stock_news",
            "entities": {
                "stock_symbols": ["AAPL", "TSLA"],
                "crypto_symbols": [],
                "timeframe": "this week",
                "topics": ["AI impact"]
            },
            "clarification_needed": False,
            "clarification_question": None
        }
        """
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
        
        response_content = await llm_serive_provider.generate_response(understanding_prompt)
        
        try:
            if response_content.startswith("```json"):
                response_content = response_content[7:]
            if response_content.endswith("```"):
                response_content = response_content[:-3]
                
            parsed_understanding = json.loads(response_content.strip())
            
            if "intent" not in parsed_understanding or "entities" not in parsed_understanding:
                raise ValueError("LLM understanding output missing required keys.")
            return parsed_understanding
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM understanding response: {e}\nRaw response: {response_content}")
            return {
                "intent": "general_chat", 
                "entities": {"stock_symbols": [], "crypto_symbols": [], "timeframe": None, "topics": [user_query]},
                "clarification_needed": True,
                "clarification_question": "I'm sorry, I had a little trouble understanding your request. Could you please rephrase it?"
            }

    async def generate_intelligent_response(self, user_query: str, current_user: UserModel, chat_history: Optional[List[Dict[str, str]]] = None):
        understanding = await self_understand_query_with_llm(user_query, current_user)
        
        print(f"LLM Understanding: {understanding}")

        if understanding.get("clarification_needed"):
            return understanding.get("clarification_question", "I'm not sure I understood. Could you rephrase?")
        
        intent = understanding.get("intent", "general_chat")
        entities = understanding.get("entities", {})
        stock_symbols = entities.get("stock_symbols", [])
        crypto_symbols = entities.get("crypto_symbols", [])
        timeframe = entities.get("timeframe")
        topics = entites.get("topics", [])
        
        context_parts = []
        user_profile_summary = self._summarize_user_profile(current_user)
        context_parts.append(f"User Profile Context:\n{user_profile_summary}")
        
        search_query_for_web = user_query
        
        if intent == "get_stock_price" and stock_symbols:
            for symbol in stock_symbols:
                quote = await financial_data_service.get_stock_quote(symbol)
                if quote and 'Global Quote' in quote and quote['Global Quote'].get('05. price'):
                    price = quote['Global Quote']['05. price']
                    context_parts.append(f"Current Price for {symbol}: ${price}")
            search_query_for_web = f"latest news or analysis for {', '.join(stock_symbols)}"

        elif intent == "get_crypto_price" and crypto_symbols:
            for symbol in crypto_symbols:
                quote_data = await financial_data_service.get_crypto_quote(symbol) 
                if quote_data and f'4a. close ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT or "USD"})' in quote_data: 
                    price = quote_data[f'4a. close ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT or "USD"})']
                    context_parts.append(f"Latest Daily Close Price for {symbol.upper()}: ${price}")
                else: 
                    crypto_price_search = await web_search_service.get_search_context(f"current price of {symbol.upper()} crypto", max_results=1)
                    if crypto_price_search and "No relevant information" not in crypto_price_search:
                         context_parts.append(f"Web Search for {symbol.upper()} Price:\n{crypto_price_search}")
            search_query_for_web = f"latest news or analysis for {', '.join(crypto_symbols)} crypto"

        elif intent == "get_stock_news" and stock_symbols:
            news_query = f"latest financial news for {', '.join(stock_symbols)}"
            if timeframe: news_query += f" in {timeframe}"
            stock_news = await web_search_service.get_search_context(news_query, max_results=3, include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"])
            if stock_news and "No relevant information" not in stock_news:
                context_parts.append(f"Stock News for {', '.join(stock_symbols)}:\n{stock_news}")
            for symbol in stock_symbols:
                overview = await financial_data_service.get_company_overview(symbol)
                if overview:
                    context_parts.append(f"Overview for {symbol}: {overview.get('Description', '')[:200]}...")

        elif intent == "get_company_info" and stock_symbols:
            for symbol in stock_symbols:
                overview = await financial_data_service.get_company_overview(symbol)
                if overview:
                    overview_summary = f"Overview for {symbol}: Name: {overview.get('Name', 'N/A')}, Sector: {overview.get('Sector', 'N/A')}, Industry: {overview.get('Industry', 'N/A')}. Description: {overview.get('Description', '')[:500]}..."
                    context_parts.append(f"Company Info for {symbol}:\n{overview_summary}")
            search_query_for_web = f"recent developments and analysis for {', '.join(stock_symbols)}"


        elif intent == "investment_suggestion" and (stock_symbols or crypto_symbols or topics):
            assets_involved = stock_symbols + crypto_symbols
            context_parts.append("Note to LLM: User is seeking an investment suggestion.")
            for asset_symbol in assets_involved:
                overview = await financial_data_service.get_company_overview(asset_symbol) 
                if overview: context_parts.append(f"Overview {asset_symbol}: {overview.get('Description', '')[:200]}...")
                
                quote_data = await financial_data_service.get_stock_quote(asset_symbol) 
                if quote_data and 'Global Quote' in quote_data and quote_data['Global Quote'].get('05. price'):
                    context_parts.append(f"Price {asset_symbol}: ${quote_data['Global Quote']['05. price']}")

            news_query = f"analysis and outlook for {', '.join(assets_involved + topics)}"
            if timeframe: news_query += f" (timeframe: {timeframe})"
            web_news = await web_search_service.get_search_context(news_query, max_results=3)
            if web_news and "No relevant information" not in web_news:
                context_parts.append(f"Web Search Context for Suggestion:\n{web_news}")

        if intent == "general_chat" or not context_parts or len(context_parts) <= 1 : 
            if topics: search_query_for_web = f"{user_query} related to {', '.join(topics)}"
            web_search_context = await web_search_service.get_search_context(search_query_for_web, max_results=2)
            if web_search_context and "No relevant information" not in web_search_context:
                context_parts.append(f"General Web Search Context:\n{web_search_context}")

        pinecone_query_text = user_query
        if topics: pinecone_query_text += " " + " ".join(topics)
        if stock_symbols: pinecone_query_text += " " + " ".join(stock_symbols)
        
       
        if "strategy" in user_query.lower() or "analysis" in user_query.lower() or "report" in user_query.lower() or topics:
            pinecone_context = await vector_db_service.get_pinecone_context(pinecone_query_text, top_k=2)
            if pinecone_context and "No relevant documents found" not in pinecone_context:
                context_parts.append(f"Information from Knowledge Base (Vector DB):\n{pinecone_context}")
        
    
        final_context = "\n\n---\n\n".join(filter(None, context_parts)) 
        
        system_prompt_for_answer = f"""You are an expert financial assistant chatbot.
        User Profile: {user_profile_summary}
        Today's Date: {datetime.now().strftime('%Y-%m-%d')}

        Your task is to answer the user's query based on the provided context.
        User's Original Query: "{user_query}"
        Understood Intent: {intent}
        Extracted Entities: {entities}

        Carefully consider the user's profile (risk appetite, experience, goals) when formulating any advice or suggestions.
        If providing investment opinions or suggestions, ALWAYS include a disclaimer: "This is not financial advice. Consult with a qualified financial advisor before making investment decisions."
        If the context is insufficient to answer the query thoroughly, state that and, if possible, suggest what additional information might be needed or where the user could look.
        Do not make up information not present in the context. If you don't know or the context doesn't say, clearly state that.
        Be clear, concise, and helpful.
        """

        messages_for_llm = [{"role": "system", "content": system_prompt_for_answer}]
        if chat_history:
            messages_for_llm.extend(chat_history)
        
        prompt_with_context = f"Based on the following context, please answer the user's original query.\n\nCONTEXT:\n{final_context if final_context else 'No specific context was retrieved for this query.'}\n\nUSER QUERY (Reminder): {user_query}"
        messages_for_llm.append({"role": "user", "content": prompt_with_context})
        
       
        llm_response = await llm_service.chat(messages_for_llm) 
        
        if isinstance(llm_response, dict) and "error" in llm_response:
            return llm_response.get("message", {}).get("content", "Sorry, I encountered an error processing your request with the LLM.")
        elif hasattr(llm_response, 'message') and 'content' in llm_response.message: 
            return llm_response.message['content']
        
        return "I'm sorry, I couldn't generate a response at this time."


rag_service = RAGService()