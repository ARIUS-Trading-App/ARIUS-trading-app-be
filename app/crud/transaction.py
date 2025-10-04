from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.transaction import Transaction as TxModel
from app.schemas.transaction import TransactionCreate, TransactionUpdate

def create_transaction(
    db: Session, portfolio_id: int, tx_in: TransactionCreate
) -> TxModel:
    """Creates a new transaction record for a portfolio.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio for this transaction.
        tx_in (TransactionCreate): The data for the new transaction.

    Returns:
        TxModel: The newly created Transaction object.
    """
    tx = TxModel(portfolio_id=portfolio_id, **tx_in.dict())
    db.add(tx); db.commit(); db.refresh(tx)
    return tx

def get_transactions(
    db: Session, portfolio_id: int,
    skip: int = 0, limit: int = 50,
    start: Optional[str] = None, end: Optional[str] = None
) -> List[TxModel]:
    """Retrieves transactions for a portfolio with optional filtering.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        start (Optional[str]): Start date for filtering (YYYY-MM-DD).
        end (Optional[str]): End date for filtering (YYYY-MM-DD).

    Returns:
        List[TxModel]: A list of Transaction objects.
    """
    q = db.query(TxModel).filter(TxModel.portfolio_id == portfolio_id)
    if start:
        q = q.filter(TxModel.timestamp >= start)
    if end:
        q = q.filter(TxModel.timestamp <= end)
    return q.order_by(TxModel.timestamp.desc()).offset(skip).limit(limit).all()

def update_transaction(
    db: Session, tx_id: int, tx_in: TransactionUpdate
) -> Optional[TxModel]:
    """Updates an existing transaction record by its ID.

    Args:
        db (Session): The SQLAlchemy database session.
        tx_id (int): The ID of the transaction to update.
        tx_in (TransactionUpdate): The fields to update.

    Returns:
        Optional[TxModel]: The updated Transaction object, or None if not found.
    """
    tx = db.query(TxModel).filter(TxModel.id == tx_id).first()
    if not tx:
        return None
    for field, value in tx_in.dict(exclude_unset=True).items():
        setattr(tx, field, value)
    db.add(tx); db.commit(); db.refresh(tx)
    return tx

def delete_transaction(db: Session, tx_id: int) -> bool:
    """Deletes a transaction record by its ID.

    Args:
        db (Session): The SQLAlchemy database session.
        tx_id (int): The ID of the transaction to delete.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    tx = db.query(TxModel).filter(TxModel.id == tx_id).first()
    if not tx:
        return False
    db.delete(tx); db.commit()
    return True