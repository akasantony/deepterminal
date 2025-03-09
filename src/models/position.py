"""
Position data model
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Position:
    """Model representing a trading position"""
    
    instrument_key: str
    exchange: str
    symbol: str
    product: str
    quantity: int
    overnight_quantity: int
    multiplier: float
    average_price: float
    close_price: float
    last_price: float
    unrealized_pnl: float
    realized_pnl: float
    
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
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Position':
        """Create a position from API response data"""
        return cls(
            instrument_key=data.get('instrument_key', ''),
            exchange=data.get('exchange', ''),
            symbol=data.get('symbol', ''),
            product=data.get('product', ''),
            quantity=int(data.get('quantity', 0)),
            overnight_quantity=int(data.get('overnight_quantity', 0)),
            multiplier=float(data.get('multiplier', 1)),
            average_price=float(data.get('average_price', 0)),
            close_price=float(data.get('close_price', 0)),
            last_price=float(data.get('last_price', 0)),
            unrealized_pnl=float(data.get('unrealized_pnl', 0)),
            realized_pnl=float(data.get('realized_pnl', 0))
        )
    
    def __str__(self) -> str:
        """String representation of the position"""
        position_type = "LONG" if self.is_long else "SHORT" if self.is_short else "FLAT"
        return f"{position_type} {abs(self.quantity)} {self.symbol} @ {self.average_price} (P&L: ₹{self.total_pnl:.2f})"