from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.crud import user as crud_user
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User as UserModel
from app.schemas.user import User, UserCreate, UserUpdate

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@router.post(
    "/",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """Creates a new user account.
    
    Args:
        user_in (UserCreate): The user details for the new account.
        db (Session): The database session dependency.
        
    Returns:
        User: The newly created user object.
        
    Raises:
        HTTPException: 400 if the email or username is already registered.
    """
    if crud_user.get_user_by_email(db, user_in.email):
        raise HTTPException(400, "Email already registered")
    if crud_user.get_user_by_username(db, user_in.username):
        raise HTTPException(400, "Username already taken")
    return crud_user.create_user(db, user_in)

@router.get(
    "/",
    response_model=List[User],
    dependencies=[Depends(get_current_user)],
)
def read_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
    db: Session = Depends(get_db),
):
    """Retrieves a list of users (requires authentication).
    
    Args:
        skip (int): The number of users to skip for pagination.
        limit (int): The maximum number of users to return.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        List[User]: A list of user objects.
    """
    return crud_user.get_users(db, skip, limit)

@router.get(
    "/me",
    response_model=User,
)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Gets the profile of the currently authenticated user.
    
    Args:
        current_user (User): The authenticated user dependency.
        
    Returns:
        User: The profile object of the current user.
    """
    return current_user

@router.get(
    "/{user_id}",
    response_model=User,
    dependencies=[Depends(get_current_user)],
)
def read_user(
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Retrieves the profile for a specific user by their ID.
    
    Args:
        user_id (int): The ID of the user to retrieve.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        User: The requested user's profile object.
        
    Raises:
        HTTPException: 404 if the user is not found.
    """
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.put(
    "/{user_id}",
    response_model=User,
    dependencies=[Depends(get_current_user)],
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Updates a user's profile information.
    
    A user can only update their own profile.
    
    Args:
        user_id (int): The ID of the user to update.
        user_in (UserUpdate): The new data for the user's profile.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        User: The updated user object.
        
    Raises:
        HTTPException: 404 if the user is not found, or 403 for insufficient permissions.
    """
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    if db_user.id != current_user.id:
        raise HTTPException(403, "Not enough permissions")
    return crud_user.update_user(db, db_user, user_in)

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Deletes a user's account.
    
    A user can only delete their own account.
    
    Args:
        user_id (int): The ID of the user to delete.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Raises:
        HTTPException: 404 if the user is not found, or 403 for insufficient permissions.
    """
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    if db_user.id != current_user.id:
        raise HTTPException(403, "Not enough permissions")
    crud_user.delete_user(db, db_user)
    return