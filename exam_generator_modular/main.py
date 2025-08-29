"""
Main application entry point for the Exam Generator
Coordinates all modules and provides the primary interface
"""

from config import initialize_all
from database.supabase_client import test_supabase_connection
from services.exam_generator import generate_exam_paper
from utils.debug import debug_database_content

def main():
    """Main function to run the exam generator application"""
    print("Enhanced Exam Generator with Supabase Integration")
    print("=" * 70)
    
    # Initialize all components
    print("\nInitializing components...")
    initialization_status = initialize_all()
    
    print("\nInitialization Status:")
    print("-" * 30)
    for component, status in initialization_status.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {component}: {'Success' if status else 'Failed'}")
    
    # Test Supabase connection
    if not test_supabase_connection():
        print("\n💡 Please set up your Supabase credentials:")
        print("   - Create a .env file with SUPABASE_URL and SUPABASE_ANON_KEY")
        print("   - Or set these as environment variables")
        return

    # Run example exam generation
    run_example_generation()

def run_example_generation():
    """Run an example exam generation to demonstrate functionality"""
    example_prompt = "Generate an exam paper for batch demo with 3 mcqs, maximum 10 marks, subject Big Data"
    organization_id = "686e4d384529d5bc5f8a93e1"  # Replace with actual organization ID
    
    print(f"\n{'='*70}")
    print("MAIN EXAM GENERATION")
    print("=" * 70)
    print(f"Original Prompt: {example_prompt}")
    print(f"Organization ID: {organization_id}")
    
    try:
        # Generate exam paper
        exam_paper, report = generate_exam_paper(example_prompt, organization_id)
        
        if exam_paper:
            print(f"\n{'='*50}")
            print("GENERATED EXAM PAPER")
            print("=" * 50)
            print(exam_paper)
        else:
            print("❌ Failed to generate exam paper")
            
            # Print the filtering report for debugging
            if report:
                print("\nDEBUGGING INFORMATION:")
                print(report.generate_report())
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Running parsing test instead...")
        
        # Fallback to show what's available in database
        try:
            from parsers.prompt_parser import parse_prompt_with_hybrid
            criteria = parse_prompt_with_hybrid(example_prompt, organization_id)
            debug_database_content(criteria, organization_id)
        except Exception as debug_error:
            print(f"❌ Debug failed: {debug_error}")

def run_interactive_mode():
    """Interactive mode for testing different prompts"""
    print("\n🔄 Interactive Mode - Enter prompts to test")
    print("Type 'exit' to quit")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\nEnter exam prompt: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                print("Please enter a valid prompt")
                continue
            
            # Ask for organization ID
            org_id = input("Enter organization ID (or press Enter for default): ").strip()
            organization_id = org_id if org_id else "686e4d384529d5bc5f8a93e1"
            
            print(f"\nProcessing prompt: {user_input}")
            print(f"Organization ID: {organization_id}")
            
            # Generate exam
            exam_paper, report = generate_exam_paper(user_input, organization_id)
            
            if exam_paper:
                print("\n📄 Generated Exam Paper:")
                print("=" * 50)
                print(exam_paper)
            else:
                print("\n❌ Could not generate exam paper")
                if report:
                    print(report.generate_report())
                    
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
    
    # Uncomment to run interactive mode
    run_interactive_mode()