from ollama import Client
from ollama import ChatResponse as OllamaChatResponseType
from ollama import Message as OllamaMessageType 
from typing import List, Dict, Union, Optional
from app.core.config import settings

class LLMProviderService:
    def __init__(self):
        self.client = Client(host=settings.OLLAMA_HOST)
        self.model_name = settings.LLM_MODEL
        self.smaller_model_name = settings.SMALLER_LLM_MODEL
        print(f"LLMProviderService initialized with model: {self.model_name}, {self.smaller_model_name} on host: {settings.OLLAMA_HOST}")
        
    async def chat(self, messages: List[Dict[str, str]], format_type: Optional[str] = None, smaller_model: bool = False) -> Union[OllamaChatResponseType, Dict]:
        try:
            if smaller_model:
                chat_kwargs = {
                    "model": self.model_name,
                    "messages": messages
                }
            else:
                chat_kwargs = {
                    "model": self.smaller_model_name,
                    "messages": messages
                }
            if format_type:
                chat_kwargs["format"] = format_type

            response = self.client.chat(**chat_kwargs)
            print(f"---response was created with {smaller_model}")
            return response
        except Exception as e: 
            print(f"LLMService.chat: Error communicating with LLM: {e}")
            return {"error": str(e), "llm_message_content": "Sorry, an LLM communication error occurred."}
            
    async def generate_response(self, prompt: str, history: List[Dict[str, str]] = None, is_json: bool = False) -> str:
        messages_for_llm = []
        if history:
            messages_for_llm.extend(history) 
        messages_for_llm.append({"role": "user", "content": prompt})
        
        format_to_use = "json" if is_json else None
        response_obj = await self.chat(messages_for_llm, format_type=format_to_use, smaller_model = is_json)
        
        if isinstance(response_obj, OllamaChatResponseType):
            if hasattr(response_obj, 'message') and isinstance(response_obj.message, OllamaMessageType):
                if hasattr(response_obj.message, 'content') and isinstance(response_obj.message.content, str):
                    return response_obj.message.content
                else:
                    print(f"LLMProviderService.generate_response: Ollama Message object present, but 'content' attribute missing or not a string.")
                    print(f"Message object details: role='{response_obj.message.role}', content_type='{type(response_obj.message.content)}'")
                    return "LLM Message object structure error (content)."
            else:
                print(f"LLMProviderService.generate_response: OllamaChatResponseType received, but 'message' attribute missing or not an Ollama Message object.")
                print(f"Malformed OllamaChatResponseType (message attribute): {response_obj}")
                return "LLM response was received but had an unexpected internal structure (message attribute)."
        
        elif isinstance(response_obj, dict) and "error" in response_obj:
            print(f"LLMProviderService.generate_response: Error received from self.chat(): {response_obj.get('error')}")
            return response_obj.get("llm_message_content", "An unspecified error occurred during LLM communication.")
        
        print(f"LLMProviderService.generate_response: Unexpected type received from self.chat(). Type: {type(response_obj)}")
        print(f"Unexpected response_obj content: {response_obj}")
        return "Sorry, an unexpected issue occurred while processing the LLM response."
    
llm_service = LLMProviderService()