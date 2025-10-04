from ollama import Client
from ollama import ChatResponse as OllamaChatResponseType
from ollama import Message as OllamaMessageType
from typing import List, Dict, Union, Optional, AsyncGenerator
from app.core.config import settings
import asyncio
import threading

class LLMProviderService:
    def __init__(self):
        """Initializes the LLMProviderService.
        
        Sets up the Ollama client and configures the primary and secondary
        LLM models from application settings.
        """
        self.client = Client(host=settings.OLLAMA_HOST)
        self.model_name = settings.LLM_MODEL
        self.smaller_model_name = settings.SMALLER_LLM_MODEL
        print(f"LLMProviderService initialized with primary model: {self.model_name}, smaller model: {self.smaller_model_name} on host: {settings.OLLAMA_HOST}")

    async def chat(self, messages: List[Dict[str, str]], format_type: Optional[str] = None, use_smaller_model: bool = False) -> Union[OllamaChatResponseType, Dict]:
        """Makes a direct, low-level call to the Ollama chat client.

        Args:
            messages (List[Dict[str, str]]): A list of message dictionaries.
            format_type (Optional[str]): The desired response format (e.g., "json").
            use_smaller_model (bool): If True, uses the smaller, faster model.

        Returns:
            Union[OllamaChatResponseType, Dict]: The response object from the
                Ollama client or an error dictionary.
        """
        try:
            model_to_use = self.smaller_model_name if use_smaller_model else self.model_name
            
            chat_kwargs = {
                "model": model_to_use,
                "messages": messages
            }
            if format_type:
                chat_kwargs["format"] = format_type

            print(f"--- LLM call with model: {model_to_use} (format: {format_type or 'text'}) ---")
            response = self.client.chat(**chat_kwargs)
            return response
        except Exception as e:
            print(f"LLMService.chat: Error communicating with LLM ({model_to_use}): {e}")
            return {"error": str(e), "llm_message_content": "Sorry, an LLM communication error occurred."}

    async def generate_response(
        self,
        prompt: str,
        history: List[Dict[str, str]] = None,
        is_json: bool = False,
        use_smaller_model: bool = False
    ) -> str:
        """Generates a complete, non-streamed response from the LLM.

        Args:
            prompt (str): The user's prompt or question. Can be None if history
                          provides the full context.
            history (List[Dict[str, str]]): The conversation history.
            is_json (bool): If True, requests a JSON formatted response.
            use_smaller_model (bool): If True, uses the smaller, faster model.

        Returns:
            str: The content of the LLM's response.
        """
        messages_for_llm = []
        if history:
            messages_for_llm.extend(history)
        if prompt:
            messages_for_llm.append({"role": "user", "content": prompt})

        format_to_use = "json" if is_json else None
        response_obj = await self.chat(messages_for_llm, format_type=format_to_use, use_smaller_model=use_smaller_model)

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
        is_json: bool = False,
        use_smaller_model: bool = False
    ) -> AsyncGenerator[str, None]:
        """Generates a streamed response, yielding content chunks as they arrive.
        
        This uses a separate thread for the blocking Ollama client call and an
        asyncio.Queue to safely pass data back to the async event loop.

        Args:
            messages (List[Dict[str, str]]): The list of messages for the chat.
            is_json (bool): If True, requests a JSON formatted response.
            use_smaller_model (bool): If True, uses the smaller, faster model.

        Yields:
            str: Chunks of the LLM response content.
        """
        model_for_request = self.smaller_model_name if use_smaller_model else self.model_name
        
        chat_kwargs = {
            "model": model_for_request,
            "messages": messages,
            "stream": True
        }
        if is_json:
            chat_kwargs["format"] = "json"

        print(f"--- LLM stream with model: {model_for_request} (format: {chat_kwargs.get('format', 'text')}) ---")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Union[Dict, Exception, None]] = asyncio.Queue()

        def _producer():
            try:
                for chunk in self.client.chat(**chat_kwargs):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=_producer, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                print(f"Error during LLM stream from producer thread: {item}")
                yield f"STREAM_ERROR: An error occurred with the LLM stream: {item}"
                return

            msg = item.get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                yield content

        thread.join(timeout=1.0)

llm_service = LLMProviderService()