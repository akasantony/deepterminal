"""
Tests for the Instrument model
"""

import pytest
from src.models.instrument import Instrument

def test_instrument_creation():
    """Test creating an instrument manually"""
    instrument = Instrument(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        instrument_type="EQ"
    )
    
    assert instrument.instrument_key == "NSE_EQ_RELIANCE"
    assert instrument.exchange == "NSE"
    assert instrument.symbol == "RELIANCE"
    assert instrument.name == "Reliance Industries Limited"
    assert instrument.instrument_type == "EQ"
    assert instrument.expiry is None
    assert instrument.strike is None
    assert instrument.option_type is None
    assert instrument.lot_size == 1
    assert instrument.tick_size == 0.05

def test_from_api_response():
    """Test creating an instrument from API response"""
    api_data = {
        "instrument_key": "NSE_EQ_RELIANCE",
        "exchange": "NSE",
        "symbol": "RELIANCE",
        "name": "Reliance Industries Limited",
        "instrument_type": "EQ",
        "lot_size": "1",
        "tick_size": "0.05"
    }
    
    instrument = Instrument.from_api_response(api_data)
    
    assert instrument.instrument_key == "NSE_EQ_RELIANCE"
    assert instrument.exchange == "NSE"
    assert instrument.symbol == "RELIANCE"
    assert instrument.name == "Reliance Industries Limited"
    assert instrument.instrument_type == "EQ"
    assert instrument.lot_size == 1
    assert instrument.tick_size == 0.05

def test_from_api_response_with_option():
    """Test creating an option instrument from API response"""
    api_data = {
        "instrument_key": "NFO_OPT_NIFTY_28JUL2022_17500_CE",
        "exchange": "NFO",
        "symbol": "NIFTY",
        "name": "Nifty 50 Index",
        "instrument_type": "CE",
        "expiry": "28JUL2022",
        "strike": "17500",
        "option_type": "CE",
        "lot_size": "50",
        "tick_size": "0.05"
    }
    
    instrument = Instrument.from_api_response(api_data)
    
    assert instrument.instrument_key == "NFO_OPT_NIFTY_28JUL2022_17500_CE"
    assert instrument.exchange == "NFO"
    assert instrument.symbol == "NIFTY"
    assert instrument.name == "Nifty 50 Index"
    assert instrument.instrument_type == "CE"
    assert instrument.expiry == "28JUL2022"
    assert instrument.strike == 17500.0
    assert instrument.option_type == "CE"
    assert instrument.lot_size == 50
    assert instrument.tick_size == 0.05

def test_str_representation():
    """Test string representation of instruments"""
    # Equity instrument
    equity = Instrument(
        instrument_key="NSE_EQ_RELIANCE",
        exchange="NSE",
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        instrument_type="EQ"
    )
    
    assert str(equity) == "RELIANCE (NSE)"
    
    # Future instrument
    future = Instrument(
        instrument_key="NFO_FUT_NIFTY_28JUL2022",
        exchange="NFO",
        symbol="NIFTY",
        name="Nifty 50 Index",
        instrument_type="FUT",
        expiry="28JUL2022"
    )
    
    assert str(future) == "NIFTY 28JUL2022 (NFO)"
    
    # Option instrument
    option = Instrument(
        instrument_key="NFO_OPT_NIFTY_28JUL2022_17500_CE",
        exchange="NFO",
        symbol="NIFTY",
        name="Nifty 50 Index",
        instrument_type="CE",
        expiry="28JUL2022",
        strike=17500.0,
        option_type="CE"
    )
    
    assert str(option) == "NIFTY 28JUL2022 17500.0 CE (NFO)"