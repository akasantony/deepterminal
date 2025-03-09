"""
Upstox WebSocket client implementation
"""

import json
import threading
import time
from typing import Dict, List, Set, Callable, Optional, Any
import websocket

from src.auth.authenticator import UpstoxAuthenticator
from src.utils.logger import logger


class UpstoxWebSocket:
    """Client for Upstox WebSocket market data feed"""
    
    # The WebSocket URL might need to be adjusted based on Upstox's latest documentation
    WS_URL = "wss://api-v2.upstox.com/feed/market-data/ws"  # Try alternative URL
    
    def __init__(self, authenticator: UpstoxAuthenticator):
        """Initialize with authenticator"""
        self.authenticator = authenticator
        self.ws = None
        self.ws_thread = None
        self.callbacks = {}
        self.connected = False
        self.subscribed_instruments = set()
    
    def connect(self) -> bool:
        """Connect to the WebSocket feed"""
        if not self.authenticator.is_authenticated():
            if not self.authenticator.authenticate():
                logger.error("Cannot connect WebSocket: Authentication failed")
                return False
        
        # Start WebSocket thread if not already running
        if self.ws_thread is None or not self.ws_thread.is_alive():
            self.ws_thread = threading.Thread(target=self._run_websocket)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Wait for connection to establish
            timeout = 5.0
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.2)
            
            return self.connected
        
        return self.connected
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Log first few messages for debugging
            if isinstance(data, dict):
                logger.debug(f"WebSocket message received: {list(data.keys())[:5]}")
            else:
                logger.debug(f"WebSocket message received: {type(data)}")
            
            # Determine message type
            msg_type = None
            if isinstance(data, dict):
                if 'type' in data:
                    msg_type = data['type']
                elif 'message-type' in data:
                    msg_type = data['message-type']
                elif 'message_type' in data:
                    msg_type = data['message_type']
                elif 'status' in data:
                    msg_type = 'status'
            
            # Handle authentication status
            if msg_type == 'status' or msg_type == 'authenticate':
                status = data.get('status')
                if status == 'success':
                    logger.info("WebSocket authentication successful")
                    self.connected = True
                else:
                    error_msg = data.get('message', 'Unknown error')
                    logger.error(f"WebSocket authentication failed: {error_msg}")
                    self.connected = False
            
            # Call callbacks for this message type
            if msg_type and msg_type in self.callbacks:
                for callback in self.callbacks[msg_type]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in WebSocket callback: {e}")
            
            # Also call general data callbacks for market data
            if 'data' in self.callbacks:
                for callback in self.callbacks['data']:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in WebSocket data callback: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established, authenticating...")
        
        if not self.authenticator.is_authenticated():
            logger.error("WebSocket authentication failed: No valid token")
            ws.close()
            return
        
        # Try different authentication message formats (based on Upstox API)
        try:
            # Format 1 - Authorization-style message with API key and token
            auth_msg = {
                "type": "authenticate",
                "api_key": self.authenticator.api_key,
                "access_token": self.authenticator.access_token
            }
            logger.debug("Sending WebSocket authentication message (Format 1)")
            ws.send(json.dumps(auth_msg))
            
            # Wait a short time and if not authenticated, try alternate format
            time.sleep(1)
            if not self.connected:
                # Format 2 - Simplified authentication with just the token
                auth_msg2 = {
                    "type": "auth",
                    "token": self.authenticator.access_token
                }
                logger.debug("Sending WebSocket authentication message (Format 2)")
                ws.send(json.dumps(auth_msg2))
        except Exception as e:
            logger.error(f"Error during WebSocket authentication: {e}")
    
    def _run_websocket(self):
        """Run WebSocket connection with retries"""
        max_retries = 3
        retry_count = 0
        retry_delay = 2  # Start with 2 seconds delay
        
        while retry_count < max_retries:
            try:
                if not self.authenticator.is_authenticated():
                    if not self.authenticator.authenticate():
                        logger.error("Failed to authenticate before WebSocket connection")
                        time.sleep(retry_delay)
                        retry_count += 1
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                # Prepare headers with authentication
                headers = {
                    "Authorization": f"Bearer {self.authenticator.access_token}",
                    "Api-Key": self.authenticator.api_key,
                    "Content-Type": "application/json"
                }
                
                # Create WebSocket connection
                logger.debug(f"Connecting to WebSocket at {self.WS_URL}")
                self.ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    header=[f"{k}: {v}" for k, v in headers.items()]
                )
                
                # Run WebSocket in blocking mode
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
                
                # If connection closed normally, break the loop
                if self.connected:
                    retry_count = 0
                    retry_delay = 2
                else:
                    # If connection failed, retry
                    retry_count += 1
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
            
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                retry_count += 1
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        if retry_count >= max_retries:
            logger.error(f"WebSocket connection failed after {max_retries} retries")
    
    def subscribe(self, instrument_keys: List[str], feed_type: str = "full") -> bool:
        """Subscribe to market data for instruments"""
        if not self.connected:
            logger.warning("WebSocket not connected, attempting to connect")
            if not self.connect():
                logger.error("Failed to connect WebSocket, cannot subscribe")
                return False
        
        # Try different subscription message formats
        subscription_formats = [
            # Format 1: Standard format with instrument_keys
            {
                "type": "subscribe",
                "instrument_keys": instrument_keys,
                "feed_type": feed_type
            },
            # Format 2: Alternative format with instrumentKeys
            {
                "type": "subscribe",
                "instrumentKeys": instrument_keys,
                "feedType": feed_type
            },
            # Format 3: Simple format
            {
                "subscribe": instrument_keys,
                "mode": feed_type
            }
        ]
        
        # Try each format
        for i, format_data in enumerate(subscription_formats):
            try:
                logger.debug(f"Sending subscription (Format {i+1}): {format_data}")
                self.ws.send(json.dumps(format_data))
                # Add to subscribed instruments set
                self.subscribed_instruments.update(instrument_keys)
                return True
            except Exception as e:
                logger.error(f"Error with subscription format {i+1}: {e}")
        
        logger.error("All subscription attempts failed")
        return False
    
    def register_callback(self, message_type: str, callback: Callable[[Dict], None]):
        """Register a callback for a specific message type"""
        if message_type not in self.callbacks:
            self.callbacks[message_type] = []
        
        self.callbacks[message_type].append(callback)
    
    def unregister_callback(self, message_type: str, callback: Callable[[Dict], None]):
        """Unregister a callback"""
        if message_type in self.callbacks and callback in self.callbacks[message_type]:
            self.callbacks[message_type].remove(callback)
