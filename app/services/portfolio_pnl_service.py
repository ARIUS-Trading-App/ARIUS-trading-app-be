# app/services/portfolio_pnl_service.py
from sqlalchemy.orm import Session
from typing import Dict
from app.crud.transaction import get_transactions # Synchronous
from app.services.portfolio_service import compute_portfolio_value # Async
from app.models.transaction import TransactionType # Enum for type comparison

async def compute_pnl(db: Session, portfolio_id: int) -> Dict[str, float]:
    """
    Calculate the realized and unrealized P&L for a given portfolio.
    Realized P&L is based on transactions (FIFO).
    Unrealized P&L is based on current market value vs. cost basis of current holdings.
    """
    # get_transactions is synchronous
    txs = get_transactions(db, portfolio_id=portfolio_id, limit=0) # Get all transactions for PNL

    realized_pnl = 0.0
    
    # For FIFO, we need to track lots of bought shares
    # {symbol: [(qty, price), (qty, price), ...]}
    bought_lots: Dict[str, list] = {}

    # Sort transactions by timestamp to process in chronological order for FIFO
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
                # Selling shares never bought (short selling not handled here, or error in data)
                # For simplicity, this might indicate an issue or unrecorded buys.
                # We'll assume sells are matched against prior buys. If no buys, P&L impact is complex.
                # One could assume cost basis of 0 for such sales if that's the business rule.
                # For now, let's say this sale contributes to P&L as full revenue if no cost basis.
                # This part needs clarification based on how short sales / data integrity is handled.
                # A simple approach for now: if no buy lots, realized PNL is sell_price * sell_qty (less robust).
                # realized_pnl += sell_quantity_remaining * price # simplistic if no cost basis
                print(f"Warning: Selling {symbol} but no prior buy lots found or all sold. P&L for this sell might be inaccurate without full history or short-sale logic.")
                # Let's assume cost basis is 0 for this calculation if no lots are found.
                # This means the entire sell amount is profit. This is a strong assumption.
                # A more conservative approach might be to not calculate PNL for this specific sell if no cost basis.
                # For this exercise, let's proceed with cost_basis = 0 for this part of sell if no matching buy.
                # realized_pnl += sell_quantity_remaining * price
                # However, standard FIFO means you can only sell what you have.
                # If this situation occurs, it might be better to flag it or log an error.
                # For now, if no lots, we just skip trying to find a cost for this part of the sale.
                # This effectively makes the realized PnL only from sales that *do* have matching buys.
                pass


            temp_lots_for_symbol = []
            for lot in bought_lots.get(symbol, []):
                if sell_quantity_remaining == 0:
                    temp_lots_for_symbol.append(lot) # Keep lot if not used
                    continue

                if lot['quantity'] <= sell_quantity_remaining:
                    # Entire lot is sold
                    realized_pnl += (price - lot['price']) * lot['quantity']
                    sell_quantity_remaining -= lot['quantity']
                else:
                    # Partial lot is sold
                    realized_pnl += (price - lot['price']) * sell_quantity_remaining
                    lot['quantity'] -= sell_quantity_remaining
                    sell_quantity_remaining = 0
                    temp_lots_for_symbol.append(lot) # Keep remaining part of lot
            
            if symbol in bought_lots: # Update the lots for the symbol
                bought_lots[symbol] = temp_lots_for_symbol


    # Calculate cost basis of current holdings for unrealized P&L
    current_holdings_cost_basis = 0.0
    for symbol_lots in bought_lots.values():
        for lot in symbol_lots:
            current_holdings_cost_basis += lot['quantity'] * lot['price']

    # compute_portfolio_value is async
    current_market_value = await compute_portfolio_value(db, portfolio_id)
    
    unrealized_pnl = current_market_value - current_holdings_cost_basis

    return {
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "current_market_value": round(current_market_value, 2),
        "cost_basis_of_current_holdings": round(current_holdings_cost_basis, 2)
    }