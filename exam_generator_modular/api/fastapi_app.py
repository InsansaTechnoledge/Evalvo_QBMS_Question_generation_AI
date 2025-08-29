# api/fastapi_app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.exam_routes import router as exam_router
from config import initialize_all

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="Exam Paper Generator API",
        description="API for generating exam papers using Supabase and hybrid parsing",
        version="1.0.0"
    )
    
    # Configure CORS
    configure_cors(app)
    
    # Include routers
    app.include_router(exam_router)
    
    # Initialize all components on startup
    @app.on_event("startup")
    async def startup_event():
        print("Starting Exam Generator API...")
        initialization_status = initialize_all()
        print("Initialization Status:")
        for component, status in initialization_status.items():
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {component}: {'Success' if status else 'Failed'}")
    
    return app

def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware"""
    origins = [
        "https://evalvotech.com",
        "http://localhost:5173",
        "http://localhost:5174", 
        "https://www.evalvotech.com",
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Create the app instance
app = create_app()