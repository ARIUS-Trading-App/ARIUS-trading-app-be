import pandas as pd
from prophet import Prophet
from app.services.financial_data_service import financial_data_service
from app.services.sentiment_service import compute_sentiment_score
from app.models.user import RiskAppetite, InvestmentGoals

RISK_FACTOR = {
    "Low": 0.8,
    "Medium": 1.0,
    "High": 1.2,
    "Very High": 1.5,
}
GOALS_FACTOR = {
    "Short-term Gains": 1.2,
    "Long-term Growth": 1.0,
    "Income Generation": 0.9,
    "Capital Preservation": 0.8,
    "Speculation": 1.3,
}

class PredictionService:
    def __init__(self):
        """Initializes the prediction service."""
        pass

    async def forecast(
        self,
        symbol: str,
        periods: int = 10,
        risk_appetite: str = "Medium",
        investment_goals: str = "Long-term Growth",
    ):
        """Generates a personalized stock price forecast using Prophet.

        This method performs a multi-step process:
        1. Fetches historical stock data.
        2. Computes a current sentiment score for the stock to use as a model regressor.
        3. Fits a Prophet time-series model to the data.
        4. Generates a forecast for the specified number of future periods.
        5. Adjusts the forecast's confidence intervals (upper and lower bounds)
           based on the user's risk appetite and investment goals.

        Args:
            symbol (str): The stock symbol to forecast.
            periods (int): The number of future business days to forecast.
            risk_appetite (str): The user's risk appetite (e.g., "Low", "Medium").
            investment_goals (str): The user's investment goals (e.g., "Long-term Growth").

        Returns:
            List[Dict]: A list of dictionaries, each representing a forecasted day
                        with the predicted price and personalized confidence bounds.
        
        Raises:
            ValueError: If historical data is insufficient or if the model fails to fit.
        """
        daily_series_data = await financial_data_service.get_daily_series(symbol, outputsize="full")
        if not daily_series_data or isinstance(daily_series_data, dict) and daily_series_data.get("Error Message"):
            error_msg = daily_series_data.get("Error Message", f"No data for symbol: {symbol}") if isinstance(daily_series_data, dict) else f"No data for symbol: {symbol}"
            raise ValueError(error_msg)

        df = (
            pd.DataFrame.from_dict(daily_series_data, orient="index")
              .reset_index()
              .rename(columns={"index": "ds", "4. close": "y"})
              [["ds", "y"]]
        )
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)
        df = df.sort_values(by='ds')

        if df.empty:
             raise ValueError(f"Historical data for {symbol} is empty after processing.")
        if len(df) < 2:
            raise ValueError(f"Not enough historical data points for {symbol} to make a forecast (requires at least 2). Found: {len(df)}")

        sentiment = await compute_sentiment_score(symbol)
        df["sentiment_regressor"] = sentiment

        model = Prophet(daily_seasonality=True)
        model.add_regressor("sentiment_regressor")
        
        try:
            model.fit(df)
        except Exception as e:
            raise ValueError(f"Error fitting Prophet model for {symbol}: {str(e)}. Ensure sufficient historical data.")

        future = model.make_future_dataframe(periods=periods, freq="B")
        future["sentiment_regressor"] = sentiment

        forecast_results = model.predict(future)

        rf_multiplier = RISK_FACTOR.get(risk_appetite, 1.0)
        gf_multiplier = GOALS_FACTOR.get(investment_goals, 1.0)
        adjustment_multiplier = rf_multiplier * gf_multiplier

        out_df = forecast_results[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

        out_df["yhat_lower_adjusted"] = out_df["yhat"] - adjustment_multiplier * (out_df["yhat"] - out_df["yhat_lower"])
        out_df["yhat_upper_adjusted"] = out_df["yhat"] + adjustment_multiplier * (out_df["yhat_upper"] - out_df["yhat"])
        
        out_df["yhat_lower_adjusted"] = out_df[["yhat_lower_adjusted", "yhat"]].min(axis=1)
        out_df["yhat_upper_adjusted"] = out_df[["yhat_upper_adjusted", "yhat"]].max(axis=1)
        out_df.loc[out_df["yhat_lower_adjusted"] > out_df["yhat_upper_adjusted"], ["yhat_lower_adjusted", "yhat_upper_adjusted"]] = \
            out_df.loc[out_df["yhat_lower_adjusted"] > out_df["yhat_upper_adjusted"], ["yhat_upper_adjusted", "yhat_lower_adjusted"]].values

        recent_forecast = out_df.tail(periods).copy()
        recent_forecast["ds"] = recent_forecast["ds"].dt.strftime('%Y-%m-%d')
        
        final_columns = ["ds", "yhat", "yhat_lower_adjusted", "yhat_upper_adjusted"]
        return recent_forecast[final_columns].to_dict(orient="records")

prediction_service = PredictionService()