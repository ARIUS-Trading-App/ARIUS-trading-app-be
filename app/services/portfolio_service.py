from sqlalchemy.orm import Session
from app.crud import portfolio as crud_portfolio
from app.services.financial_data_service import FinancialDataService
import asyncio

fd_service = FinancialDataService()

async def compute_portfolio_value(db: Session, portfolio_id: int) -> float:
    positions = crud_portfolio.get_positions(db, portfolio_id)
    total = 0.0
    for pos in positions:
        # 1) Fetch quote asincron
        quote = await fd_service.get_stock_quote(pos.symbol)
        price = float(quote.get("05. price", 0))
        total += price * pos.quantity
    return total

async def get_portfolio_24h_change_percentage(db: Session, portfolio_id: int) -> float:
    """
    Calculates the overall 24-hour change percentage of the portfolio.
    This is based on the change from the previous closing prices to current prices.
    """
    # Assuming crud_portfolio.get_positions is synchronous. If async, await it.
    positions = crud_portfolio.get_positions(db, portfolio_id)
    if not positions:
        return 0.0  # No positions, so no change

    total_current_value = 0.0
    total_previous_day_value = 0.0
    
    # Prepare tasks for fetching quotes concurrently
    tasks = []
    for pos in positions:
        # Ensure pos.symbol is a string
        tasks.append(fd_service.get_stock_quote(str(pos.symbol)))
    
    # Execute all quote fetching tasks concurrently
    # The _run_sync in FinancialDataService handles yfinance's sync nature in an async context,
    # so asyncio.gather here will allow multiple _run_sync calls to be managed by the event loop.
    quotes_results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_data_for_change_calculation_found = False
    for i, pos in enumerate(positions):
        quote = quotes_results[i]

        if isinstance(quote, Exception):
            print(f"Error fetching quote for {pos.symbol}: {quote}. Skipping for 24h change calculation.")
            continue # Skip this position if fetching its quote failed

        if quote:
            try:
                current_price_str = quote.get("05. price")
                previous_close_str = quote.get("08. previous close")

                # Ensure quantity is a float
                quantity = float(pos.quantity)

                if current_price_str and current_price_str != 'N/A' and \
                    previous_close_str and previous_close_str != 'N/A':
                    
                    current_price = float(current_price_str)
                    previous_close_price = float(previous_close_str)
                    
                    total_current_value += current_price * quantity
                    total_previous_day_value += previous_close_price * quantity
                    valid_data_for_change_calculation_found = True
                else:
                    # If only one is missing, this position won't be accurately part of the change.
                    print(f"Warning: Missing current or previous price for {pos.symbol}. Skipping its contribution to 24h change.")
            
            except ValueError as e:
                print(f"Error converting price or quantity data for {pos.symbol}: {e}. Skipping for 24h change calculation.")
            except TypeError as e:
                print(f"Error with data types for position {pos.symbol} (e.g. quantity): {e}. Skipping for 24h change calculation.")
        else:
            print(f"Warning: Could not fetch quote for {pos.symbol}. Skipping for 24h change calculation.")

    if not valid_data_for_change_calculation_found:
        print("No valid price data found for any positions to calculate 24h change.")
        return 0.0

    if total_previous_day_value == 0:
        if total_current_value > 0:
            # Portfolio might be new and all assets appreciated from a zero base (unlikely for prev_close)
            # Or all assets had a previous close of 0.
            # Returning 0 to avoid division by zero and indicate no calculable *percentage* change from zero.
            # Alternatively, could return float('inf') or 100.0 if appropriate for business logic.
            print("Warning: Total previous day value is zero. Cannot calculate percentage change accurately.")
            return 0.0 
        return 0.0  # Both current and previous total values are zero

    change_percentage = ((total_current_value - total_previous_day_value) / total_previous_day_value) * 100
    return change_percentage