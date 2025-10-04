from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncGenerator

from app.schemas.chat_schemas import ChatRequest, ChatResponse, ChatMessage
from app.services.rag_service import rag_service
from app.core.dependencies import get_current_user
from app.models.user import User as UserModel

import traceback

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/")
async def ask_chatbot(
    request_data: ChatRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """Handles a user's query and streams the chatbot's response back."""
    if not request_data.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        history_for_rag = None
        if request_data.history:
            history_for_rag = [msg.model_dump() for msg in request_data.history]

        response_generator = rag_service.generate_intelligent_response(
            user_query=request_data.query,
            current_user=current_user,
            chat_history=history_for_rag
        )
        
        async def safe_generator_wrapper(generator: AsyncGenerator[str, None]):
            """Wraps the generator to catch errors during streaming."""
            try:
                async for chunk in generator:
                    yield chunk
            except HTTPException as he:
                print(f"HTTPException during stream: {he.detail}")
                yield f"\nSTREAM_ERROR: An HTTPException occurred: {he.detail}\n"
            except Exception as e:
                print(f"Error during streaming response generation: {e}")
                traceback.print_exc()
                yield f"\nSTREAM_ERROR: An unexpected error occurred while processing your request: {str(e)}\n"

        return StreamingResponse(safe_generator_wrapper(response_generator), media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint (before streaming): {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred before processing your request: {str(e)}")