# app/services/prediction_service.py
import pandas as pd
from prophet import Prophet
from app.services.financial_data_service import financial_data_service # Updated instance name
from app.services.sentiment_service import compute_sentiment_score # Async
from app.models.user import RiskAppetite, InvestmentGoals # Assuming enums are in user model

# maps your enums → numerical multipliers
RISK_FACTOR = {
    RiskAppetite.LOW: 0.8,
    RiskAppetite.MEDIUM: 1.0,
    RiskAppetite.HIGH: 1.2,
    RiskAppetite.VERY_HIGH: 1.5,
}
GOALS_FACTOR = {
    InvestmentGoals.Short_term_Gains: 1.2,
    InvestmentGoals.Long_term_Growth: 1.0,
    InvestmentGoals.Income_Generation: 0.9,
    InvestmentGoals.Capital_Preservation: 0.8,
    InvestmentGoals.Speculation: 1.3,
}

class PredictionService:
    def __init__(self):
        # self.fd is already financial_data_service instance
        pass

    async def forecast(
        self,
        symbol: str,
        periods: int = 10,
        risk_appetite: str = "Medium", # String values from Enum
        investment_goals: str = "Long-term Growth", # String values from Enum
    ):
        # 1) Load OHLC history from financial_data_service
        # get_daily_series returns a dict of dicts: {'YYYY-MM-DD': {'1. open': ..., '4. close': ...}}
        daily_series_data = await financial_data_service.get_daily_series(symbol, outputsize="full")
        if not daily_series_data or isinstance(daily_series_data, dict) and daily_series_data.get("Error Message"):
            error_msg = daily_series_data.get("Error Message", f"No data for symbol: {symbol}") if isinstance(daily_series_data, dict) else f"No data for symbol: {symbol}"
            raise ValueError(error_msg)

        # Convert to DataFrame expected by Prophet
        # Original code expected: data.get("Time Series (Daily)", {})
        # The new get_daily_series returns the time series data directly.
        df = (
            pd.DataFrame.from_dict(daily_series_data, orient="index")
              .reset_index()
              .rename(columns={"index": "ds", "4. close": "y"})
              [["ds", "y"]]
        )
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)
        df = df.sort_values(by='ds') # Prophet expects ds to be sorted

        if df.empty:
             raise ValueError(f"Historical data for {symbol} is empty after processing.")
        if len(df) < 2: # Prophet requires at least 2 data points
            raise ValueError(f"Not enough historical data points for {symbol} to make a forecast (requires at least 2). Found: {len(df)}")


        # 2) Compute _one_ sentiment score for this symbol
        sentiment = await compute_sentiment_score(symbol) # This is async
        df["sentiment_regressor"] = sentiment # Apply as a constant regressor

        # 3) Fit Prophet with that regressor
        model = Prophet(daily_seasonality=True)
        model.add_regressor("sentiment_regressor")
        
        try:
            model.fit(df)
        except Exception as e:
            raise ValueError(f"Error fitting Prophet model for {symbol}: {str(e)}. Ensure sufficient historical data.")


        # 4) Build future frame, fill in the same sentiment
        future = model.make_future_dataframe(periods=periods, freq="B") # Business days
        future["sentiment_regressor"] = sentiment

        # 5) Predict
        forecast_results = model.predict(future)

        # 6) Tweak confidence bands by risk × goals
        # Convert string risk_appetite/investment_goals to Enum keys if necessary, or use string directly
        # The provided RISK_FACTOR and GOALS_FACTOR use string keys, which is fine.
        rf_multiplier = RISK_FACTOR.get(risk_appetite, 1.0)
        gf_multiplier = GOALS_FACTOR.get(investment_goals, 1.0)
        adjustment_multiplier = rf_multiplier * gf_multiplier

        out_df = forecast_results[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        # Adjust confidence intervals based on the multiplier
        # Width of original interval: yhat_upper - yhat_lower
        # Half-width: (yhat_upper - yhat_lower) / 2
        # Or distance from yhat: (yhat - yhat_lower) and (yhat_upper - yhat)
        # New lower: yhat - multiplier * (yhat - yhat_lower_original)
        # New upper: yhat + multiplier * (yhat_upper_original - yhat)
        out_df["yhat_lower_adjusted"] = out_df["yhat"] - adjustment_multiplier * (out_df["yhat"] - out_df["yhat_lower"])
        out_df["yhat_upper_adjusted"] = out_df["yhat"] + adjustment_multiplier * (out_df["yhat_upper"] - out_df["yhat"])
        
        # Ensure adjusted bounds don't cross yhat or each other illogically
        out_df["yhat_lower_adjusted"] = out_df[["yhat_lower_adjusted", "yhat"]].min(axis=1)
        out_df["yhat_upper_adjusted"] = out_df[["yhat_upper_adjusted", "yhat"]].max(axis=1)
        # Ensure lower < upper
        out_df.loc[out_df["yhat_lower_adjusted"] > out_df["yhat_upper_adjusted"], ["yhat_lower_adjusted", "yhat_upper_adjusted"]] = \
            out_df.loc[out_df["yhat_lower_adjusted"] > out_df["yhat_upper_adjusted"], ["yhat_upper_adjusted", "yhat_lower_adjusted"]].values


        # 7) Only emit the last `periods` rows (the forecasted part)
        # Also convert ds to string for JSON compatibility
        recent_forecast = out_df.tail(periods).copy()
        recent_forecast["ds"] = recent_forecast["ds"].dt.strftime('%Y-%m-%d')
        
        # Select final columns to return
        final_columns = ["ds", "yhat", "yhat_lower_adjusted", "yhat_upper_adjusted"]
        return recent_forecast[final_columns].to_dict(orient="records")

prediction_service = PredictionService()