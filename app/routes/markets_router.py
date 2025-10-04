from fastapi import APIRouter, Query
from typing import Dict, Optional

from app.services.financial_data_service import financial_data_service as financial_service

router = APIRouter(prefix="/markets", tags=["Markets"])


@router.get("/snapshot", summary="Aggregated snapshot for markets page")
async def markets_snapshot(
    equities: Optional[str] = Query(None, description="Comma-separated equity symbols e.g., AAPL,MSFT"),
    crypto_base: str = Query("BTC", description="Crypto base symbol e.g., BTC"),
    crypto_quote: str = Query("USD", description="Crypto quote symbol e.g., USD"),
    fx_from: str = Query("USD", description="FX base currency e.g., USD"),
    fx_to: str = Query("JPY", description="FX quote currency e.g., JPY"),
    gdp_interval: str = Query("quarterly", description="GDP interval e.g., quarterly or annual"),
):
    # Equities quotes
    equities_map: Dict[str, dict] = {}
    if equities:
        symbols = [s.strip().upper() for s in equities.split(',') if s.strip()]
        for sym in symbols:
            try:
                q = await financial_service.get_stock_quote(sym)
                equities_map[sym] = q or {"Error": "No data"}
            except Exception as e:
                equities_map[sym] = {"Error": str(e)}

    # Crypto rate
    crypto_pair = f"{crypto_base.upper()}/{crypto_quote.upper()}"
    crypto_rate_val: Optional[float] = None
    crypto_raw = await financial_service.get_crypto_exchange_rate(crypto_base, crypto_quote)
    try:
        crypto_rate_val = float(
            (crypto_raw.get("exchange_rate")
             or crypto_raw.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
             or "")
        )
    except Exception:
        crypto_rate_val = None

    # FX latest daily close
    fx_pair = f"{fx_from.upper()}/{fx_to.upper()}"
    fx_rate_val: Optional[float] = None
    fx_hist = await financial_service.get_daily_fx_rates(fx_from, fx_to, 'compact')
    try:
        series = fx_hist.get('Time Series FX (Daily)', {})
        if isinstance(series, dict) and series:
            latest_date = sorted(series.keys())[-1]
            latest = series[latest_date]
            close_str = latest.get('4. close') or latest.get('close') or latest.get('price')
            fx_rate_val = float(close_str) if close_str is not None else None
    except Exception:
        fx_rate_val = None

    # GDP (may be a placeholder from service)
    gdp_data = await financial_service.get_real_gdp(gdp_interval)

    return {
        "equities": equities_map,
        "crypto": {"pair": crypto_pair, "rate": crypto_rate_val, "raw": crypto_raw},
        "fx": {"pair": fx_pair, "rate": fx_rate_val},
        "gdp": gdp_data,
    }


