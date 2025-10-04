from sqlalchemy.orm import Session
from app.crud import portfolio as crud_portfolio
from app.services.financial_data_service import financial_data_service
import asyncio
from typing import List, Dict, Union

async def compute_portfolio_value(db: Session, portfolio_id: int) -> float:
    """Computes the total current market value of a portfolio.

    This function fetches the current price for each position in the portfolio
    concurrently and sums their market values.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio.

    Returns:
        float: The total market value of the portfolio.
    """
    positions = crud_portfolio.get_positions(db, portfolio_id)
    total_value = 0.0

    if not positions:
        return 0.0

    tasks = []
    for pos in positions:
        tasks.append(financial_data_service.get_stock_quote(str(pos.symbol)))
    
    quotes_results: List[Union[Dict, None]] = await asyncio.gather(*tasks, return_exceptions=True)

    for i, pos in enumerate(positions):
        quote_data = quotes_results[i]
        
        if isinstance(quote_data, Exception):
            print(f"Error fetching quote for {pos.symbol} in compute_portfolio_value: {quote_data}. Omitting from total value.")
            continue

        if quote_data and isinstance(quote_data, dict) and "Error Message" not in quote_data:
            try:
                price_str = quote_data.get("05. price")
                if price_str and price_str != 'N/A':
                    price = float(price_str)
                    total_value += price * float(pos.quantity)
                else:
                    print(f"Warning: Could not get current price for {pos.symbol} in compute_portfolio_value. Price: {price_str}. Omitting from total value.")
            except ValueError:
                print(f"Warning: Could not convert price '{price_str}' to float for {pos.symbol}. Omitting from total value.")
            except Exception as e:
                print(f"An unexpected error occurred processing position {pos.symbol}: {e}. Omitting from total value.")
        else:
            error_msg = quote_data.get("Error Message", "Unknown error") if isinstance(quote_data, dict) else "Received non-dict quote_data"
            print(f"Warning: Could not fetch or use quote for {pos.symbol} in compute_portfolio_value: {error_msg}. Omitting from total value.")
            
    return total_value

async def get_portfolio_24h_change_percentage(db: Session, portfolio_id: int) -> float:
    """Calculates the overall 24-hour change percentage of the portfolio.

    This is calculated as the percentage change from the total value at the
    previous day's close to the total value at the current market price.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio.

    Returns:
        float: The 24-hour change as a percentage.
    """
    positions = crud_portfolio.get_positions(db, portfolio_id)
    if not positions:
        return 0.0

    total_current_value = 0.0
    total_previous_day_value = 0.0
    
    tasks = [financial_data_service.get_stock_quote(str(pos.symbol)) for pos in positions]
    quotes_results: List[Union[Dict, None]] = await asyncio.gather(*tasks, return_exceptions=True)

    valid_data_for_change_calculation_found = False
    for i, pos in enumerate(positions):
        quote = quotes_results[i]

        if isinstance(quote, Exception):
            print(f"Error fetching quote for {pos.symbol} in 24h change calc: {quote}. Skipping.")
            continue

        if quote and isinstance(quote, dict) and "Error Message" not in quote:
            try:
                current_price_str = quote.get("05. price")
                previous_close_str = quote.get("08. previous close")
                quantity = float(pos.quantity)

                if current_price_str and current_price_str != 'N/A' and \
                   previous_close_str and previous_close_str != 'N/A':
                    
                    current_price = float(current_price_str)
                    previous_close_price = float(previous_close_str)
                    
                    total_current_value += current_price * quantity
                    total_previous_day_value += previous_close_price * quantity
                    valid_data_for_change_calculation_found = True
                else:
                    print(f"Warning: Missing current or previous price for {pos.symbol} in 24h change. Current: '{current_price_str}', Previous: '{previous_close_str}'. Skipping.")
            
            except (ValueError, TypeError) as e:
                print(f"Error converting price/quantity for {pos.symbol} in 24h change: {e}. Skipping.")
        else:
            error_msg = quote.get("Error Message", "Unknown error") if isinstance(quote, dict) else "Received non-dict quote data"
            print(f"Warning: Could not fetch/use quote for {pos.symbol} in 24h change: {error_msg}. Skipping.")

    if not valid_data_for_change_calculation_found:
        print("No valid price data found for any positions to calculate 24h portfolio change.")
        return 0.0

    if total_previous_day_value == 0:
        if total_current_value > 0:
            print("Warning: Total previous day portfolio value is zero, current value positive. Percentage change is effectively infinite or undefined.")
            return 100.0
        return 0.0 

    change_percentage = ((total_current_value - total_previous_day_value) / total_previous_day_value) * 100
    return change_percentage