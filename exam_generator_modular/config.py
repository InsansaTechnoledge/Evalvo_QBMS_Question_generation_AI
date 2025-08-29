# config.py
import os
import warnings
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client
from transformers.models.auto.tokenization_auto import AutoTokenizer
from transformers.models.auto.modeling_auto import AutoModelForCausalLM

class Config:
    """Configuration class to hold all application settings"""
    def __init__(self):
        self.supabase_url: Optional[str] = None
        self.supabase_anon_key: Optional[str] = None
        self.supabase_client: Optional[Client] = None
        self.tokenizer = None
        self.model = None
        self.model_name = "microsoft/DialoGPT-medium"

# Global config instance
config = Config()

def load_environment_config() -> None:
    """Load environment variables from .env file"""
    try:
        load_dotenv()
        print("✅ Environment configuration loaded successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not load environment configuration: {e}")

def get_supabase_config() -> Dict[str, Optional[str]]:
    """Get Supabase configuration from environment variables"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    config.supabase_url = supabase_url
    config.supabase_anon_key = supabase_anon_key
    
    return {
        "supabase_url": supabase_url,
        "supabase_anon_key": supabase_anon_key
    }

def initialize_supabase_client() -> Optional[Client]:
    """Initialize and return Supabase client"""
    try:
        if config.supabase_url and config.supabase_anon_key:
            config.supabase_client = create_client(config.supabase_url, config.supabase_anon_key)
            print("✅ Supabase client initialized successfully")
            return config.supabase_client
        else:
            print("⚠️ Warning: Supabase credentials not found. Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
            return None
    except Exception as e:
        print(f"❌ Error initializing Supabase client: {e}")
        return None

def get_model_config() -> Dict[str, str]:
    """Get model configuration"""
    return {
        "model_name": config.model_name,
        "tokenizer_name": config.model_name
    }

def initialize_models() -> Tuple[Optional[AutoTokenizer], Optional[AutoModelForCausalLM]]:
    """Initialize and return tokenizer and model for LLM fallback"""
    warnings.filterwarnings("ignore", category=UserWarning, module='transformers')
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        model = AutoModelForCausalLM.from_pretrained(config.model_name)
        tokenizer.pad_token = tokenizer.eos_token
        
        config.tokenizer = tokenizer
        config.model = model
        
        print(f"✅ {config.model_name} loaded successfully for LLM fallback")
        return tokenizer, model
        
    except Exception as e:
        print(f"⚠️ Warning: Could not load {config.model_name}: {e}")
        config.tokenizer = None
        config.model = None
        return None, None

def get_supabase_client() -> Optional[Client]:
    """Get the initialized Supabase client"""
    return config.supabase_client

def get_tokenizer():
    """Get the initialized tokenizer"""
    return config.tokenizer

def get_model():
    """Get the initialized model"""
    return config.model

def initialize_all() -> Dict[str, Any]:
    """Initialize all components and return status"""
    status = {}
    
    # Load environment
    load_environment_config()
    
    # Get Supabase config
    supabase_config = get_supabase_config()
    status["supabase_config"] = bool(supabase_config["supabase_url"] and supabase_config["supabase_anon_key"])
    
    # Initialize Supabase client
    supabase_client = initialize_supabase_client()
    status["supabase_client"] = bool(supabase_client)
    
    # Initialize models
    tokenizer, model = initialize_models()
    status["models"] = bool(tokenizer and model)
    
    return status