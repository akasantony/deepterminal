"""
Risk calculator for DeepTerminal.

This module provides the risk calculator for determining position sizes
based on account balance, risk tolerance, and market conditions.
"""

import logging
from typing import Dict, List, Optional, Any

from deepterminal.core.models.instrument import Instrument


class RiskCalculator:
    """Calculator for determining position sizes based on risk parameters."""
    
    def __init__(
        self,
        default_risk_percentage: float = 0.01,  # 1% of account by default
        max_risk_percentage: float = 0.05,      # 5% of account maximum
        min_risk_reward_ratio: float = 1.5,     # Minimum risk/reward ratio
        enable_logging: bool = True
    ):
        """
        Initialize the risk calculator.
        
        Args:
            default_risk_percentage (float): Default risk per trade as a percentage of account.
            max_risk_percentage (float): Maximum risk per trade as a percentage of account.
            min_risk_reward_ratio (float): Minimum risk/reward ratio to take a trade.
            enable_logging (bool): Whether to enable logging.
        """
        self.default_risk_percentage = default_risk_percentage
        self.max_risk_percentage = max_risk_percentage
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.enable_logging = enable_logging
        
        # Logging
        self.logger = logging.getLogger("risk.calculator")
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        instrument: Instrument,
        risk_percentage: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> float:
        """
        Calculate the position size based on risk parameters.
        
        Args:
            account_balance (float): Current account balance.
            entry_price (float): Entry price for the trade.
            stop_loss (float): Stop loss price for the trade.
            instrument (Instrument): The instrument to trade.
            risk_percentage (Optional[float]): Risk percentage to use. If None, uses default.
            take_profit (Optional[float]): Take profit price for the trade.
            
        Returns:
            float: The calculated position size.
        """
        # Use default risk percentage if none provided
        if risk_percentage is None:
            risk_percentage = self.default_risk_percentage
        
        # Cap risk percentage at the maximum
        risk_percentage = min(risk_percentage, self.max_risk_percentage)
        
        # Calculate the risk amount
        risk_amount = account_balance * risk_percentage
        
        # Calculate the per-unit risk
        per_unit_risk = abs(entry_price - stop_loss)
        
        if per_unit_risk <= 0:
            if self.enable_logging:
                self.logger.error("Invalid risk: Entry price and stop loss are equal or inverted")
            return 0.0
        
        # Check the risk/reward ratio if take profit is provided
        if take_profit is not None:
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / per_unit_risk
            
            # If the risk/reward ratio is below the minimum, reduce the position size
            if risk_reward_ratio < self.min_risk_reward_ratio:
                if self.enable_logging:
                    self.logger.warning(
                        f"Risk/reward ratio {risk_reward_ratio:.2f} is below minimum "
                        f"{self.min_risk_reward_ratio:.2f}, reducing position size"
                    )
                
                # Adjust the risk amount based on the ratio
                risk_amount = risk_amount * (risk_reward_ratio / self.min_risk_reward_ratio)
        
        # Calculate the raw position size
        raw_position_size = risk_amount / per_unit_risk
        
        # Adjust for instrument contract size
        contract_size = getattr(instrument, 'contract_size', 1.0)
        position_size = raw_position_size / contract_size
        
        # Round to the nearest lot size
        lot_size = instrument.lot_size
        position_size = round(position_size / lot_size) * lot_size
        
        # Ensure position size is at least one lot
        if position_size < lot_size:
            position_size = lot_size
        
        if self.enable_logging:
            self.logger.info(
                f"Calculated position size: {position_size} "
                f"(risk: {risk_percentage*100:.2f}%, "
                f"account: {account_balance:.2f}, "
                f"risk amount: {risk_amount:.2f}, "
                f"per-unit risk: {per_unit_risk:.2f})"
            )
        
        return position_size
    
    def validate_trade(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Validate a trade based on risk parameters.
        
        Args:
            entry_price (float): Entry price for the trade.
            stop_loss (float): Stop loss price for the trade.
            take_profit (Optional[float]): Take profit price for the trade.
            
        Returns:
            bool: True if the trade is valid, False otherwise.
        """
        # Check that entry and stop loss are valid
        if entry_price <= 0 or stop_loss <= 0:
            if self.enable_logging:
                self.logger.error("Invalid prices: Entry or stop loss is zero or negative")
            return False
        
        # Check that there is risk
        per_unit_risk = abs(entry_price - stop_loss)
        if per_unit_risk <= 0:
            if self.enable_logging:
                self.logger.error("Invalid risk: Entry price and stop loss are equal or inverted")
            return False
        
        # Check risk/reward ratio if take profit is provided
        if take_profit is not None:
            if take_profit <= 0:
                if self.enable_logging:
                    self.logger.error("Invalid take profit: Zero or negative")
                return False
            
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / per_unit_risk
            
            if risk_reward_ratio < self.min_risk_reward_ratio:
                if self.enable_logging:
                    self.logger.warning(
                        f"Risk/reward ratio {risk_reward_ratio:.2f} is below minimum "
                        f"{self.min_risk_reward_ratio:.2f}"
                    )
                return False
        
        return True
    
    def calculate_max_positions(
        self,
        account_balance: float,
        instruments: List[Instrument],
        entry_prices: Dict[str, float],
        stop_losses: Dict[str, float]
    ) -> Dict[str, int]:
        """
        Calculate the maximum number of positions that can be held based on risk parameters.
        
        Args:
            account_balance (float): Current account balance.
            instruments (List[Instrument]): List of instruments to consider.
            entry_prices (Dict[str, float]): Entry prices for each instrument.
            stop_losses (Dict[str, float]): Stop loss prices for each instrument.
            
        Returns:
            Dict[str, int]: Maximum number of positions for each instrument.
        """
        result = {}
        
        for instrument in instruments:
            symbol = instrument.symbol
            
            # Skip if missing price data
            if symbol not in entry_prices or symbol not in stop_losses:
                result[symbol] = 0
                continue
            
            entry_price = entry_prices[symbol]
            stop_loss = stop_losses[symbol]
            
            # Calculate position size
            position_size = self.calculate_position_size(
                account_balance=account_balance,
                entry_price=entry_price,
                stop_loss=stop_loss,
                instrument=instrument
            )
            
            # Calculate the number of positions based on lot size
            lot_size = instrument.lot_size
            max_positions = int(position_size / lot_size) if lot_size > 0 else 0
            
            result[symbol] = max_positions
        
        return result
    
    def adjust_position_for_correlation(
        self,
        position_size: float,
        correlation: float,
        correlation_threshold: float = 0.7
    ) -> float:
        """
        Adjust position size based on correlation with existing positions.
        
        Args:
            position_size (float): Original position size.
            correlation (float): Correlation coefficient with existing positions (-1.0 to 1.0).
            correlation_threshold (float): Threshold above which to reduce position size.
            
        Returns:
            float: Adjusted position size.
        """
        if abs(correlation) <= correlation_threshold:
            # Correlation is below the threshold, no adjustment needed
            return position_size
        
        # Calculate the adjustment factor
        # Higher correlation = more reduction
        adjustment_factor = 1.0 - ((abs(correlation) - correlation_threshold) / (1.0 - correlation_threshold))
        
        # Ensure the adjustment is at least 25%
        adjustment_factor = max(adjustment_factor, 0.25)
        
        # Apply the adjustment
        adjusted_size = position_size * adjustment_factor
        
        if self.enable_logging:
            self.logger.info(
                f"Adjusted position size for correlation {correlation:.2f}: "
                f"{position_size:.2f} -> {adjusted_size:.2f} "
                f"(factor: {adjustment_factor:.2f})"
            )
        
        return adjusted_size