from ollama import Client, Response
from typing import List, Dict, Union
from app.core.config import settings

class LLMProviderService:
    def __init__(self):
        self.client = Client(host=settings.OLLAMA_HOST)
        self.model_name = settings.LLM_MODEL
        self.small_model_name = settings.SMALL_LLM_MODEL
        
    async def chat(self, messages: List[Dict[str, str]]) -> Union[Response, Dict]:
        try:
            response = self.client.chat(
                model = self.model_name,
                messages = messages
            )
            return response
        except Exception as e:
            print(f"Error communicating with LLM: {e}")
            return {"error": str(e), "message": {"role": "assistant", "content": "Sorry, I couldn't process that."}}
        
        
    async def generate_response(self, prompt: str, history: List[Dict[str, str]] = None) -> str:
        messages = []
        if history:
            messages.extend(messages)
        messages.append({"role": "user", "content":prompt})
        
        response_obj = await self.chat(messages)
        
        if isinstance(response_obj, Response):
            return response_obj.message['content']
        elif isinstance(response_obj, Dict) and "error" in response_obj:
            return response_obj.message['content']
        return "Sorry, an unexpected error occurred with the LLM."
    
llm_service = LLMProviderService()

# add using small_llm_model possibility
