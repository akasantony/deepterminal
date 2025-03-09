"""
Example of using a custom trading strategy with the application
"""

import asyncio
import sys

from src.api.upstox_client import UpstoxClient
from src.auth.authenticator import UpstoxAuthenticator
from src.models.instrument import Instrument
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.utils.config import load_config
from src.utils.logger import setup_logger

# Import your custom strategy
from examples.sample_strategy import RSIStrategy


async def main():
    """Run a custom trading strategy"""
    # Load configuration
    config = load_config()
    
    # Setup logging
    logger = setup_logger(config.get("LOG_LEVEL", "INFO"))
    logger.info("Starting custom strategy example")
    
    # Initialize authentication
    authenticator = UpstoxAuthenticator(
        api_key=config["API_KEY"],
        api_secret=config["API_SECRET"],
        redirect_uri=config["REDIRECT_URI"]
    )
    
    # Authenticate
    if not authenticator.authenticate():
        logger.error("Authentication failed")
        sys.exit(1)
    
    # Initialize API client
    client = UpstoxClient(authenticator)
    
    # Initialize order manager and position tracker
    order_manager = OrderManager(client)
    position_tracker = PositionTracker(client)
    
    # Set default order quantity
    order_manager.set_default_quantity(config.get("DEFAULT_QUANTITY", 1))
    
    # Start position monitoring
    position_tracker.start_monitoring()
    
    # Setup websocket connection
    client.connect_websocket()
    
    # Search for instruments
    logger.info("Searching for instruments...")
    symbol = "RELIANCE"  # Change to your desired symbol
    exchange = config.get("DEFAULT_EXCHANGE", "NSE")
    
    instruments_data = client.search_instruments(exchange=exchange, symbol=symbol)
    
    if not instruments_data:
        logger.error(f"No instruments found for {symbol} on {exchange}")
        sys.exit(1)
    
    # Convert to Instrument objects
    instruments = [Instrument.from_api_response(item) for item in instruments_data]
    
    logger.info(f"Found {len(instruments)} instruments")
    for inst in instruments:
        logger.info(f"  - {inst}")
    
    # Initialize strategy
    strategy = RSIStrategy(client, order_manager, position_tracker)
    
    # Set strategy parameters
    strategy.set_parameters({
        'rsi_period': 14,
        'overbought': 70,
        'oversold': 30,
        'quantity': config.get("DEFAULT_QUANTITY", 1)
    })
    
    # Set instruments to trade
    strategy.set_instruments(instruments)
    
    # Start the strategy
    logger.info("Starting strategy...")
    strategy.start()
    
    try:
        # Keep the script running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping strategy...")
        strategy.stop()
        logger.info("Strategy stopped")


if __name__ == "__main__":
    asyncio.run(main())