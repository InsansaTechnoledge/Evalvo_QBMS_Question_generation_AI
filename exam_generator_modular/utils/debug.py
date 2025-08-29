# utils/debug.py
from typing import Optional, Dict, List
from database.question_repository import fetch_questions_from_supabase

def debug_database_content(criteria: Dict, organization_id: Optional[str] = None) -> List[Dict]:
    """Debug function to show what's available in the database"""
    print("\nDEBUG: Database Analysis")
    print("=" * 50)
    
    # Fetch all questions to analyze database content
    questions = list(fetch_questions_from_supabase(organization_id=organization_id))
    print(f"Total questions in database: {len(questions)}")
    
    if questions:
        # Show unique values for each field
        for field in ['subject', 'chapter', 'question_type', 'difficulty', 'bloom_level', 'positive_marks']:
            unique_vals = list(set([str(q.get(field, '')) for q in questions if q.get(field) is not None]))
            print(f"{field.capitalize()}: {sorted([val for val in unique_vals if val.strip()])}")
    
    print(f"\nSearch criteria: {criteria}")
    return questions
