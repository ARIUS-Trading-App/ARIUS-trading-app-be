from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatMessage(BaseModel):
    role: str
    content: str
    
class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatMessage]] = None
    
class ChatResponse(BaseModel):
    answer: str