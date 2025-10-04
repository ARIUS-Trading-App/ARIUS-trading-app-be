from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from datetime import datetime
from app.services.prediction_service import prediction_service
from app.schemas.prediction import ForecastPoint
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/forecast", tags=["Forecast"])

@router.get(
    "/{symbol}",
    response_model=List[ForecastPoint],
    summary="Forecast next N business days for a symbol"
)
async def get_forecast(
    symbol: str,
    periods: int = Query(10, gt=0, le=30),
    current_user = Depends(get_current_user)
):
    """Generates a price forecast for a given stock symbol.

    This endpoint uses the prediction service to forecast future price points
    but does not use the current user's profile for personalization in this version.

    Args:
        symbol (str): The stock ticker symbol to forecast.
        periods (int): The number of future business days to predict.
        current_user: The authenticated user dependency.

    Returns:
        List[ForecastPoint]: A list of forecasted data points.

    Raises:
        HTTPException: 503 if the forecasting service encounters an error.
    """
    try:
        data = await prediction_service.forecast(symbol, periods=periods)
        return data
    except Exception as e:
        raise HTTPException(503, f"Forecast error: {str(e)}")