# app/services/prediction_service.py
import pandas as pd
from prophet import Prophet
from app.services.financial_data_service import FinancialDataService
from app.services.sentiment_service import compute_sentiment_score

# maps your enums → numerical multipliers
RISK_FACTOR = {
    "Low": 0.8,
    "Medium": 1.0,
    "High": 1.2,
    "Very High": 1.5,
}
GOALS_FACTOR = {
    "Short-term Gains":    1.2,
    "Long-term Growth":    1.0,
    "Income Generation":   0.9,
    "Capital Preservation":0.8,
    "Speculation":         1.3,
}

class PredictionService:
    def __init__(self):
        self.fd = FinancialDataService()

    async def forecast(
        self,
        symbol: str,
        periods: int = 10,
        risk_appetite: str = "Medium",
        investment_goals: str = "Long-term Growth",
    ):
        # 1) Load OHLC history
        ts = await self.fd.get_daily_series(symbol, outputsize="full")
        if not ts:
            raise ValueError(f"No data for symbol: {symbol}")

        df = (
            pd.DataFrame.from_dict(ts, orient="index")
              .reset_index()
              .rename(columns={"index":"ds","4. close":"y"})
              [["ds","y"]]
        )
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)

        # 2) Compute _one_ sentiment score for this symbol
        sentiment = await compute_sentiment_score(symbol)
        #    apply it as a constant regressor
        df["sentiment"] = sentiment

        # 3) Fit Prophet with that regressor
        model = Prophet(daily_seasonality=True)
        model.add_regressor("sentiment")
        model.fit(df)

        # 4) Build future frame, fill in the same sentiment
        future = model.make_future_dataframe(periods=periods, freq="B")
        future["sentiment"] = sentiment

        # 5) Predict
        forecast = model.predict(future)

        # 6) Tweak confidence bands by risk × goals
        rf = RISK_FACTOR.get(risk_appetite, 1.0)
        gf = GOALS_FACTOR.get(investment_goals, 1.0)
        mult = rf * gf

        # we'll return these columns:
        out = forecast[["ds","yhat","yhat_lower","yhat_upper"]].copy()
        out["yhat_lower_adj"] = out["yhat"] - mult * (out["yhat"] - out["yhat_lower"])
        out["yhat_upper_adj"] = out["yhat"] + mult * (out["yhat_upper"] - out["yhat"])

        # 7) Only emit the last `periods` rows
        recent = out.tail(periods)
        return recent.to_dict(orient="records")


# singleton instance
prediction_service = PredictionService()
