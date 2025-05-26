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
    # dependencies=[Depends(get_current_user)],
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new user.
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
    """
    Retrieve a list of users.
    """
    return crud_user.get_users(db, skip, limit)

#! Probleme
@router.get(
    "/me",
    response_model=User,
)
def read_current_user(current_user: UserModel = Depends(get_current_user)):
    return current_user

@router.get(
    "/{user_id}",
    response_model=User,
    dependencies=[Depends(get_current_user)],
)
def read_user(
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
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
    """
    Update a user.
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
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    if db_user.id != current_user.id:
        raise HTTPException(403, "Not enough permissions")
    crud_user.delete_user(db, db_user)
    return
