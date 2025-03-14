"""
Position models for DeepTerminal.

This module defines the models for trading positions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import OrderSide


class PositionSide(str, Enum):
    """Position side - long or short."""
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    """Possible statuses of a position."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"


class Position(BaseModel):
    """Model for a trading position."""
    id: str = Field(..., description="Unique position ID")
    instrument: Instrument = Field(..., description="Instrument being traded")
    side: PositionSide = Field(..., description="Long or short")
    quantity: float = Field(..., description="Position size (in contracts/units)")
    entry_price: float = Field(..., description="Average entry price")
    current_price: float = Field(..., description="Current market price")
    unrealized_pnl: float = Field(0.0, description="Unrealized profit/loss")
    realized_pnl: float = Field(0.0, description="Realized profit/loss")
    open_time: datetime = Field(..., description="Time when position was opened")
    close_time: Optional[datetime] = Field(None, description="Time when position was closed")
    status: PositionStatus = Field(PositionStatus.OPEN, description="Position status")
    
    # Risk management
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    trailing_stop: Optional[float] = Field(None, description="Trailing stop price")
    
    # Related orders
    entry_order_ids: List[str] = Field(default_factory=list, description="IDs of entry orders")
    exit_order_ids: List[str] = Field(default_factory=list, description="IDs of exit orders")
    stop_order_ids: List[str] = Field(default_factory=list, description="IDs of stop orders")
    
    # Strategy information
    strategy_id: Optional[str] = Field(None, description="ID of the strategy that created this position")
    
    # Additional data
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional position data")
    
    class Config:
        """Pydantic model configuration."""
        arbitrary_types_allowed = True
    
    def update_price(self, current_price: float) -> None:
        """
        Update the current price and recalculate unrealized PnL.
        
        Args:
            current_price (float): The current market price.
        """
        self.current_price = current_price
        self.calculate_unrealized_pnl()
    
    def calculate_unrealized_pnl(self) -> float:
        """
        Calculate the unrealized profit/loss of the position.
        
        Returns:
            float: The unrealized profit/loss.
        """
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.quantity
        
        return self.unrealized_pnl
    
    def close(self, exit_price: float, quantity: Optional[float] = None) -> float:
        """
        Close the position (fully or partially) and calculate realized PnL.
        
        Args:
            exit_price (float): The exit price.
            quantity (Optional[float]): Quantity to close. If None, closes the whole position.
            
        Returns:
            float: The realized profit/loss from this closure.
        """
        quantity_to_close = quantity if quantity is not None else self.quantity
        
        if quantity_to_close > self.quantity:
            raise ValueError(f"Cannot close more than the position size ({self.quantity})")
        
        # Calculate PnL for the closed portion
        if self.side == PositionSide.LONG:
            pnl = (exit_price - self.entry_price) * quantity_to_close
        else:  # SHORT
            pnl = (self.entry_price - exit_price) * quantity_to_close
        
        self.realized_pnl += pnl
        
        # Update position
        self.quantity -= quantity_to_close
        
        if self.quantity <= 0:
            self.status = PositionStatus.CLOSED
            self.close_time = datetime.utcnow()
        else:
            self.status = PositionStatus.PARTIALLY_CLOSED
        
        return pnl
    
    def update_stop_loss(self, price: Optional[float]) -> None:
        """
        Update the stop loss price.
        
        Args:
            price (Optional[float]): The new stop loss price. None to remove stop loss.
        """
        self.stop_loss = price
    
    def update_take_profit(self, price: Optional[float]) -> None:
        """
        Update the take profit price.
        
        Args:
            price (Optional[float]): The new take profit price. None to remove take profit.
        """
        self.take_profit = price
    
    def update_trailing_stop(self, price: Optional[float]) -> None:
        """
        Update the trailing stop price.
        
        Args:
            price (Optional[float]): The new trailing stop price. None to remove trailing stop.
        """
        self.trailing_stop = price
    
    @property
    def duration(self) -> Optional[float]:
        """
        Calculate the duration of the position in seconds.
        
        Returns:
            Optional[float]: The duration in seconds, or None if the position is still open.
        """
        end_time = self.close_time if self.close_time else datetime.utcnow()
        return (end_time - self.open_time).total_seconds()
    
    @property
    def is_open(self) -> bool:
        """
        Check if the position is open (fully or partially).
        
        Returns:
            bool: True if the position is open, False otherwise.
        """
        return self.status != PositionStatus.CLOSED
    
    @property
    def unrealized_pnl_percentage(self) -> float:
        """
        Calculate the unrealized PnL as a percentage of the initial investment.
        
        Returns:
            float: The unrealized PnL percentage.
        """
        if self.entry_price <= 0:
            return 0.0
        
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100


class PositionFactory:
    """Factory for creating position instances."""
    
    @staticmethod
    def create_position(
        instrument: Instrument,
        side: OrderSide,
        quantity: float,
        entry_price: float,
        current_price: Optional[float] = None,
        strategy_id: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        entry_order_ids: Optional[List[str]] = None,
        **kwargs
    ) -> Position:
        """
        Create a new position.
        
        Args:
            instrument (Instrument): The instrument being traded.
            side (OrderSide): Buy or sell.
            quantity (float): Position size.
            entry_price (float): Entry price.
            current_price (Optional[float]): Current market price. If None, uses entry_price.
            strategy_id (Optional[str]): ID of the strategy that created this position.
            stop_loss (Optional[float]): Stop loss price.
            take_profit (Optional[float]): Take profit price.
            entry_order_ids (Optional[List[str]]): IDs of the orders that created this position.
            **kwargs: Additional position parameters.
            
        Returns:
            Position: A new position instance.
        """
        # Convert OrderSide to PositionSide
        position_side = PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT
        
        # Use entry price as current price if not provided
        if current_price is None:
            current_price = entry_price
        
        # Prepare entry order IDs
        if entry_order_ids is None:
            entry_order_ids = []
        
        position_id = f"{instrument.symbol}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        position = Position(
            id=position_id,
            instrument=instrument,
            side=position_side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            open_time=datetime.utcnow(),
            strategy_id=strategy_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_order_ids=entry_order_ids,
            **kwargs
        )
        
        # Calculate initial unrealized PnL
        position.calculate_unrealized_pnl()
        
        return position