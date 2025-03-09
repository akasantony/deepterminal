"""
Configuration loader for the trading app
"""

import os
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

def find_dotenv() -> str:
    """Find the .env file looking in the current directory and up"""
    env_path = Path('.env')
    if env_path.exists():
        return str(env_path)
    
    # If not found, look in parent directories
    current_dir = Path.cwd()
    while current_dir != current_dir.parent:
        env_path = current_dir / '.env'
        if env_path.exists():
            return str(env_path)
        current_dir = current_dir.parent
    
    # Default to current dir even if not found
    return '.env'

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    # Load environment variables from .env file
    dotenv_path = find_dotenv()
    load_dotenv(dotenv_path)
    
    # Create configuration dictionary
    config = {
        # Upstox API credentials
        "API_KEY": os.getenv("UPSTOX_API_KEY", ""),
        "API_SECRET": os.getenv("UPSTOX_API_SECRET", ""),
        "REDIRECT_URI": os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/callback"),
        
        # App configuration
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "DEFAULT_EXCHANGE": os.getenv("DEFAULT_EXCHANGE", "NSE"),
        
        # Trading parameters
        "DEFAULT_QUANTITY": int(os.getenv("DEFAULT_QUANTITY", "1")),
        "RISK_PERCENTAGE": float(os.getenv("RISK_PERCENTAGE", "2.0")),
    }
    
    return config