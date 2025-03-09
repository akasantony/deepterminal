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
        # Ensure client is authenticated before making the request
        if not self.client.authenticator.is_authenticated():
            if not self.client.authenticator.authenticate():
                logger.error("Cannot fetch positions: Authentication failed")
                return []
        
        response = self.client.get_positions()
        
        if response.get('status') == 'error':
            logger.error(f"Failed to fetch positions: {response.get('message')}")
            return []
        
        positions = []
        
        # Handle the new response format for positions
        data = response.get('data', {})
        positions_data = []
        
        # Check if the data is in the expected format
        if isinstance(data, dict):
            # For the new API format that might return categories of positions
            if 'short_term_positions' in data:
                positions_data.extend(data['short_term_positions'])
            elif 'day_positions' in data:
                positions_data.extend(data['day_positions'])
            elif 'holdings' in data:
                positions_data.extend(data['holdings'])
            # If positions are directly in data
            elif 'positions' in data:
                positions_data.extend(data['positions'])
            # If data itself is the positions list
            elif len(data) > 0 and isinstance(list(data.values())[0], dict):
                positions_data.extend(data.values())
        elif isinstance(data, list):
            # Direct list of positions
            positions_data = data
        
        for position_data in positions_data:
            try:
                position = Position.from_api_response(position_data)
                
                # Only store/return non-zero positions unless already tracking
                if position.quantity != 0 or position.instrument_key in self.positions:
                    self.positions[position.instrument_key] = position
                    positions.append(position)
                    
                    # Add to subscribed instruments for live updates
                    if position.quantity != 0 and position.instrument_key not in self.subscribed_instruments:
                        self.subscribed_instruments.add(position.instrument_key)
                        try:
                            # Ensure WebSocket is connected before subscribing
                            if not self.client.ws_connected:
                                self.client.connect_websocket()
                                # Give it a moment to connect
                                time.sleep(1)
                            
                            if self.client.ws_connected:
                                self.client.subscribe_feeds([position.instrument_key])
                        except Exception as e:
                            logger.error(f"Failed to subscribe to feed: {e}")
            except Exception as e:
                logger.error(f"Error processing position data: {e}")
        
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
    
    def start_monitoring(self, refresh_interval: float = 5.0, max_retries: int = 3):
        """Start monitoring positions in a background thread"""
        if self.monitoring:
            return True
        
        # Check authentication first - try multiple times if needed
        for retry in range(max_retries):
            try:
                if not self.client.authenticator.is_authenticated():
                    if not self.client.authenticator.authenticate():
                        logger.error("Cannot start position monitoring: Authentication failed")
                        if retry < max_retries - 1:
                            logger.info(f"Retrying authentication ({retry+1}/{max_retries})")
                            time.sleep(2)  # Wait before retrying
                            continue
                        return False
                
                # Test API access before starting monitoring
                test_response = self.client.get_profile()
                if isinstance(test_response, dict) and test_response.get('status') == 'error':
                    logger.error(f"API access test failed: {test_response.get('message')}")
                    if retry < max_retries - 1:
                        logger.info(f"Retrying API access test ({retry+1}/{max_retries})")
                        time.sleep(2)
                        continue
                    return False
                
                # API access successful, proceed with monitoring
                break
            except Exception as e:
                logger.error(f"Error testing API access: {e}")
                if retry < max_retries - 1:
                    logger.info(f"Retrying ({retry+1}/{max_retries})")
                    time.sleep(2)
                    continue
                return False
                    
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
        return True
    
    def stop_monitoring(self):
        """Stop monitoring positions"""
        self.monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
    
    def setup_live_updates(self):
        """Setup live market data updates for positions"""
        # Make sure we're authenticated first
        if not self.client.authenticator.is_authenticated():
            if not self.client.authenticator.authenticate():
                logger.error("Cannot setup live updates: Authentication failed")
                return False
        
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
        
        # First ensure that WebSocket is connected
        if not self.client.ws_connected:
            if not self.client.connect_websocket():
                logger.error("Failed to connect WebSocket")
                return False
            # Give it a moment to connect
            time.sleep(1)
        
        # Subscribe to feeds for all current positions
        instrument_keys = [pos.instrument_key for pos in self.positions.values() if pos.quantity != 0]
        if instrument_keys:
            try:
                success = self.client.subscribe_feeds(instrument_keys)
                if success:
                    self.subscribed_instruments.update(instrument_keys)
                    return True
                else:
                    logger.error("Failed to subscribe to position feeds")
                    return False
            except Exception as e:
                logger.error(f"Failed to subscribe to position feeds: {e}")
                return False
        
        return True