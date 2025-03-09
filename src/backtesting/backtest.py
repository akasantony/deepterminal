"""
Simple backtesting engine for trading strategies
"""

import csv
import datetime
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Type, Optional, Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.trading.strategy import TradingStrategy
from src.utils.logger import setup_logger

logger = setup_logger("backtest")

class MockInstrument:
    """Mock instrument for backtesting"""
    
    def __init__(self, instrument_key, exchange, symbol, name, instrument_type="EQ"):
        self.instrument_key = instrument_key
        self.exchange = exchange
        self.symbol = symbol
        self.name = name
        self.instrument_type = instrument_type
        self.expiry = None
        self.strike = None
        self.option_type = None
        self.lot_size = 1
        self.tick_size = 0.05
    
    def __str__(self) -> str:
        return f"{self.symbol} ({self.exchange})"

class MockOrder:
    """Mock order for backtesting"""
    
    def __init__(self, order_id, instrument_key, transaction_type, quantity, price, timestamp):
        self.order_id = order_id
        self.instrument_key = instrument_key
        self.transaction_type = transaction_type
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp
        self.status = "COMPLETE"

class MockPosition:
    """Mock position for backtesting"""
    
    def __init__(self, instrument_key, exchange, symbol, quantity, average_price, last_price):
        self.instrument_key = instrument_key
        self.exchange = exchange
        self.symbol = symbol
        self.product = "BACKTEST"
        self.quantity = quantity
        self.overnight_quantity = 0
        self.multiplier = 1.0
        self.average_price = average_price
        self.close_price = last_price
        self.last_price = last_price
        self.unrealized_pnl = (last_price - average_price) * quantity
        self.realized_pnl = 0.0
    
    @property
    def total_pnl(self) -> float:
        """Calculate total P&L (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def is_long(self) -> bool:
        """Check if position is long (buy)"""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """Check if position is short (sell)"""
        return self.quantity < 0

class MockOrderManager:
    """Mock order manager for backtesting"""
    
    def __init__(self):
        self.orders = []
        self.next_order_id = 1
        self.default_quantity = 1
    
    def set_default_quantity(self, quantity: int):
        """Set default order quantity"""
        self.default_quantity = quantity
    
    def place_market_order(self, instrument, transaction_type, quantity=None, product="BACKTEST", timestamp=None, price=None):
        """Place a mock market order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        order_id = f"BT_{self.next_order_id}"
        self.next_order_id += 1
        
        order = MockOrder(
            order_id=order_id,
            instrument_key=instrument.instrument_key,
            transaction_type=transaction_type,
            quantity=actual_quantity,
            price=price,
            timestamp=timestamp
        )
        
        self.orders.append(order)
        return order_id
    
    def place_limit_order(self, instrument, transaction_type, price, quantity=None, product="BACKTEST", timestamp=None):
        """Place a mock limit order"""
        return self.place_market_order(
            instrument=instrument,
            transaction_type=transaction_type,
            quantity=quantity,
            product=product,
            timestamp=timestamp,
            price=price
        )
    
    def place_sl_order(self, instrument, transaction_type, trigger_price, price=None, quantity=None, product="BACKTEST", timestamp=None):
        """Place a mock stop-loss order"""
        # In backtesting, we use the trigger price for execution
        use_price = trigger_price if price is None else price
        return self.place_market_order(
            instrument=instrument,
            transaction_type=transaction_type,
            quantity=quantity,
            product=product,
            timestamp=timestamp,
            price=use_price
        )

class MockPositionTracker:
    """Mock position tracker for backtesting"""
    
    def __init__(self):
        self.positions = {}
        self.position_callbacks = {}
        self.global_callbacks = []
    
    def get_position(self, instrument_key: str) -> Optional[MockPosition]:
        """Get a position by instrument key"""
        return self.positions.get(instrument_key)
    
    def update_position(self, instrument_key: str, transaction_type: str, quantity: int, price: float, timestamp: datetime.datetime):
        """Update a position based on a new order"""
        position = self.positions.get(instrument_key)
        
        # Get instrument details from existing position or create placeholder
        if position:
            exchange = position.exchange
            symbol = position.symbol
            current_quantity = position.quantity
            current_average_price = position.average_price
            realized_pnl = position.realized_pnl
        else:
            # This would typically come from the instrument, but we use placeholders
            exchange = "BACKTEST"
            symbol = instrument_key.split("_")[-1]
            current_quantity = 0
            current_average_price = 0
            realized_pnl = 0
        
        # Calculate new quantity
        if transaction_type == "BUY":
            # If we're short, this is reducing position size
            if current_quantity < 0 and abs(current_quantity) >= quantity:
                # Partial or full cover
                new_quantity = current_quantity + quantity
                closing_quantity = quantity
                
                # Calculate realized P&L for the closed portion
                trade_pnl = (current_average_price - price) * closing_quantity
                realized_pnl += trade_pnl
                
                # If full cover, reset average price
                if new_quantity == 0:
                    new_average_price = 0
                else:
                    # Keep the same average price for remaining short position
                    new_average_price = current_average_price
            else:
                # Adding to long position or flipping from short to long
                closing_quantity = min(abs(current_quantity), quantity) if current_quantity < 0 else 0
                new_position_quantity = quantity - closing_quantity
                
                # Calculate realized P&L for any closed portion
                if closing_quantity > 0:
                    trade_pnl = (current_average_price - price) * closing_quantity
                    realized_pnl += trade_pnl
                
                # Calculate new position details
                if current_quantity <= 0:
                    # Starting fresh long position
                    new_quantity = new_position_quantity
                    new_average_price = price
                else:
                    # Adding to existing long position
                    new_quantity = current_quantity + quantity
                    new_average_price = ((current_quantity * current_average_price) + (quantity * price)) / new_quantity
        else:  # SELL
            # If we're long, this is reducing position size
            if current_quantity > 0 and current_quantity >= quantity:
                # Partial or full liquidation
                new_quantity = current_quantity - quantity
                closing_quantity = quantity
                
                # Calculate realized P&L for the closed portion
                trade_pnl = (price - current_average_price) * closing_quantity
                realized_pnl += trade_pnl
                
                # If fully liquidated, reset average price
                if new_quantity == 0:
                    new_average_price = 0
                else:
                    # Keep the same average price for remaining long position
                    new_average_price = current_average_price
            else:
                # Adding to short position or flipping from long to short
                closing_quantity = min(current_quantity, quantity) if current_quantity > 0 else 0
                new_position_quantity = quantity - closing_quantity
                
                # Calculate realized P&L for any closed portion
                if closing_quantity > 0:
                    trade_pnl = (price - current_average_price) * closing_quantity
                    realized_pnl += trade_pnl
                
                # Calculate new position details
                if current_quantity >= 0:
                    # Starting fresh short position
                    new_quantity = -new_position_quantity
                    new_average_price = price
                else:
                    # Adding to existing short position
                    new_quantity = current_quantity - quantity
                    # For shorts, we use a weighted average entry price
                    current_abs_quantity = abs(current_quantity)
                    new_abs_quantity = abs(new_quantity)
                    new_average_price = ((current_abs_quantity * current_average_price) + (quantity * price)) / new_abs_quantity
        
        # Create or update position
        self.positions[instrument_key] = MockPosition(
            instrument_key=instrument_key,
            exchange=exchange,
            symbol=symbol,
            quantity=new_quantity,
            average_price=new_average_price if new_quantity != 0 else 0,
            last_price=price
        )
        
        # Set realized P&L
        self.positions[instrument_key].realized_pnl = realized_pnl
        
        # Update unrealized P&L
        self.positions[instrument_key].unrealized_pnl = (price - new_average_price) * new_quantity
        
        # Call position callbacks
        if instrument_key in self.position_callbacks:
            for callback in self.position_callbacks[instrument_key]:
                try:
                    callback(self.positions[instrument_key])
                except Exception as e:
                    logger.error(f"Error in position callback: {e}")
        
        # Call global callbacks
        for callback in self.global_callbacks:
            try:
                callback(self.positions)
            except Exception as e:
                logger.error(f"Error in global position callback: {e}")
    
    def update_market_price(self, instrument_key: str, price: float):
        """Update the market price for a position"""
        if instrument_key in self.positions:
            position = self.positions[instrument_key]
            position.last_price = price
            position.unrealized_pnl = (price - position.average_price) * position.quantity
            
            # Call position callbacks
            if instrument_key in self.position_callbacks:
                for callback in self.position_callbacks[instrument_key]:
                    try:
                        callback(position)
                    except Exception as e:
                        logger.error(f"Error in position callback: {e}")
            
            # Call global callbacks
            for callback in self.global_callbacks:
                try:
                    callback(self.positions)
                except Exception as e:
                    logger.error(f"Error in global position callback: {e}")
    
    def register_position_callback(self, instrument_key: str, callback):
        """Register a callback for position updates"""
        if instrument_key not in self.position_callbacks:
            self.position_callbacks[instrument_key] = []
        
        self.position_callbacks[instrument_key].append(callback)
    
    def register_global_callback(self, callback):
        """Register a callback for all position updates"""
        self.global_callbacks.append(callback)
    
    def fetch_positions(self):
        """Fetch all positions"""
        return list(self.positions.values())

class BacktestEngine:
    """Simple backtesting engine for trading strategies"""
    
    def __init__(self, strategy_class: Type[TradingStrategy], params: Dict[str, Any] = None):
        """
        Initialize the backtesting engine
        
        Args:
            strategy_class: Strategy class to test
            params: Strategy parameters (optional)
        """
        self.strategy_class = strategy_class
        self.strategy_params = params or {}
        self.order_manager = MockOrderManager()
        self.position_tracker = MockPositionTracker()
        self.strategy = None
        self.instruments = {}
        self.results = None
    
    def load_price_data(self, data_path: str, instrument_key: str = None, exchange: str = "NSE", symbol: str = None):
        """
        Load price data from a CSV file
        
        Args:
            data_path: Path to the CSV file
            instrument_key: Instrument key (optional, will be generated if not provided)
            exchange: Exchange (optional, default: NSE)
            symbol: Symbol (optional, will be extracted from filename if not provided)
        """
        # Load data
        try:
            data = pd.read_csv(data_path)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False
        
        # Check required columns
        required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Generate symbol from filename if not provided
        if not symbol:
            symbol = Path(data_path).stem.upper()
        
        # Generate instrument key if not provided
        if not instrument_key:
            instrument_key = f"{exchange}_EQ_{symbol}"
        
        # Create instrument
        self.instruments[instrument_key] = MockInstrument(
            instrument_key=instrument_key,
            exchange=exchange,
            symbol=symbol,
            name=symbol,
            instrument_type="EQ"
        )
        
        # Ensure Date column is datetime
        try:
            data['Date'] = pd.to_datetime(data['Date'])
        except Exception as e:
            logger.error(f"Error converting Date column to datetime: {e}")
            return False
        
        # Sort data by date
        data = data.sort_values('Date')
        
        # Add instrument key column
        data['instrument_key'] = instrument_key
        
        # Store data
        self.price_data = data
        logger.info(f"Loaded {len(data)} price bars for {symbol}")
        
        return True
    
    def run(self) -> Dict[str, Any]:
        """
        Run the backtest
        
        Returns:
            Dictionary of backtest results
        """
        if not hasattr(self, 'price_data') or self.price_data is None:
            logger.error("No price data loaded")
            return None
        
        if not self.instruments:
            logger.error("No instruments defined")
            return None
        
        # Initialize strategy
        self.strategy = self.strategy_class(None, self.order_manager, self.position_tracker)
        self.strategy.set_parameters(self.strategy_params)
        self.strategy.set_instruments(list(self.instruments.values()))
        
        # Initialize tracking variables
        trades = []
        equity_curve = []
        current_equity = 0
        
        # Track daily returns
        daily_returns = []
        prev_date = None
        prev_equity = 0
        
        # Run strategy initialization
        self.strategy.initialize()
        
        # Process each bar
        for idx, row in self.price_data.iterrows():
            date = row['Date']
            instrument_key = row['instrument_key']
            instrument = self.instruments[instrument_key]
            
            # Create market data
            tick_data = {
                'instrument_key': instrument_key,
                'ltp': row['Close'],
                'open': row['Open'],
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                'volume': row['Volume'],
                'timestamp': date
            }
            
            # Update position market prices
            self.position_tracker.update_market_price(instrument_key, row['Close'])
            
            # Process tick data in strategy
            try:
                self.strategy.on_tick_data(tick_data)
            except Exception as e:
                logger.error(f"Error processing tick data: {e}")
            
            # Calculate equity at this point
            current_positions = self.position_tracker.fetch_positions()
            current_equity = sum([pos.realized_pnl + pos.unrealized_pnl for pos in current_positions])
            
            # Track equity curve
            equity_curve.append({
                'date': date,
                'equity': current_equity,
                'close': row['Close']
            })
            
            # Track daily returns (if we've moved to a new day)
            if prev_date is not None and date.date() != prev_date.date():
                daily_return = (current_equity - prev_equity) / (prev_equity if prev_equity != 0 else 1)
                daily_returns.append({
                    'date': prev_date.date(),
                    'return': daily_return
                })
                prev_equity = current_equity
            
            prev_date = date
            
            # Process any new orders
            for order in self.order_manager.orders:
                if order not in trades:
                    trades.append(order)
                    
                    # Update positions based on order
                    self.position_tracker.update_position(
                        instrument_key=order.instrument_key,
                        transaction_type=order.transaction_type,
                        quantity=order.quantity,
                        price=order.price,
                        timestamp=order.timestamp
                    )
        
        # Add final day's return if we have data
        if prev_date is not None and prev_equity != 0:
            daily_return = (current_equity - prev_equity) / prev_equity
            daily_returns.append({
                'date': prev_date.date(),
                'return': daily_return
            })
        
        # Calculate performance metrics
        self.results = self._calculate_performance_metrics(trades, equity_curve, daily_returns)
        
        return self.results
    
    def _calculate_performance_metrics(self, trades, equity_curve, daily_returns) -> Dict[str, Any]:
        """Calculate performance metrics from backtest results"""
        if not equity_curve:
            return {}
            
        # Convert to DataFrame for easier analysis
        equity_df = pd.DataFrame(equity_curve)
        returns_df = pd.DataFrame(daily_returns) if daily_returns else pd.DataFrame(columns=['date', 'return'])
        
        # Basic metrics
        start_equity = equity_df.iloc[0]['equity']
        end_equity = equity_df.iloc[-1]['equity']
        total_return = ((end_equity - start_equity) / start_equity) * 100 if start_equity != 0 else 0
        
        # Trading metrics
        num_trades = len(trades)
        
        # Drawdown analysis
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # Return statistics
        if not returns_df.empty:
            avg_daily_return = returns_df['return'].mean() * 100
            std_daily_return = returns_df['return'].std() * 100
            
            # Sharpe ratio (assuming risk-free rate of 0)
            days_per_year = 252  # Trading days in a year
            sharpe_ratio = (avg_daily_return / 100) * np.sqrt(days_per_year) / (std_daily_return / 100) if std_daily_return != 0 else 0
            
            # Annualized return
            total_days = (equity_df.iloc[-1]['date'] - equity_df.iloc[0]['date']).days
            if total_days > 0:
                years = total_days / 365
                annualized_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100
            else:
                annualized_return = total_return
        else:
            avg_daily_return = 0
            std_daily_return = 0
            sharpe_ratio = 0
            annualized_return = 0
        
        # Create results dictionary
        results = {
            'start_date': equity_df.iloc[0]['date'],
            'end_date': equity_df.iloc[-1]['date'],
            'start_equity': start_equity,
            'end_equity': end_equity,
            'total_return_pct': total_return,
            'annualized_return_pct': annualized_return,
            'num_trades': num_trades,
            'max_drawdown_pct': max_drawdown,
            'avg_daily_return_pct': avg_daily_return,
            'std_daily_return_pct': std_daily_return,
            'sharpe_ratio': sharpe_ratio,
            'equity_curve': equity_df.to_dict('records'),
            'trades': [{'order_id': t.order_id, 
                        'instrument_key': t.instrument_key, 
                        'transaction_type': t.transaction_type, 
                        'quantity': t.quantity, 
                        'price': t.price, 
                        'timestamp': t.timestamp} for t in trades]
        }
        
        return results
    
    def plot_results(self, save_path: Optional[str] = None):
        """Plot backtest results"""
        if self.results is None:
            logger.error("No backtest results to plot")
            return
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        # Extract data
        equity_curve = pd.DataFrame(self.results['equity_curve'])
        equity_curve['date'] = pd.to_datetime(equity_curve['date'])
        
        # Plot equity curve
        ax1.plot(equity_curve['date'], equity_curve['equity'], label='Portfolio Value')
        ax1.set_title('Backtest Results - Equity Curve')
        ax1.set_ylabel('Equity')
        ax1.legend()
        ax1.grid(True)
        
        # Plot drawdown
        equity_curve['drawdown'] = equity_curve['drawdown'] * -1  # Make positive for better visualization
        ax2.fill_between(equity_curve['date'], 0, equity_curve['drawdown'], color='red', alpha=0.3)
        ax2.set_title('Drawdown (%)')
        ax2.set_ylabel('Drawdown %')
        ax2.set_ylim(bottom=0, top=max(10, equity_curve['drawdown'].max() * 1.1))  # Set reasonable y-axis limits
        ax2.grid(True)
        
        # Format x-axis to show dates
        fig.autofmt_xdate()
        
        # Add key metrics as text
        metrics_text = (
            f"Total Return: {self.results['total_return_pct']:.2f}%\n"
            f"Annualized Return: {self.results['annualized_return_pct']:.2f}%\n"
            f"Sharpe Ratio: {self.results['sharpe_ratio']:.2f}\n"
            f"Max Drawdown: {self.results['max_drawdown_pct']:.2f}%\n"
            f"Number of Trades: {self.results['num_trades']}"
        )
        
        # Position the text box in figure coords
        plt.figtext(0.02, 0.02, metrics_text, fontsize=10, 
                   bbox=dict(facecolor='white', alpha=0.7))
        
        plt.tight_layout()
        
        # Save if path provided
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Results plot saved to {save_path}")
        
        # Show the plot
        plt.show()
    
    def save_results(self, file_path: str):
        """Save backtest results to a JSON file"""
        if self.results is None:
            logger.error("No backtest results to save")
            return False
        
        try:
            # Convert dates to strings for JSON serialization
            serializable_results = self.results.copy()
            
            # Handle start and end dates
            serializable_results['start_date'] = str(serializable_results['start_date'])
            serializable_results['end_date'] = str(serializable_results['end_date'])
            
            # Handle equity curve dates
            for item in serializable_results['equity_curve']:
                item['date'] = str(item['date'])
            
            # Handle trade timestamps
            for trade in serializable_results['trades']:
                if trade['timestamp'] is not None:
                    trade['timestamp'] = str(trade['timestamp'])
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(serializable_results, f, indent=2)
            
            logger.info(f"Results saved to {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return False