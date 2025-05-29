from fastapi import APIRouter, Path, HTTPException
from app.services.sentiment_service import compute_sentiment_score, classify_score

router = APIRouter(prefix="/sentiment", tags=["Sentiment"])

@router.get("/{symbol}", summary="Fear/Greed & Buy/Sell index")
async def sentiment_index(symbol: str = Path(..., description="Ticker, e.g. AAPL")):
    """
    Returns:
      - `score` ∈ [-1..1]
      - `action` ∈ {'buy','hold','sell'}
      - `mood`   ∈ {'greed','neutral','fear'}
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
