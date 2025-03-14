"""
Base strategy class for DeepTerminal.

This module defines the abstract base class for trading strategies.
"""

from abc import ABC, abstractmethod
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
import uuid

import pandas as pd
import numpy as np

from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import OrderSide
from deepterminal.core.models.signal import Signal, SignalFactory, SignalStrength


class StrategyBase(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(
        self,
        name: str,
        instruments: List[Instrument],
        timeframe: str = "1h",
        parameters: Optional[Dict[str, Any]] = None,
        risk_per_trade: float = 0.01,  # 1% of account per trade by default
        enable_logging: bool = True,
    ):
        """
        Initialize the strategy.
        
        Args:
            name (str): Strategy name.
            instruments (List[Instrument]): List of instruments to trade.
            timeframe (str): Timeframe for analysis (e.g., "1m", "5m", "1h", "1d").
            parameters (Optional[Dict[str, Any]]): Strategy-specific parameters.
            risk_per_trade (float): Maximum risk per trade as a fraction of account.
            enable_logging (bool): Whether to enable logging.
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.instruments = instruments
        self.timeframe = timeframe
        self.parameters = parameters or {}
        self.risk_per_trade = risk_per_trade
        
        # Strategy state
        self.is_active = False
        self.last_run_time = None
        self.last_signals = []
        
        # Performance tracking
        self.total_signals = 0
        self.winning_signals = 0
        self.losing_signals = 0
        
        # Logging
        self.logger = logging.getLogger(f"strategy.{name}")
        self.enable_logging = enable_logging
        
        # Initialize any strategy-specific state
        self._initialize()
    
    def _initialize(self) -> None:
        """
        Initialize strategy-specific state. Override in subclasses if needed.
        """
        pass
    
    @abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate trading signals based on market data.
        
        Args:
            data (Dict[str, pd.DataFrame]): Market data for each instrument.
            
        Returns:
            List[Signal]: Generated trading signals.
        """
        pass
    
    def preprocess_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Preprocess market data before signal generation.
        
        Args:
            data (Dict[str, pd.DataFrame]): Market data for each instrument.
            
        Returns:
            Dict[str, pd.DataFrame]: Preprocessed market data.
        """
        processed_data = {}
        
        for symbol, df in data.items():
            # Make a copy to avoid modifying the original
            processed_df = df.copy()
            
            # Ensure the dataframe has standard OHLCV columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in processed_df.columns:
                    if self.enable_logging:
                        self.logger.warning(f"Missing required column {col} for {symbol}")
            
            # Ensure the index is a datetime
            if not isinstance(processed_df.index, pd.DatetimeIndex):
                try:
                    processed_df.index = pd.to_datetime(processed_df.index)
                except Exception as e:
                    if self.enable_logging:
                        self.logger.error(f"Error converting index to datetime for {symbol}: {e}")
            
            # Sort by timestamp
            processed_df.sort_index(inplace=True)
            
            # Store the processed dataframe
            processed_data[symbol] = processed_df
        
        return processed_data
    
    def validate_parameters(self) -> bool:
        """
        Validate that the strategy parameters are valid.
        
        Returns:
            bool: True if parameters are valid, False otherwise.
        """
        # Override in subclasses to perform strategy-specific validation
        return True
    
    def activate(self) -> bool:
        """
        Activate the strategy.
        
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        if not self.validate_parameters():
            if self.enable_logging:
                self.logger.error("Strategy parameters are invalid")
            return False
        
        self.is_active = True
        
        if self.enable_logging:
            self.logger.info(f"Strategy {self.name} activated")
        
        return True
    
    def deactivate(self) -> None:
        """Deactivate the strategy."""
        self.is_active = False
        
        if self.enable_logging:
            self.logger.info(f"Strategy {self.name} deactivated")
    
    def run(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Run the strategy on the provided data.
        
        Args:
            data (Dict[str, pd.DataFrame]): Market data for each instrument.
            
        Returns:
            List[Signal]: Generated trading signals.
        """
        if not self.is_active:
            if self.enable_logging:
                self.logger.warning("Attempt to run inactive strategy")
            return []
        
        self.last_run_time = datetime.utcnow()
        
        # Preprocess the data
        processed_data = self.preprocess_data(data)
        
        # Generate signals
        try:
            signals = self.generate_signals(processed_data)
            self.last_signals = signals
            self.total_signals += len(signals)
            
            if self.enable_logging and signals:
                self.logger.info(f"Generated {len(signals)} signals")
            
            return signals
        except Exception as e:
            if self.enable_logging:
                self.logger.error(f"Error generating signals: {e}")
            return []
    
    def update_signal_result(self, signal_id: str, win: bool, profit_loss: float) -> None:
        """
        Update the result of a signal.
        
        Args:
            signal_id (str): The ID of the signal.
            win (bool): Whether the signal resulted in a win.
            profit_loss (float): The profit/loss from the signal.
        """
        if win:
            self.winning_signals += 1
        else:
            self.losing_signals += 1
        
        # Log the result
        if self.enable_logging:
            self.logger.info(f"Signal {signal_id} result: {'Win' if win else 'Loss'}, P&L: {profit_loss}")
    
    @property
    def win_rate(self) -> float:
        """
        Calculate the win rate of the strategy.
        
        Returns:
            float: The win rate as a percentage.
        """
        total_completed = self.winning_signals + self.losing_signals
        if total_completed == 0:
            return 0.0
        
        return (self.winning_signals / total_completed) * 100
    
    def calculate_position_size(
        self, 
        account_balance: float, 
        entry_price: float, 
        stop_loss: float
    ) -> float:
        """
        Calculate the position size based on risk parameters.
        
        Args:
            account_balance (float): Current account balance.
            entry_price (float): Entry price for the trade.
            stop_loss (float): Stop loss price for the trade.
            
        Returns:
            float: The calculated position size.
        """
        # Calculate the risk amount
        risk_amount = account_balance * self.risk_per_trade
        
        # Calculate the per-unit risk
        per_unit_risk = abs(entry_price - stop_loss)
        
        if per_unit_risk == 0:
            if self.enable_logging:
                self.logger.warning("Cannot calculate position size: Zero distance between entry and stop loss")
            return 0.0
        
        # Calculate the position size
        position_size = risk_amount / per_unit_risk
        
        return position_size
    
    def update_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Update the strategy parameters.
        
        Args:
            parameters (Dict[str, Any]): New parameters.
            
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        # Store the old parameters in case validation fails
        old_parameters = self.parameters.copy()
        
        # Update the parameters
        self.parameters.update(parameters)
        
        # Validate the new parameters
        if not self.validate_parameters():
            # Restore the old parameters
            self.parameters = old_parameters
            
            if self.enable_logging:
                self.logger.error("Failed to update parameters: validation failed")
            
            return False
        
        if self.enable_logging:
            self.logger.info("Parameters updated successfully")
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the strategy's state and performance.
        
        Returns:
            Dict[str, Any]: Strategy summary.
        """
        return {
            "id": self.id,
            "name": self.name,
            "active": self.is_active,
            "instruments": [inst.symbol for inst in self.instruments],
            "timeframe": self.timeframe,
            "parameters": self.parameters,
            "risk_per_trade": self.risk_per_trade,
            "total_signals": self.total_signals,
            "winning_signals": self.winning_signals,
            "losing_signals": self.losing_signals,
            "win_rate": self.win_rate,
            "last_run_time": self.last_run_time,
        }
    
    def __str__(self) -> str:
        """Return a string representation of the strategy."""
        return f"Strategy({self.name}, active={self.is_active}, win_rate={self.win_rate:.2f}%)"