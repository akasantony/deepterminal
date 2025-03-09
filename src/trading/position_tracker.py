"""
Position tracking system
"""

import threading
import time
from typing import Dict, List, Callable, Optional, Set

from src.api.upstox_client import UpstoxClient
from src.models.position import Position
from src.models.instrument import Instrument
from src.utils.logger import logger

class PositionTracker:
    """Tracks and manages trading positions"""
    
    def __init__(self, client: UpstoxClient):
        """Initialize with API client"""
        self.client = client
        self.positions: Dict[str, Position] = {}
        self.position_callbacks: Dict[str, List[Callable[[Position], None]]] = {}
        self.global_callbacks: List[Callable[[Dict[str, Position]], None]] = []
        self.monitoring = False
        self.monitoring_thread = None
        self.subscribed_instruments: Set[str] = set()
    
    def fetch_positions(self) -> List[Position]:
        """Fetch current positions from API"""
        response = self.client.get_positions()
        
        if response.get('status') == 'error':
            logger.error(f"Failed to fetch positions: {response.get('message')}")
            return []
        
        positions = []
        for position_data in response.get('data', []):
            position = Position.from_api_response(position_data)
            
            # Only store/return non-zero positions unless already tracking
            if position.quantity != 0 or position.instrument_key in self.positions:
                self.positions[position.instrument_key] = position
                positions.append(position)
                
                # Add to subscribed instruments for live updates
                if position.quantity != 0 and position.instrument_key not in self.subscribed_instruments:
                    self.subscribed_instruments.add(position.instrument_key)
                    try:
                        self.client.subscribe_feeds([position.instrument_key])
                    except Exception as e:
                        logger.error(f"Failed to subscribe to feed: {e}")
        
        return positions
    
    def get_position(self, instrument_key: str) -> Optional[Position]:
        """Get a position by instrument key"""
        # If not in local cache, try to fetch from API
        if instrument_key not in self.positions:
            self.fetch_positions()
        
        return self.positions.get(instrument_key)
    
    def register_position_callback(self, instrument_key: str, callback: Callable[[Position], None]):
        """Register a callback for position updates"""
        if instrument_key not in self.position_callbacks:
            self.position_callbacks[instrument_key] = []
        
        self.position_callbacks[instrument_key].append(callback)
    
    def register_global_callback(self, callback: Callable[[Dict[str, Position]], None]):
        """Register a callback for all position updates"""
        self.global_callbacks.append(callback)
    
    def start_monitoring(self, refresh_interval: float = 5.0):
        """Start monitoring positions in a background thread"""
        if self.monitoring:
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    positions = self.fetch_positions()
                    
                    # Trigger callbacks for positions with registered callbacks
                    for instrument_key, callbacks in self.position_callbacks.items():
                        if instrument_key in self.positions:
                            position = self.positions[instrument_key]
                            for callback in callbacks:
                                try:
                                    callback(position)
                                except Exception as e:
                                    logger.error(f"Error in position callback: {e}")
                    
                    # Trigger global callbacks
                    for callback in self.global_callbacks:
                        try:
                            callback(self.positions)
                        except Exception as e:
                            logger.error(f"Error in global position callback: {e}")
                    
                    # Sleep until next check
                    time.sleep(refresh_interval)
                except Exception as e:
                    logger.error(f"Error in position monitoring: {e}")
                    time.sleep(refresh_interval)
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=monitor_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring positions"""
        self.monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
    
    def setup_live_updates(self):
        """Setup live market data updates for positions"""
        # First ensure we have the latest positions
        self.fetch_positions()
        
        # Register websocket callback for position updates
        def on_tick_data(data):
            instrument_key = data.get('instrument_key')
            if not instrument_key or instrument_key not in self.positions:
                return
            
            position = self.positions[instrument_key]
            
            # Update last price and unrealized P&L
            ltp = data.get('ltp')
            if ltp:
                # Calculate new unrealized P&L
                old_last_price = position.last_price
                position.last_price = ltp
                
                # Update unrealized P&L based on price change
                if position.quantity != 0:
                    price_diff = position.last_price - position.average_price
                    position.unrealized_pnl = price_diff * position.quantity * position.multiplier
                
                # Trigger callbacks for this position
                if instrument_key in self.position_callbacks:
                    for callback in self.position_callbacks[instrument_key]:
                        try:
                            callback(position)
                        except Exception as e:
                            logger.error(f"Error in position tick callback: {e}")
                
                # Trigger global callbacks if price changed
                if old_last_price != position.last_price:
                    for callback in self.global_callbacks:
                        try:
                            callback(self.positions)
                        except Exception as e:
                            logger.error(f"Error in global tick callback: {e}")
        
        # Register the callback with the API client
        self.client.register_callback('full', on_tick_data)
        self.client.register_callback('ltpc', on_tick_data)
        
        # Subscribe to feeds for all current positions
        instrument_keys = [pos.instrument_key for pos in self.positions.values() if pos.quantity != 0]
        if instrument_keys:
            try:
                self.client.subscribe_feeds(instrument_keys)
                self.subscribed_instruments.update(instrument_keys)
            except Exception as e:
                logger.error(f"Failed to subscribe to position feeds: {e}")