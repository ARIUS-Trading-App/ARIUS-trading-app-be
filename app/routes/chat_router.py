from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.chat_schemas import ChatRequest, ChatResponse, ChatMessage
from app.services.rag_service import rag_service
from app.core.dependencies import get_current_user
from app.models.user import User as UserModel

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/", response_model=ChatResponse)
async def ask_chatbot(
    request_data: ChatRequest,
    current_user: UserModel = Depends(get_current_user)
):
    if not request_data.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        history_for_rag = None
        if request_data.history:
            history_for_rag = [msg.model_dump() for msg in request_data.history]
            
        answer = await rag_service.generate_intelligent_response(
            user_query=request_data.query,
            current_user=current_user,
            chat_history=history_for_rag
        )
        return ChatResponse(answer=answer)
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your request: {str(e)}")