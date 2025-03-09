"""
Configuration validator
"""

from typing import Dict, Any, Optional
import re

from src.utils.logger import logger

class ConfigError(Exception):
    """Exception raised for configuration errors"""
    pass

def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate configuration parameters
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validated configuration (with defaults for missing values)
        
    Raises:
        ConfigError: If configuration is invalid
    """
    errors = []
    
    # Required fields
    if not config.get("API_KEY"):
        errors.append("UPSTOX_API_KEY is missing in configuration")
    
    if not config.get("API_SECRET"):
        errors.append("UPSTOX_API_SECRET is missing in configuration")
    
    # Validate redirect URI
    redirect_uri = config.get("REDIRECT_URI")
    if not redirect_uri:
        errors.append("UPSTOX_REDIRECT_URI is missing in configuration")
    elif not redirect_uri.startswith(("http://", "https://")):
        errors.append(f"UPSTOX_REDIRECT_URI '{redirect_uri}' is invalid, must start with http:// or https://")
    
    # Validate numeric values
    try:
        default_quantity = int(config.get("DEFAULT_QUANTITY", 1))
        if default_quantity <= 0:
            errors.append(f"DEFAULT_QUANTITY '{default_quantity}' is invalid, must be positive")
        else:
            config["DEFAULT_QUANTITY"] = default_quantity
    except ValueError:
        errors.append(f"DEFAULT_QUANTITY '{config.get('DEFAULT_QUANTITY')}' is not a valid integer")
    
    try:
        risk_percentage = float(config.get("RISK_PERCENTAGE", 2.0))
        if risk_percentage <= 0 or risk_percentage > 100:
            errors.append(f"RISK_PERCENTAGE '{risk_percentage}' is invalid, must be between 0 and 100")
        else:
            config["RISK_PERCENTAGE"] = risk_percentage
    except ValueError:
        errors.append(f"RISK_PERCENTAGE '{config.get('RISK_PERCENTAGE')}' is not a valid float")
    
    # Validate exchange
    valid_exchanges = ["NSE", "BSE", "NFO", "BFO", "MCX", "CDS"]
    default_exchange = config.get("DEFAULT_EXCHANGE", "NSE")
    if default_exchange not in valid_exchanges:
        errors.append(f"DEFAULT_EXCHANGE '{default_exchange}' is invalid, must be one of {valid_exchanges}")
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_level = config.get("LOG_LEVEL", "INFO").upper()
    if log_level not in valid_log_levels:
        errors.append(f"LOG_LEVEL '{log_level}' is invalid, must be one of {valid_log_levels}")
    else:
        config["LOG_LEVEL"] = log_level
    
    # If there are errors, raise exception
    if errors:
        error_message = "Configuration errors:\n" + "\n".join(f"- {error}" for error in errors)
        logger.error(error_message)
        raise ConfigError(error_message)
    
    # Set defaults for optional values that might be missing
    defaults = {
        "LOG_LEVEL": "INFO",
        "DEFAULT_EXCHANGE": "NSE",
        "DEFAULT_QUANTITY": 1,
        "RISK_PERCENTAGE": 2.0,
    }
    
    for key, value in defaults.items():
        if key not in config or config[key] is None:
            config[key] = value
            
    return config