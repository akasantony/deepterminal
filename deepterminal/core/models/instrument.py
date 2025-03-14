"""
Financial instrument models for DeepTerminal.

This module defines the models for financial instruments such as futures and options.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class InstrumentType(str, Enum):
    """Types of financial instruments supported by the application."""
    STOCK = "stock"
    FUTURE = "future"
    CALL_OPTION = "call_option"
    PUT_OPTION = "put_option"
    FOREX = "forex"
    CRYPTO = "crypto"


class ExpiryType(str, Enum):
    """Types of expiry for derivatives."""
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    QUARTERLY = "quarterly"
    PERPETUAL = "perpetual"  # For perpetual futures


class Instrument(BaseModel):
    """Base model for all financial instruments."""
    symbol: str = Field(..., description="Trading symbol for the instrument")
    exchange: str = Field(..., description="Exchange where the instrument is traded")
    instrument_type: InstrumentType = Field(..., description="Type of financial instrument")
    tick_size: float = Field(0.01, description="Minimum price movement")
    lot_size: float = Field(1.0, description="Standard trading unit size")
    margin_requirement: Optional[float] = Field(None, description="Margin requirement percentage")
    trading_hours: Optional[dict] = Field(None, description="Trading hours information")
    description: Optional[str] = Field(None, description="Description of the instrument")
    
    class Config:
        """Pydantic model configuration."""
        arbitrary_types_allowed = True


class DerivativeInstrument(Instrument):
    """Base model for derivative instruments (futures and options)."""
    underlying: str = Field(..., description="Symbol of the underlying asset")
    expiry_date: datetime = Field(..., description="Expiration date and time")
    expiry_type: ExpiryType = Field(..., description="Type of expiry")
    contract_size: float = Field(1.0, description="Size of one contract")
    settlement_type: str = Field("cash", description="Settlement type (cash or physical)")
    
    class Config:
        """Pydantic model configuration."""
        arbitrary_types_allowed = True


class Future(DerivativeInstrument):
    """Model for futures contracts."""
    
    def __init__(self, **data):
        """Initialize a Future with instrument type set to FUTURE."""
        super().__init__(instrument_type=InstrumentType.FUTURE, **data)


class Option(DerivativeInstrument):
    """Model for options contracts."""
    strike_price: float = Field(..., description="Strike price of the option")
    is_call: bool = Field(..., description="True for call option, False for put option")
    
    def __init__(self, **data):
        """Initialize an Option with the appropriate instrument type."""
        # Set the instrument type based on whether it's a call or put
        instr_type = InstrumentType.CALL_OPTION if data.get('is_call', True) else InstrumentType.PUT_OPTION
        super().__init__(instrument_type=instr_type, **data)


class InstrumentFactory:
    """Factory for creating instrument instances."""
    
    @staticmethod
    def create_instrument(data: dict) -> Instrument:
        """
        Create an instrument instance based on the provided data.
        
        Args:
            data (dict): Dictionary containing instrument data.
            
        Returns:
            Instrument: The created instrument instance.
        """
        instrument_type = data.get('instrument_type')
        
        if instrument_type == InstrumentType.FUTURE or instrument_type == 'future':
            return Future(**data)
        elif instrument_type in [InstrumentType.CALL_OPTION, InstrumentType.PUT_OPTION] or \
             instrument_type in ['call_option', 'put_option']:
            return Option(**data)
        else:
            return Instrument(**data)