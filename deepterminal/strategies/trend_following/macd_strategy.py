"""
MACD Strategy implementation for DeepTerminal.

This module implements a trading strategy based on the MACD (Moving Average Convergence Divergence) indicator.
"""

import logging
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
import ta

from deepterminal.strategies.base import StrategyBase
from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import OrderSide
from deepterminal.core.models.signal import Signal, SignalFactory, SignalStrength


class MACDStrategy(StrategyBase):
    """Strategy based on the MACD indicator."""
    
    def __init__(
        self,
        instruments: List[Instrument],
        timeframe: str = "1h",
        parameters: Optional[Dict[str, Any]] = None,
        risk_per_trade: float = 0.01,
        enable_logging: bool = True
    ):
        """
        Initialize the MACD strategy.
        
        Args:
            instruments (List[Instrument]): List of instruments to trade.
            timeframe (str): Timeframe for analysis (e.g., "1m", "5m", "1h", "1d").
            parameters (Optional[Dict[str, Any]]): Strategy-specific parameters.
            risk_per_trade (float): Maximum risk per trade as a fraction of account.
            enable_logging (bool): Whether to enable logging.
        """
        # Default MACD parameters
        default_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "atr_period": 14,
            "stop_loss_atr_multiplier": 2.0,
            "take_profit_atr_multiplier": 3.0,
            "volume_filter_enabled": True,
            "min_volume_percentile": 50,
            "signal_threshold": 0.0,  # Signal line crossover threshold
            "confirmation_period": 1,  # Number of periods to confirm a signal
        }
        
        # Merge default with provided parameters
        merged_params = default_params.copy()
        if parameters:
            merged_params.update(parameters)
        
        super().__init__(
            name="MACD",
            instruments=instruments,
            timeframe=timeframe,
            parameters=merged_params,
            risk_per_trade=risk_per_trade,
            enable_logging=enable_logging
        )
    
    def validate_parameters(self) -> bool:
        """
        Validate that the strategy parameters are valid.
        
        Returns:
            bool: True if parameters are valid, False otherwise.
        """
        # Validate period parameters
        for param_name in ["fast_period", "slow_period", "signal_period", "atr_period", "confirmation_period"]:
            if param_name not in self.parameters:
                if self.enable_logging:
                    self.logger.error(f"Missing required parameter: {param_name}")
                return False
            
            if not isinstance(self.parameters[param_name], int) or self.parameters[param_name] <= 0:
                if self.enable_logging:
                    self.logger.error(f"Parameter {param_name} must be a positive integer")
                return False
        
        # Validate that fast_period < slow_period
        if self.parameters["fast_period"] >= self.parameters["slow_period"]:
            if self.enable_logging:
                self.logger.error("fast_period must be less than slow_period")
            return False
        
        # Validate multiplier parameters
        for param_name in ["stop_loss_atr_multiplier", "take_profit_atr_multiplier"]:
            if param_name not in self.parameters:
                if self.enable_logging:
                    self.logger.error(f"Missing required parameter: {param_name}")
                return False
            
            if not isinstance(self.parameters[param_name], (int, float)) or self.parameters[param_name] <= 0:
                if self.enable_logging:
                    self.logger.error(f"Parameter {param_name} must be a positive number")
                return False
        
        # Validate volume filter parameters
        if "volume_filter_enabled" in self.parameters and self.parameters["volume_filter_enabled"]:
            if "min_volume_percentile" not in self.parameters:
                if self.enable_logging:
                    self.logger.error("Missing required parameter: min_volume_percentile")
                return False
            
            if not isinstance(self.parameters["min_volume_percentile"], (int, float)) or \
               not 0 <= self.parameters["min_volume_percentile"] <= 100:
                if self.enable_logging:
                    self.logger.error("Parameter min_volume_percentile must be between 0 and 100")
                return False
        
        return True
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate MACD and ATR indicators.
        
        Args:
            df (pd.DataFrame): Price data with OHLCV columns.
            
        Returns:
            pd.DataFrame: DataFrame with added indicator columns.
        """
        # Extract parameters
        fast_period = self.parameters["fast_period"]
        slow_period = self.parameters["slow_period"]
        signal_period = self.parameters["signal_period"]
        atr_period = self.parameters["atr_period"]
        
        # Calculate MACD
        macd = ta.trend.MACD(
            close=df["close"],
            window_slow=slow_period,
            window_fast=fast_period,
            window_sign=signal_period
        )
        
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_histogram"] = macd.macd_diff()
        
        # Calculate ATR for stop loss and take profit
        atr = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=atr_period
        )
        
        df["atr"] = atr.average_true_range()
        
        # Calculate volume percentile if volume filter is enabled
        if self.parameters["volume_filter_enabled"] and "volume" in df.columns:
            df["volume_pct"] = df["volume"].rolling(window=50).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100
            )
        
        return df
    
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate trading signals based on MACD crossovers.
        
        Args:
            data (Dict[str, pd.DataFrame]): Market data for each instrument.
            
        Returns:
            List[Signal]: Generated trading signals.
        """
        signals = []
        
        for symbol, df in data.items():
            if len(df) < max(self.parameters["slow_period"], self.parameters["atr_period"]) + 10:
                if self.enable_logging:
                    self.logger.warning(f"Not enough data for {symbol} to calculate indicators")
                continue
            
            # Find the instrument
            instrument = next((i for i in self.instruments if i.symbol == symbol), None)
            if not instrument:
                if self.enable_logging:
                    self.logger.warning(f"Instrument not found for symbol {symbol}")
                continue
            
            # Calculate indicators
            df = self.calculate_indicators(df)
            
            # Check for NaN values
            if df["macd"].isna().any() or df["macd_signal"].isna().any() or df["atr"].isna().any():
                if self.enable_logging:
                    self.logger.warning(f"NaN values in indicators for {symbol}")
                continue
            
            # Apply the signal generation logic
            signal_threshold = self.parameters["signal_threshold"]
            confirmation_period = self.parameters["confirmation_period"]
            
            # Check for buy signals
            buy_signal_condition = (
                (df["macd"].shift(confirmation_period) < df["macd_signal"].shift(confirmation_period) - signal_threshold) &
                (df["macd"] > df["macd_signal"] + signal_threshold)
            )
            
            # Check for sell signals
            sell_signal_condition = (
                (df["macd"].shift(confirmation_period) > df["macd_signal"].shift(confirmation_period) + signal_threshold) &
                (df["macd"] < df["macd_signal"] - signal_threshold)
            )
            
            # Apply volume filter if enabled
            if self.parameters["volume_filter_enabled"] and "volume_pct" in df.columns:
                min_volume_pct = self.parameters["min_volume_percentile"]
                volume_filter = df["volume_pct"] > min_volume_pct
                buy_signal_condition = buy_signal_condition & volume_filter
                sell_signal_condition = sell_signal_condition & volume_filter
            
            # Get the latest data point
            latest = df.iloc[-1]
            
            # Check if we have a signal
            if buy_signal_condition.iloc[-1]:
                # Calculate stop loss and take profit
                stop_loss = latest["close"] - (latest["atr"] * self.parameters["stop_loss_atr_multiplier"])
                take_profit = latest["close"] + (latest["atr"] * self.parameters["take_profit_atr_multiplier"])
                
                # Determine signal strength
                histogram_strength = abs(latest["macd_histogram"]) / latest["atr"]
                
                if histogram_strength > 0.5:
                    strength = SignalStrength.STRONG
                elif histogram_strength > 0.25:
                    strength = SignalStrength.MODERATE
                else:
                    strength = SignalStrength.WEAK
                
                # Calculate confidence
                confidence = min(0.5 + (histogram_strength / 2), 0.95)
                
                # Create the signal
                indicators = {
                    "macd": latest["macd"],
                    "macd_signal": latest["macd_signal"],
                    "macd_histogram": latest["macd_histogram"],
                    "atr": latest["atr"],
                }
                
                signal = SignalFactory.create_entry_signal(
                    instrument=instrument,
                    side=OrderSide.BUY,
                    strategy_id=self.id,
                    strength=strength,
                    confidence=confidence,
                    entry_price=latest["close"],
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators=indicators
                )
                
                signals.append(signal)
                
                if self.enable_logging:
                    self.logger.info(
                        f"Buy signal for {symbol}: entry={latest['close']:.2f}, "
                        f"stop={stop_loss:.2f}, target={take_profit:.2f}"
                    )
            
            elif sell_signal_condition.iloc[-1]:
                # Calculate stop loss and take profit
                stop_loss = latest["close"] + (latest["atr"] * self.parameters["stop_loss_atr_multiplier"])
                take_profit = latest["close"] - (latest["atr"] * self.parameters["take_profit_atr_multiplier"])
                
                # Determine signal strength
                histogram_strength = abs(latest["macd_histogram"]) / latest["atr"]
                
                if histogram_strength > 0.5:
                    strength = SignalStrength.STRONG
                elif histogram_strength > 0.25:
                    strength = SignalStrength.MODERATE
                else:
                    strength = SignalStrength.WEAK
                
                # Calculate confidence
                confidence = min(0.5 + (histogram_strength / 2), 0.95)
                
                # Create the signal
                indicators = {
                    "macd": latest["macd"],
                    "macd_signal": latest["macd_signal"],
                    "macd_histogram": latest["macd_histogram"],
                    "atr": latest["atr"],
                }
                
                signal = SignalFactory.create_entry_signal(
                    instrument=instrument,
                    side=OrderSide.SELL,
                    strategy_id=self.id,
                    strength=strength,
                    confidence=confidence,
                    entry_price=latest["close"],
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators=indicators
                )
                
                signals.append(signal)
                
                if self.enable_logging:
                    self.logger.info(
                        f"Sell signal for {symbol}: entry={latest['close']:.2f}, "
                        f"stop={stop_loss:.2f}, target={take_profit:.2f}"
                    )
        
        return signals