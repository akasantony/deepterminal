#!/usr/bin/env python
"""
Script to run a backtest for a trading strategy
"""

import argparse
import importlib
import inspect
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root to path

from src.backtesting.backtest import BacktestEngine
from src.trading.strategy import TradingStrategy
from src.utils.logger import setup_logger

def discover_strategies() -> dict:
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

def main():
    """Run a backtest"""
    # Set up logger
    logger = setup_logger("backtest_runner")
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run a backtest for a trading strategy")
    
    # Discover available strategies
    available_strategies = discover_strategies()
    strategy_names = list(available_strategies.keys())
    
    # Strategy selection
    parser.add_argument("--strategy", choices=strategy_names, required=True,
                      help="Strategy to test")
    
    # Data input
    parser.add_argument("--data", type=str, required=True,
                      help="Path to CSV file with price data")
    parser.add_argument("--symbol", type=str, default=None,
                      help="Symbol name (default: extracted from filename)")
    parser.add_argument("--exchange", type=str, default="NSE",
                      help="Exchange name (default: NSE)")
    
    # Strategy parameters
    parser.add_argument("--params", type=str, default=None,
                      help="Strategy parameters as JSON string (e.g., '{\"fast_period\": 10}')")
    
    # Output options
    parser.add_argument("--output", type=str, default=None,
                      help="Path to save results JSON (default: results_{strategy}_{timestamp}.json)")
    parser.add_argument("--plot", action="store_true",
                      help="Show performance plot")
    parser.add_argument("--plot-output", type=str, default=None,
                      help="Path to save plot image (default: results_{strategy}_{timestamp}.png)")
    
    args = parser.parse_args()
    
    # Parse strategy parameters if provided
    strategy_params = {}
    if args.params:
        try:
            strategy_params = json.loads(args.params)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON parameters: {e}")
            sys.exit(1)
    
    # Initialize backtest engine
    strategy_class = available_strategies[args.strategy]
    backtest = BacktestEngine(strategy_class, strategy_params)
    
    # Load price data
    logger.info(f"Loading price data from {args.data}")
    if not backtest.load_price_data(args.data, symbol=args.symbol, exchange=args.exchange):
        logger.error("Failed to load price data")
        sys.exit(1)
    
    # Run backtest
    logger.info("Running backtest...")
    results = backtest.run()
    
    if not results:
        logger.error("Backtest failed")
        sys.exit(1)
    
    # Log key results
    logger.info(f"Backtest completed: {args.strategy}")
    logger.info(f"Period: {results['start_date']} to {results['end_date']}")
    logger.info(f"Total Return: {results['total_return_pct']:.2f}%")
    logger.info(f"Annualized Return: {results['annualized_return_pct']:.2f}%")
    logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    logger.info(f"Number of Trades: {results['num_trades']}")
    
    # Generate output paths if not provided
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not args.output:
        output_dir = Path("backtest_results")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"results_{args.strategy}_{timestamp}.json"
    else:
        output_path = Path(args.output)
    
    if not args.plot_output and args.plot:
        output_dir = Path("backtest_results")
        output_dir.mkdir(exist_ok=True)
        plot_path = output_dir / f"results_{args.strategy}_{timestamp}.png"
    else:
        plot_path = args.plot_output
    
    # Save results
    if backtest.save_results(output_path):
        logger.info(f"Results saved to {output_path}")
    
    # Show/save plot
    if args.plot:
        backtest.plot_results(save_path=plot_path)
        if plot_path:
            logger.info(f"Plot saved to {plot_path}")

if __name__ == "__main__":
    main()
