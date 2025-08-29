# database/question_repository.py
from functools import lru_cache
from typing import Optional, Dict, List
from config import get_supabase_client

# Cache for database results to improve performance
@lru_cache(maxsize=128)
def fetch_questions_from_supabase(organization_id: Optional[str] = None, subject: Optional[str] = None, 
                                chapter: Optional[str] = None, question_type: Optional[str] = None, 
                                difficulty: Optional[str] = None, bloom_level: Optional[str] = None, 
                                positive_marks: Optional[int] = None) -> tuple:
    """Fetch questions from Supabase with optional filters (cached for performance)"""
    supabase = get_supabase_client()
    if not supabase:
        raise Exception("Supabase client not initialized")
    
    try:
        query = supabase.table('questions').select('*')
        
        # Apply filters only if they have values
        filters_applied = []
        if organization_id:
            query = query.eq('organization_id', organization_id)
            filters_applied.append(f"organization_id={organization_id}")
        if subject:
            query = query.ilike('subject', f'%{subject}%')  # Case-insensitive partial match
            filters_applied.append(f"subject={subject}")
        if chapter:
            query = query.ilike('chapter', f'%{chapter}%')  # Case-insensitive partial match
            filters_applied.append(f"chapter={chapter}")
        if question_type:
            query = query.eq('question_type', question_type)
            filters_applied.append(f"question_type={question_type}")
        if difficulty:
            query = query.eq('difficulty', difficulty)
            filters_applied.append(f"difficulty={difficulty}")
        if bloom_level:
            query = query.eq('bloom_level', bloom_level)
            filters_applied.append(f"bloom_level={bloom_level}")
        if positive_marks:
            query = query.eq('positive_marks', positive_marks)
            filters_applied.append(f"positive_marks={positive_marks}")
        
        print(f"Database query with filters: {', '.join(filters_applied) if filters_applied else 'No filters'}")
        
        response = query.execute()
        questions = response.data
        
        print(f"Found {len(questions)} questions matching criteria")
        return tuple(questions)  # Return tuple for caching
    
    except Exception as e:
        print(f"Error fetching questions: {e}")
        return tuple()

# Cache for question details
@lru_cache(maxsize=256)
def fetch_question_details(question_id: str, question_type: str) -> Dict:
    """Fetch detailed question data based on type (cached for performance)"""
    supabase = get_supabase_client()
    if not supabase:
        return {}
    
    try:
        table_name = f'question_{question_type}'
        print(f"Fetching details from table: {table_name} for ID: {question_id}")
        
        response = supabase.table(table_name).select('*').eq('id', question_id).execute()
        
        if response.data:
            details = response.data[0]
            print(f"Found details for {question_type} question: {question_id}")
            return details
        else:
            print(f"No details found for {question_type} question: {question_id}")
        return {}
    
    except Exception as e:
        print(f"Error fetching question details for {question_type}: {e}")
        return {}