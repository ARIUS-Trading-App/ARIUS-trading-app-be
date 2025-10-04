from fastapi import APIRouter, HTTPException, Query, Depends, Body
from fastapi.responses import JSONResponse
from pydantic import EmailStr
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.utils import create_magic_token, send_email_link
from app.core.config import settings
from app.db.session import get_db
from app.crud import user as crud_user
from app.schemas.user import UserCreate

SECRET_KEY = settings.SECRET_KEY
ALGORITHM  = settings.ALGORITHM  

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/request-token")
async def request_token(email: EmailStr = Body(..., embed=True)):
    """Creates a magic link token and sends it to the user's email."""
    try:
        token = create_magic_token(email)
        send_email_link(email, token)
      
        return {"msg": f"Magic link sent to {email}", "token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not send email: {str(e)}")


@router.get("/verify-token")
async def verify_token(
    token: str = Query(...),
    db:    Session = Depends(get_db),
):
    """Verifies a magic link token and authenticates the user.

    If the user is logging in for the first time, their account is
    automatically created.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token payload")

        user = crud_user.get_user_by_email(db, email)
        if user is None:
            username = email.split("@")[0]
            user_in  = UserCreate(username=username, email=email)
            user     = crud_user.create_user(db, user_in)

        response = JSONResponse(content={"msg": f"Authenticated: {email}"})
        return response

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")