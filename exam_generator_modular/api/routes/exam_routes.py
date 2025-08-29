# api/routes/exam_routes.py
from fastapi import APIRouter, HTTPException
from ..models import ExamRequest, ExamResponse, ConnectionTestResponse
from services.exam_generator import generate_exam_paper
from database.supabase_client import test_supabase_connection

router = APIRouter()

@router.get("/", response_model=dict)
def root_endpoint():
    """Root endpoint to check if API is running"""
    return {"message": "Exam Generator API is running"}

@router.post("/generate_exam", response_model=ExamResponse)
def generate_exam_endpoint(request: ExamRequest):
    """Generate exam paper based on prompt"""
    try:
        paper, report = generate_exam_paper(
            user_prompt=request.prompt,
            organization_id=request.organization_id
        )
        
        if paper:
            return ExamResponse(
                success=True, 
                exam_paper=paper,
                report=report.generate_report() if report else None
            )
        else:
            return ExamResponse(
                success=False, 
                error="Failed to generate exam paper",
                report=report.generate_report() if report else None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test_connection", response_model=ConnectionTestResponse)
def test_connection_endpoint():
    """Test database connection"""
    try:
        success = test_supabase_connection()
        return ConnectionTestResponse(
            success=success,
            message="Connection test completed" if success else "Connection test failed"
        )
    except Exception as e:
        return ConnectionTestResponse(success=False, error=str(e))