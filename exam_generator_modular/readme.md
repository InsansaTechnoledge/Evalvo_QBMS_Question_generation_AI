# Exam Generator  

A modular **exam paper generation system** built with **FastAPI**, **Supabase**, and **Python**.  
Supports both a **standalone script** and an **API server** for flexible usage.  

---

## 📂 Project Structure

```bash
exam_generator/
├── config.py
├── main.py
├── server.py
├── requirements.txt
├── .env
├── database/
│   ├── __init__.py
│   ├── supabase_client.py
│   ├── question_repository.py
│   └── batch_repository.py
├── models/
│   ├── __init__.py
│   └── filtering_report.py
├── parsers/
│   ├── __init__.py
│   └── prompt_parser.py
├── services/
│   ├── __init__.py
│   ├── exam_generator.py
│   └── question_filter.py
├── formatters/
│   ├── __init__.py
│   └── paper_formatter.py
├── utils/
│   ├── __init__.py
│   └── debug.py
└── api/
    ├── __init__.py
    ├── fastapi_app.py
    ├── models.py
    ├── dependencies.py
    └── routes/
        ├── __init__.py
        └── exam_routes.py


⚙️ Setup Instructions
1. Clone the repository

git clone https://github.com/your-username/exam-generator.git
cd exam-generator


2. Install dependencies

pip install -r requirements.txt

3. Configure environment variables

Create a .env file in the project root:

SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
'''

🚀 Running the Application

Standalone version
python main.py

API server
python server.py
         OR
uvicorn api.fastapi_app:app --host 0.0.0.0 --port 8000 --reload

🌐 API Endpoints

Root: http://localhost:8000/
Generate Exam: POST /generate_exam
Test Connection: GET /test_connection
Docs (Swagger): http://localhost:8000/docs

📌 Example Usage
curl -X POST "http://localhost:8000/generate_exam" \
     -H "Content-Type: application/json" \
     -d '{
           "prompt": "Generate an exam paper for batch demo with 3 mcqs, maximum 10 marks, subject Big Data",
           "organization_id": "686e4d384529d5bc5f8a93e1"
         }'
