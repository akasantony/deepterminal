"""
Order models for DeepTerminal.

This module defines the models for trading orders and their statuses.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
from pydantic import BaseModel, Field

from deepterminal.core.models.instrument import Instrument


class OrderType(str, Enum):
    """Types of orders that can be placed."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order side - buy or sell."""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """Time in force options for orders."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    DAY = "day"  # Day order


class OrderStatus(str, Enum):
    """Possible statuses of an order."""
    CREATED = "created"        # Order created but not yet submitted
    PENDING = "pending"        # Order submitted but not yet acknowledged
    ACCEPTED = "accepted"      # Order accepted by the exchange
    PARTIALLY_FILLED = "partially_filled"  # Order partially filled
    FILLED = "filled"          # Order completely filled
    CANCELLED = "cancelled"    # Order cancelled
    REJECTED = "rejected"      # Order rejected by the exchange
    EXPIRED = "expired"        # Order expired
    ERROR = "error"            # Error occurred with the order


class Order(BaseModel):
    """Model for a trading order."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique order ID")
    exchange_order_id: Optional[str] = Field(None, description="Order ID assigned by the exchange")
    
    # Order details
    instrument: Instrument = Field(..., description="Instrument to trade")
    side: OrderSide = Field(..., description="Buy or sell")
    order_type: OrderType = Field(..., description="Type of order")
    quantity: float = Field(..., description="Order quantity")
    price: Optional[float] = Field(None, description="Order price (for limit orders)")
    stop_price: Optional[float] = Field(None, description="Stop price (for stop orders)")
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    
    # Order lifecycle
    status: OrderStatus = Field(OrderStatus.CREATED, description="Current order status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    filled_quantity: float = Field(0.0, description="Quantity filled so far")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")
    remaining_quantity: Optional[float] = Field(None, description="Remaining quantity to fill")
    
    # Additional parameters
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")
    
    # Strategy information
    strategy_id: Optional[str] = Field(None, description="ID of the strategy that created this order")
    parent_order_id: Optional[str] = Field(None, description="ID of the parent order, if any")
    child_order_ids: List[str] = Field(default_factory=list, description="IDs of child orders, if any")
    
    # Trade management
    stop_loss_price: Optional[float] = Field(None, description="Stop loss price")
    take_profit_price: Optional[float] = Field(None, description="Take profit price")
    
    class Config:
        """Pydantic model configuration."""
        arbitrary_types_allowed = True
    
    def update_status(self, new_status: OrderStatus, filled_qty: Optional[float] = None, 
                      fill_price: Optional[float] = None) -> None:
        """
        Update the order status and fill information.
        
        Args:
            new_status (OrderStatus): The new order status.
            filled_qty (Optional[float]): Additional quantity filled.
            fill_price (Optional[float]): Price at which the order was filled.
        """
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if filled_qty is not None and filled_qty > 0:
            previous_filled = self.filled_quantity
            self.filled_quantity += filled_qty
            
            # Update average fill price
            if fill_price is not None:
                if self.average_fill_price is None:
                    self.average_fill_price = fill_price
                else:
                    self.average_fill_price = (
                        (previous_filled * self.average_fill_price) + (filled_qty * fill_price)
                    ) / self.filled_quantity
            
            # Update remaining quantity
            self.remaining_quantity = max(0, self.quantity - self.filled_quantity)
            
            # Update status based on fill
            if self.filled_quantity >= self.quantity:
                self.status = OrderStatus.FILLED
            elif self.filled_quantity > 0:
                self.status = OrderStatus.PARTIALLY_FILLED
    
    def is_active(self) -> bool:
        """
        Check if the order is still active (not filled, cancelled, rejected, or expired).
        
        Returns:
            bool: True if the order is active, False otherwise.
        """
        inactive_statuses = [
            OrderStatus.FILLED, 
            OrderStatus.CANCELLED, 
            OrderStatus.REJECTED, 
            OrderStatus.EXPIRED,
            OrderStatus.ERROR
        ]
        return self.status not in inactive_statuses
    
    def clone(self) -> 'Order':
        """
        Create a copy of this order with a new ID.
        
        Returns:
            Order: A new order with the same parameters but a new ID.
        """
        data = self.dict(exclude={'id', 'created_at', 'updated_at', 'exchange_order_id', 
                                 'filled_quantity', 'average_fill_price', 'remaining_quantity',
                                 'status'})
        return Order(**data)


class OrderFactory:
    """Factory for creating different types of orders."""
    
    @staticmethod
    def create_market_order(
        instrument: Instrument,
        side: OrderSide,
        quantity: float,
        **kwargs
    ) -> Order:
        """
        Create a market order.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell.
            quantity (float): Order quantity.
            **kwargs: Additional order parameters.
            
        Returns:
            Order: A market order.
        """
        return Order(
            instrument=instrument,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            **kwargs
        )
    
    @staticmethod
    def create_limit_order(
        instrument: Instrument,
        side: OrderSide,
        quantity: float,
        price: float,
        **kwargs
    ) -> Order:
        """
        Create a limit order.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell.
            quantity (float): Order quantity.
            price (float): Limit price.
            **kwargs: Additional order parameters.
            
        Returns:
            Order: A limit order.
        """
        return Order(
            instrument=instrument,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            **kwargs
        )
    
    @staticmethod
    def create_stop_order(
        instrument: Instrument,
        side: OrderSide,
        quantity: float,
        stop_price: float,
        **kwargs
    ) -> Order:
        """
        Create a stop order.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell.
            quantity (float): Order quantity.
            stop_price (float): Stop price.
            **kwargs: Additional order parameters.
            
        Returns:
            Order: A stop order.
        """
        return Order(
            instrument=instrument,
            side=side,
            order_type=OrderType.STOP,
            quantity=quantity,
            stop_price=stop_price,
            **kwargs
        )
    
    @staticmethod
    def create_stop_limit_order(
        instrument: Instrument,
        side: OrderSide,
        quantity: float,
        stop_price: float,
        limit_price: float,
        **kwargs
    ) -> Order:
        """
        Create a stop-limit order.
        
        Args:
            instrument (Instrument): The instrument to trade.
            side (OrderSide): Buy or sell.
            quantity (float): Order quantity.
            stop_price (float): Stop price.
            limit_price (float): Limit price.
            **kwargs: Additional order parameters.
            
        Returns:
            Order: A stop-limit order.
        """
        return Order(
            instrument=instrument,
            side=side,
            order_type=OrderType.STOP_LIMIT,
            quantity=quantity,
            price=limit_price,
            stop_price=stop_price,
            **kwargs
        )