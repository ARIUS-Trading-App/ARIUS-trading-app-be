from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import engine, Base
from app.models import user

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading LLM App")

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Allow requests from these origins
    allow_credentials=True,          # Allow cookies, authorization headers, etc.
    allow_methods=["*"],             # Allow all HTTP methods
    allow_headers=["*"],             # Allow all headers
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Trading LLM App!"}