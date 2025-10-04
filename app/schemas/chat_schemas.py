from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatMessage(BaseModel):
    """Represents a single message in a chat history."""
    role: str
    content: str
    
class ChatRequest(BaseModel):
    """Defines the structure for a user's request to the chat endpoint."""
    query: str
    history: Optional[List[ChatMessage]] = None
    
class ChatResponse(BaseModel):
    """Defines the structure for the chatbot's final response."""
    answer: str