"""
Utilities for data persistence
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from src.utils.logger import logger

def get_data_dir() -> Path:
    """Get the data directory, creating it if it doesn't exist"""
    # Use ~/.deepterminal as the data directory
    data_dir = Path.home() / '.deepterminal'
    
    # Create directory if it doesn't exist
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        logger.info(f"Created data directory: {data_dir}")
    
    return data_dir

def save_strategy_settings(strategy_name: str, settings: Dict[str, Any]) -> bool:
    """
    Save strategy settings to file
    
    Args:
        strategy_name: Name of the strategy
        settings: Strategy settings to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        data_dir = get_data_dir()
        strategies_dir = data_dir / 'strategies'
        
        # Create strategies directory if it doesn't exist
        if not strategies_dir.exists():
            strategies_dir.mkdir(parents=True)
        
        # Create file path
        file_path = strategies_dir / f"{strategy_name}.json"
        
        # Add timestamp
        settings_with_timestamp = settings.copy()
        settings_with_timestamp['last_modified'] = datetime.now().isoformat()
        
        # Save settings to file
        with open(file_path, 'w') as f:
            json.dump(settings_with_timestamp, f, indent=2)
        
        logger.info(f"Saved strategy settings for '{strategy_name}' to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving strategy settings: {e}")
        return False

def load_strategy_settings(strategy_name: str) -> Optional[Dict[str, Any]]:
    """
    Load strategy settings from file
    
    Args:
        strategy_name: Name of the strategy
        
    Returns:
        Strategy settings if found, None otherwise
    """
    try:
        data_dir = get_data_dir()
        file_path = data_dir / 'strategies' / f"{strategy_name}.json"
        
        # Check if file exists
        if not file_path.exists():
            logger.debug(f"No settings file found for strategy '{strategy_name}'")
            return None
        
        # Load settings from file
        with open(file_path, 'r') as f:
            settings = json.load(f)
        
        logger.info(f"Loaded strategy settings for '{strategy_name}' from {file_path}")
        return settings
    
    except Exception as e:
        logger.error(f"Error loading strategy settings: {e}")
        return None

def list_saved_strategies() -> List[str]:
    """
    List names of saved strategies
    
    Returns:
        List of strategy names
    """
    try:
        data_dir = get_data_dir()
        strategies_dir = data_dir / 'strategies'
        
        # Check if directory exists
        if not strategies_dir.exists():
            return []
        
        # Get list of JSON files
        strategy_files = strategies_dir.glob('*.json')
        
        # Extract strategy names from filenames
        return [f.stem for f in strategy_files]
    
    except Exception as e:
        logger.error(f"Error listing saved strategies: {e}")
        return []

def save_trading_session(session_data: Dict[str, Any]) -> bool:
    """
    Save trading session data
    
    Args:
        session_data: Session data to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        data_dir = get_data_dir()
        sessions_dir = data_dir / 'sessions'
        
        # Create sessions directory if it doesn't exist
        if not sessions_dir.exists():
            sessions_dir.mkdir(parents=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = sessions_dir / f"session_{timestamp}.json"
        
        # Add timestamp to session data
        session_data['timestamp'] = timestamp
        session_data['date'] = datetime.now().isoformat()
        
        # Save session data to file
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"Saved trading session data to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving trading session data: {e}")
        return False

def load_trading_sessions(count: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load trading session data
    
    Args:
        count: Number of most recent sessions to load (None for all)
        
    Returns:
        List of session data dictionaries, ordered by most recent first
    """
    try:
        data_dir = get_data_dir()
        sessions_dir = data_dir / 'sessions'
        
        # Check if directory exists
        if not sessions_dir.exists():
            return []
        
        # Get list of JSON files
        session_files = sessions_dir.glob('*.json')
        
        # Sort files by modification time (most recent first)
        sorted_files = sorted(session_files, key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Limit to specified count if provided
        if count is not None:
            sorted_files = sorted_files[:count]
        
        # Load sessions
        sessions = []
        for file_path in sorted_files:
            try:
                with open(file_path, 'r') as f:
                    session_data = json.load(f)
                    sessions.append(session_data)
            except Exception as e:
                logger.error(f"Error loading session data from {file_path}: {e}")
        
        return sessions
    
    except Exception as e:
        logger.error(f"Error loading trading sessions: {e}")
        return []
