# parsers/prompt_parser.py
import re
import torch
from typing import Optional, Dict, Any
from config import get_tokenizer, get_model

def parse_multiple_question_types(prompt: str) -> Dict[str, int]:
    """Parse prompts with multiple question types and their counts"""
    question_types_breakdown = {}
    
    # More precise patterns to avoid overlapping matches
    multi_type_patterns = [
        # Pattern: "2 mcqs, 2 msqs, 1 true false" - most specific first
        r'(\d+)\s+(mcqs?|msqs?|multiple\s*choice|multiple\s*select|true[\s/-]*false|tf|fill[\s-]*in[\s-]*the[\s-]*blanks?|fill[\s-]*ups?|descriptive|numerical|match(?:ing)?(?:\s+the\s+following)?|comprehension)(?:\s*questions?)?(?:\s*[,;]|\s+and\s+|\s*$)',
    ]
    
    # Question type mappings for normalization
    type_mappings = {
        'mcq': 'mcq', 'mcqs': 'mcq', 'multiple choice': 'mcq', 'multiple-choice': 'mcq',
        'msq': 'msq', 'msqs': 'msq', 'multiple select': 'msq', 'multiple-select': 'msq',
        'true false': 'tf', 'true/false': 'tf', 'true-false': 'tf', 'tf': 'tf',
        'fill in the blanks': 'fill', 'fill in the blank': 'fill', 'fill-in-the-blanks': 'fill',
        'fill-in-the-blank': 'fill', 'fill ups': 'fill', 'fill up': 'fill', 'fillups': 'fill',
        'descriptive': 'descriptive', 'essay': 'descriptive',
        'numerical': 'numerical', 'numeric': 'numerical',
        'match': 'match', 'matching': 'match', 'match the following': 'match',
        'comprehension': 'comprehension'
    }
    
    # Clean the prompt and find matches
    cleaned_prompt = prompt.lower().strip()
    
    # Use finditer to get non-overlapping matches
    pattern = multi_type_patterns[0]
    matches = list(re.finditer(pattern, cleaned_prompt, re.IGNORECASE))
    
    print(f"Debug: Found {len(matches)} matches in: '{cleaned_prompt}'")
    
    for match in matches:
        count_str = match.group(1)
        q_type_str = match.group(2)
        
        print(f"Debug: Match found - '{count_str}' '{q_type_str}'")
        
        try:
            count = int(count_str)
            normalized_type = type_mappings.get(q_type_str.lower().strip(), q_type_str.lower().strip())
            
            # Only add if not already present (avoid duplicates)
            if normalized_type not in question_types_breakdown:
                question_types_breakdown[normalized_type] = count
                print(f"Added: {normalized_type} = {count}")
            else:
                # If duplicate, add to existing count
                question_types_breakdown[normalized_type] += count
                print(f"Updated: {normalized_type} = {question_types_breakdown[normalized_type]}")
                
        except ValueError:
            print(f"Could not parse count: '{count_str}'")
            continue
    
    # Fallback: try simpler pattern if no matches found
    if not question_types_breakdown:
        print("Trying fallback patterns...")
        
        # Alternative patterns for different formats
        fallback_patterns = [
            r'with\s+(\d+)\s+(mcqs?|msqs?|true[\s/-]*false|tf|fill[\s-]*ups?|descriptive|numerical|match(?:ing)?|comprehension)',
            r'(\d+)\s+(mcqs?|msqs?|true[\s/-]*false|tf|fill[\s-]*ups?|descriptive|numerical|match(?:ing)?|comprehension)(?:\s+questions?)?',
        ]
        
        for fallback_pattern in fallback_patterns:
            matches = re.findall(fallback_pattern, cleaned_prompt, re.IGNORECASE)
            for count_str, q_type_str in matches:
                try:
                    count = int(count_str)
                    normalized_type = type_mappings.get(q_type_str.lower().strip(), q_type_str.lower().strip())
                    
                    if normalized_type not in question_types_breakdown:
                        question_types_breakdown[normalized_type] = count
                        print(f"Fallback added: {normalized_type} = {count}")
                        
                except ValueError:
                    continue
    
    print(f"Final breakdown: {question_types_breakdown}")
    return question_types_breakdown if question_types_breakdown else {}

def parse_prompt_with_hybrid(user_prompt: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced prompt parser with comprehensive extraction and LLM fallback"""
    criteria: Dict[str, Optional[int | str | Dict[str, int]]] = {
        "num_questions": None, "max_marks": None, "subject": None,
        "chapter": None, "question_type": None, "difficulty": None,
        "positive_marks": None, "bloom_level": None, "question_types_breakdown": None,
        "batch_name": None, "organization_id": organization_id
    }

    normalized_prompt = user_prompt.lower().strip()
    
    # NEW: Parse multiple question types with counts
    question_types_breakdown = parse_multiple_question_types(normalized_prompt)
    if question_types_breakdown:
        criteria["question_types_breakdown"] = question_types_breakdown
        criteria["num_questions"] = sum(question_types_breakdown.values())
        print(f"Detected multiple question types: {question_types_breakdown}")
        print(f"Total questions: {criteria['num_questions']}")
    
    # Enhanced regex patterns with comprehensive question type detection
    patterns = {
        "batch_name": [
            r"batch\s*[:=]\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"(?:for|in)\s*batch\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"batch\s+name\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"batch\s+([A-Za-z0-9\s\-_]+?)(?:\s+with\s+\d+|\s*[,\n]|$)"  # Stop at "with" keyword
        ],
        "num_questions": [
            r"(?:generate|create|make)?\s*(?:an?\s*)?(?:exam\s*paper\s*with\s*)?(\d+)\s*(?:questions?)",
            r"(\d+)\s*questions?\s*(?:exam|paper|test)?",
            r"questions?\s*[:=]\s*(\d+)",
            r"total\s*questions?\s*[:=]?\s*(\d+)"
        ],
        "max_marks": [
            r"maximum\s*(\d+)\s*(?:positive\s*)?marks?",
            r"max\s*marks?\s*[:=]?\s*(\d+)",
            r"total\s*marks?\s*[:=]?\s*(\d+)",
            r"(\d+)\s*(?:positive\s*)?marks?\s*(?:maximum|max|total)",
            r"marks?\s*[:=]\s*(\d+)"
        ],
        "positive_marks": [
            r"(\d+)\s*positive\s*marks?",
            r"positive\s*marks?\s*[:=]?\s*(\d+)",
            r"marks?\s*per\s*question\s*[:=]?\s*(\d+)"
        ],
        "subject": [
            r"subject\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"(?:in|for|on)\s*subject\s*([^,\n]+?)(?:\s*[,\n]|$)"
        ],
        "chapter": [
            r"chapter\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"(?:from|on|in)\s*chapter\s*([^,\n]+?)(?:\s*[,\n]|$)"
        ],
        "difficulty": [
            r"difficulty\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"difficulty\s+([^,\n]+?)(?:\s*[,\n]|$)",
            r"(?:easy|medium|hard|difficult|simple|basic|beginner|intermediate|moderate|average|advanced|challenging|complex)(?:\s*(?:difficulty|level|questions?))?",
        ],
        "bloom_level": [
            r"bloom\s*level\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"bloom\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"(?:remember|understand|apply|analyze|analyse|evaluate|create|recall|memorize|recognize|identify|comprehend|explain|describe|interpret|use|implement|solve|demonstrate|examine|compare|contrast|assess|judge|critique|justify|design|develop|compose|construct)(?:\s*(?:level|questions?))?",
            r"cognitive\s*level\s*[:=]?\s*([^,\n]+?)(?:\s*[,\n]|$)"
        ],
        "question_type": [
            # First check for explicit type declarations
            r"question\s*type\s*[:=]\s*([^,\n]+?)(?:\s*[,\n]|$)",
            r"type\s*[:=]\s*([^,\n]+?)(?:\s*[,\n]|$)",
            
            # Then check for specific question types without numbers
            r"\b(?:mcq|msq|multiple[\s-]choice|multiple[\s-]select|descriptive|numerical|true[\s-]false|tf|fill[\s-]in[\s-]the[\s-]blanks?|match(?:ing)?|comprehension)\b(?:\s*questions?)?",
            
            # Finally check for questions with type
            r"questions?\s+(?:of\s+)?type\s+([^,\n]+?)(?:\s*[,\n]|$)"
        ]
    }

    # Update the pattern application order
    field_order = ['batch_name', 'question_type', 'num_questions', 'max_marks', 'subject', 'chapter', 'difficulty', 'bloom_level', 'positive_marks']

    # Apply regex patterns in specific order
    for key in field_order:
        if key not in patterns:
            continue
        pattern_list = patterns[key]
        for pattern in pattern_list:
            match = re.search(pattern, normalized_prompt, re.IGNORECASE)
            if match:
                if key in ["num_questions", "max_marks", "positive_marks"]:
                    try:
                        criteria[key] = int(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
                else:
                    try:
                        if match.groups():
                            extracted_value = match.group(1).strip()
                        else:
                            extracted_value = match.group(0).strip()
                        
                        extracted_value = re.sub(r'[,\.\s]+$', '', extracted_value)
                        if extracted_value:
                            criteria[key] = extracted_value
                            break
                    except IndexError:
                        continue

    # Comprehensive question type keyword detection with priority
    question_type_keywords = {
        # Fill in the blanks - all possible variations
        'fill': [
            'fill in the blanks', 'fill in the blank', 'fill-in-the-blanks', 'fill-in-the-blank',
            'fill in blanks', 'fill in blank', 'fill-in-blanks', 'fill-in-blank',
            'fill ups', 'fill up', 'fill-ups', 'fill-up', 'fillups', 'fillup',
            'blanks', 'blank questions', 'blank question', 'filling blanks',
            'complete the blanks', 'complete the blank', 'completion type',
            'cloze test', 'cloze questions', 'gap filling', 'gap fill'
        ],
        # Multiple Choice Questions
        'mcq': [
            'mcq', 'mcqs', 'multiple choice', 'multiple-choice', 'multi choice',
            'multi-choice', 'choice questions', 'choice question', 'objective questions',
            'objective question', 'single choice', 'single-choice'
        ],
        # Multiple Select Questions
        'msq': [
            'msq', 'msqs', 'multiple select', 'multiple-select', 'multi select',
            'multi-select', 'multiple selection', 'multi selection', 'checkbox questions',
            'select multiple', 'multiple answer', 'multiple answers'
        ],
        # True/False
        'tf': [
            'true false', 'true/false', 'tf', 't/f', 'true or false',
            'true-false', 't-f', 'boolean questions', 'yes no', 'yes/no',
            'binary questions', 'dichotomous questions'
        ],
        # Descriptive/Essay
        'descriptive': [
            'descriptive', 'essay', 'long answer', 'subjective', 'written',
            'narrative', 'explanation', 'elaborate', 'discuss', 'explain',
            'describe', 'paragraph', 'composition', 'free response'
        ],
        # Numerical
        'numerical': [
            'numerical', 'numeric', 'calculation', 'mathematical', 'math',
            'compute', 'calculate', 'solve', 'problem solving', 'quantitative',
            'arithmetic', 'algebraic', 'formula based'
        ],
        # Matching
        'match': [
            'match', 'matching', 'match the following', 'match columns',
            'pair', 'pairing', 'correspondence', 'associate', 'connect',
            'link', 'relate', 'column matching'
        ],
        # Comprehension
        'comprehension': [
            'comprehension', 'passage', 'reading comprehension', 'reading',
            'paragraph', 'text based', 'passage based', 'extract',
            'interpretation', 'analysis'
        ]
    }

    # Check for question type in the prompt (case-insensitive) with priority
    for q_type, keywords in question_type_keywords.items():
        for keyword in keywords:
            if keyword in normalized_prompt:
                criteria["question_type"] = q_type
                break
        if criteria["question_type"] is not None:
            break

    # Enhanced common value mappings
    value_mappings = {
        'difficulty': {
            'easy': 'easy', 'simple': 'easy', 'basic': 'easy', 'beginner': 'easy',
            'elementary': 'easy', 'low': 'easy',
            'medium': 'medium', 'intermediate': 'medium', 'moderate': 'medium', 
            'average': 'medium', 'normal': 'medium', 'mid': 'medium',
            'hard': 'hard', 'difficult': 'hard', 'complex': 'hard', 
            'advanced': 'hard', 'challenging': 'hard', 'tough': 'hard', 'high': 'hard'
        },
        'bloom_level': {
            'remember': 'remember', 'recall': 'remember', 'memorize': 'remember', 
            'recognize': 'remember', 'identify': 'remember', 'list': 'remember',
            'understand': 'understand', 'comprehend': 'understand', 'explain': 'understand', 
            'describe': 'understand', 'interpret': 'understand', 'summarize': 'understand',
            'apply': 'apply', 'use': 'apply', 'implement': 'apply', 'solve': 'apply', 
            'demonstrate': 'apply', 'execute': 'apply',
            'analyze': 'analyze', 'analyse': 'analyze', 'examine': 'analyze', 
            'compare': 'analyze', 'contrast': 'analyze', 'differentiate': 'analyze',
            'evaluate': 'evaluate', 'assess': 'evaluate', 'judge': 'evaluate', 
            'critique': 'evaluate', 'justify': 'evaluate', 'appraise': 'evaluate',
            'create': 'create', 'design': 'create', 'develop': 'create', 
            'compose': 'create', 'construct': 'create', 'formulate': 'create'
        },
        'question_type': {
            # Fill variations
            'fill': 'fill', 'fill in the blank': 'fill', 'fill in the blanks': 'fill',
            'fill-in-the-blank': 'fill', 'fill-in-the-blanks': 'fill', 'fill up': 'fill',
            'fill ups': 'fill', 'fill-up': 'fill', 'fill-ups': 'fill', 'blanks': 'fill',
            'blank questions': 'fill', 'blank question': 'fill', 'completion': 'fill',
            'cloze': 'fill', 'gap fill': 'fill', 'gap filling': 'fill',
            
            # MCQ variations
            'mcq': 'mcq', 'mcqs': 'mcq', 'multiple choice': 'mcq', 'multiple-choice': 'mcq',
            'multi choice': 'mcq', 'multi-choice': 'mcq', 'choice questions': 'mcq',
            'objective': 'mcq', 'single choice': 'mcq',
            
            # MSQ variations
            'msq': 'msq', 'msqs': 'msq', 'multiple select': 'msq', 'multiple-select': 'msq',
            'multi select': 'msq', 'multiple selection': 'msq', 'checkbox': 'msq',
            'select multiple': 'msq', 'multiple answer': 'msq',
            
            # True/False variations
            'tf': 'tf', 'true false': 'tf', 'true/false': 'tf', 't/f': 'tf',
            'true or false': 'tf', 'true-false': 'tf', 'boolean': 'tf', 'yes no': 'tf',
            'binary': 'tf', 'dichotomous': 'tf',
            
            # Descriptive variations
            'descriptive': 'descriptive', 'essay': 'descriptive', 'long answer': 'descriptive',
            'subjective': 'descriptive', 'written': 'descriptive', 'narrative': 'descriptive',
            'explanation': 'descriptive', 'paragraph': 'descriptive', 'composition': 'descriptive',
            
            # Numerical variations
            'numerical': 'numerical', 'numeric': 'numerical', 'calculation': 'numerical',
            'mathematical': 'numerical', 'math': 'numerical', 'compute': 'numerical',
            'calculate': 'numerical', 'quantitative': 'numerical', 'arithmetic': 'numerical',
            
            # Match variations
            'match': 'match', 'matching': 'match', 'match the following': 'match',
            'match columns': 'match', 'pair': 'match', 'pairing': 'match',
            'correspondence': 'match', 'associate': 'match', 'connect': 'match',
            
            # Comprehension variations
            'comprehension': 'comprehension', 'passage': 'comprehension', 'reading': 'comprehension',
            'reading comprehension': 'comprehension', 'text based': 'comprehension',
            'passage based': 'comprehension', 'interpretation': 'comprehension'
        }
    }

    # Apply value mappings
    for field, mappings in value_mappings.items():
        if criteria[field] is not None:
            normalized_value = str(criteria[field]).lower().strip()
            if normalized_value in mappings:
                criteria[field] = mappings[normalized_value]

    # Clean up batch name to remove exam-related keywords
    if criteria.get('batch_name') and isinstance(criteria['batch_name'], str):
        batch_name = criteria['batch_name'].strip()
        # Remove common exam-related suffixes
        cleanup_patterns = [
            r'\s+with\s+\d+.*$',  # Remove "with 3 mcqs" etc
            r'\s+exam.*$',        # Remove "exam paper" etc
            r'\s+paper.*$',       # Remove "paper" etc
            r'\s+questions?.*$'   # Remove "questions" etc
        ]
        for pattern in cleanup_patterns:
            batch_name = re.sub(pattern, '', batch_name, flags=re.IGNORECASE)
        criteria['batch_name'] = batch_name.strip()

    # LLM fallback for missing critical fields using DialoGPT-medium
    missing_fields = [k for k, v in criteria.items() if v is None and k in ['num_questions', 'max_marks', 'subject', 'chapter', 'question_type']]
    
    tokenizer = get_tokenizer()
    model = get_model()
    
    if missing_fields and tokenizer is not None and model is not None:
        try:
            print(f"Using DialoGPT-medium fallback for missing fields: {missing_fields}")
            
            extraction_prompt = f"""Extract information from this exam request: "{user_prompt}"

STRICT RULES:
- Only extract information that is EXPLICITLY mentioned in the prompt
- For batch_name: extract only the actual batch identifier, not the full exam description
- If a field is not clearly specified, return "NULL" for that field
- Do not make assumptions or use default values
- Convert spelled numbers to digits (e.g., 'two' -> 2)
- If user does spelling mistake then take it as the nearest correct word which is related. 

Extract these fields:
batch_name: [batch identifier only, like "CS101" or "Data Science Batch A", or NULL]
questions: [number of questions or NULL]
marks: [total marks or NULL] 
subject: [subject name or NULL]
chapter: [chapter name or NULL]
type: [one of: mcq, msq, fill, descriptive, numerical, tf, match, comprehension, or NULL]
difficulty: [one of: easy, medium, hard, or NULL]
bloom: [one of: remember, understand, apply, analyze, evaluate, create, or NULL]

Examples:
Input: "Generate 5 MCQ questions for Math"
Output: questions: 5, marks: NULL, subject: Math, chapter: NULL, type: mcq, difficulty: NULL, bloom: NULL

Input: "Create fill in blanks with 10 marks"  
Output: questions: NULL, marks: 10, subject: NULL, chapter: NULL, type: fill, difficulty: NULL, bloom: NULL

Now extract from: "{user_prompt}"
Output:"""

            inputs = tokenizer(extraction_prompt, return_tensors='pt', padding=True, truncation=True, max_length=512)
            
            with torch.no_grad():
                output = model.generate(
                    inputs['input_ids'],
                    attention_mask=inputs.get('attention_mask'),
                    max_new_tokens=150,
                    pad_token_id=tokenizer.eos_token_id,
                    do_sample=False,
                    num_beams=2,
                    temperature=0.1
                )
            
            response = tokenizer.decode(output[0], skip_special_tokens=True)
            response = response.replace(extraction_prompt, '').strip()
            
            # Parse LLM response with improved null handling
            llm_patterns = {
                'batch_name': r'batch_name\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)',
                'num_questions': r'questions?\s*[:=]\s*(\d+|NULL)',
                'max_marks': r'marks?\s*[:=]\s*(\d+|NULL)',
                'subject': r'subject\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)',
                'chapter': r'chapter\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)',
                'question_type': r'type\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)',
                'difficulty': r'difficulty\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)',
                'bloom_level': r'bloom\s*[:=]\s*([^\n,]+?)(?:\s*[,\n]|$)'
            }
            
            for field, pattern in llm_patterns.items():
                if criteria[field] is None:
                    match = re.search(pattern, response, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        
                        # Skip if value is NULL or similar indicators
                        if value.upper() in ['NULL', 'NONE', 'N/A', 'NOT SPECIFIED', '']:
                            continue
                            
                        if field in ['num_questions', 'max_marks']:
                            try:
                                criteria[field] = int(value)
                            except ValueError:
                                continue
                        else:
                            # Apply value mappings to LLM extracted values
                            if field in value_mappings:
                                normalized_value = value.lower().strip()
                                if normalized_value in value_mappings[field]:
                                    criteria[field] = value_mappings[field][normalized_value]
                                else:
                                    # Only set if it's a valid value, otherwise keep as None
                                    if normalized_value not in ['null', 'none', 'not specified', '']:
                                        criteria[field] = value
                            else:
                                if value.lower() not in ['null', 'none', 'not specified', '']:
                                    criteria[field] = value
            
            print(f"LLM extracted: {[(k, v) for k, v in criteria.items() if k in missing_fields and v is not None]}")
                
        except Exception as e:
            print(f"LLM fallback failed: {e}")

    # Final fallback: try to extract basic numbers from prompt
    if criteria['num_questions'] is None or criteria['max_marks'] is None:
        numbers = re.findall(r'\b(\d+)\b', user_prompt)
        if len(numbers) >= 2:
            if criteria['num_questions'] is None:
                criteria['num_questions'] = int(numbers[0])
                print(f"Inferred num_questions: {numbers[0]}")
            if criteria['max_marks'] is None:
                criteria['max_marks'] = int(numbers[1])
                print(f"Inferred max_marks: {numbers[1]}")

    # Validate required fields
    if criteria['num_questions'] is None or criteria['max_marks'] is None:
        raise ValueError("Number of questions and maximum marks must be specified in the prompt.")

    return criteria