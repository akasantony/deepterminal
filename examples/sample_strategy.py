"""
Sample trading strategy implementation
"""

from typing import Dict, Any
import pandas as pd
import numpy as np

from src.trading.strategy import TradingStrategy
from src.models.position import Position


class RSIStrategy(TradingStrategy):
    """
    RSI (Relative Strength Index) based trading strategy
    
    This strategy:
    - Calculates RSI based on price movements
    - Goes long when RSI crosses below oversold threshold (30)
    - Goes short when RSI crosses above overbought threshold (70)
    - Closes positions when RSI returns to neutral zone (40-60)
    """
    
    def initialize(self):
        """Initialize the strategy"""
        # Get strategy parameters with defaults
        self.rsi_period = self.get_parameter('rsi_period', 14)
        self.overbought = self.get_parameter('overbought', 70)
        self.oversold = self.get_parameter('oversold', 30)
        self.neutral_high = self.get_parameter('neutral_high', 60)
        self.neutral_low = self.get_parameter('neutral_low', 40)
        self.quantity = self.get_parameter('quantity', 1)
        
        # Initialize data storage for each instrument
        self.prices: Dict[str, list] = {}
        self.rsi_values: Dict[str, float] = {}
        self.position_side: Dict[str, str] = {}  # 'LONG', 'SHORT', or None
        
        # Initialize for each instrument
        for instrument_key in self.instruments:
            self.prices[instrument_key] = []
            self.rsi_values[instrument_key] = 50  # Start with neutral RSI
            self.position_side[instrument_key] = None
            
            # Get initial position if exists
            position = self.position_tracker.get_position(instrument_key)
            if position:
                if position.quantity > 0:
                    self.position_side[instrument_key] = 'LONG'
                elif position.quantity < 0:
                    self.position_side[instrument_key] = 'SHORT'
    
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
        if len(self.prices[instrument_key]) > self.rsi_period * 3:
            self.prices[instrument_key] = self.prices[instrument_key][-(self.rsi_period * 3):]
        
        # Calculate RSI if we have enough data
        if len(self.prices[instrument_key]) >= self.rsi_period + 1:
            self._calculate_rsi(instrument_key)
            
            # Generate trading signals
            self._generate_signals(instrument_key)
    
    def _calculate_rsi(self, instrument_key: str):
        """Calculate RSI for an instrument"""
        prices = np.array(self.prices[instrument_key])
        
        # Need at least rsi_period + 1 data points to calculate RSI
        if len(prices) <= self.rsi_period:
            return
        
        # Calculate price changes
        deltas = np.diff(prices)
        
        # Calculate gains (positive changes) and losses (negative changes)
        gains = np.copy(deltas)
        losses = np.copy(deltas)
        
        gains[gains < 0] = 0
        losses[losses > 0] = 0
        losses = abs(losses)
        
        # Calculate average gains and losses over RSI period
        avg_gain = np.sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = np.sum(losses[-self.rsi_period:]) / self.rsi_period
        
        if avg_loss == 0:
            # If no losses, RSI is 100
            rsi = 100
        else:
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Store RSI value
        self.rsi_values[instrument_key] = rsi
    
    def _generate_signals(self, instrument_key: str):
        """Generate trading signals based on RSI"""
        instrument = self.instruments[instrument_key]
        current_side = self.position_side[instrument_key]
        current_rsi = self.rsi_values[instrument_key]
        
        # Get current position
        position = self.position_tracker.get_position(instrument_key)
        
        # RSI crossed below oversold threshold -> BUY signal
        if current_rsi < self.oversold and (current_side is None or current_side == 'SHORT'):
            # If we're short, close the position
            if current_side == 'SHORT' and position and position.quantity < 0:
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="BUY",
                    quantity=abs(position.quantity)
                )
            
            # Open a new long position
            self.order_manager.place_market_order(
                instrument=instrument,
                transaction_type="BUY",
                quantity=self.quantity
            )
            
            self.position_side[instrument_key] = 'LONG'
        
        # RSI crossed above overbought threshold -> SELL signal
        elif current_rsi > self.overbought and (current_side is None or current_side == 'LONG'):
            # If we're long, close the position
            if current_side == 'LONG' and position and position.quantity > 0:
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="SELL",
                    quantity=position.quantity
                )
            
            # Open a new short position
            self.order_manager.place_market_order(
                instrument=instrument,
                transaction_type="SELL",
                quantity=self.quantity
            )
            
            self.position_side[instrument_key] = 'SHORT'
        
        # RSI returned to neutral zone -> Close position
        elif (self.neutral_low <= current_rsi <= self.neutral_high):
            # Close position if we have one
            if position:
                if current_side == 'LONG' and position.quantity > 0:
                    self.order_manager.place_market_order(
                        instrument=instrument,
                        transaction_type="SELL",
                        quantity=position.quantity
                    )
                    self.position_side[instrument_key] = None
                
                elif current_side == 'SHORT' and position.quantity < 0:
                    self.order_manager.place_market_order(
                        instrument=instrument,
                        transaction_type="BUY",
                        quantity=abs(position.quantity)
                    )
                    self.position_side[instrument_key] = None
    
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