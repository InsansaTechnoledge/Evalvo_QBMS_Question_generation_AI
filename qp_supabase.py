import json
import re
import random
from functools import lru_cache
from transformers.models.auto.tokenization_auto import AutoTokenizer
from transformers.models.auto.modeling_auto import AutoModelForCausalLM
from typing import Optional, Dict, Any, List, Tuple
import torch
import warnings
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

warnings.filterwarnings("ignore", category=UserWarning, module='transformers')

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Initialize Supabase client
supabase = None
try:
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✅ Supabase client initialized successfully")
    else:
        print("⚠️ Warning: Supabase credentials not found. Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
except Exception as e:
    print(f"❌ Error initializing Supabase client: {e}")

# Load the model and tokenizer for parsing (using DialoGPT-medium)
try:
    tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
    model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
    tokenizer.pad_token = tokenizer.eos_token
    print("✅ DialoGPT-medium loaded successfully for LLM fallback")
except Exception as e:
    print(f"⚠️ Warning: Could not load DialoGPT-medium: {e}")
    tokenizer = None
    model = None

# Add a class to track filtering process
class FilteringReport:
    def __init__(self):
        self.steps = []
        self.warnings = []
        self.suggestions = []
        self.final_count = 0
        self.initial_count = 0
        
    def add_step(self, step_description, before_count, after_count):
        self.steps.append({
            'description': step_description,
            'before': before_count,
            'after': after_count
        })
        
    def add_warning(self, warning_message):
        self.warnings.append(warning_message)
        
    def add_suggestion(self, suggestion):
        self.suggestions.append(suggestion)
        
    def set_initial_count(self, count):
        self.initial_count = count
        
    def set_final_count(self, count):
        self.final_count = count
        
    def generate_report(self):
        report = "\n" + "="*60 + "\n"
        report += "FILTERING PROCESS REPORT\n"
        report += "="*60 + "\n"
        
        report += f"Initial questions in database: {self.initial_count}\n\n"
        
        if self.steps:
            report += "Step-by-step filtering:\n"
            report += "-" * 30 + "\n"
            for step in self.steps:
                report += f"• {step['description']}: {step['before']} → {step['after']} questions\n"
            
            report += f"\nFinal filtered results: {self.final_count} questions\n"
        
        if self.warnings:
            report += "\nWARNINGS:\n"
            report += "-" * 15 + "\n"
            for warning in self.warnings:
                report += f"⚠️  {warning}\n"
        
        if self.suggestions:
            report += "\nSUGGESTIONS:\n"
            report += "-" * 20 + "\n"
            for suggestion in self.suggestions:
                report += f"💡 {suggestion}\n"
        
        report += "\n" + "="*60 + "\n"
        return report

# Cache for database results to improve performance
@lru_cache(maxsize=128)
def fetch_questions_from_supabase(organization_id: Optional[str] = None, subject: Optional[str] = None, 
                                chapter: Optional[str] = None, question_type: Optional[str] = None, 
                                difficulty: Optional[str] = None, bloom_level: Optional[str] = None, 
                                positive_marks: Optional[int] = None) -> tuple:
    """Fetch questions from Supabase with optional filters (cached for performance)"""
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
        
        print(f"🔍 Database query with filters: {', '.join(filters_applied) if filters_applied else 'No filters'}")
        
        response = query.execute()
        questions = response.data
        
        print(f"📊 Found {len(questions)} questions matching criteria")
        return tuple(questions)  # Return tuple for caching
    
    except Exception as e:
        print(f"❌ Error fetching questions: {e}")
        return tuple()

# Cache for question details
@lru_cache(maxsize=256)
def fetch_question_details(question_id: str, question_type: str) -> Dict:
    """Fetch detailed question data based on type (cached for performance)"""
    if not supabase:
        return {}
    
    try:
        table_name = f'question_{question_type}'
        print(f"🔍 Fetching details from table: {table_name} for ID: {question_id}")
        
        response = supabase.table(table_name).select('*').eq('id', question_id).execute()
        
        if response.data:
            details = response.data[0]
            print(f"✅ Found details for {question_type} question: {question_id}")
            return details
        else:
            print(f"⚠️ No details found for {question_type} question: {question_id}")
        return {}
    
    except Exception as e:
        print(f"❌ Error fetching question details for {question_type}: {e}")
        return {}

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
    
    print(f"🔍 Debug: Found {len(matches)} matches in: '{cleaned_prompt}'")
    
    for match in matches:
        count_str = match.group(1)
        q_type_str = match.group(2)
        
        print(f"🔍 Debug: Match found - '{count_str}' '{q_type_str}'")
        
        try:
            count = int(count_str)
            normalized_type = type_mappings.get(q_type_str.lower().strip(), q_type_str.lower().strip())
            
            # Only add if not already present (avoid duplicates)
            if normalized_type not in question_types_breakdown:
                question_types_breakdown[normalized_type] = count
                print(f"✅ Added: {normalized_type} = {count}")
            else:
                # If duplicate, add to existing count
                question_types_breakdown[normalized_type] += count
                print(f"✅ Updated: {normalized_type} = {question_types_breakdown[normalized_type]}")
                
        except ValueError:
            print(f"❌ Could not parse count: '{count_str}'")
            continue
    
    # Fallback: try simpler pattern if no matches found
    if not question_types_breakdown:
        print("🔍 Trying fallback patterns...")
        
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
                        print(f"✅ Fallback added: {normalized_type} = {count}")
                        
                except ValueError:
                    continue
    
    print(f"🎯 Final breakdown: {question_types_breakdown}")
    return question_types_breakdown if question_types_breakdown else {}

def parse_prompt_with_hybrid(user_prompt: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced prompt parser with comprehensive extraction and LLM fallback"""
    criteria: Dict[str, Optional[int | str | Dict[str, int]]] = {
        "num_questions": None, "max_marks": None, "subject": None,
        "chapter": None, "question_type": None, "difficulty": None,
        "positive_marks": None, "bloom_level": None, "question_types_breakdown": None,
        "organization_id": organization_id
    }

    normalized_prompt = user_prompt.lower().strip()
    
    # NEW: Parse multiple question types with counts
    question_types_breakdown = parse_multiple_question_types(normalized_prompt)
    if question_types_breakdown:
        criteria["question_types_breakdown"] = question_types_breakdown
        criteria["num_questions"] = sum(question_types_breakdown.values())
        print(f"📊 Detected multiple question types: {question_types_breakdown}")
        print(f"📊 Total questions: {criteria['num_questions']}")
    
    # Enhanced regex patterns with comprehensive question type detection
    patterns = {
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
    field_order = ['question_type', 'num_questions', 'max_marks', 'subject', 'chapter', 'difficulty', 'bloom_level', 'positive_marks']
    
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

    # LLM fallback for missing critical fields using DialoGPT-medium
    missing_fields = [k for k, v in criteria.items() if v is None and k in ['num_questions', 'max_marks', 'subject', 'chapter', 'question_type']]
    
    if missing_fields and tokenizer is not None and model is not None:
        try:
            print(f"🤖 Using DialoGPT-medium fallback for missing fields: {missing_fields}")
            
            # IMPROVED PROMPT - More explicit about returning null/empty values
            extraction_prompt = f"""Extract information from this exam request: "{user_prompt}"

STRICT RULES:
- Only extract information that is EXPLICITLY mentioned in the prompt
- If a field is not clearly specified, return "NULL" for that field
- Do not make assumptions or use default values
- Convert spelled numbers to digits (e.g., 'two' -> 2)
- If user does spelling mistake then take it as the nearest correct word which is related. 

Extract these fields:
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
            
            print(f"✅ LLM extracted: {[(k, v) for k, v in criteria.items() if k in missing_fields and v is not None]}")
                
        except Exception as e:
            print(f"⚠️ LLM fallback failed: {e}")

    # Final fallback: try to extract basic numbers from prompt
    if criteria['num_questions'] is None or criteria['max_marks'] is None:
        numbers = re.findall(r'\b(\d+)\b', user_prompt)
        if len(numbers) >= 2:
            if criteria['num_questions'] is None:
                criteria['num_questions'] = int(numbers[0])
                print(f"📝 Inferred num_questions: {numbers[0]}")
            if criteria['max_marks'] is None:
                criteria['max_marks'] = int(numbers[1])
                print(f"📝 Inferred max_marks: {numbers[1]}")

    # Validate required fields
    if criteria['num_questions'] is None or criteria['max_marks'] is None:
        raise ValueError("Number of questions and maximum marks must be specified in the prompt.")

    return criteria

def debug_database_content(criteria, organization_id: Optional[str] = None):
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
            print(f"\n❌ Error: {error_msg}")
            
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
        return paper, report
        
    except Exception as e:
        report.add_warning(f"Error generating exam paper: {e}")
        print(f"❌ Error generating exam paper: {e}")
        return "", report

def filter_questions_with_report(questions: List[Dict], criteria: Dict) -> Tuple[List[Dict], FilteringReport]:
    """Filter questions based on criteria with detailed reporting"""
    report = FilteringReport()
    filtered = questions
    report.set_initial_count(len(questions))
    
    filter_fields = ['subject', 'chapter', 'question_type', 'difficulty', 'bloom_level', 'positive_marks']
    
    print(f"🔍 Filtering {len(filtered)} questions with criteria:")
    
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
    
    print(f"🎯 Finding {num_questions} questions totaling {max_marks} marks")
    
    # Group questions by marks for better selection
    questions_by_marks = {}
    for q in filtered_questions:
        marks = q.get('positive_marks', 1)
        if marks not in questions_by_marks:
            questions_by_marks[marks] = []
        questions_by_marks[marks].append(q)
    
    print(f"📊 Questions grouped by marks: {[(marks, len(qs)) for marks, qs in questions_by_marks.items()]}")
    
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
            print(f"✅ Found exact match: {num_questions} questions, {max_marks} marks")
            return sample, warnings
    
    if best_selection:
        actual_marks = sum([q.get('positive_marks', 0) for q in best_selection])
        if best_diff > 0:
            warning = f"Cannot find exact match for {max_marks} marks. Using {actual_marks} marks instead of {max_marks} (difference: {best_diff})"
            warnings.append(warning)
            print(f"⚠️ Warning: {warning}")
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

def generate_multi_type_exam(criteria: Dict, all_questions: List[Dict], organization_id: Optional[str] = None) -> Tuple[str, FilteringReport]:
    """Generate exam with multiple question types from Supabase with detailed reporting"""
    report = FilteringReport()
    question_types_breakdown = criteria["question_types_breakdown"]
    max_marks = criteria.get("max_marks")
    
    all_selected_questions = []
    total_questions = 0
    total_marks_used = 0
    
    report.set_initial_count(len(all_questions))
    
    print(f"\n🎯 Generating multi-type exam:")
    print(f"   Question breakdown: {question_types_breakdown}")
    print(f"   Target marks: {max_marks}")
    
    for q_type, count in question_types_breakdown.items():
        print(f"\n📝 Processing {q_type}: {count} questions")
        
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
            print(f"   ❌ {warning}")
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
            
            print(f"   ✅ Selected {len(selected)} {q_type} questions ({selected_marks} marks)")
    
    if not all_selected_questions:
        report.add_warning("No questions could be selected for any question type")
        print("❌ No questions could be selected for any question type")
        return "", report
    
    # Check for marks mismatch in multi-type exam
    if max_marks and total_marks_used != max_marks:
        warning = f"Total marks mismatch in multi-type exam. Target: {max_marks}, Actual: {total_marks_used}"
        report.add_warning(warning)
    
    report.set_final_count(total_questions)
    print(f"\n📊 Final selection: {total_questions} questions, {total_marks_used} marks")
    
    # Generate the paper
    paper = generate_multi_type_paper_content_with_report(all_selected_questions, criteria, question_types_breakdown, report)
    return paper, report

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


def test_supabase_connection():
    """Test Supabase database connection"""
    print("\nTesting Supabase Connection:")
    print("=" * 50)
    
    if not supabase:
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

# Main function
def main():
    print("🚀 Enhanced Exam Generator with Supabase Integration")
    print("=" * 70)
    
    # Test Supabase connection first
    if not test_supabase_connection():
        print("\n💡 Please set up your Supabase credentials:")
        print("   - Create a .env file with SUPABASE_URL and SUPABASE_ANON_KEY")
        print("   - Or set these as environment variables")
        return

    # Main exam generation with multi-type example
    example_prompt = "Generate an exam paper with 3 mcqs, maximum 10 marks, subject Big Data"
    organization_id = "686e4d384529d5bc5f8a93e1"  # Replace with actual organization ID
    
    print(f"\n{'='*70}")
    print("MAIN EXAM GENERATION")
    print("=" * 70)
    print(f"Original Prompt: {example_prompt}")
    print(f"Organization ID: {organization_id}")
    
    try:
        # Generate exam paper
        exam_paper = generate_exam_paper(example_prompt, organization_id)
        
        if exam_paper:
            print(f"\n{'='*50}")
            print("GENERATED EXAM PAPER")
            print("=" * 50)
            print(exam_paper)
        else:
            print("❌ Failed to generate exam paper")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Running parsing test instead...")

if __name__ == "__main__":
    main()