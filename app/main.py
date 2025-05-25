from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import engine, Base
from app.models import user

from app.routes import auth_router
from app.routes import user_router
from app.routes import chat_router

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

app.include_router(auth_router.router)

app.include_router(user_router.router)
app.include_router(chat_router.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Trading LLM App!"}
