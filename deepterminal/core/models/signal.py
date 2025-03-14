"""
Signal models for DeepTerminal.

This module defines the models for trading signals.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4
from pydantic import BaseModel, Field

from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import OrderSide


class SignalType(str, Enum):
    """Types of trading signals."""
    ENTRY = "entry"  # Signal to enter a position
    EXIT = "exit"    # Signal to exit a position
    ALERT = "alert"  # Informational alert, not actionable


class SignalStrength(str, Enum):
    """Signal strength levels."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class SignalStatus(str, Enum):
    """Possible statuses of a signal."""
    ACTIVE = "active"        # Signal is active and not yet acted upon
    EXECUTED = "executed"    # Signal has been acted upon (order placed)
    EXPIRED = "expired"      # Signal has expired without being acted upon
    CANCELLED = "cancelled"  # Signal was cancelled
    INVALIDATED = "invalidated"  # Signal was invalidated by market conditions


class Signal(BaseModel):
    """Model for a trading signal."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique signal ID")
    instrument: Instrument = Field(..., description="Instrument to trade")
    signal_type: SignalType = Field(..., description="Type of signal")
    side: OrderSide = Field(..., description="Buy or sell")
    
    # Signal metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Signal generation time")
    expiration: Optional[datetime] = Field(None, description="Signal expiration time")
    status: SignalStatus = Field(SignalStatus.ACTIVE, description="Current signal status")
    
    # Signal quality metrics
    strength: SignalStrength = Field(SignalStrength.MODERATE, description="Signal strength")
    confidence: float = Field(0.5, description="Confidence level (0.0-1.0)")
    win_probability: float = Field(0.5, description="Estimated win probability (0.0-1.0)")
    
    # Trade parameters
    entry_price: Optional[float] = Field(None, description="Suggested entry price")
    stop_loss: Optional[float] = Field(None, description="Suggested stop loss price")
    take_profit: Optional[float] = Field(None, description="Suggested take profit price")
    risk_reward_ratio: Optional[float] = Field(None, description="Calculated risk/reward ratio")
    suggested_position_size: Optional[float] = Field(None, description="Suggested position size")
    
    # Source information
    strategy_id: str = Field(..., description="ID of the strategy that generated this signal")
    indicators: Dict[str, Any] = Field(default_factory=dict, description="Indicator values that triggered this signal")
    
    # Result tracking
    result: Optional[bool] = Field(None, description="Signal result (True=Win, False=Loss, None=Unknown)")
    profit_loss: Optional[float] = Field(None, description="Actual profit/loss from this signal")
    notes: Optional[str] = Field(None, description="Additional notes about this signal")
    
    # Related entities
    order_ids: List[str] = Field(default_factory=list, description="IDs of orders created from this signal")
    position_id: Optional[str] = Field(None, description="ID of position created from this signal")
    
    class Config:
        """Pydantic model configuration."""
        arbitrary_types_allowed = True
    
    def is_active(self) -> bool:
        """
        Check if the signal is still active.
        
        Returns:
            bool: True if the signal is active, False otherwise.
        """
        if self.status != SignalStatus.ACTIVE:
            return False
        
        # Check expiration
        if self.expiration and datetime.utcnow() > self.expiration:
            self.status = SignalStatus.EXPIRED
            return False
        
        return True
    
    def execute(self, order_ids: List[str], position_id: Optional[str] = None) -> None:
        """
        Mark the signal as executed and store the related order and position IDs.
        
        Args:
            order_ids (List[str]): IDs of orders created from this signal.
            position_id (Optional[str]): ID of position created from this signal.
        """
        self.status = SignalStatus.EXECUTED
        self.order_ids.extend(order_ids)
        if position_id:
            self.position_id = position_id
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancel the signal.
        
        Args:
            reason (Optional[str]): Reason for cancellation.
        """
        self.status = SignalStatus.CANCELLED
        if reason:
            self.notes = f"Cancelled: {reason}"
    
    def invalidate(self, reason: Optional[str] = None) -> None:
        """
        Invalidate the signal due to changed market conditions.
        
        Args:
            reason (Optional[str]): Reason for invalidation.
        """
        self.status = SignalStatus.INVALIDATED
        if reason:
            self.notes = f"Invalidated: {reason}"
    
    def set_result(self, win: bool, profit_loss: float, notes: Optional[str] = None) -> None:
        """
        Set the result of the signal.
        
        Args:
            win (bool): Whether the signal resulted in a win (True) or loss (False).
            profit_loss (float): The actual profit/loss from this signal.
            notes (Optional[str]): Additional notes about the result.
        """
        self.result = win
        self.profit_loss = profit_loss
        if notes:
            self.notes = notes


class SignalFactory:
    """Factory for creating signal instances."""
    
    @staticmethod
    def create_entry_signal(
        instrument: Instrument,
        side: OrderSide,
        strategy_id: str,
        strength: SignalStrength = SignalStrength.MODERATE,
        confidence: float = 0.5,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        expiration_minutes: Optional[int] = 60,
        indicators: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Signal:
        """
        Create an entry signal.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell.
            strategy_id (str): ID of the strategy generating this signal.
            strength (SignalStrength): Signal strength.
            confidence (float): Confidence level (0.0-1.0).
            entry_price (Optional[float]): Suggested entry price.
            stop_loss (Optional[float]): Suggested stop loss price.
            take_profit (Optional[float]): Suggested take profit price.
            expiration_minutes (Optional[int]): Minutes until signal expiration. None for no expiration.
            indicators (Optional[Dict[str, Any]]): Indicator values that triggered this signal.
            **kwargs: Additional signal parameters.
            
        Returns:
            Signal: An entry signal.
        """
        expiration = None
        if expiration_minutes is not None:
            expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        # Calculate risk/reward ratio if both stop loss and take profit are provided
        risk_reward_ratio = None
        if entry_price is not None and stop_loss is not None and take_profit is not None:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            if risk > 0:
                risk_reward_ratio = reward / risk
        
        # Prepare indicators
        if indicators is None:
            indicators = {}
        
        return Signal(
            instrument=instrument,
            signal_type=SignalType.ENTRY,
            side=side,
            strategy_id=strategy_id,
            strength=strength,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            expiration=expiration,
            risk_reward_ratio=risk_reward_ratio,
            indicators=indicators,
            **kwargs
        )
    
    @staticmethod
    def create_exit_signal(
        instrument: Instrument,
        side: OrderSide,
        strategy_id: str,
        position_id: str,
        strength: SignalStrength = SignalStrength.MODERATE,
        confidence: float = 0.5,
        exit_price: Optional[float] = None,
        expiration_minutes: Optional[int] = 30,
        indicators: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Signal:
        """
        Create an exit signal.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell (opposite of the position side).
            strategy_id (str): ID of the strategy generating this signal.
            position_id (str): ID of the position to exit.
            strength (SignalStrength): Signal strength.
            confidence (float): Confidence level (0.0-1.0).
            exit_price (Optional[float]): Suggested exit price.
            expiration_minutes (Optional[int]): Minutes until signal expiration. None for no expiration.
            indicators (Optional[Dict[str, Any]]): Indicator values that triggered this signal.
            **kwargs: Additional signal parameters.
            
        Returns:
            Signal: An exit signal.
        """
        expiration = None
        if expiration_minutes is not None:
            expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        # Prepare indicators
        if indicators is None:
            indicators = {}
        
        return Signal(
            instrument=instrument,
            signal_type=SignalType.EXIT,
            side=side,
            strategy_id=strategy_id,
            position_id=position_id,
            strength=strength,
            confidence=confidence,
            entry_price=exit_price,  # Use entry_price field for exit price
            expiration=expiration,
            indicators=indicators,
            **kwargs
        )
    
    @staticmethod
    def create_alert_signal(
        instrument: Instrument,
        strategy_id: str,
        message: str,
        indicators: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Signal:
        """
        Create an alert signal (informational, not actionable).
        
        Args:
            instrument (Instrument): The instrument related to the alert.
            strategy_id (str): ID of the strategy generating this alert.
            message (str): Alert message.
            indicators (Optional[Dict[str, Any]]): Indicator values that triggered this alert.
            **kwargs: Additional signal parameters.
            
        Returns:
            Signal: An alert signal.
        """
        # Prepare indicators
        if indicators is None:
            indicators = {}
        
        return Signal(
            instrument=instrument,
            signal_type=SignalType.ALERT,
            side=OrderSide.BUY,  # Dummy value, not used for alerts
            strategy_id=strategy_id,
            notes=message,
            indicators=indicators,
            **kwargs
        )