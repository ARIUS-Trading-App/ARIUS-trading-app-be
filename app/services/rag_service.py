from app.services.llm_provider_service import llm_service
from app.models.user import User as UserModel
from app.llm_tools.tool_schemas import AVAILABLE_TOOLS_SCHEMAS
from app.llm_tools.tool_functions import TOOL_FUNCTIONS
from typing import Dict, List, Optional, Any, AsyncGenerator
import json
from datetime import datetime
import inspect
import traceback

MAX_TOOL_ITERATIONS = 6

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
        if tool_name not in TOOL_FUNCTIONS:
            return f"Error: Tool '{tool_name}' not found."
        
        tool_function = TOOL_FUNCTIONS[tool_name]
        sig = inspect.signature(tool_function)
        valid_args = {k: v for k, v in tool_args.items() if k in sig.parameters}
        
        try:
            print(f"Executing tool: {tool_name} with valid_args: {valid_args}")
            if inspect.iscoroutinefunction(tool_function):
                result = await tool_function(**valid_args)
            else:
                result = tool_function(**valid_args) 
            
            result_str = str(result)
            print(f"Tool {tool_name} result (first 300 chars): {result_str[:300]}...")
            return result_str
        except Exception as e:
            print(f"Error executing tool {tool_name} with args {tool_args}: {e}")
            return f"Error during {tool_name} execution for arguments {tool_args}: {str(e)}. Please check arguments or try an alternative approach."

    async def generate_intelligent_response(
        self,
        user_query: str,
        current_user: UserModel,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        user_profile_summary = self._summarize_user_profile(current_user)
        tool_schemas_for_llm_str = json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2)

        # conversation_messages_for_this_turn will store the evolving history for *this specific turn's* tool selection calls
        # It starts with the overall chat_history (if any) and adds messages related to tool use within this turn.
        conversation_messages_for_this_turn: List[Dict[str, Any]] = []
        if chat_history:
            # Make sure history items are dicts, not Pydantic models, if LLM service expects raw dicts
            conversation_messages_for_this_turn.extend([msg if isinstance(msg, dict) else msg.model_dump() for msg in chat_history])


        current_contextual_query_for_llm = user_query
        accumulated_tool_outputs = [] # Stores {"tool_name": ..., "arguments": ..., "output": ...} for the final synthesis

        for iteration in range(MAX_TOOL_ITERATIONS):
            yield f"DEBUG: --- RAG Service: Iteration {iteration + 1} / {MAX_TOOL_ITERATIONS} ---\n"

            system_prompt_tool_selection = f"""You are a sophisticated financial assistant. Your primary goal is to accurately understand the user's query and utilize available tools to gather necessary information, or decide to answer directly if appropriate.

User Profile:
{user_profile_summary}

Today's Date: {datetime.now().strftime('%Y-%m-%d')}

Available Tools:
{tool_schemas_for_llm_str}

**Your Task & Decision Process:**
1.  **Analyze User's Request & History:** Carefully consider the current user request below, the overall chat history (if any from previous turns), and information gathered from tool calls in *this current turn*.
2.  **Tool Selection (Primary Action):**
    * Identify the *next logical piece of information* needed to address any *unanswered parts* of the user's original request.
    * If a tool can provide this, select the *single most appropriate tool*.
    * Respond ONLY with a single JSON object for the chosen tool: {{"tool_name": "TOOL_NAME", "arguments": {{"arg1": "value1", ...}}}}
    * Ensure arguments match the tool's schema. Infer arguments like stock symbols (e.g., "Apple company" -> "AAPL", "Bitcoin crypto" -> "BTC") if not explicitly provided.
    * **Asset Type Specificity:** Pay close attention to tool descriptions. Use `get_stock_price` for company stocks ONLY. Use `get_crypto_price` for cryptocurrencies ONLY. Know the difference between stocks and crypto currencies, and use the correct functions for stocks, or respectively for crypto.
    * **Multi-part Queries:** Address complex queries sequentially, one tool call per iteration for each distinct piece of information needed.
    * **Tool Failure Handling:** If a tool was called previously in *this turn* for a specific piece of information and FAILED (e.g., API limit, invalid symbol for that tool), DO NOT call the exact same tool with the exact same arguments again for that same piece of information. Instead, consider:
        a. Using `general_web_search` as a fallback.
        b. Choosing a different tool if applicable.
        c. If the failure was likely due to an incorrect argument (e.g., wrong symbol type for the tool), you may try the *correct* tool with the corrected argument.
        d. If no alternative exists, you will later synthesize an answer acknowledging this gap.
3.  **Direct Answer / Clarification (Alternative Actions):**
    * If ALL parts of the user's original request have been addressed by previous tool calls in this turn, OR if the request is simple and does not require tools (e.g., a greeting), then respond directly in PLAIN TEXT.
    * If the request is ambiguous and you need more information from the user to proceed, ask a clarifying question in PLAIN TEXT.
    * If you decide to answer directly or ask a question, your entire response should be that text, NOT JSON.

**Information Gathered So Far in This Turn (from previous iterations of this same turn):**
{json.dumps(accumulated_tool_outputs, indent=2) if accumulated_tool_outputs else "No tool calls yet in this turn."}

**Current User Request (relative to gathered info):**
"{current_contextual_query_for_llm}"

Based on all the above, decide your next action: either a tool call (JSON object) or a direct textual response/clarification.
"""
            messages_for_llm_tool_selection = [{"role": "system", "content": system_prompt_tool_selection}]
            # Add conversation history relevant for THIS TURN's tool selection LLM.
            # This includes overall history + assistant/user messages from tool executions within THIS TURN.
            messages_for_llm_tool_selection.extend(conversation_messages_for_this_turn) # This should contain the original chat history
            # The user's current query for this iteration of tool selection
            messages_for_llm_tool_selection.append({"role": "user", "content": current_contextual_query_for_llm})

            yield f"DEBUG: LLM (Tool Selection) Input Messages (showing last 3): {json.dumps(messages_for_llm_tool_selection[-3:], indent=2)}\n"

            llm_decision_str = await llm_service.generate_response(
                prompt=None,
                history=messages_for_llm_tool_selection,
                is_json=True # Hint for the LLM service/mock that it should try to output JSON or plain text as per prompt
            )
            yield f"DEBUG: LLM (Tool Selection) Raw Output: '''{llm_decision_str}'''\n"
            llm_decision_str_cleaned = self._clean_llm_json_response(llm_decision_str)

            tool_called_this_iteration = False
            try:
                tool_call_data = json.loads(llm_decision_str_cleaned) # Try to parse as JSON

                if isinstance(tool_call_data, dict) and \
                   "tool_name" in tool_call_data and \
                   "arguments" in tool_call_data and \
                   tool_call_data["tool_name"] and \
                   isinstance(tool_call_data["arguments"], dict):

                    tool_name = tool_call_data["tool_name"]
                    tool_args = tool_call_data["arguments"]

                    if tool_name not in TOOL_FUNCTIONS:
                        yield f"WARN: LLM chose an invalid tool: {tool_name}. Breaking to synthesis.\n"
                        break # Proceed to synthesis

                    yield f"ASSISTANT_ACTION: Planning to use tool '{tool_name}' with arguments: {json.dumps(tool_args)}.\n"
                    tool_output_str = await self._execute_tool(tool_name, tool_args)
                    yield f"ASSISTANT_ACTION: Executed tool '{tool_name}'. Output: {tool_output_str}\n"

                    accumulated_tool_outputs.append({
                        "tool_name": tool_name, "arguments": tool_args, "output": tool_output_str
                    })

                    # Add LLM's decision (the tool call JSON) and tool's output to this turn's history for the next tool selection iteration
                    conversation_messages_for_this_turn.append({"role": "assistant", "content": llm_decision_str_cleaned}) # LLM's decision to call tool
                    conversation_messages_for_this_turn.append({"role": "user", "content": f"Tool Output from '{tool_name}':\n{tool_output_str}"}) # Simulating user providing tool output

                    current_contextual_query_for_llm = f"Given the previous actions and tool outputs, what is the next step to fully address my original request: '{user_query}'? Or, if all parts are addressed, synthesize the answer."
                    tool_called_this_iteration = True

                    if iteration == MAX_TOOL_ITERATIONS - 1:
                        yield "DEBUG: Max tool iterations reached. Proceeding to final synthesis.\n"
                        break # Break from loop to go to final synthesis
                    # else continue to next iteration

                else: # Valid JSON, but not the expected tool_call format
                    yield f"WARN: LLM provided JSON, but not a valid tool_call format: '{llm_decision_str_cleaned}'. Assuming it wants to answer directly or is stuck. Breaking to synthesis.\n"
                    break # Proceed to synthesis

            except json.JSONDecodeError: # LLM response was not JSON, so it's a direct textual answer as per prompt
                yield f"DEBUG: LLM response (tool selection phase) was not JSON. Treating as direct answer/clarification.\n"
                if llm_decision_str_cleaned.strip(): # Make sure it's not empty
                    yield llm_decision_str_cleaned # Stream the direct answer
                else:
                    yield "INFO: Assistant provided an empty direct response. No further output.\n"
                return # Stop generation, as the answer has been provided.

            if not tool_called_this_iteration and iteration < MAX_TOOL_ITERATIONS -1 : # Should not happen if logic above is correct unless loop is exited
                 yield "WARN: No tool called in this iteration, and not a direct answer. Breaking to synthesis.\n"
                 break


        # --- Final Synthesis Phase ---
        if not accumulated_tool_outputs:
            yield "INFO: No tools were successfully called during this turn.\n"
            # Check if the very first llm_decision was a non-JSON (direct answer) and already handled.
            # If we are here, it means either tools failed, or max iterations reached with no useful tool calls,
            # or an unexpected state. We'll attempt synthesis anyway.
            # The original code had a path here: if 'llm_decision_str_cleaned' in locals() ... return llm_decision_str_cleaned
            # This should have been handled by the JSONDecodeError path which yields and returns.
            # So, if we reach here with no tool outputs, it implies the loop completed without successful tool use OR direct answer.
            # The final synthesis prompt is designed to handle cases with no tool output too.
            yield "ASSISTANT_ACTION: Attempting to provide an answer without specific tool information, or based on general knowledge.\n"


        yield f"\nDEBUG: --- RAG Service: Final Synthesis based on {len(accumulated_tool_outputs)} tool call(s) ---\n"
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

To address this query, the following information was gathered using available tools:
--- TOOL CALLS AND RESULTS ---
{accumulated_outputs_str if accumulated_tool_outputs else "No specific information was gathered using tools for this query."}
--- END OF TOOL CALLS AND RESULTS ---

**Your Task: Synthesize a Final Answer**
Based on ALL the above information (user profile, original query, chat history context if provided, and ALL tool outputs), generate a single, natural language response to the user.
-   **Address All Parts:** Ensure your answer directly addresses all aspects of the "user's original query".
-   **Integrate Information:** Synthesize information from multiple tool calls if necessary. Do NOT just list tool outputs.
-   **Natural Tone:** Speak as if you possess the knowledge directly. **AVOID** phrases like "The tool 'get_stock_price' returned...", "Based on the web search...", "The arguments for the tool were...". Instead, integrate the information naturally (e.g., "The current price of Apple (AAPL) is $150.").
-   **Handle Errors/Missing Info:** If a tool reported an error or couldn't find specific information (e.g., "Could not fetch direct API price..."), acknowledge that part gracefully (e.g., "I couldn't find the specific P/E ratio for X directly from my primary source, but web search suggests Y."). Do NOT invent information.
-   **Investment Opinions/Advice:** If the query asks for an investment opinion (e.g., "should I buy X?"):
    * Frame it cautiously (e.g., "Some analysts suggest...", "Considering its recent performance...", "Factors to consider include...").
    * ALWAYS include the disclaimer: "This is not financial advice. Always do your own research and consult with a qualified financial professional before making investment decisions."
-   **Clarity:** Provide specific and actionable answers where appropriate. Briefly explain technical terms if the user profile suggests they are a beginner.
-   **Structure:** Use paragraphs or bullet points for readability if answering multiple points.

**Chat History (for broader context of the conversation, if provided from previous turns):**
{json.dumps(chat_history, indent=2) if chat_history else "No prior chat history for this session."}

Now, generate the comprehensive final response to the user's original query: "{user_query}"
"""
        synthesis_llm_messages = [
            {"role": "system", "content": system_prompt_synthesis},
            {"role": "user", "content": f"Please provide a comprehensive answer to my query: \"{user_query}\", using all the context and information gathered."}
        ]

        yield f"DEBUG: LLM (Final Synthesis) Input Messages (System + User): {json.dumps(synthesis_llm_messages, indent=2)}\n"
        yield "ASSISTANT_ACTION: Synthesizing the final answer...\n"

        async for chunk in llm_service.generate_streamed_response(
            messages=synthesis_llm_messages
        ):
            print(chunk)
            yield chunk
        yield "\n" # Ensure a final newline for clean output

rag_service = RAGService()