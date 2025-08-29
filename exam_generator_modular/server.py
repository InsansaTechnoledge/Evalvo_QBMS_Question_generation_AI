# server.py - FastAPI server entry point
"""
Create this file to run the FastAPI server
"""
import uvicorn
from api.fastapi_app import app

if __name__ == "__main__":
    uvicorn.run(
        "api.fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )