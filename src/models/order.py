"""
Order data model
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Order:
    """Model representing a trading order"""
    
    order_id: str
    instrument_key: str
    exchange: str
    symbol: str
    transaction_type: str  # BUY or SELL
    product: str  # INTRADAY, DELIVERY, etc.
    order_type: str  # MARKET, LIMIT, SL, SL-M
    quantity: int
    status: str
    
    # Optional fields
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: int = 0
    validity: str = "DAY"
    variety: str = "NORMAL"
    
    # Status information
    order_timestamp: Optional[datetime] = None
    exchange_order_id: Optional[str] = None
    average_price: Optional[float] = None
    filled_quantity: int = 0
    pending_quantity: Optional[int] = None
    cancelled_quantity: int = 0
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Order':
        """Create an order from API response data"""
        order_timestamp = None
        if data.get('order_timestamp'):
            try:
                order_timestamp = datetime.fromisoformat(data['order_timestamp'].replace('Z', '+00:00'))
            except ValueError:
                pass
        
        return cls(
            order_id=data.get('order_id', ''),
            instrument_key=data.get('instrument_key', ''),
            exchange=data.get('exchange', ''),
            symbol=data.get('symbol', ''),
            transaction_type=data.get('transaction_type', ''),
            product=data.get('product', ''),
            order_type=data.get('order_type', ''),
            quantity=int(data.get('quantity', 0)),
            status=data.get('status', 'PENDING'),
            price=float(data.get('price', 0)) if data.get('price') else None,
            trigger_price=float(data.get('trigger_price', 0)) if data.get('trigger_price') else None,
            disclosed_quantity=int(data.get('disclosed_quantity', 0)),
            validity=data.get('validity', 'DAY'),
            variety=data.get('variety', 'NORMAL'),
            order_timestamp=order_timestamp,
            exchange_order_id=data.get('exchange_order_id'),
            average_price=float(data.get('average_price', 0)) if data.get('average_price') else None,
            filled_quantity=int(data.get('filled_quantity', 0)),
            pending_quantity=int(data.get('pending_quantity', 0)) if data.get('pending_quantity') is not None else None,
            cancelled_quantity=int(data.get('cancelled_quantity', 0)),
        )
    
    def __str__(self) -> str:
        """String representation of the order"""
        price_str = f" @ {self.price}" if self.price else ""
        trigger_str = f" (Trigger: {self.trigger_price})" if self.trigger_price else ""
        return f"Order {self.order_id}: {self.transaction_type} {self.quantity} {self.symbol} {self.order_type}{price_str}{trigger_str} - {self.status}"