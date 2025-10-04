from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

def get_user(db: Session, user_id: int) -> Optional[User]:
    """Retrieves a single user by their unique ID.

    Args:
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user to retrieve.

    Returns:
        Optional[User]: The User object if found, otherwise None.
    """
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieves a single user by their email address.

    Args:
        db (Session): The SQLAlchemy database session.
        email (str): The email address of the user.

    Returns:
        Optional[User]: The User object if found, otherwise None.
    """
    user = db.query(User).filter(User.email == email).first()
    print(f"Retrieved user: {str(user)}")
    return user

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieves a single user by their username.

    Args:
        db (Session): The SQLAlchemy database session.
        username (str): The username of the user.

    Returns:
        Optional[User]: The User object if found, otherwise None.
    """
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Retrieves a list of users with pagination.

    Args:
        db (Session): The SQLAlchemy database session.
        skip (int): The number of users to skip.
        limit (int): The maximum number of users to return.

    Returns:
        List[User]: A list of User objects.
    """
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user_in: UserCreate) -> User:
    """Creates a new user in the database.

    Args:
        db (Session): The SQLAlchemy database session.
        user_in (UserCreate): The data for the new user.

    Returns:
        User: The newly created User object.
    """
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    """Updates an existing user's information in the database.

    Args:
        db (Session): The SQLAlchemy database session.
        db_user (User): The existing User object to update.
        user_in (UserUpdate): The new data to apply.

    Returns:
        User: The updated User object.
    """
    for field, value in user_in.dict(exclude_unset=True).items():
        setattr(db_user, field, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, db_user: User) -> None:
    """Deletes a user from the database.

    Args:
        db (Session): The SQLAlchemy database session.
        db_user (User): The User object to delete.
    """
    db.delete(db_user)
    db.commit()