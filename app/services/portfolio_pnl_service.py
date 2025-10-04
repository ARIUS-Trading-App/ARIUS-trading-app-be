from sqlalchemy.orm import Session
from typing import Dict
from app.crud.transaction import get_transactions
from app.services.portfolio_service import compute_portfolio_value
from app.models.transaction import TransactionType

async def compute_pnl(db: Session, portfolio_id: int) -> Dict[str, float]:
    """Calculates the P&L for a portfolio.

    This function computes both realized and unrealized profit and loss.
    - Realized P&L is calculated using the First-In, First-Out (FIFO)
      accounting method on the portfolio's transaction history.
    - Unrealized P&L is the difference between the current market value
      of holdings and their original cost basis.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio to analyze.

    Returns:
        Dict[str, float]: A dictionary containing the realized_pnl,
                          unrealized_pnl, current_market_value, and
                          the cost_basis_of_current_holdings.
    """
    txs = get_transactions(db, portfolio_id=portfolio_id, limit=0)

    realized_pnl = 0.0
    bought_lots: Dict[str, list] = {}

    txs.sort(key=lambda tx: tx.timestamp)

    for tx in txs:
        symbol = tx.symbol
        quantity = float(tx.quantity)
        price = float(tx.price)

        if tx.type == TransactionType.BUY:
            bought_lots.setdefault(symbol, []).append({'quantity': quantity, 'price': price})
        
        elif tx.type == TransactionType.SELL:
            sell_quantity_remaining = quantity
            
            if symbol not in bought_lots or not bought_lots[symbol]:
                print(f"Warning: Selling {symbol} but no prior buy lots found or all sold. P&L for this sell might be inaccurate without full history or short-sale logic.")
                pass

            temp_lots_for_symbol = []
            for lot in bought_lots.get(symbol, []):
                if sell_quantity_remaining == 0:
                    temp_lots_for_symbol.append(lot)
                    continue

                if lot['quantity'] <= sell_quantity_remaining:
                    realized_pnl += (price - lot['price']) * lot['quantity']
                    sell_quantity_remaining -= lot['quantity']
                else:
                    realized_pnl += (price - lot['price']) * sell_quantity_remaining
                    lot['quantity'] -= sell_quantity_remaining
                    sell_quantity_remaining = 0
                    temp_lots_for_symbol.append(lot)
            
            if symbol in bought_lots:
                bought_lots[symbol] = temp_lots_for_symbol

    current_holdings_cost_basis = 0.0
    for symbol_lots in bought_lots.values():
        for lot in symbol_lots:
            current_holdings_cost_basis += lot['quantity'] * lot['price']

    current_market_value = await compute_portfolio_value(db, portfolio_id)
    
    unrealized_pnl = current_market_value - current_holdings_cost_basis

    return {
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "current_market_value": round(current_market_value, 2),
        "cost_basis_of_current_holdings": round(current_holdings_cost_basis, 2)
    }