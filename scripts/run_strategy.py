if __name__ == "__main__":
    asyncio.run(main())#!/usr/bin/env python
"""
Script to run a trading strategy from the command line
"""

import argparse
import asyncio
import importlib
import inspect
import json
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Type

sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root to path

from src.api.upstox_client import UpstoxClient
from src.auth.authenticator import UpstoxAuthenticator
from src.models.instrument import Instrument
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.trading.strategy import TradingStrategy
from src.utils.config import load_config
from src.utils.logger import setup_logger
from src.utils.persistence import save_trading_session

def discover_strategies() -> Dict[str, Type[TradingStrategy]]:
    """Discover available strategies in the project"""
    from src.trading.strategy import TradingStrategy
    
    strategies = {}
    
    # Import strategy modules
    try:
        # Try to import the strategies package
        import src.trading.strategies
        
        # Get all modules in the strategies package
        strategies_dir = Path(src.trading.strategies.__file__).parent
        for file_path in strategies_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
                
            module_name = f"src.trading.strategies.{file_path.stem}"
            try:
                module = importlib.import_module(module_name)
                
                # Find strategy classes in the module
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, TradingStrategy) and 
                        obj is not TradingStrategy):
                        strategies[name] = obj
            except Exception as e:
                print(f"Error importing module {module_name}: {e}")
    
    except ImportError:
        # Basic strategies from the main strategy module
        import src.trading.strategy as strategy_module
        
        for name, obj in inspect.getmembers(strategy_module):
            if (inspect.isclass(obj) and 
                issubclass(obj, TradingStrategy) and 
                obj is not TradingStrategy):
                strategies[name] = obj
    
    return strategies

class PaperTradingOrderManager(OrderManager):
    """Order manager that simulates orders without actually placing them"""
    
    def __init__(self, client):
        super().__init__(client)
        self.logger = setup_logger("paper_trading")
        self.next_order_id = 1000
    
    def place_market_order(self, instrument, transaction_type, quantity=None, product="INTRADAY"):
        """Simulate placing a market order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        order_id = f"PAPER_{self.next_order_id}"
        self.next_order_id += 1
        
        self.logger.info(f"PAPER TRADING: Market order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol}")
        
        # Create a simulated order
        order_data = {
            "order_id": order_id,
            "instrument_key": instrument.instrument_key,
            "exchange": instrument.exchange,
            "symbol": instrument.symbol,
            "transaction_type": transaction_type,
            "product": product,
            "order_type": "MARKET",
            "quantity": actual_quantity,
            "status": "COMPLETE",
            "filled_quantity": actual_quantity,
            "pending_quantity": 0,
            "cancelled_quantity": 0,
        }
        
        # Update local orders cache
        self.orders[order_id] = Order.from_api_response(order_data)
        
        return order_id
    
    def place_limit_order(self, instrument, transaction_type, price, quantity=None, product="INTRADAY"):
        """Simulate placing a limit order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        order_id = f"PAPER_{self.next_order_id}"
        self.next_order_id += 1
        
        self.logger.info(f"PAPER TRADING: Limit order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol} @ {price}")
        
        # Create a simulated order
        order_data = {
            "order_id": order_id,
            "instrument_key": instrument.instrument_key,
            "exchange": instrument.exchange,
            "symbol": instrument.symbol,
            "transaction_type": transaction_type,
            "product": product,
            "order_type": "LIMIT",
            "quantity": actual_quantity,
            "price": price,
            "status": "OPEN",
            "filled_quantity": 0,
            "pending_quantity": actual_quantity,
            "cancelled_quantity": 0,
        }
        
        # Update local orders cache
        self.orders[order_id] = Order.from_api_response(order_data)
        
        return order_id
    
    def place_sl_order(self, instrument, transaction_type, trigger_price, price=None, quantity=None, product="INTRADAY"):
        """Simulate placing a stop-loss order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        order_type = "SL" if price is not None else "SL-M"
        order_id = f"PAPER_{self.next_order_id}"
        self.next_order_id += 1
        
        price_str = f" @ {price}" if price is not None else ""
        self.logger.info(f"PAPER TRADING: SL order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol}{price_str} (Trigger: {trigger_price})")
        
        # Create a simulated order
        order_data = {
            "order_id": order_id,
            "instrument_key": instrument.instrument_key,
            "exchange": instrument.exchange,
            "symbol": instrument.symbol,
            "transaction_type": transaction_type,
            "product": product,
            "order_type": order_type,
            "quantity": actual_quantity,
            "price": price if price is not None else 0,
            "trigger_price": trigger_price,
            "status": "TRIGGER PENDING",
            "filled_quantity": 0,
            "pending_quantity": actual_quantity,
            "cancelled_quantity": 0,
        }
        
        # Update local orders cache
        self.orders[order_id] = Order.from_api_response(order_data)
        
        return order_id
    
    def cancel_order(self, order_id):
        """Simulate cancelling an order"""
        if order_id not in self.orders:
            self.logger.error(f"PAPER TRADING: Order {order_id} not found")
            return False
        
        order = self.orders[order_id]
        
        if order.status in ["COMPLETE", "CANCELLED"]:
            self.logger.warning(f"PAPER TRADING: Cannot cancel order {order_id} with status {order.status}")
            return False
        
        # Update order status
        order_data = {
            "order_id": order_id,
            "status": "CANCELLED",
            "pending_quantity": 0,
            "cancelled_quantity": order.pending_quantity,
        }
        
        # Update the order
        for key, value in order_data.items():
            setattr(order, key, value)
        
        self.logger.info(f"PAPER TRADING: Order cancelled: {order_id}")
        
        return True

async def main():
    """Run the selected strategy"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run a trading strategy")
    
    # Discover available strategies
    available_strategies = discover_strategies()
    strategy_names = list(available_strategies.keys())
    
    parser.add_argument("--strategy", choices=strategy_names, required=True,
                      help="Strategy to run")
    parser.add_argument("--symbol", type=str, required=True,
                      help="Stock symbol (e.g., RELIANCE)")
    parser.add_argument("--exchange", type=str, default=None,
                      help="Exchange (e.g., NSE, BSE, NFO) - uses default from config if not specified")
    parser.add_argument("--quantity", type=int, default=None,
                      help="Order quantity - uses default from config if not specified")
    parser.add_argument("--paper-trading", action="store_true",
                      help="Run in paper trading mode (no real orders)")
    parser.add_argument("--params", type=str, default=None,
                      help="Strategy parameters as JSON string (e.g., '{\"fast_period\": 10}')")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Setup logging
    logger = setup_logger(config.get("LOG_LEVEL", "INFO"))
    logger.info(f"Starting strategy runner for {args.strategy}")
    
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
    if args.paper_trading:
        logger.info("Running in paper trading mode - orders will be simulated")
        order_manager = PaperTradingOrderManager(client)
    else:
        order_manager = OrderManager(client)
    position_tracker = PositionTracker(client)
    
    # Set default order quantity
    quantity = args.quantity if args.quantity is not None else config["DEFAULT_QUANTITY"]
    order_manager.set_default_quantity(quantity)
    
    # Start position monitoring
    position_tracker.start_monitoring()
    
    # Setup websocket connection
    client.connect_websocket()
    
    # Search for instruments
    logger.info("Searching for instruments...")
    exchange = args.exchange if args.exchange else config["DEFAULT_EXCHANGE"]
    
    instruments_data = client.search_instruments(exchange=exchange, symbol=args.symbol)
    
    if not instruments_data:
        logger.error(f"No instruments found for {args.symbol} on {exchange}")
        sys.exit(1)
    
    # Convert to Instrument objects
    instruments = [Instrument.from_api_response(item) for item in instruments_data]
    
    logger.info(f"Found {len(instruments)} instruments:")
    for i, inst in enumerate(instruments):
        logger.info(f"  [{i}] {inst}")
    
    # If multiple instruments found, ask user to select one
    selected_instrument = None
    if len(instruments) > 1:
        try:
            selection = int(input("Enter the number of the instrument to use: "))
            if 0 <= selection < len(instruments):
                selected_instrument = instruments[selection]
            else:
                logger.error(f"Invalid selection: {selection}")
                sys.exit(1)
        except ValueError:
            logger.error("Please enter a valid number")
            sys.exit(1)
    else:
        selected_instrument = instruments[0]
    
    logger.info(f"Selected instrument: {selected_instrument}")
    
    # Initialize strategy
    strategy_class = available_strategies[args.strategy]
    strategy = strategy_class(client, order_manager, position_tracker)
    
    # Parse strategy parameters if provided
    if args.params:
        try:
            params = json.loads(args.params)
            strategy.set_parameters(params)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON parameters: {e}")
            sys.exit(1)
    
    # Set instruments to trade
    strategy.set_instruments([selected_instrument])
    
    # Initialize session data for recording
    session_data = {
        "strategy": args.strategy,
        "symbol": args.symbol,
        "exchange": exchange,
        "quantity": quantity,
        "paper_trading": args.paper_trading,
        "parameters": strategy.strategy_params
    }
    
    # Setup signal handlers for graceful shutdown
    def handle_shutdown(sig, frame):
        logger.info("Stopping strategy...")
        strategy.stop()
        
        # Save session data
        session_data["end_time"] = time.time()
        save_trading_session(session_data)
        
        logger.info("Strategy stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_shutdown)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, handle_shutdown)  # Handle termination signal
    
    # Record start time
    session_data["start_time"] = time.time()
    
    try:
        # Start the strategy
        logger.info("Starting strategy...")
        strategy.start()
        
        # Keep the script running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping...")
        strategy.stop()
        
        # Save session data
        session_data["end_time"] = time.time()
        save_trading_session(session_data)
        
        logger.info("Strategy stopped")
    except Exception as e:
        logger.error(f"Error running strategy: {e}")
        strategy.stop()
        
        # Save session data with error
        session_data["end_time"] = time.time()
        session_data["error"] = str(e)
        save_trading_session(session_data)
        
        sys.exit(1)