# api/models.py
from pydantic import BaseModel
from typing import Optional

class ExamRequest(BaseModel):
    """Request model for exam generation"""
    prompt: str
    organization_id: Optional[str] = None

class ExamResponse(BaseModel):
    """Response model for exam generation"""
    success: bool
    exam_paper: Optional[str] = None
    error: Optional[str] = None
    report: Optional[str] = None

class ConnectionTestResponse(BaseModel):
    """Response model for connection test"""
    success: bool
    error: Optional[str] = None
    message: Optional[str] = None