# database/batch_repository.py
from typing import Optional, Dict, List
from datetime import date
from config import get_supabase_client

def store_batch_exam(criteria: Dict, selected_questions: List[Dict]) -> Optional[str]:
    """Store batch exam details in the database"""
    supabase = get_supabase_client()
    if not supabase or not criteria.get('batch_name'):
        return None
    
    try:
        total_marks = sum([q.get('positive_marks', 0) for q in selected_questions])
        subjects = list(set([q.get('subject') for q in selected_questions if q.get('subject')]))
        
        exam_data = {
            'name': criteria['batch_name'],
            'date': date.today().isoformat(),
            'organization_id': criteria['organization_id'],
            'total_marks': total_marks,
            'subjects': subjects,
            'description': f"Auto-generated exam with {len(selected_questions)} questions"
        }
        
        print(f"Debug: Attempting to insert: {exam_data}")  # Debug line
        response = supabase.table('batch_exam').insert(exam_data).execute()
        
        if response.data:
            print(f"Stored batch exam: {criteria['batch_name']}")
            return response.data[0]['id']
    except Exception as e:
        print(f"Error storing batch exam: {e}")
        print("Debug: Check if RLS policy is properly enabled for INSERT operations")
    return None