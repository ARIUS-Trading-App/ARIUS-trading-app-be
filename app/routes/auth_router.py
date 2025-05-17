from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import EmailStr
from jose import JWTError, jwt

from app.core.utils import create_magic_token, send_email_link
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/request-token")
async def request_token(email: EmailStr):
    """Send a magic link to the user's email for login."""
    try:
        token = create_magic_token(email)
        send_email_link(email, token)
        return {"msg" : f"Magic link sent to {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not send email: {str(e)}")

@router.get("/verify-token")
async def verify_token(token: str = Query(...)):
    """Verify the token when user click the magic link."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token payload")

        response = JSONResponse(content={"msg": f"Authenticated: {email}"})
        response.set_cookie("access_token", token, httponly=True, samesite="lax")
        return response
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")