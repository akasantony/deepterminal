"""
Strategy interface for implementing custom trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from src.api.upstox_client import UpstoxClient
from src.models.instrument import Instrument
from src.models.position import Position
from src.models.order import Order
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker


class TradingStrategy(ABC):
    """Base class for implementing trading strategies"""
    
    def __init__(self, client: UpstoxClient, order_manager: OrderManager, position_tracker: PositionTracker):
        """Initialize with API client and trading components"""
        self.client = client
        self.order_manager = order_manager
        self.position_tracker = position_tracker
        self.instruments: Dict[str, Instrument] = {}
        self.is_running = False
        self.strategy_params: Dict[str, Any] = {}
    
    def set_instruments(self, instruments: List[Instrument]):
        """Set the instruments to trade"""
        self.instruments = {instrument.instrument_key: instrument for instrument in instruments}
    
    def set_parameters(self, params: Dict[str, Any]):
        """Set strategy parameters"""
        self.strategy_params = params
    
    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a strategy parameter value"""
        return self.strategy_params.get(name, default)
    
    def start(self):
        """Start the strategy"""
        if self.is_running:
            return
        
        self.is_running = True
        self.initialize()
        
        # Register for position updates
        for instrument_key in self.instruments:
            self.position_tracker.register_position_callback(instrument_key, self.on_position_update)
        
        # Register for market data updates
        self.setup_market_data_subscriptions()
        
        # Initialize with current positions
        positions = self.position_tracker.fetch_positions()
        for position in positions:
            if position.instrument_key in self.instruments:
                self.on_position_update(position)
    
    def stop(self):
        """Stop the strategy"""
        self.is_running = False
        self.cleanup()
    
    def setup_market_data_subscriptions(self):
        """Set up market data subscriptions"""
        instrument_keys = list(self.instruments.keys())
        if instrument_keys:
            try:
                self.client.subscribe_feeds(instrument_keys)
                
                # Register callbacks for tick data
                self.client.register_callback('full', self.on_tick_data)
                self.client.register_callback('ltpc', self.on_tick_data)
            except Exception as e:
                from src.utils.logger import logger
                logger.error(f"Failed to setup market data subscriptions: {e}")
    
    @abstractmethod
    def initialize(self):
        """Initialize the strategy - to be implemented by subclasses"""
        pass
    
    @abstractmethod
    def on_tick_data(self, data: Dict[str, Any]):
        """Process tick data - to be implemented by subclasses"""
        pass
    
    @abstractmethod
    def on_position_update(self, position: Position):
        """Process position updates - to be implemented by subclasses"""
        pass
    
    def on_order_update(self, order: Order):
        """Process order updates - can be overridden by subclasses"""
        pass
    
    def cleanup(self):
        """Clean up resources - can be overridden by subclasses"""
        pass


class SimpleMovingAverageStrategy(TradingStrategy):
    """Example strategy using Simple Moving Averages"""
    
    def initialize(self):
        """Initialize the strategy"""
        # Get strategy parameters with defaults
        self.short_period = self.get_parameter('short_period', 10)
        self.long_period = self.get_parameter('long_period', 30)
        self.quantity = self.get_parameter('quantity', 1)
        
        # Initialize data storage for each instrument
        self.prices: Dict[str, List[float]] = {}
        self.short_ma: Dict[str, Optional[float]] = {}
        self.long_ma: Dict[str, Optional[float]] = {}
        self.position_side: Dict[str, str] = {}  # 'LONG', 'SHORT', or None
        
        # Initialize price lists
        for instrument_key in self.instruments:
            self.prices[instrument_key] = []
            self.short_ma[instrument_key] = None
            self.long_ma[instrument_key] = None
            self.position_side[instrument_key] = None
            
            # Get initial position if exists
            position = self.position_tracker.get_position(instrument_key)
            if position:
                if position.quantity > 0:
                    self.position_side[instrument_key] = 'LONG'
                elif position.quantity < 0:
                    self.position_side[instrument_key] = 'SHORT'
    
    def on_tick_data(self, data: Dict[str, Any]):
        """Process incoming tick data"""
        instrument_key = data.get('instrument_key')
        
        # Ensure this is an instrument we're watching
        if not instrument_key or instrument_key not in self.instruments:
            return
        
        # Extract price data
        ltp = data.get('ltp')
        if not ltp:
            return
        
        # Update price history
        self.prices[instrument_key].append(ltp)
        
        # Keep only enough price history for calculations
        max_period = max(self.short_period, self.long_period)
        if len(self.prices[instrument_key]) > max_period:
            self.prices[instrument_key] = self.prices[instrument_key][-max_period:]
        
        # Calculate moving averages
        self._calculate_moving_averages(instrument_key)
        
        # Generate trading signals
        self._generate_signals(instrument_key)
    
    def _calculate_moving_averages(self, instrument_key: str):
        """Calculate moving averages for an instrument"""
        prices = self.prices[instrument_key]
        
        # Calculate short MA if enough data
        if len(prices) >= self.short_period:
            self.short_ma[instrument_key] = sum(prices[-self.short_period:]) / self.short_period
        
        # Calculate long MA if enough data
        if len(prices) >= self.long_period:
            self.long_ma[instrument_key] = sum(prices[-self.long_period:]) / self.long_period
    
    def _generate_signals(self, instrument_key: str):
        """Generate trading signals based on moving averages"""
        # Ensure we have both MAs calculated
        if self.short_ma[instrument_key] is None or self.long_ma[instrument_key] is None:
            return
        
        instrument = self.instruments[instrument_key]
        current_side = self.position_side[instrument_key]
        
        # Get current position
        position = self.position_tracker.get_position(instrument_key)
        
        # Check for buy signal (short MA crosses above long MA)
        if self.short_ma[instrument_key] > self.long_ma[instrument_key]:
            # If we're not already long, go long
            if current_side != 'LONG':
                # Close any existing short position
                if current_side == 'SHORT' and position and position.quantity < 0:
                    self.order_manager.place_market_order(
                        instrument=instrument,
                        transaction_type="BUY",
                        quantity=abs(position.quantity)
                    )
                
                # Open a new long position
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="BUY",
                    quantity=self.quantity
                )
                
                self.position_side[instrument_key] = 'LONG'
        
        # Check for sell signal (short MA crosses below long MA)
        elif self.short_ma[instrument_key] < self.long_ma[instrument_key]:
            # If we're not already short, go short
            if current_side != 'SHORT':
                # Close any existing long position
                if current_side == 'LONG' and position and position.quantity > 0:
                    self.order_manager.place_market_order(
                        instrument=instrument,
                        transaction_type="SELL",
                        quantity=position.quantity
                    )
                
                # Open a new short position
                self.order_manager.place_market_order(
                    instrument=instrument,
                    transaction_type="SELL",
                    quantity=self.quantity
                )
                
                self.position_side[instrument_key] = 'SHORT'
    
    def on_position_update(self, position: Position):
        """Process position updates"""
        instrument_key = position.instrument_key
        
        # Update position side based on quantity
        if position.quantity > 0:
            self.position_side[instrument_key] = 'LONG'
        elif position.quantity < 0:
            self.position_side[instrument_key] = 'SHORT'
        else:
            self.position_side[instrument_key] = None