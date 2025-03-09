"""
Instrument data model
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Instrument:
    """Model representing a tradable instrument"""
    
    instrument_key: str
    exchange: str
    symbol: str
    name: str
    instrument_type: str
    
    # Optional fields
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None
    lot_size: int = 1
    tick_size: float = 0.05
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Instrument':
        """Create an instrument from API response data"""
        return cls(
            instrument_key=data.get('instrument_key', ''),
            exchange=data.get('exchange', ''),
            symbol=data.get('symbol', ''),
            name=data.get('name', ''),
            instrument_type=data.get('instrument_type', ''),
            expiry=data.get('expiry', None),
            strike=float(data.get('strike', 0)) if data.get('strike') else None,
            option_type=data.get('option_type', None),
            lot_size=int(data.get('lot_size', 1)),
            tick_size=float(data.get('tick_size', 0.05))
        )
    
    def __str__(self) -> str:
        """String representation of the instrument"""
        if self.instrument_type == 'EQ':
            return f"{self.symbol} ({self.exchange})"
        elif self.instrument_type in ['FUT', 'CE', 'PE']:
            expiry_str = f" {self.expiry}" if self.expiry else ""
            strike_str = f" {self.strike}" if self.strike else ""
            option_type = f" {self.option_type}" if self.option_type else ""
            return f"{self.symbol}{expiry_str}{strike_str}{option_type} ({self.exchange})"
        else:
            return f"{self.symbol} {self.instrument_type} ({self.exchange})"