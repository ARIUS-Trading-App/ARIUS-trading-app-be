from app.services.llm_provider_service import llm_service
from app.models.user import User as UserModel
from app.llm_tools.tool_schemas import get_tool_schemas_for_llm, AVAILABLE_TOOLS_SCHEMAS 
from app.llm_tools.tool_functions import TOOL_FUNCTIONS 
from typing import Dict, List, Optional, Any
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
    ):
        user_profile_summary = self._summarize_user_profile(current_user)
        tool_schemas_for_llm_str = json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2) 
        
        conversation_messages = [] 
        if chat_history:
            conversation_messages.extend(chat_history)
        
        current_contextual_query = user_query

        accumulated_tool_outputs = [] 

        for iteration in range(MAX_TOOL_ITERATIONS):
            print(f"\n--- RAG Service: Iteration {iteration + 1} / {MAX_TOOL_ITERATIONS} ---")
            
            system_prompt_tool_selection = f"""You are a sophisticated financial assistant. Your primary goal is to accurately understand the user's query and utilize available tools to gather necessary information, or decide to answer directly if appropriate.

User Profile:
{user_profile_summary}

Today's Date: {datetime.now().strftime('%Y-%m-%d')}

Available Tools:
{tool_schemas_for_llm_str}

**Your Task & Decision Process:**

1.  **Analyze the User's Request & History:** Carefully consider the current user request below, the overall chat history, and any information already gathered from previous tool calls in this turn.
2.  **Tool Selection (Primary Action):**
    *   If one or more tools can help gather information to address the *unanswered parts* of the user's request, select the *single most relevant tool* to call NEXT.
    *   Respond ONLY with a single JSON object for the chosen tool: {{"tool_name": "TOOL_NAME", "arguments": {{"arg1": "value1", ...}}}}
    *   Ensure arguments match the tool's schema. Infer arguments like stock symbols (e.g., "Apple" -> "AAPL", "Bitcoin" -> "BTC") if not explicitly provided.
    *   **Multi-part Queries:** If the user's request has multiple parts (e.g., "price of AAPL and news for MSFT"), you will address them sequentially, one tool call per iteration. Choose the tool for the most immediate, unresolved part.
    *   **Tool Failure Handling:** If a tool was called previously in this turn and FAILED (e.g., due to API limits, invalid symbol), DO NOT call the exact same tool with the exact same arguments again. Consider an alternative tool (e.g., `general_web_search` if a specific price API fails) or reformulating arguments if the failure seemed due to an input issue. If all direct tools for a piece of information fail, you might need to rely on `general_web_search` or inform the user.
3.  **Direct Answer / Clarification (Alternative Actions):**
    *   If you have gathered enough information from previous tool calls in this turn to comprehensively answer the user's *entire original request*, OR if the request does not require tools (e.g., a simple greeting, general knowledge question you already know), then respond directly in plain text.
    *   If the request is ambiguous, or you need more specific information from the user to proceed effectively, ask a clarifying question in plain text.

**Information Gathered So Far in This Turn:**
{json.dumps(accumulated_tool_outputs, indent=2) if accumulated_tool_outputs else "No tool calls yet in this turn."}

**Current User Request (relative to gathered info):**
"{current_contextual_query}"

Based on all the above, decide your next action (tool call as JSON, or direct answer/clarification as text).
"""
    
            messages_for_llm_tool_selection = [{"role": "system", "content": system_prompt_tool_selection}]
            if conversation_messages: 
                 messages_for_llm_tool_selection.extend(conversation_messages)
            messages_for_llm_tool_selection.append({"role": "user", "content": current_contextual_query})


            print(f"LLM (Tool Selection) Input Messages (showing last few): {json.dumps(messages_for_llm_tool_selection[-3:], indent=2)}")
            
            llm_decision_str = await llm_service.generate_response(
                prompt=None, 
                history=messages_for_llm_tool_selection, 
                is_json=True 
            )
            print(f"LLM (Tool Selection) Raw Output: '''{llm_decision_str}'''")

            llm_decision_str_cleaned = self._clean_llm_json_response(llm_decision_str)
            
            tool_called_this_iteration = False
            try:
                tool_call_data = json.loads(llm_decision_str_cleaned)
                
                if isinstance(tool_call_data, dict) and "tool_name" in tool_call_data and "arguments" in tool_call_data:
                    tool_name = tool_call_data["tool_name"]
                    tool_args = tool_call_data["arguments"]

                    if tool_name not in TOOL_FUNCTIONS:
                        print(f"LLM chose an invalid tool: {tool_name}. Treating as direct response attempt.")
                       
                        if not llm_decision_str_cleaned.startswith("{"): 
                             return llm_decision_str_cleaned 
                        break 

                    tool_output_str = await self._execute_tool(tool_name, tool_args)
                    
                    accumulated_tool_outputs.append({
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "output": tool_output_str
                    })
                    
                    conversation_messages.append({"role": "assistant", "content": llm_decision_str_cleaned}) 
                    conversation_messages.append({"role": "user", "content": f"Tool Output from '{tool_name}':\n{tool_output_str}"}) 
                    
                    current_contextual_query = f"Given the previous actions and tool outputs, what is the next step to fully address my original request: '{user_query}'? Or, if all parts are addressed, synthesize the answer."
                    
                    tool_called_this_iteration = True
                    print(f"Tool {tool_name} executed. Output added to context. Iteration {iteration + 1} ends.")

                    if iteration == MAX_TOOL_ITERATIONS - 1:
                        print("Max tool iterations reached. Proceeding to final synthesis.")
                        break 
                else: 
                    print("LLM provided JSON, but not a valid tool_call format. Assuming direct answer.")
                    return llm_decision_str_cleaned 
            
            except json.JSONDecodeError:
                print("LLM response was not JSON. Treating as direct answer or clarification.")
                return llm_decision_str 
            
            if not tool_called_this_iteration:
                print("No tool called in this iteration, and not a direct answer. Breaking to synthesis or returning current LLM output.")
                if len(llm_decision_str_cleaned) > 50 and not llm_decision_str_cleaned.startswith("{"): 
                    return llm_decision_str_cleaned
                break 

        if not accumulated_tool_outputs:
            print("No tools were successfully called. The LLM might have tried to answer directly or failed to choose a tool.")
            if 'llm_decision_str_cleaned' in locals() and not llm_decision_str_cleaned.startswith("{"):
                return llm_decision_str_cleaned
            return "I was unable to gather the necessary information or formulate a response for your query. Please try rephrasing or be more specific."

        print(f"\n--- RAG Service: Final Synthesis based on {len(accumulated_tool_outputs)} tool call(s) ---")
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
{accumulated_outputs_str}
--- END OF TOOL CALLS AND RESULTS ---

**Your Task: Synthesize a Final Answer**

Based on ALL the above information (user profile, original query, chat history context if provided, and ALL tool outputs), generate a single, natural language response to the user.
-   **Address All Parts:** Ensure your answer directly addresses all aspects of the "user's original query".
-   **Integrate Information:** Synthesize information from multiple tool calls if necessary. Do NOT just list tool outputs.
-   **Natural Tone:** Speak as if you possess the knowledge directly. **AVOID** phrases like "The tool 'get_stock_price' returned...", "Based on the web search...", "The arguments for the tool were...". Instead, integrate the information naturally (e.g., "The current price of Apple (AAPL) is $150.").
-   **Handle Errors/Missing Info:** If a tool reported an error or couldn't find specific information, acknowledge that part gracefully (e.g., "I couldn't find the specific P/E ratio for X, but its current price is Y."). Do NOT invent information.
-   **Investment Opinions/Advice:** If the query asks for an investment opinion (e.g., "should I buy X?"):
    *   Frame it cautiously (e.g., "Some analysts suggest...", "Considering its recent performance...", "Factors to consider include...").
    *   ALWAYS include the disclaimer: "This is not financial advice. Always do your own research and consult with a qualified financial professional before making investment decisions."
-   **Clarity and Conciseness:** Provide specific and actionable answers where appropriate. Briefly explain technical terms if the user profile suggests they are a beginner.
-   **Structure:** Use paragraphs or bullet points for readability if answering multiple points.

**Chat History (for broader context of the conversation, if provided):**
{json.dumps(chat_history, indent=2) if chat_history else "No prior chat history for this session."}

Now, generate the comprehensive final response to the user's original query: "{user_query}"
"""
        
        synthesis_llm_messages = [
            {"role": "system", "content": system_prompt_synthesis},
            {"role": "user", "content": f"Please provide a comprehensive answer to my query: \"{user_query}\", using all the context and information gathered."}
        ]
        
        print(f"LLM (Final Synthesis) Input Messages (System + User): {json.dumps(synthesis_llm_messages, indent=2)}")
        final_llm_answer = await llm_service.generate_response(
            prompt=None, 
            history=synthesis_llm_messages, 
            is_json=False 
        )
        print(f"LLM (Final Synthesis) Raw Output: '''{final_llm_answer}'''")
        return final_llm_answer

rag_service = RAGService()