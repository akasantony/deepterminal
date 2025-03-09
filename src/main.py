#!/usr/bin/env python
"""
Upstox Trading Terminal - Main Entry Point
"""

import asyncio
import sys
from src.ui.app import TradingApp
from src.utils.config import load_config
from src.utils.logger import setup_logger

def main() -> None:
    """Application entry point"""
    # Load configuration
    config = load_config()
    
    # Setup logging
    logger = setup_logger(config.get("LOG_LEVEL", "INFO"))
    logger.info("Starting Upstox Trading Terminal")
    
    # Create and run the app
    app = TradingApp()
    
    try:
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()