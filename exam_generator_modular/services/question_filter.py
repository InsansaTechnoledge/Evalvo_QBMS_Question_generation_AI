# services/question_filter.py
import random
from typing import List, Dict, Tuple, Optional
from functools import lru_cache
from models.filtering_report import FilteringReport

def filter_questions_with_report(questions: List[Dict], criteria: Dict) -> Tuple[List[Dict], FilteringReport]:
    """Filter questions based on criteria with detailed reporting"""
    report = FilteringReport()
    filtered = questions
    report.set_initial_count(len(questions))
    
    filter_fields = ['subject', 'chapter', 'question_type', 'difficulty', 'bloom_level', 'positive_marks']
    
    print(f"Filtering {len(filtered)} questions with criteria:")
    
    for field in filter_fields:
        if criteria.get(field) is not None:
            before_count = len(filtered)
            
            if isinstance(criteria[field], str):
                # Case-insensitive partial match for strings
                filtered = [q for q in filtered if criteria[field].lower() in str(q.get(field, '')).lower()]
            else:
                # Exact match for numbers
                filtered = [q for q in filtered if q.get(field) == criteria[field]]
            
            after_count = len(filtered)
            step_desc = f"Filter by {field}={criteria[field]}"
            report.add_step(step_desc, before_count, after_count)
            print(f"   {field}={criteria[field]}: {before_count} → {after_count} questions")
    
    return filtered, report

def suggest_relaxed_criteria_with_report(all_questions: List[Dict], criteria: Dict) -> List[str]:
    """Suggest relaxed criteria when not enough questions are found"""
    suggestions = []
    filter_fields = ['subject', 'chapter', 'question_type', 'difficulty', 'bloom_level', 'positive_marks']
    
    for field in filter_fields:
        if criteria.get(field) is not None:
            # Try without this field
            temp_filtered = all_questions
            for other_field in filter_fields:
                if other_field != field and criteria.get(other_field) is not None:
                    if isinstance(criteria[other_field], str):
                        temp_filtered = [q for q in temp_filtered if q.get(other_field, '').lower() == criteria[other_field].lower()]
                    else:
                        temp_filtered = [q for q in temp_filtered if q.get(other_field) == criteria[other_field]]
            
            temp_count = len(temp_filtered)
            suggestion = f"Remove '{field}={criteria[field]}' constraint: {temp_count} questions available"
            suggestions.append(suggestion)
    
    return suggestions

def find_balanced_subset_with_report(filtered_questions: List[Dict], criteria: Dict) -> Tuple[List[Dict], List[str]]:
    """Find subset that matches total marks exactly with warnings"""
    warnings = []
    num_questions = criteria['num_questions']
    max_marks = criteria.get('max_marks')
    
    if len(filtered_questions) < num_questions:
        return [], warnings
    
    # If no marks constraint, just return random selection
    if not max_marks:
        return random.sample(filtered_questions, num_questions), warnings
    
    print(f"Finding {num_questions} questions totaling {max_marks} marks")
    
    # Group questions by marks for better selection
    questions_by_marks = {}
    for q in filtered_questions:
        marks = q.get('positive_marks', 1)
        if marks not in questions_by_marks:
            questions_by_marks[marks] = []
        questions_by_marks[marks].append(q)
    
    print(f"Questions grouped by marks: {[(marks, len(qs)) for marks, qs in questions_by_marks.items()]}")
    
    # Try dynamic programming approach for small sets
    if len(filtered_questions) <= 50 and num_questions <= 10:
        result = find_exact_subset_dp(filtered_questions, num_questions, max_marks)
        if result:
            return result, warnings
    
    # Fallback to random sampling with improvement attempts
    best_selection = None
    best_diff = float('inf')
    
    max_tries = min(1000, len(filtered_questions) * 10)
    for _ in range(max_tries):
        sample = random.sample(filtered_questions, num_questions)
        total_marks = sum([q.get('positive_marks', 0) for q in sample])
        diff = abs(total_marks - max_marks)
        
        if diff < best_diff:
            best_diff = diff
            best_selection = sample
            
        if diff == 0:  # Perfect match
            print(f"Found exact match: {num_questions} questions, {max_marks} marks")
            return sample, warnings
    
    if best_selection:
        actual_marks = sum([q.get('positive_marks', 0) for q in best_selection])
        if best_diff > 0:
            warning = f"Cannot find exact match for {max_marks} marks. Using {actual_marks} marks instead of {max_marks} (difference: {best_diff})"
            warnings.append(warning)
            print(f"Warning: {warning}")
        return best_selection, warnings
    
    return [], warnings

def find_exact_subset_dp(questions: List[Dict], num_questions: int, target_marks: int) -> List[Dict]:
    """Dynamic programming approach to find exact subset (for small datasets)"""
    n = len(questions)
    
    # dp[i][j][k] = True if we can select exactly j questions from first i questions with total marks k
    # This is memory intensive, so we only use it for small datasets
    if n > 50 or num_questions > 10 or target_marks > 100:
        return []
    
    try:
        # Use a different approach: recursive with memoization
        from functools import lru_cache
        
        @lru_cache(maxsize=None)
        def dp(idx: int, remaining_questions: int, remaining_marks: int) -> Optional[List[int]]:
            if remaining_questions == 0 and remaining_marks == 0:
                return []
            if idx >= n or remaining_questions <= 0 or remaining_marks < 0:
                return None
            
            # Option 1: Skip current question
            result = dp(idx + 1, remaining_questions, remaining_marks)
            if result is not None:
                return result
            
            # Option 2: Take current question
            current_marks = questions[idx].get('positive_marks', 0)
            result = dp(idx + 1, remaining_questions - 1, remaining_marks - current_marks)
            if result is not None:
                return [idx] + result
            
            return None

        indices = dp(0, num_questions, target_marks)
        if indices is not None:
            return [questions[i] for i in indices]
        else:
            return []
    except Exception as e:
        print(f"Error in dynamic programming subset selection: {e}")
        return []

def find_questions_for_marks(filtered_questions: List[Dict], count: int, target_marks: int) -> List[Dict]:
    """Try to find questions that approximately match target marks"""
    if len(filtered_questions) < count:
        return random.sample(filtered_questions, len(filtered_questions))
    
    # Try multiple combinations to find the best match
    best_diff = float('inf')
    best_selection = None
    
    for _ in range(min(100, len(filtered_questions))):  # Try up to 100 combinations
        sample = random.sample(filtered_questions, count)
        total_marks = sum([q.get('positive_marks', 0) for q in sample])
        diff = abs(total_marks - target_marks)
        
        if diff < best_diff:
            best_diff = diff
            best_selection = sample
            
        if diff == 0:  # Perfect match
            break
    
    return best_selection if best_selection is not None else random.sample(filtered_questions, count)