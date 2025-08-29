# database/supabase_client.py
from supabase import Client
from config import get_supabase_client
from database.question_repository import fetch_questions_from_supabase, fetch_question_details

def create_supabase_client() -> Client:
    """Create and return Supabase client (wrapper for config function)"""
    from config import initialize_supabase_client
    client = initialize_supabase_client()
    if client is None:
        raise RuntimeError("Failed to initialize Supabase client")
    return client

def test_supabase_connection() -> bool:
    """Test Supabase database connection"""
    print("\nTesting Supabase Connection:")
    print("=" * 50)
    
    supabase_client = get_supabase_client()
    if not supabase_client:
        print("❌ Supabase client not initialized")
        return False
    
    try:
        # Test fetching questions
        questions = fetch_questions_from_supabase()
        print(f"✅ Successfully connected to Supabase")
        print(f"✅ Found {len(questions)} questions in database")
        
        if questions:
            # Show some sample data
            sample_question = questions[0]
            print(f"✅ Sample question: {sample_question}")
            
            # Test fetching question details
            q_id = sample_question['id']
            q_type = sample_question['question_type']
            details = fetch_question_details(q_id, q_type)
            print(f"✅ Successfully fetched details for {q_type} question")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing Supabase connection: {e}")
        return False