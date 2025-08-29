# api/dependencies.py
from fastapi import HTTPException, Header
from typing import Optional
from config import get_supabase_client

def get_organization_id(organization_id: Optional[str] = Header(None, alias="X-Organization-ID")) -> Optional[str]:
    """Extract organization ID from header"""
    return organization_id

def validate_request(prompt: str) -> None:
    """Validate incoming request"""
    if not prompt or len(prompt.strip()) < 10:
        raise HTTPException(status_code=400, detail="Prompt must be at least 10 characters long")

def get_database_client():
    """Get database client dependency"""
    client = get_supabase_client()
    if not client:
        raise HTTPException(status_code=503, detail="Database connection not available")
    return client