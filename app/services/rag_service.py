from app.services.llm_provider_service import llm_service
from app.models.user import User as UserModel
from app.llm_tools.tool_schemas import AVAILABLE_TOOLS_SCHEMAS
from app.llm_tools.tool_functions import TOOL_FUNCTIONS
from typing import Dict, List, Optional, Any, AsyncGenerator, Set, Tuple # Added Set, Tuple
import json
from datetime import datetime
import inspect
import traceback
from cachetools import TTLCache
import asyncio # Added for _stream_plain_text helper

MAX_TOOL_ITERATIONS = 5

class RAGService:
    def __init__(self):
        self.tool_execution_cache = TTLCache(maxsize=200, ttl=60)

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

    def _clean_llm_json_response(self, llm_response_str: str) -> str:
        clean_response_str = llm_response_str.strip()
        if clean_response_str.startswith("```json"):
            clean_response_str = clean_response_str[len("```json"):].strip()
        elif clean_response_str.startswith("```"):
            clean_response_str = clean_response_str[len("```"):].strip()
        
        if clean_response_str.endswith("```"):
            clean_response_str = clean_response_str[:-len("```")].strip()
        return clean_response_str

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        # Ensure tool_args are consistently ordered for caching
        # frozenset of items is good for dicts within args.
        cache_key_args = tuple(sorted(tool_args.items())) if isinstance(tool_args, dict) else tuple(str(tool_args)) # Ensure hashable
        cache_key = (tool_name, cache_key_args)

        if cache_key in self.tool_execution_cache:
            print(f"Cache HIT for tool: {tool_name} with args: {tool_args}")
            return self.tool_execution_cache[cache_key]
        print(f"Cache MISS for tool: {tool_name} with args: {tool_args}")

        if tool_name not in TOOL_FUNCTIONS:
            return f"Error: Tool '{tool_name}' not found."

        tool_function = TOOL_FUNCTIONS[tool_name]
        sig = inspect.signature(tool_function)
        
        valid_args = {}
        for k, v in tool_args.items():
            if k in sig.parameters:
                param_type = sig.parameters[k].annotation
                try:
                    if param_type == int and not isinstance(v, int):
                        v = int(v)
                    elif param_type == float and not isinstance(v, float):
                        v = float(v)
                except ValueError:
                    print(f"Warning: Could not coerce argument '{k}' value '{v}' to type {param_type} for tool {tool_name}")
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
            self.tool_execution_cache[cache_key] = result_str
            return result_str
        except Exception as e:
            print(f"Error executing tool {tool_name} with args {valid_args}: {e}")
            traceback.print_exc()
            error_message = f"Error during {tool_name} execution with arguments {valid_args}: {str(e)}."
            arg_symbol = valid_args.get("symbol", valid_args.get("from_currency_symbol"))
            if arg_symbol: # Add specific feedback for asset type mismatch
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
        simple_closings_thanks = ["thanks", "thank you", "thx", "ty", "appreciate it", "ok thanks"]
        simple_closings_bye = ["bye", "goodbye", "see ya", "later", "cya"]
        simple_banter = ["how are you", "how are you doing", "what's up", "sup", "hows it going"]

        if normalized_query in simple_greetings:
            simple_response_messages = [
                {"role": "system", "content": "You are a friendly and concise assistant. Respond warmly to the user's greeting."},
                {"role": "user", "content": user_query}
            ]
            async for chunk in llm_service.generate_streamed_response(messages=simple_response_messages, use_smaller_model=True):
                yield chunk
            yield "\n"
            return
        
        if any(phrase == normalized_query for phrase in simple_closings_thanks) or any(normalized_query.startswith(phrase) for phrase in simple_closings_thanks):
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
        tool_schemas_for_llm_str = json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2)

        conversation_messages_for_this_turn: List[Dict[str, Any]] = []
        if chat_history: # Only add chat_history once at the beginning of the turn
            conversation_messages_for_this_turn.extend([msg if isinstance(msg, dict) else msg.model_dump() for msg in chat_history])

        # Tracks (tool_name, frozenset(args.items())) for successful calls *within this turn*
        executed_tool_calls_this_turn: Set[Tuple[str, frozenset]] = set()
        accumulated_tool_outputs = [] # Stores full output details for synthesis

        current_contextual_query_for_llm = user_query # Initial context for LLM

        for iteration in range(MAX_TOOL_ITERATIONS):
            yield f"DEBUG: --- RAG Service: Iteration {iteration + 1} / {MAX_TOOL_ITERATIONS} ---\n" # Keep for debugging

            system_prompt_tool_selection = f"""You are a sophisticated financial assistant. Your primary goal is to accurately understand the user's query, identify ALL necessary pieces of information, and use available tools sequentially to gather them, or decide to answer directly if appropriate.

User Profile:
{user_profile_summary}
Today's Date: {datetime.now().strftime('%Y-%m-%d')}
Available Tools (ensure your chosen tool_name and arguments match these schemas exactly):
{tool_schemas_for_llm_str}

**Original User Request for this turn (your ultimate goal):** "{user_query}"

**Information Gathered So Far IN THIS TURN (tool calls & their outputs):**
{json.dumps(accumulated_tool_outputs, indent=2) if accumulated_tool_outputs else "No tool calls yet in this turn."}

**Your Task & Decision Process (Iterative - Strive for NEW information each step):**
1.  **Analyze Original Request & Progress:** Based on the "Original User Request" and "Information Gathered So Far IN THIS TURN", what is the *next distinct piece of information* required to fully answer the original request?
2.  **Tool Selection (Primary Action - Aim for NOVELTY):**
    *   If a tool can provide this *new* piece of information, select the single most appropriate tool.
    *   **CRITICAL: DO NOT re-request information if its exact tool call (name and arguments combination) is already listed in "Information Gathered So Far IN THIS TURN". Choosing a redundant call will result in corrective feedback, and you will be prompted to select a different, novel action.**
    *   Respond ONLY with a single JSON object for the chosen tool: `{{"tool_name": "TOOL_NAME", "arguments": {{"arg1": "value1", ...}}}}`
    *   **Asset Type Specificity (CRITICAL):** Use `get_stock_quote`, etc. for stocks (AAPL, MSFT). Use `get_crypto_exchange_rate`, etc. for crypto (BTC, ETH). If unsure about an asset's type, use `general_web_search` to clarify.
    *   **Complex Queries:** Break down the "Original User Request" into sub-questions. Address one sub-question per tool call. Example: "Price of AAPL and BTC" requires two separate tool calls in two iterations.
3.  **Direct Answer / Clarification (Alternative Actions):**
    *   If ALL parts of the "Original User Request" have been addressed by tool calls in "Information Gathered So Far IN THIS TURN", OR if the request is simple (e.g., "What is your purpose?") and clearly does not require tools, then respond directly in PLAIN TEXT. Your entire response should be that text, NOT JSON.
    *   If the request is ambiguous and you need more information *from the user* to proceed effectively, ask a clarifying question in PLAIN TEXT.

Based on all the above, and the current contextual query below, decide your next action: either a tool call (JSON) for NEW information, or a direct textual response/clarification.
"""
            # Construct messages for LLM tool selection
            # Start with system prompt
            messages_for_llm_tool_selection = [{"role": "system", "content": system_prompt_tool_selection}]
            # Add conversation history (previous turns + current turn's assistant/tool messages)
            messages_for_llm_tool_selection.extend(conversation_messages_for_this_turn)
            # Add the current contextual query as the latest user message
            # This ensures the LLM focuses on the immediate task based on previous feedback or new info
            messages_for_llm_tool_selection.append({"role": "user", "content": current_contextual_query_for_llm})

            yield f"DEBUG: LLM (Tool Selection) Input History (last 3): {json.dumps(messages_for_llm_tool_selection[-3:], indent=2)}\n"

            llm_decision_str = await llm_service.generate_response(
                prompt=None, # Prompt is integrated into history
                history=messages_for_llm_tool_selection,
                is_json=True, # LLM should decide if output is JSON (tool) or text (direct)
                use_smaller_model=False # Use primary model for this complex reasoning
            )
            yield f"DEBUG: LLM (Tool Selection) Raw Output: '''{llm_decision_str}'''\n"
            llm_decision_str_cleaned = self._clean_llm_json_response(llm_decision_str)

            tool_call_attempted_this_iteration = False
            try:
                tool_call_data = json.loads(llm_decision_str_cleaned)

                if isinstance(tool_call_data, dict) and "tool_name" in tool_call_data and "arguments" in tool_call_data:
                    tool_name = tool_call_data["tool_name"]
                    # Ensure tool_args is a dictionary, even if LLM provides null or other types
                    tool_args = tool_call_data.get("arguments") 
                    if not isinstance(tool_args, dict):
                        tool_args = {} # Default to empty dict if arguments are not a dict

                    tool_call_attempted_this_iteration = True
                    current_call_signature = (tool_name, frozenset(sorted(tool_args.items())))

                    if tool_name not in TOOL_FUNCTIONS:
                        yield f"WARN: LLM chose an invalid tool: {tool_name}.\n"
                        tool_output_str = f"Error: Tool '{tool_name}' is not a recognized available tool. Please choose from the provided list of tools."
                        # Add LLM's choice (assistant) and this error feedback (user) to conversation
                        conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned})
                        conversation_messages_for_this_turn.append({"role": "user", "content": f"System Feedback: {tool_output_str}"})
                        current_contextual_query_for_llm = f"The tool '{tool_name}' is invalid. Review the original query ('{user_query}'), the 'Information Gathered So Far IN THIS TURN', and available tools, then select a VALID tool for the next piece of information or synthesize if complete."
                        if iteration == MAX_TOOL_ITERATIONS - 1: break
                        else: continue

                    # **** CORE LOGIC FOR PREVENTING IN-TURN DUPLICATE TOOL EXECUTION ****
                    if current_call_signature in executed_tool_calls_this_turn:
                        yield f"INFO: LLM attempted to re-call {tool_name} with {tool_args} which was already successfully executed THIS TURN. Guiding LLM.\n"
                        feedback_to_llm = f"System Feedback: The information for tool '{tool_name}' with arguments {tool_args} has ALREADY been successfully gathered in this current turn (see 'Information Gathered So Far IN THIS TURN'). Please choose a tool to gather *different, new* information needed for the original query ('{user_query}'), or synthesize the final answer if all parts are now covered."
                        conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned}) # Log LLM's redundant choice
                        conversation_messages_for_this_turn.append({"role": "user", "content": feedback_to_llm}) # Corrective feedback as if from user
                        current_contextual_query_for_llm = feedback_to_llm # Make this the direct next prompt to LLM
                        if iteration == MAX_TOOL_ITERATIONS - 1: break
                        else: continue

                    # If it's a valid, novel call for this turn:
                    yield f"ASSISTANT_ACTION: Planning to use tool '{tool_name}' with arguments: {json.dumps(tool_args)}.\n"
                    tool_output_str = await self._execute_tool(tool_name, tool_args) # Uses API cache
                    yield f"ASSISTANT_ACTION: Executed tool '{tool_name}'. Output (first 100): {tool_output_str[:100]}\n"

                    # Add to successful calls *this turn* and accumulated outputs
                    executed_tool_calls_this_turn.add(current_call_signature)
                    accumulated_tool_outputs.append({
                        "tool_name": tool_name, "arguments": tool_args, "output": tool_output_str
                    })

                    # Add LLM's decision (tool call JSON) and tool's output to the turn's conversation history
                    conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned})
                    conversation_messages_for_this_turn.append({"role": "user", "content": f"Tool Output from '{tool_name}':\n{tool_output_str}"})
                    current_contextual_query_for_llm = f"Given the 'Information Gathered So Far IN THIS TURN' (now including output from '{tool_name}'), what is the NEXT piece of NEW information needed to fully address my original query: '{user_query}'? Or, if all parts are addressed, synthesize the answer directly in plain text."
                    
                    if iteration == MAX_TOOL_ITERATIONS - 1:
                        yield "DEBUG: Max tool iterations reached. Proceeding to final synthesis.\n"
                        break
                else: 
                    yield f"WARN: LLM provided JSON, but not a valid tool_call format: '{llm_decision_str_cleaned}'. Assuming direct answer attempt.\n"
                    if llm_decision_str_cleaned.strip():
                         async for chunk in self._stream_plain_text(llm_decision_str_cleaned): yield chunk
                         return
                    break # Break to synthesis if empty or malformed and not a tool call

            except json.JSONDecodeError: 
                yield f"DEBUG: LLM response (tool selection phase) was not JSON. Treating as direct answer/clarification: '{llm_decision_str_cleaned}'\n"
                if llm_decision_str_cleaned.strip():
                    async for chunk in self._stream_plain_text(llm_decision_str_cleaned): yield chunk
                return # This is a final answer from the LLM

            if not tool_call_attempted_this_iteration and iteration < MAX_TOOL_ITERATIONS - 1 :
                   yield "WARN: No tool call attempted by LLM in this iteration, and not a direct answer. Breaking to synthesis.\n"
                   break


        # --- Final Synthesis Step ---
        yield f"\nDEBUG: --- RAG Service: Final Synthesis based on {len(accumulated_tool_outputs)} tool call(s) this turn ---\n"
        accumulated_outputs_str = "\n\n".join([
            f"Tool: {item['tool_name']}\nArguments: {json.dumps(item['arguments'])}\nOutput:\n{item['output']}"
            for item in accumulated_tool_outputs
        ])

        # Construct synthesis prompt
        system_prompt_synthesis = f"""You are a highly capable, trustworthy, and articulate financial assistant chatbot.
Your primary goal is to provide a single, clear, comprehensive, and helpful answer to the user's original query, based on all information gathered.

User Profile:
{user_profile_summary}
Today's Date: {datetime.now().strftime('%Y-%m-%d')}

The user's original query for this turn was: "{user_query}"

Chat History (from previous turns, for broader context):
{json.dumps(chat_history[-5:], indent=2) if chat_history else "No prior chat history for this session."} 

Information Gathered IN THIS CURRENT TURN to address the original query:
--- TOOL CALLS AND RESULTS FROM THIS TURN ---
{accumulated_outputs_str if accumulated_tool_outputs else "No specific information was gathered using tools for this query this turn, or a direct answer was decided earlier."}
--- END OF TOOL CALLS AND RESULTS ---

**Your Task: Synthesize a Final Answer**
Based on ALL the above information (user profile, original query, full chat history context, AND all tool outputs from THIS CURRENT TURN), generate a single, natural language response to the user.
-   **Address All Parts of Original Query:** Ensure your answer directly addresses all aspects of "{user_query}".
-   **Integrate Information Naturally:** Synthesize information from multiple tool calls if necessary. Do NOT just list tool outputs. Avoid phrases like "The tool 'X' returned...". Instead, integrate naturally (e.g., "The price of AAPL is...").
-   **Handle Errors/Missing Info:** If a tool reported an error, couldn't find specific information, or if no tools were applicable/successful for a part of the query, acknowledge that part gracefully. Do NOT invent information.
-   **Investment Opinions/Advice:** If the query asks for an investment opinion (e.g., "should I buy X?"):
    * Frame it cautiously (e.g., "Some analysts suggest...", "Considering its recent performance...", "Factors to consider include...").
    * ALWAYS include the disclaimer: "This is not financial advice. Always do your own research and consult with a qualified financial professional before making investment decisions."
-   **Clarity & Conciseness:** Provide specific and actionable answers. Briefly explain technical terms if the user profile suggests they are a beginner.
-   **Structure:** Use paragraphs or bullet points for readability if answering multiple points.

Now, generate the comprehensive final response to the user's original query for this turn: "{user_query}"
Your response should be in plain text.
"""
        synthesis_llm_messages = [{"role": "system", "content": system_prompt_synthesis}]
        # No explicit user message needed here for synthesis, as the system prompt encapsulates the task.

        yield f"DEBUG: LLM (Final Synthesis) Input System Prompt (first 300 chars): {system_prompt_synthesis[:300]}...\n"

        async for chunk in llm_service.generate_streamed_response(
            messages=synthesis_llm_messages,
            use_smaller_model=False # Use primary model for high-quality synthesis
        ):
            yield chunk
        yield "\n"

    async def _stream_plain_text(self, text: str, chunk_size: int = 10) -> AsyncGenerator[str, None]:
        """Helper to stream plain text in chunks for consistency with LLM streaming."""
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
            await asyncio.sleep(0.001) # Tiny sleep to allow event loop to cycle
        if text and not text.endswith("\n"): # Ensure newline if text is not empty
             yield "\n"

rag_service = RAGService()