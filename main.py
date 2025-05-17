from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Define the list of allowed origins for CORS
origins = [
    "http://localhost:3000",
    # Add more origins as needed
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Allow requests from these origins
    allow_credentials=True,          # Allow cookies, authorization headers, etc.
    allow_methods=["*"],             # Allow all HTTP methods
    allow_headers=["*"],             # Allow all headers
)

@app.get("/")
async def root():
    return {"message": "Hello, FastAPI with CORS!"}