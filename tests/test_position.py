"""
Tests for the Position model
"""

import pytest
from src.models.position import Position

def test_position_creation():
    """Test creating a position manually"""
    position = Position(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        product="INTRADAY",
        quantity=10,
        overnight_quantity=0,
        multiplier=1.0,
        average_price=1500.0,
        close_price=1480.0,
        last_price=1520.0,
        unrealized_pnl=200.0,
        realized_pnl=0.0
    )
    
    assert position.instrument_key == "NSE_EQ_RELIANCE"
    assert position.exchange == "NSE"
    assert position.symbol == "RELIANCE"
    assert position.product == "INTRADAY"
    assert position.quantity == 10
    assert position.overnight_quantity == 0
    assert position.multiplier == 1.0
    assert position.average_price == 1500.0
    assert position.close_price == 1480.0
    assert position.last_price == 1520.0
    assert position.unrealized_pnl == 200.0
    assert position.realized_pnl == 0.0

def test_from_api_response():
    """Test creating a position from API response"""
    api_data = {
        "instrument_key": "NSE_EQ_RELIANCE",
        "exchange": "NSE",
        "symbol": "RELIANCE",
        "product": "INTRADAY",
        "quantity": "10",
        "overnight_quantity": "0",
        "multiplier": "1.0",
        "average_price": "1500.0",
        "close_price": "1480.0",
        "last_price": "1520.0",
        "unrealized_pnl": "200.0",
        "realized_pnl": "0.0"
    }
    
    position = Position.from_api_response(api_data)
    
    assert position.instrument_key == "NSE_EQ_RELIANCE"
    assert position.exchange == "NSE"
    assert position.symbol == "RELIANCE"
    assert position.product == "INTRADAY"
    assert position.quantity == 10
    assert position.overnight_quantity == 0
    assert position.multiplier == 1.0
    assert position.average_price == 1500.0
    assert position.close_price == 1480.0
    assert position.last_price == 1520.0
    assert position.unrealized_pnl == 200.0
    assert position.realized_pnl == 0.0

def test_position_properties():
    """Test position helper properties"""
    # Long position
    long_position = Position(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        product="INTRADAY",
        quantity=10,
        overnight_quantity=0,
        multiplier=1.0,
        average_price=1500.0,
        close_price=1480.0,
        last_price=1520.0,
        unrealized_pnl=200.0,
        realized_pnl=50.0
    )
    
    assert long_position.is_long is True
    assert long_position.is_short is False
    assert long_position.total_pnl == 250.0
    
    # Short position
    short_position = Position(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        product="INTRADAY",
        quantity=-5,
        overnight_quantity=0,
        multiplier=1.0,
        average_price=1550.0,
        close_price=1480.0,
        last_price=1520.0,
        unrealized_pnl=150.0,
        realized_pnl=30.0
    )
    
    assert short_position.is_long is False
    assert short_position.is_short is True
    assert short_position.total_pnl == 180.0
    
    # Flat position
    flat_position = Position(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        product="INTRADAY",
        quantity=0,
        overnight_quantity=0,
        multiplier=1.0,
        average_price=1500.0,
        close_price=1480.0,
        last_price=1520.0,
        unrealized_pnl=0.0,
        realized_pnl=120.0
    )
    
    