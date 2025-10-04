from fastapi import APIRouter, Path, HTTPException
from app.services.sentiment_service import compute_sentiment_score, classify_score

router = APIRouter(
    prefix="/sentiment",
    tags=["Sentiment"],
)

@router.get("/{symbol}", summary="Fear/Greed & Buy/Sell index")
async def sentiment_index(
    symbol: str = Path(..., description="Ticker, e.g. AAPL")
):
    """Calculates a sentiment score based on recent news and social media.
    
    The score is computed over the last 24 hours of available data and
    classified into a suggested action and corresponding market mood.

    Args:
        symbol (str): The stock ticker symbol.

    Returns:
        dict: An object containing the symbol, a compound score from -1 to 1,
              an 'action' (buy/hold/sell), and a 'mood' (greed/neutral/fear).
              
    Raises:
        HTTPException: 500 if an error occurs during sentiment calculation.
    """
    try:
        score = await compute_sentiment_score(symbol.upper())
        action, mood = classify_score(score)
        return {
            "symbol": symbol.upper(),
            "score": round(score, 3),
            "action": action,
            "mood": mood,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))