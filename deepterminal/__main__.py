"""
Main entry point for DeepTerminal.

This module provides the main application entry point and command-line interface.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Optional, Any

import click
from dotenv import load_dotenv

from deepterminal.ui.app import DeepTerminalApp
from deepterminal.config.app_config import load_config


@click.group()
@click.version_option()
def cli():
    """DeepTerminal: Algorithmic Trading Application for Options and Futures."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('deepterminal.log')
        ]
    )
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    load_config()


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file.')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode.')
def run(config: Optional[str], debug: bool):
    """Run the DeepTerminal application."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug mode enabled")
    
    # If a config file is specified, load it
    if config:
        load_config(config)
    
    # Run the application
    app = DeepTerminalApp()
    app.run()


@cli.command()
@click.option('--broker', '-b', type=str, required=True, help='Broker to use (mock, interactive_brokers, tdameritrade).')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file.')
def authenticate(broker: str, config: Optional[str]):
    """Authenticate with a broker."""
    # If a config file is specified, load it
    if config:
        load_config(config)
    
    # Run the authentication flow
    from deepterminal.exchange.connection import authenticate_broker
    
    async def auth():
        await authenticate_broker(broker)
    
    asyncio.run(auth())
    
    click.echo(f"Authentication with {broker} completed.")


@cli.command()
@click.option('--strategy', '-s', type=str, required=True, help='Strategy to backtest.')
@click.option('--symbol', '-sym', type=str, required=True, help='Symbol to backtest.')
@click.option('--timeframe', '-t', type=str, default='1h', help='Timeframe for backtesting (e.g., 1m, 5m, 1h, 1d).')
@click.option('--start', type=str, required=True, help='Start date (YYYY-MM-DD).')
@click.option('--end', type=str, help='End date (YYYY-MM-DD). Defaults to today.')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file.')
@click.option('--output', '-o', type=click.Path(), help='Path to output file.')
def backtest(strategy: str, symbol: str, timeframe: str, start: str, end: Optional[str], config: Optional[str], output: Optional[str]):
    """Run a backtest for a strategy."""
    from deepterminal.backtesting.engine import BacktestEngine
    
    # If a config file is specified, load it
    if config:
        load_config(config)
    
    # Run the backtest
    engine = BacktestEngine()
    results = engine.run_backtest(
        strategy_name=strategy,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start,
        end_date=end
    )
    
    # Save results if output path is specified
    if output:
        engine.save_results(results, output)
    
    # Display summary
    engine.print_summary(results)


@cli.command()
@click.option('--output', '-o', type=click.Path(), default='strategies.txt', help='Path to output file.')
def list_strategies(output: str):
    """List all available strategies."""
    from deepterminal.strategies.registry import StrategyRegistry
    
    # Get all registered strategies
    registry = StrategyRegistry()
    strategies = registry.get_all_strategies()
    
    # Display and save the list
    with open(output, 'w') as f:
        for name, strategy_class in strategies.items():
            description = getattr(strategy_class, '__doc__', 'No description available').strip()
            line = f"{name}: {description}"
            click.echo(line)
            f.write(line + '\n')
    
    click.echo(f"\nStrategy list saved to {output}")


@cli.command()
def create_config():
    """Create a default configuration file."""
    from deepterminal.config.app_config import create_default_config
    
    config_path = create_default_config()
    click.echo(f"Default configuration file created at {config_path}")
    click.echo("Please edit this file with your preferences and broker settings.")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()