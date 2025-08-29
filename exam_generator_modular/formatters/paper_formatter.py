# formatters/paper_formatter.py
from typing import Dict, List
from database.question_repository import fetch_question_details
from models.filtering_report import FilteringReport

def format_question(q_type: str, detail: Dict, marks: int, is_sub: bool = False) -> str:
    """Format individual questions with proper option labeling"""
    prefix = "Sub-question: " if is_sub else ""
    
    if q_type == 'mcq':
        try:
            options = detail.get('options', [])
            question_text = detail.get('question_text', '')
            
            # Format with a, b, c, d labels
            formatted_options = []
            option_labels = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']  # Extended for more options
            
            for i, option in enumerate(options):
                if i < len(option_labels):
                    formatted_options.append(f"{option_labels[i]}) {option}")
                else:
                    formatted_options.append(f"{i+1}) {option}")  # Fallback to numbers
            
            return f"{prefix}MCQ: {question_text}\n" + "\n".join(formatted_options)
        except Exception as e:
            return f"{prefix}MCQ: {detail.get('question_text', '')}\n[Options formatting error: {e}]"
    
    elif q_type == 'msq':
        try:
            options = detail.get('options', [])
            question_text = detail.get('question_text', '')
            
            # Format with a, b, c, d labels (same as MCQ but with multiple select instruction)
            formatted_options = []
            option_labels = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
            
            for i, option in enumerate(options):
                if i < len(option_labels):
                    formatted_options.append(f"{option_labels[i]}) {option}")
                else:
                    formatted_options.append(f"{i+1}) {option}")
            
            return f"{prefix}MSQ (Multiple Select): {question_text}\n(Select all correct options)\n" + "\n".join(formatted_options)
        except Exception as e:
            return f"{prefix}MSQ: {detail.get('question_text', '')}\n[Options formatting error: {e}]"
    
    elif q_type == 'tf':
        # Add True/False options
        statement = detail.get('statement', '')
        return f"{prefix}True/False: {statement}\na) True\nb) False"
    
    elif q_type == 'match':
        try:
            left_items = detail.get('left_items', [])
            right_items = detail.get('right_items', [])
            
            # Format left items with a, b, c, d...
            left_labels = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
            formatted_left = []
            for i, item in enumerate(left_items):
                if i < len(left_labels):
                    formatted_left.append(f"{left_labels[i]}) {item}")
                else:
                    formatted_left.append(f"{chr(97+i)}) {item}")  # Continue with alphabet
            
            # Format right items with 1, 2, 3, 4...
            formatted_right = []
            for i, item in enumerate(right_items):
                formatted_right.append(f"{i+1}) {item}")
            
            # Create side-by-side columns
            max_items = max(len(formatted_left), len(formatted_right))
            
            # Pad shorter list with empty strings
            while len(formatted_left) < max_items:
                formatted_left.append("")
            while len(formatted_right) < max_items:
                formatted_right.append("")
            
            # Calculate column width for alignment
            left_width = max(len(item) for item in formatted_left) if formatted_left else 0
            left_width = max(left_width, len("Column A"))
            
            # Create header
            header = f"{'Column A':<{left_width + 5}} Column B"
            separator = f"{'-' * (left_width + 5)} {'-' * 10}"
            
            # Create rows
            rows = []
            for left, right in zip(formatted_left, formatted_right):
                rows.append(f"{left:<{left_width + 5}} {right}")
            
            columns_display = "\n".join([header, separator] + rows)
            
            return f"{prefix}Match the following:\n{columns_display}\n\nMatch each item in Column A with the correct item in Column B."
            
        except Exception as e:
            return f"{prefix}Match: Matching question\n[Matching items formatting error: {e}]"
    
    elif q_type == 'descriptive':
        question_text = detail.get('question_text', '')
        min_words = detail.get('min_words', 'N/A')
        max_words = detail.get('max_words', 'N/A')
        return f"{prefix}Descriptive: {question_text}\n(Min: {min_words} words, Max: {max_words} words)"
    
    elif q_type == 'numerical':
        question_text = detail.get('question_text', '')
        return f"{prefix}Numerical: {question_text}"
    
    elif q_type == 'fill':
        question_text = detail.get('question_text', '')
        return f"{prefix}Fill in the blank: {question_text}"
    
    elif q_type == 'comprehension':
        # Handle comprehension questions with passage
        passage = detail.get('passage', '')
        sub_question_ids = detail.get('sub_question_ids', [])
        
        formatted_question = f"{prefix}Comprehension: "
        if passage:
            formatted_question += f"Read the following passage and answer the questions:\n\n{passage}\n\n"
            
            # If there are sub-questions, fetch and format them
            if sub_question_ids:
                formatted_question += "Questions:\n"
                for i, sub_id in enumerate(sub_question_ids, 1):
                    # This would require additional logic to fetch sub-questions
                    # For now, just indicate their presence
                    formatted_question += f"{i}. [Sub-question {sub_id}]\n"
        else:
            formatted_question += "[Passage not found]"
            
        return formatted_question
    
    elif q_type == 'code':
        # Handle coding questions
        prompt = detail.get('prompt', '')
        title = detail.get('title', '')
        description = detail.get('description', '')
        sample_input = detail.get('sample_input', '')
        sample_output = detail.get('sample_output', '')
        
        formatted_question = f"{prefix}Coding Problem"
        if title:
            formatted_question += f": {title}"
        formatted_question += "\n"
        
        if description:
            formatted_question += f"Description: {description}\n"
        
        formatted_question += f"Problem: {prompt}\n"
        
        if sample_input and sample_output:
            formatted_question += f"\nSample Input:\n{sample_input}\n"
            formatted_question += f"Sample Output:\n{sample_output}"
            
        return formatted_question
    
    else:
        return f"{prefix}{q_type.upper()}: {detail.get('question_text', detail.get('statement', 'Question text not available'))}"

def generate_paper_content_with_report(selected_questions: List[Dict], criteria: Dict, report: FilteringReport) -> str:
    """Generate the formatted exam paper for single question type with filtering report"""
    paper = report.generate_report()
    
    paper += "\nExam Paper\n"
    paper += "=" * 50 + "\n"
    paper += f"Subject: {criteria.get('subject', 'Various')}\n"
    paper += f"Chapter: {criteria.get('chapter', 'Various')}\n"
    paper += f"Difficulty: {criteria.get('difficulty', 'Mixed')}\n"
    paper += f"Bloom Level: {criteria.get('bloom_level', 'Mixed')}\n"
    paper += f"Total Questions: {len(selected_questions)}\n"
    paper += f"Maximum Marks: {sum([q.get('positive_marks', 0) for q in selected_questions])}\n\n"
    
    for idx, question in enumerate(selected_questions, 1):
        q_id = question['id']
        q_type = question['question_type']
        marks = question.get('positive_marks', 1)
        
        # Fetch detailed question data
        detail = fetch_question_details(q_id, q_type)
        
        if detail:
            paper += f"Question {idx} ({marks} marks):\n"
            paper += format_question(q_type, detail, marks) + "\n\n"
        else:
            paper += f"Question {idx} ({marks} marks): [Question details not found for ID {q_id}]\n\n"
    
    return paper

def generate_multi_type_paper_content_with_report(selected_questions: List[Dict], criteria: Dict, question_types_breakdown: Dict, report: FilteringReport) -> str:
    """Generate the formatted exam paper for multiple question types with filtering report"""
    paper = report.generate_report()
    
    paper += "\nExam Paper\n"
    paper += "=" * 50 + "\n"
    paper += f"Subject: {criteria.get('subject', 'Various')}\n"
    paper += f"Chapter: {criteria.get('chapter', 'Various')}\n"
    paper += f"Difficulty: {criteria.get('difficulty', 'Mixed')}\n"
    paper += f"Bloom Level: {criteria.get('bloom_level', 'Mixed')}\n"
    
    # Show breakdown of question types
    paper += f"Question Types: "
    breakdown_str = ", ".join([f"{count} {q_type.upper()}" for q_type, count in question_types_breakdown.items()])
    paper += breakdown_str + "\n"
    
    paper += f"Total Questions: {len(selected_questions)}\n"
    paper += f"Maximum Marks: {sum([q.get('positive_marks', 0) for q in selected_questions])}\n\n"
    
    # Group questions by type for organized presentation
    question_counter = 1
    
    for q_type, expected_count in question_types_breakdown.items():
        type_questions = [q for q in selected_questions if q.get('question_type') == q_type]
        
        if type_questions:
            paper += f"Section: {q_type.upper()} Questions\n"
            paper += "-" * 30 + "\n"
            
            for question in type_questions:
                q_id = question['id']
                marks = question.get('positive_marks', 1)
                
                # Fetch detailed question data
                detail = fetch_question_details(q_id, q_type)
                
                if detail:
                    paper += f"Question {question_counter} ({marks} marks):\n"
                    paper += format_question(q_type, detail, marks) + "\n\n"
                else:
                    paper += f"Question {question_counter} ({marks} marks): [Question details not found for ID {q_id}]\n\n"
                
                question_counter += 1
            
            paper += "\n"
    
    return paper