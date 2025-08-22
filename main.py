from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import qp_supabase  # your existing logic

app = FastAPI(
    title="Exam Paper Generator API",
    description="API for generating exam papers using Supabase and hybrid parsing",
    version="1.0.0"
)

# Input schema
class ExamRequest(BaseModel):
    prompt: str
    organization_id: Optional[str] = None


@app.get("/")
def root():
    return {"message": "✅ Exam Generator API is running"}


@app.post("/generate_exam")
def generate_exam(request: ExamRequest):
    try:
        paper = qp_supabase.generate_exam_paper(
            user_prompt=request.prompt,
            organization_id=request.organization_id
        )
        if paper:
            return {"success": True, "exam_paper": paper}
        else:
            return {"success": False, "error": "Failed to generate exam paper"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/test_connection")
def test_connection():
    try:
        success = qp_supabase.test_supabase_connection()
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}
