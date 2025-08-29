# services/exam_generator.py
import random
from typing import Tuple, Dict, List, Optional
from models.filtering_report import FilteringReport
from parsers.prompt_parser import parse_prompt_with_hybrid
from database.question_repository import fetch_questions_from_supabase
from services.question_filter import (
    filter_questions_with_report, 
    suggest_relaxed_criteria_with_report,
    find_balanced_subset_with_report,
    find_questions_for_marks
)
from formatters.paper_formatter import (
    generate_paper_content_with_report,
    generate_multi_type_paper_content_with_report
)
from database.batch_repository import store_batch_exam
from utils.debug import debug_database_content

def generate_exam_paper(user_prompt: str, organization_id: Optional[str] = None) -> Tuple[str, FilteringReport]:
    """Generate exam paper with Supabase data fetching and return filtering report"""
    report = FilteringReport()
    
    try:
        criteria = parse_prompt_with_hybrid(user_prompt, organization_id)
        
        # Debug the database content
        all_questions = debug_database_content(criteria, organization_id)
        report.set_initial_count(len(all_questions))
        
        if not all_questions:
            report.add_warning("No questions found in database")
            return "", report
        
        # Handle multiple question types
        if criteria.get("question_types_breakdown"):
            paper, multi_report = generate_multi_type_exam(criteria, all_questions, organization_id)
            # Merge reports
            report.steps.extend(multi_report.steps)
            report.warnings.extend(multi_report.warnings)
            report.suggestions.extend(multi_report.suggestions)
            report.set_final_count(multi_report.final_count)
            return paper, report
        
        # Original single-type logic
        filtered_questions, filter_report = filter_questions_with_report(all_questions, criteria)
        report = filter_report
        
        print(f"\nFinal filtered results: {len(filtered_questions)} questions")
        report.set_final_count(len(filtered_questions))
        
        if len(filtered_questions) < criteria['num_questions']:
            error_msg = f"Not enough questions matching criteria. Required: {criteria['num_questions']}, Available: {len(filtered_questions)}"
            report.add_warning(error_msg)
            print(f"\nError: {error_msg}")
            
            # Suggest relaxed criteria
            suggestions = suggest_relaxed_criteria_with_report(all_questions, criteria)
            for suggestion in suggestions:
                report.add_suggestion(suggestion)
            return "", report
        
        # Find balanced subset
        selected_questions, balance_warnings = find_balanced_subset_with_report(filtered_questions, criteria)
        for warning in balance_warnings:
            report.add_warning(warning)
            
        if not selected_questions:
            report.add_warning("Cannot find questions that sum to the exact total marks")
            return "", report
        
        # Generate the paper
        paper = generate_paper_content_with_report(selected_questions, criteria, report)
        
        # Store batch exam if batch name is provided
        if criteria.get('batch_name'):
            exam_id = store_batch_exam(criteria, selected_questions)
            if exam_id:
                paper = f"Batch Exam ID: {exam_id}\n" + paper
        
        return paper, report
        
    except Exception as e:
        report.add_warning(f"Error generating exam paper: {e}")
        print(f"Error generating exam paper: {e}")
        return "", report

def generate_multi_type_exam(criteria: Dict, all_questions: List[Dict], organization_id: Optional[str] = None) -> Tuple[str, FilteringReport]:
    """Generate exam with multiple question types from Supabase with detailed reporting"""
    report = FilteringReport()
    question_types_breakdown = criteria["question_types_breakdown"]
    max_marks = criteria.get("max_marks")
    
    all_selected_questions = []
    total_questions = 0
    total_marks_used = 0
    
    report.set_initial_count(len(all_questions))
    
    print(f"\nGenerating multi-type exam:")
    print(f"   Question breakdown: {question_types_breakdown}")
    print(f"   Target marks: {max_marks}")
    
    for q_type, count in question_types_breakdown.items():
        print(f"\nProcessing {q_type}: {count} questions")
        
        # Filter questions for this type
        type_questions = [q for q in all_questions if q.get('question_type', '').lower() == q_type.lower()]
        before_count = len(type_questions)
        
        # Apply other criteria
        filtered_questions = type_questions
        filter_fields = ['subject', 'chapter', 'difficulty', 'bloom_level']
        for field in filter_fields:
            if criteria.get(field) is not None:
                before_field_count = len(filtered_questions)
                if isinstance(criteria[field], str):
                    filtered_questions = [q for q in filtered_questions if q.get(field, '').lower() == criteria[field].lower()]
                else:
                    filtered_questions = [q for q in filtered_questions if q.get(field) == criteria[field]]
                after_field_count = len(filtered_questions)
                
                step_desc = f"{q_type.upper()} - Filter by {field}={criteria[field]}"
                report.add_step(step_desc, before_field_count, after_field_count)
        
        print(f"   Available {q_type} questions: {len(filtered_questions)}")
        
        if len(filtered_questions) < count:
            warning = f"Not enough {q_type} questions available. Required: {count}, Available: {len(filtered_questions)}"
            report.add_warning(warning)
            print(f"   {warning}")
            continue
        
        # If we have max_marks constraint, try to distribute marks evenly
        if max_marks:
            remaining_types = len([t for t in question_types_breakdown.keys() 
                                if t not in [q['question_type'] for q in all_selected_questions]])
            remaining_marks = max_marks - total_marks_used
            remaining_questions = sum(question_types_breakdown.values()) - total_questions
            
            if remaining_questions > 0:
                target_marks_for_type = remaining_marks * count // remaining_questions
                
                # Try to find questions that fit the marks constraint
                selected = find_questions_for_marks(filtered_questions, count, target_marks_for_type)
            else:
                selected = random.sample(filtered_questions, count)
        else:
            # No marks constraint, just pick random questions
            selected = random.sample(filtered_questions, count)
        
        if selected:
            all_selected_questions.extend(selected)
            total_questions += len(selected)
            selected_marks = sum([q.get('positive_marks', 0) for q in selected])
            total_marks_used += selected_marks
            
            print(f"   Selected {len(selected)} {q_type} questions ({selected_marks} marks)")
    
    if not all_selected_questions:
        report.add_warning("No questions could be selected for any question type")
        print("No questions could be selected for any question type")
        return "", report
    
    # Check for marks mismatch in multi-type exam
    if max_marks and total_marks_used != max_marks:
        warning = f"Total marks mismatch in multi-type exam. Target: {max_marks}, Actual: {total_marks_used}"
        report.add_warning(warning)
    
    report.set_final_count(total_questions)
    print(f"\nFinal selection: {total_questions} questions, {total_marks_used} marks")
    
    # Generate the paper
    paper = generate_multi_type_paper_content_with_report(all_selected_questions, criteria, question_types_breakdown, report)
    
    # Store batch exam if batch name is provided
    if criteria.get('batch_name'):
        exam_id = store_batch_exam(criteria, all_selected_questions)
        if exam_id:
            paper = f"Batch Exam ID: {exam_id}\n" + paper
    
    return paper, report