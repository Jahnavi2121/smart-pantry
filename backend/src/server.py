from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.products import router as products_router


app = FastAPI(
    title="Smart Pantry API",
    description="Backend API for the Smart Pantry capstone project.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "smart-pantry-api"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )