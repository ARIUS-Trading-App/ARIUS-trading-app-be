import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.crud import user as crud_user
from app.schemas.user import UserCreate
from app.services.prediction_service import prediction_service

from pytest_regressions.json_regression import JsonRegressionFixture

# Setup in-memory DB & overrides
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_db

# Create a dummy user and override auth
def dummy_current_user():
    db = TestingSessionLocal()
    user = crud_user.create_user(db, UserCreate(username="snap_user", email="snap@example.com"))
    db.close()
    return user

from app.core.dependencies import get_current_user
app.dependency_overrides[get_current_user] = dummy_current_user

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def mock_services(monkeypatch):
    # Mock forecast
    async def fake_forecast(symbol, periods):
        return [{"ds": "2025-01-01T00:00:00", "yhat": 50.0 + i} for i in range(periods)]
    monkeypatch.setattr(prediction_service, "forecast", fake_forecast)
    # Mock market data
    from app.services.financial_data_service import FinancialDataService
    async def dummy_price(self, symbol):
        return {"05. price": "100.0"}
    monkeypatch.setattr(FinancialDataService, "get_stock_quote", dummy_price)

def test_end_to_end_snapshot(client, json_regression: JsonRegressionFixture):
    # 1) Create portfolio
    pf = client.post("/portfolios/", json={"name": "SnapPF"}).json()
    json_regression.check(pf, basename="portfolio_create")
    pf_id = pf["id"]

    # 2) Add tx
    txs = []
    for tx in [
        {"symbol":"AAPL","type":"buy","quantity":1,"price":10},
        {"symbol":"AAPL","type":"sell","quantity":1,"price":20}
    ]:
        res = client.post(f"/portfolios/{pf_id}/transactions", json=tx).json()
        txs.append(res)
    json_regression.check(txs, basename="transactions_create")

    # 3) Snapshot list
    lst = client.get(f"/portfolios/{pf_id}/transactions").json()
    json_regression.check(lst, basename="transactions_list")

    # 4) Snapshot P&L
    pnl = client.get(f"/portfolios/{pf_id}/pnl").json()
    json_regression.check(pnl, basename="pnl")

    # 5) Snapshot forecast
    fc = client.get("/forecast/AAPL?periods=3").json()
    json_regression.check(fc, basename="forecast")