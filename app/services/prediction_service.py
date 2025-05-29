import pandas as pd
from prophet import Prophet
from app.services.financial_data_service import FinancialDataService

class PredictionService:
    def __init__(self):
        self.fd = FinancialDataService()

    async def forecast(self, symbol: str, periods: int = 10):
        """
        Forecast the next `periods` days of stock prices for a given symbol."""
        # Fetch daily OHLC data
        ts = await self.fd.get_daily_series(symbol, outputsize="full")
        if not ts:
            raise ValueError(f"No data found for symbol: {symbol}")
        # Convert the data to a DataFrame
        df = (
            pd.DataFrame.from_dict(ts, orient="index")
              .reset_index()
              .rename(columns={
                  "index": "ds",
                  "4. close": "y"
              })[["ds","y"]]
        )
        # Convert the date column to datetime and the price column to float
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)

        # Train the Prophet model
        model = Prophet(daily_seasonality=True)
        model.fit(df)

        # Create a DataFrame for future dates
        # and make predictions
        future = model.make_future_dataframe(periods=periods, freq="B")  
        forecast = model.predict(future)

        # Extract the relevant columns
        preds = forecast[["ds","yhat"]].tail(periods)
        return preds.to_dict("records")

prediction_service = PredictionService()
