"""
MACD (Moving Average Convergence Divergence) trading strategy
"""

import numpy as np
from typing import Dict, List, Any, Optional

from src.api.upstox_client import UpstoxClient
from src.models.instrument import Instrument
from src.models.position import Position
from src.models.order import Order
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.trading.strategy import TradingStrategy
from src.utils.logger import logger
from src.utils.persistence import save_strategy_settings, load_strategy_settings


class MACDStrategy(TradingStrategy):
    """
    MACD (Moving Average Convergence Divergence) trading strategy
    
    The MACD is calculated by subtracting the 26-period EMA from the 12-period EMA.
    The MACD Signal line is a 9-period EMA of the MACD line.
    
    Trading rules:
    - Buy when MACD line crosses above the Signal line
    - Sell when MACD line crosses below the Signal line
    """
    
    def initialize(self):
        """Initialize the strategy"""
        # Get strategy parameters with defaults
        self.fast_period = int(self.get_parameter('fast_period', 12))
        self.slow_period = int(self.get_parameter('slow_period', 26))
        self.signal_period = int(self.get_parameter('signal_period', 9))
        self.quantity = int(self.get_parameter('quantity', 1))
        
        # Initialize data storage for each instrument
        self.prices: Dict[str, List[float]] = {}
        self.macd_line: Dict[str, Optional[float]] = {}
        self.signal_line: Dict[str, Optional[float]] = {}
        self.position_side: Dict[str, str] = {}  # 'LONG', 'SHORT', or None
        self.previous_crossover: Dict[str, str] = {}  # 'ABOVE', 'BELOW', or None
        
        # Initialize state for each instrument
        for instrument_key in self.instruments:
            self.prices[instrument_key] = []
            self.macd_line[instrument_key] = None
            self.signal_line[instrument_key] = None
            self.position_side[instrument_key] = None
            self.previous_crossover[instrument_key] = None
            
            # Get initial position if exists
            position = self.position_tracker.get_position(instrument_key)
            if position:
                if position.quantity > 0:
                    self.position_side[instrument_key] = 'LONG'
                elif position.quantity < 0:
                    self.position_side[instrument_key] = 'SHORT'
        
        # Log initialization
        strategy_name = self.__class__.__name__
        logger.info(f"Initialized {strategy_name} with settings: fast={self.fast_period}, slow={self.slow_period}, signal={self.signal_period}")
        
        # Try to save strategy settings
        settings = {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period,
            'quantity': self.quantity
        }
        save_strategy_settings(strategy_name, settings)
    
    def on_tick_data(self, data: Dict[str, Any]):
        """Process incoming tick data"""
        instrument_key = data.get('instrument_key')
        
        # Ensure this is an instrument we're watching
        if not instrument_key or instrument_key not in self.instruments:
            return
        
        # Extract price data
        ltp = data.get('ltp')
        if not ltp:
            return
        
        # Update price history
        self.prices[instrument_key].append(ltp)
        
        # Keep only enough price history for calculations
        # We need at least slow_period + signal_period data points
        required_points = max(self.slow_period, self.fast_period) + self.signal_period
        if len(self.prices[instrument_key]) > required_points * 3:  # Keep 3x required data for possible analysis
            self.prices[instrument_key] = self.prices[instrument_key][-(required_points * 3):]
        
        # Calculate MACD if we have enough data
        self._calculate_macd(instrument_key)
        
        # Generate trading signals
        self._generate_signals(instrument_key)
    
    def _calculate_macd(self, instrument_key: str):
        """Calculate MACD for an instrument"""
        prices = np.array(self.prices[instrument_key])
        
        # Need at least slow_period data points
        if len(prices) < self.slow_period:
            return
        
        try:
            # Calculate fast EMA
            fast_ema = self._calculate_ema(prices, self.fast_period)
            
            # Calculate slow EMA
            slow_ema = self._calculate_ema(prices, self.slow_period)
            
            # Calculate MACD line
            macd = fast_ema - slow_ema
            
            # Calculate signal line (EMA of MACD)
            # Need at least signal_period MACD values
            if len(macd) >= self.signal_period:
                signal = self._calculate_ema(macd, self.signal_period)
                
                # Store the latest values
                self.macd_line[instrument_key] = macd[-1]
                self.signal_line[instrument_key] = signal[-1]
        
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return np.array([])
        
        # Initialize EMA with SMA for the first period points
        ema = np.zeros_like(data)
        ema[:period] = np.mean(data[:period])
        
        # Calculate multiplier
        multiplier = 2 / (period + 1)
        
        # Calculate EMA for the rest of the points
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        
        return ema
    
    def _generate_signals(self, instrument_key: str):
        """Generate trading signals based on MACD"""
        # Ensure we have both MACD and signal line values
        if self.macd_line[instrument_key] is None or self.signal_line[instrument_key] is None:
            return
        
        instrument = self.instruments[instrument_key]
        current_side = self.position_side[instrument_key]
        
        # Get current position
        position = self.position_tracker.get_position(instrument_key)
        
        # Determine current crossover state
        macd_value = self.macd_line[instrument_key]
        signal_value = self.signal_line[instrument_key]
        
        if macd_value > signal_value:
            current_crossover = 'ABOVE'
        else:
            current_crossover = 'BELOW'
        
        # Compare with previous crossover state to detect crossovers
        previous_crossover = self.previous_crossover[instrument_key]
        
        # Update previous crossover state for next time
        self.previous_crossover[instrument_key] = current_crossover
        
        # If this is the first calculation, just record the state
        if previous_crossover is None:
            return
        
        # MACD line crosses above signal line -> BUY signal
        if previous_crossover == 'BELOW' and current_crossover == 'ABOVE':
            # If we're short, close the position
            if current_side == 'SHORT' and position and position.quantity < 0:
                logger.info(f"MACD crossover BUY signal: Closing SHORT position for {instrument.symbol}")
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="BUY",
                    quantity=abs(position.quantity)
                )
            
            # Only open a new long position if not already long
            if current_side != 'LONG':
                logger.info(f"MACD crossover BUY signal: Opening LONG position for {instrument.symbol}")
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="BUY",
                    quantity=self.quantity
                )
                
                self.position_side[instrument_key] = 'LONG'
        
        # MACD line crosses below signal line -> SELL signal
        elif previous_crossover == 'ABOVE' and current_crossover == 'BELOW':
            # If we're long, close the position
            if current_side == 'LONG' and position and position.quantity > 0:
                logger.info(f"MACD crossover SELL signal: Closing LONG position for {instrument.symbol}")
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="SELL",
                    quantity=position.quantity
                )
            
            # Only open a new short position if not already short
            if current_side != 'SHORT':
                logger.info(f"MACD crossover SELL signal: Opening SHORT position for {instrument.symbol}")
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="SELL",
                    quantity=self.quantity
                )
                
                self.position_side[instrument_key] = 'SHORT'
    
    def on_position_update(self, position: Position):
        """Process position updates"""
        instrument_key = position.instrument_key
        
        # Update position side based on quantity
        if position.quantity > 0:
            self.position_side[instrument_key] = 'LONG'
        elif position.quantity < 0:
            self.position_side[instrument_key] = 'SHORT'
        else:
            self.position_side[instrument_key] = None
    
    def cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up {self.__class__.__name__} strategy")
        
        # Clear data structures
        self.prices.clear()
        self.macd_line.clear()
        self.signal_line.clear()
        self.position_side.clear()
        self.previous_crossover.clear()
    
    @classmethod
    def load_saved_settings(cls) -> Dict[str, Any]:
        """Load saved settings for this strategy"""
        strategy_name = cls.__name__
        settings = load_strategy_settings(strategy_name)
        
        if not settings:
            # Return default settings
            return {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'quantity': 1
            }
        
        return settings