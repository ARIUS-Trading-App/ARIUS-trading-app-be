from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.db.session import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ———————————————
# Setup DB override (same as above)
# ———————————————
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

def auth_c(client):
    token = client.post("/auth/request-token", json={"email": "tx@user.com"}).json()["token"]
    res = client.get(f"/auth/verify-token?token={token}")
    client.cookies["access_token"] = res.cookies["access_token"]
    return client

def test_transaction_crud_flow(client):
    c = auth_c(client)
    # 1) Create portfolio
    pf = c.post("/portfolios/", json={"name": "Tx PF"}).json()
    pf_id = pf["id"]

    # 2) Add three buy transactions
    for i in range(3):
        r = c.post(
            f"/portfolios/{pf_id}/transactions",
            json={"symbol": "AAPL", "type": "buy", "quantity": 1, "price": 100 + i}
        )
        assert r.status_code == 201

    # 3) List w/ pagination
    page1 = c.get(f"/portfolios/{pf_id}/transactions?skip=0&limit=2")
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    # 4) Update one
    tx_id = page1.json()[0]["id"]
    upd = c.put(
        f"/portfolios/{pf_id}/transactions/{tx_id}",
        json={"price": 123.45}
    )
    assert upd.status_code == 200
    assert upd.json()["price"] == 123.45

    # 5) Delete it
    dl = c.delete(f"/portfolios/{pf_id}/transactions/{tx_id}")
    assert dl.status_code == 204

    # 6) Ensure it's gone
    remaining = c.get(f"/portfolios/{pf_id}/transactions")
    assert all(tx["id"] != tx_id for tx in remaining.json())
