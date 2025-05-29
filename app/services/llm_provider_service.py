from ollama import Client
from ollama import ChatResponse as OllamaChatResponseType
from ollama import Message as OllamaMessageType 
from typing import List, Dict, Union, Optional, AsyncGenerator
from app.core.config import settings
import asyncio
import threading

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
            if smaller_model:
                print(f"---response was created with {self.smaller_model_name}")
            else:
                print(f"---response was created with {self.model_name}")
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
    
    async def generate_streamed_response(
        self,
        messages: List[Dict[str, str]],
        is_json: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Generates a streamed response from Ollama, yielding content chunks as they arrive.
        """
        # Decide which model to use
        model_for_request = self.model_name if is_json else self.smaller_model_name
        chat_kwargs = {
            "model": model_for_request,
            "messages": messages,
            "stream": True
        }
        if is_json:
            chat_kwargs["format"] = "json"

        # Grab the running event loop and set up a queue
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Union[Dict, Exception, None]] = asyncio.Queue()

        def _producer():
            try:
                for chunk in self.client.chat(**chat_kwargs):
                    # Safely schedule queue.put_nowait(chunk) in the event loop thread
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                # Sentinel to mark end of stream
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # Start the producer in a real thread
        thread = threading.Thread(target=_producer, daemon=True)
        thread.start()

        # Consume the queue from the async context
        while True:
            item = await queue.get()
            if item is None:  # end‐of‐stream sentinel
                break
            if isinstance(item, Exception):
                yield f"STREAM_ERROR: {item}"
                return
            # item is a dict chunk; extract the content if present
            msg = item.get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                yield content

        # Optionally join the thread (it should already have finished)
        thread.join(timeout=0.1)
    
llm_service = LLMProviderService()