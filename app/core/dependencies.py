from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.crud import user as crud_user
from app.models.user import User

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency to authenticate and retrieve the current user.

    This function inspects the 'Authorization: Bearer <token>' header, decodes
    the JWT, and fetches the corresponding user from the database. It's used
    to protect routes that require user authentication.

    Args:
        authorization (str, optional): The content of the Authorization header.
        db (Session, optional): The database session dependency.

    Returns:
        User: The authenticated user's database object.

    Raises:
        HTTPException: 401 for missing, malformed, or invalid tokens, or
                       404 if the user from the token is not found in the database.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if parts[0].lower() != "bearer" or len(parts) == 1 or len(parts) > 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: Missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = crud_user.get_user_by_email(db, email=email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return user