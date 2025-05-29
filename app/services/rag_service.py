from app.services.llm_provider_service import llm_service
from app.models.user import User as UserModel
from app.llm_tools.tool_schemas import AVAILABLE_TOOLS_SCHEMAS
from app.llm_tools.tool_functions import TOOL_FUNCTIONS
from typing import Dict, List, Optional, Any, AsyncGenerator
import json
from datetime import datetime
import inspect
import traceback
from cachetools import TTLCache # Added for caching

MAX_TOOL_ITERATIONS = 5 # Slightly reduced from 6, can be tuned

class RAGService:
    def __init__(self):
        # Cache for tool execution results. Key: (tool_name, frozenset(args.items()))
        # General TTL of 60 seconds. Specific tools could have different TTLs if a more complex cache manager is built.
        self.tool_execution_cache = TTLCache(maxsize=200, ttl=60)
        # Example: Define more granular TTLs if needed, though TTLCache itself has one TTL.
        # For more granular TTLs, you might use multiple TTLCache instances or a different caching lib.
        # self.price_cache = TTLCache(maxsize=50, ttl=30) # e.g., for prices
        # self.overview_cache = TTLCache(maxsize=50, ttl=3600) # e.g., for company overviews
        # For this implementation, we'll use the single self.tool_execution_cache.

    def _summarize_user_profile(self, user: UserModel) -> str:
        # ... (existing code)
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


    def _clean_llm_json_response(self, llm_response_str: str) -> str:
        # ... (existing code)
        clean_response_str = llm_response_str.strip()
        if clean_response_str.startswith("```json"):
            clean_response_str = clean_response_str[len("```json"):].strip()
        elif clean_response_str.startswith("```"):
            clean_response_str = clean_response_str[len("```"):].strip()
        
        if clean_response_str.endswith("```"):
            clean_response_str = clean_response_str[:-len("```")].strip()
        return clean_response_str

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        # Ensure tool_args are consistently ordered for caching if they are dicts
        # frozenset of items is good for dicts within args if any.
        # For simplicity, assuming args are mostly primitive or Pydantic models that stringify consistently.
        # A more robust key would involve deep sorting of dicts/lists if they appear in args.
        cache_key_args = tuple(sorted(tool_args.items())) if isinstance(tool_args, dict) else tool_args
        cache_key = (tool_name, cache_key_args)

        if cache_key in self.tool_execution_cache:
            print(f"Cache HIT for tool: {tool_name} with args: {tool_args}")
            return self.tool_execution_cache[cache_key]
        print(f"Cache MISS for tool: {tool_name} with args: {tool_args}")

        if tool_name not in TOOL_FUNCTIONS:
            return f"Error: Tool '{tool_name}' not found."

        tool_function = TOOL_FUNCTIONS[tool_name]
        sig = inspect.signature(tool_function)
        
        # Filter arguments to only those accepted by the function
        valid_args = {}
        for k, v in tool_args.items():
            if k in sig.parameters:
                param_type = sig.parameters[k].annotation
                # Basic type coercion for common cases (e.g., LLM sends "5" for an int)
                try:
                    if param_type == int and not isinstance(v, int):
                        v = int(v)
                    elif param_type == float and not isinstance(v, float):
                        v = float(v)
                    # Add other coercions if necessary
                except ValueError:
                    # If coercion fails, it might be a genuinely incorrect arg type
                    print(f"Warning: Could not coerce argument '{k}' value '{v}' to type {param_type} for tool {tool_name}")
                    # Depending on strictness, you might return an error here or pass it as is
                valid_args[k] = v
            else:
                print(f"Warning: Argument '{k}' not accepted by tool {tool_name}. Ignoring.")
        
        try:
            print(f"Executing tool: {tool_name} with valid_args: {valid_args}")
            if inspect.iscoroutinefunction(tool_function):
                result = await tool_function(**valid_args)
            else:
                result = tool_function(**valid_args)

            result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            
            print(f"Tool {tool_name} result (first 300 chars): {result_str[:300]}...")
            self.tool_execution_cache[cache_key] = result_str # Cache successful result
            return result_str
        except Exception as e:
            print(f"Error executing tool {tool_name} with args {valid_args}: {e}")
            traceback.print_exc()
            error_message = f"Error during {tool_name} execution with arguments {valid_args}: {str(e)}."
            # Add more specific feedback for asset type mismatch
            # This relies on tool names like 'get_stock_quote' and 'get_crypto_exchange_rate'
            # and common argument names like 'symbol'.
            arg_symbol = valid_args.get("symbol", valid_args.get("from_currency_symbol"))
            if arg_symbol:
                if "stock" in tool_name.lower() or "company" in tool_name.lower():
                    error_message += f" Please ensure '{arg_symbol}' is a valid stock ticker for this function. If it's a cryptocurrency, use a crypto-specific tool."
                elif "crypto" in tool_name.lower() or "digital_currency" in tool_name.lower():
                    error_message += f" Please ensure '{arg_symbol}' is a valid cryptocurrency symbol for this function. If it's a stock, use a stock-specific tool."
            return error_message

    async def generate_intelligent_response(
        self,
        user_query: str,
        current_user: UserModel,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:

        # --- BEGIN PRE-FILTER FOR SIMPLE QUERIES ---
        normalized_query = user_query.lower().strip()
        simple_greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "hiya", "howdy"]
        simple_closings_thanks = ["thanks", "thank you", "thx", "ty", "appreciate it"]
        simple_closings_bye = ["bye", "goodbye", "see ya", "later"]
        simple_banter = ["how are you", "how are you doing", "what's up", "sup"]

        if normalized_query in simple_greetings:
            simple_response_messages = [
                {"role": "system", "content": "You are a friendly and concise assistant. Respond warmly to the user's greeting."},
                {"role": "user", "content": user_query}
            ]
            async for chunk in llm_service.generate_streamed_response(messages=simple_response_messages, use_smaller_model=True):
                yield chunk
            yield "\n"
            return
        
        if any(phrase in normalized_query for phrase in simple_closings_thanks):
            yield "You're welcome! Let me know if there's anything else I can assist with.\n"
            return
        
        if normalized_query in simple_closings_bye:
            yield "Goodbye! Have a great day.\n"
            return

        if normalized_query in simple_banter:
            simple_response_messages = [
                {"role": "system", "content": "You are a friendly assistant. Respond to the user's conversational opening in a brief and engaging way."},
                {"role": "user", "content": user_query}
            ]
            async for chunk in llm_service.generate_streamed_response(messages=simple_response_messages, use_smaller_model=True):
                yield chunk
            yield "\n"
            return
        # --- END PRE-FILTER ---

        user_profile_summary = self._summarize_user_profile(current_user)
        # Ensure tool names in this string EXACTLY match the keys in TOOL_FUNCTIONS / AVAILABLE_TOOLS_SCHEMAS
        tool_schemas_for_llm_str = json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2)

        conversation_messages_for_this_turn: List[Dict[str, Any]] = []
        if chat_history:
            conversation_messages_for_this_turn.extend([msg if isinstance(msg, dict) else msg.model_dump() for msg in chat_history])

        current_contextual_query_for_llm = user_query
        accumulated_tool_outputs = []

        for iteration in range(MAX_TOOL_ITERATIONS):
            # Construct the system prompt for tool selection
            # IMPORTANT: Tool names like `get_stock_quote` and `get_crypto_price` (or `get_crypto_exchange_rate`)
            # mentioned here MUST match the actual tool names provided in `AVAILABLE_TOOLS_SCHEMAS`.
            # I am using `get_stock_quote` and `get_crypto_exchange_rate` as examples based on FinancialDataService.
            # Adjust if your tool schema names them differently (e.g., a generic `get_asset_price`).
            system_prompt_tool_selection = f"""You are a sophisticated financial assistant. Your primary goal is to accurately understand the user's query and utilize available tools to gather necessary information, or decide to answer directly if appropriate.

User Profile:
{user_profile_summary}

Today's Date: {datetime.now().strftime('%Y-%m-%d')}

Available Tools (ensure your chosen tool_name and arguments match these schemas exactly):
{tool_schemas_for_llm_str}

**Your Task & Decision Process (Iterative):**
1.  **Analyze User's Request, History & Current Turn Info:** Carefully consider:
    a. The user's original request for this turn: "{user_query}"
    b. The overall chat history (if any from previous turns).
    c. Information gathered from tool calls *in this current turn so far* (see below).
    d. The current contextual query: "{current_contextual_query_for_llm}"
2.  **Tool Selection (Primary Action):**
    *   Identify the *next logical piece of information* needed to address any *unanswered parts* of the user's original request.
    *   If a tool can provide this, select the *single most appropriate tool*.
    *   **Respond ONLY with a single JSON object for the chosen tool:** `{{"tool_name": "TOOL_NAME", "arguments": {{"arg1": "value1", ...}}}}`
    *   **Argument Inference:** Infer arguments like stock symbols (e.g., "Apple company" -> "AAPL", "Bitcoin crypto" -> "BTC", "Ether" -> "ETH") if not explicitly provided. Be precise.
    *   **Asset Type Specificity (CRITICAL):**
        *   Pay EXTREMELY close attention to tool descriptions for asset types.
        *   For company stocks (e.g., AAPL, MSFT), use tools like `get_stock_quote`, `get_daily_adjusted_stock_data`, etc.
        *   For cryptocurrencies (e.g., BTC, ETH, SOL), use tools like `get_crypto_exchange_rate`, `get_daily_crypto_data`, etc.
        *   **DO NOT confuse stocks and cryptocurrencies.** If unsure about an asset's type from the query, you may use `general_web_search` first to clarify (e.g., "What type of asset is [asset_name]?").
    *   **Avoiding Redundant Calls in THIS Turn:**
        *   Review "Information Gathered So Far in This Turn" (below).
        *   If a tool has already been successfully called with the *exact same arguments* for the *exact same piece of information* in this turn, and the output was useful, DO NOT call it again. Use the existing information to decide your next step or synthesize an answer.
        *   Only re-call a tool if you need *new or different information* from it (e.g., different arguments like a new symbol, or the user's follow-up implies the previous data is insufficient for a *new aspect* of their query).
    *   **Tool Failure Handling (from previous attempts in THIS turn):**
        *   If a tool FAILED previously in *this turn* (e.g., API limit, invalid symbol *for that specific tool*), DO NOT call the exact same tool with the exact same arguments again for that same piece of information.
        *   Instead:
            a. If failure was due to an incorrect argument (e.g., wrong symbol type like using a stock symbol for `get_crypto_exchange_rate`), try the *correct* tool type (e.g., `get_stock_quote` if `get_crypto_exchange_rate` failed for a stock symbol, or vice-versa).
            b. Use `general_web_search` as a fallback for factual data.
            c. Choose a different, relevant tool.
            d. If no alternative exists, you will later synthesize an answer acknowledging this gap.
3.  **Direct Answer / Clarification (Alternative Actions):**
    *   If ALL parts of the user's original request have been addressed by previous tool calls in this turn, OR if the request is simple and clearly does not require tools (e.g., "What's your purpose?", general knowledge questions not covered by tools), then respond directly in PLAIN TEXT. Your entire response should be that text, NOT JSON.
    *   If the request is ambiguous and you need more information *from the user* to proceed effectively, ask a clarifying question in PLAIN TEXT.
    *   **My pre-filter handles basic greetings/thanks. You should handle other simple conversational queries or when tool use is clearly unnecessary.**

**Information Gathered So Far in This Turn (from previous iterations of this same turn):**
{json.dumps(accumulated_tool_outputs, indent=2) if accumulated_tool_outputs else "No tool calls yet in this turn."}

Based on all the above, decide your next action: either a tool call (JSON object) or a direct textual response/clarification.
Your response for this step must be *either* a single JSON object for a tool call *or* plain text for a direct answer/clarification.
"""
            messages_for_llm_tool_selection = [{"role": "system", "content": system_prompt_tool_selection}]
            # Add current turn's conversation history (user query, assistant tool choice, user tool output)
            messages_for_llm_tool_selection.extend(conversation_messages_for_this_turn)
            # The final message is the user's immediate request or the contextual prompt
            if not conversation_messages_for_this_turn or conversation_messages_for_this_turn[-1]['role'] != 'user':
                 messages_for_llm_tool_selection.append({"role": "user", "content": current_contextual_query_for_llm})


            # Use the primary (more capable) LLM for tool selection/decision making
            llm_decision_str = await llm_service.generate_response(
                prompt=None, # Prompt is part of history now
                history=messages_for_llm_tool_selection,
                is_json=True, # Expecting JSON for tool call or knows to give text
                use_smaller_model=False # Use primary model for critical tool selection
            )
            # yield f"DEBUG: LLM (Tool Selection) Raw Output: '''{llm_decision_str}'''\n" # For debugging
            llm_decision_str_cleaned = self._clean_llm_json_response(llm_decision_str)

            tool_called_this_iteration = False
            try:
                tool_call_data = json.loads(llm_decision_str_cleaned)

                if isinstance(tool_call_data, dict) and \
                   "tool_name" in tool_call_data and \
                   "arguments" in tool_call_data and \
                   tool_call_data["tool_name"] and \
                   isinstance(tool_call_data["arguments"], dict):

                    tool_name = tool_call_data["tool_name"]
                    tool_args = tool_call_data["arguments"]

                    if tool_name not in TOOL_FUNCTIONS:
                        # yield f"WARN: LLM chose an invalid tool: {tool_name}. Breaking to synthesis.\n" # For debugging
                        # Add this as a "tool output" so LLM knows its choice was bad
                        accumulated_tool_outputs.append({
                            "tool_name": tool_name, "arguments": tool_args, "output": f"Error: Tool '{tool_name}' is not a recognized available tool."
                        })
                        conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned})
                        conversation_messages_for_this_turn.append({"role": "user", "content": f"Tool Output from '{tool_name}': Error: Tool '{tool_name}' is not a recognized available tool."})
                        # Update contextual query to reflect this failure
                        current_contextual_query_for_llm = f"My previous attempt to use tool '{tool_name}' failed because it's not an available tool. Based on my original request ('{user_query}') and other gathered info, what should I do next?"
                        tool_called_this_iteration = True # It was an attempt, albeit failed
                        # continue to next iteration to let LLM try again
                        if iteration == MAX_TOOL_ITERATIONS - 1: break
                        else: continue


                    # yield f"ASSISTANT_ACTION: Planning to use tool '{tool_name}' with arguments: {json.dumps(tool_args)}.\n" # For debugging
                    tool_output_str = await self._execute_tool(tool_name, tool_args)
                    # yield f"ASSISTANT_ACTION: Executed tool '{tool_name}'. Output (first 100): {tool_output_str[:100]}\n" # For debugging

                    accumulated_tool_outputs.append({
                        "tool_name": tool_name, "arguments": tool_args, "output": tool_output_str
                    })

                    # Add LLM's decision (the tool call JSON) and the tool's output to the conversation for the *next* iteration's context
                    conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned}) # LLM's thought process (tool call)
                    conversation_messages_for_this_turn.append({"role": "user", "content": f"Tool Output from '{tool_name}':\n{tool_output_str}"}) # Pretend 'user' provides tool output

                    current_contextual_query_for_llm = f"Given the previous actions and tool outputs, what is the next step to fully address my original request: '{user_query}'? Or, if all parts are addressed, synthesize the answer directly in plain text."
                    tool_called_this_iteration = True

                    if iteration == MAX_TOOL_ITERATIONS - 1:
                        # yield "DEBUG: Max tool iterations reached. Proceeding to final synthesis.\n" # For debugging
                        break
                else:
                    # LLM provided JSON, but not a valid tool_call format.
                    # yield f"WARN: LLM provided JSON, but not a valid tool_call format: '{llm_decision_str_cleaned}'. Treating as direct answer attempt.\n" # For debugging
                    # This indicates the LLM intends to answer directly, but might have failed to format it as plain text.
                    # We'll pass this to the synthesis step if it's non-empty, or if empty, let synthesis take over.
                    if llm_decision_str_cleaned.strip(): # If there's content, maybe it's the answer
                         async for chunk in self._stream_plain_text(llm_decision_str_cleaned): yield chunk
                         return
                    break # Break to synthesis if it's an invalid JSON structure not meant as direct answer

            except json.JSONDecodeError:
                # LLM response was not JSON, so it's a direct answer or clarification.
                # yield f"DEBUG: LLM response (tool selection phase) was not JSON. Treating as direct answer/clarification: '{llm_decision_str_cleaned}'\n" # For debugging
                if llm_decision_str_cleaned.strip():
                    async for chunk in self._stream_plain_text(llm_decision_str_cleaned): yield chunk
                # else:
                    # yield "INFO: Assistant provided an empty direct response. No further output.\n" # For debugging
                return # This is a final answer from the LLM

            if not tool_called_this_iteration and iteration < MAX_TOOL_ITERATIONS - 1 :
                # LLM didn't call a tool and didn't give a plain text answer (e.g. empty response, or malformed JSON not caught above)
                # yield "WARN: No tool called in this iteration, and not a direct answer. Breaking to synthesis.\n" # For debugging
                break


        # --- Final Synthesis Step ---
        # yield f"\nDEBUG: --- RAG Service: Final Synthesis based on {len(accumulated_tool_outputs)} tool call(s) ---\n" # For debugging
        accumulated_outputs_str = "\n\n".join([
            f"Tool: {item['tool_name']}\nArguments: {json.dumps(item['arguments'])}\nOutput:\n{item['output']}"
            for item in accumulated_tool_outputs
        ])

        system_prompt_synthesis = f"""You are a highly capable, trustworthy, and articulate financial assistant chatbot.
Your primary goal is to provide a single, clear, comprehensive, and helpful answer to the user's original query, based on all information gathered.

User Profile:
{user_profile_summary}

Today's Date: {datetime.now().strftime('%Y-%m-%d')}

The user's original query for this turn was: "{user_query}"

Chat History (previous turns, for broader context):
{json.dumps(chat_history[-5:], indent=2) if chat_history else "No prior chat history for this session."} 
User messages from this turn (including original query and any tool outputs presented as user messages):
{json.dumps([m for m in conversation_messages_for_this_turn if m['role'] == 'user'], indent=2)}

To address this query, the following information was gathered using available tools IN THIS CURRENT TURN:
--- TOOL CALLS AND RESULTS ---
{accumulated_outputs_str if accumulated_tool_outputs else "No specific information was gathered using tools for this query this turn, or you decided to answer directly."}
--- END OF TOOL CALLS AND RESULTS ---

**Your Task: Synthesize a Final Answer**
Based on ALL the above information (user profile, original query, full chat history context, AND all tool outputs from THIS TURN), generate a single, natural language response to the user.
-   **Address All Parts:** Ensure your answer directly addresses all aspects of the "user's original query for this turn".
-   **Integrate Information:** Synthesize information from multiple tool calls if necessary. Do NOT just list tool outputs.
-   **Natural Tone:** Speak as if you possess the knowledge directly. **AVOID** phrases like "The tool 'get_stock_quote' returned...", "Based on the web search...", "The arguments for the tool were...". Instead, integrate the information naturally (e.g., "The current price of Apple (AAPL) is $150.").
-   **Handle Errors/Missing Info:** If a tool reported an error, couldn't find specific information, or if no tools were applicable/successful, acknowledge that part gracefully (e.g., "I couldn't find the specific P/E ratio for X directly from my primary sources at this moment."). Do NOT invent information. If no tools were used, answer based on general knowledge if appropriate, or state inability if it requires data.
-   **Investment Opinions/Advice:** If the query asks for an investment opinion (e.g., "should I buy X?"):
    * Frame it cautiously (e.g., "Some analysts suggest...", "Considering its recent performance...", "Factors to consider include...").
    * ALWAYS include the disclaimer: "This is not financial advice. Always do your own research and consult with a qualified financial professional before making investment decisions."
-   **Clarity & Conciseness:** Provide specific and actionable answers. Briefly explain technical terms if the user profile suggests they are a beginner. Be helpful but not overly verbose.
-   **Structure:** Use paragraphs or bullet points for readability if answering multiple points.

Now, generate the comprehensive final response to the user's original query for this turn: "{user_query}"
Your response should be in plain text.
"""
        synthesis_llm_messages = [
            {"role": "system", "content": system_prompt_synthesis}
            # The user's query is already part of the system prompt context and previous messages
        ]
        # We can add the immediate user query again to ensure focus, though it's in the system prompt.
        # synthesis_llm_messages.append({"role": "user", "content": f"Please now provide the final answer to my original query: \"{user_query}\""})


        # yield f"DEBUG: LLM (Final Synthesis) Input Messages (System + User): {json.dumps(synthesis_llm_messages, indent=2)}\n" # For debugging
        # yield "ASSISTANT_ACTION: Synthesizing the final answer...\n" # For debugging

        # Use primary (more capable) LLM for high-quality synthesis, can be tuned to smaller if performance is an issue.
        async for chunk in llm_service.generate_streamed_response(
            messages=synthesis_llm_messages,
            use_smaller_model=False # Use primary model for synthesis quality
        ):
            yield chunk
        yield "\n"

    async def _stream_plain_text(self, text: str, chunk_size: int = 10) -> AsyncGenerator[str, None]:
        """Helper to stream plain text in chunks for consistency with LLM streaming."""
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
            await asyncio.sleep(0.001) # Tiny sleep to allow event loop to cycle if needed
        if not text.endswith("\n"):
             yield "\n"


rag_service = RAGService()