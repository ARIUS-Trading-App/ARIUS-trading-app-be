from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import engine, Base
from app.models import user
from app.models import portfolio
from app.models import transaction

from app.routes import auth_router
from app.routes import user_router
from app.routes import portfolio_router
from app.routes import feed_router
from app.routes import prediction_router
from app.routes import chat_router
from app.routes import financial_router
from app.routes import sentiment_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading LLM App")

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication router
app.include_router(auth_router.router)
# Include user router
app.include_router(user_router.router)
# Include chat router
app.include_router(chat_router.router)
# Include portfolio router
app.include_router(portfolio_router.router)
# Include feed router
app.include_router(feed_router.router)
# Include prediction router
app.include_router(prediction_router.router)
# Include financial data router
app.include_router(financial_router.router)
# Include sentiment index router
app.include_router(sentiment_router.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Trading LLM App!"}
