"""
Upstox API client for interacting with the Upstox trading platform
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple, Union
import websocket
import requests
import threading

from src.auth.authenticator import UpstoxAuthenticator
from src.utils.logger import logger

class UpstoxClient:
    """Client for interacting with Upstox API"""
    
    BASE_URL = "https://api.upstox.com/v2"
    WS_URL = "wss://api.upstox.com/v2/feed/market-data/socket"
    
    def __init__(self, authenticator: UpstoxAuthenticator):
        """Initialize with an authenticator"""
        self.authenticator = authenticator
        self.ws = None
        self.ws_thread = None
        self.ws_callbacks = {}
        self.ws_connected = False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated headers for API requests"""
        return self.authenticator.get_auth_headers()
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make an authenticated request to the Upstox API"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self._get_headers()
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle API response
            if response.status_code in (200, 201):
                return response.json()
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return {"status": "error", "code": response.status_code, "message": response.text}
                
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_profile(self) -> Dict:
        """Get user profile information"""
        return self._make_request('GET', 'user/profile')
    
    def get_funds(self) -> Dict:
        """Get user funds and margins"""
        return self._make_request('GET', 'user/funds-and-margin')
    
    def get_positions(self) -> Dict:
        """Get current positions"""
        return self._make_request('GET', 'portfolio/positions')
    
    def get_holdings(self) -> Dict:
        """Get current holdings"""
        return self._make_request('GET', 'portfolio/holdings')
    
    def search_instruments(self, exchange: str, symbol: str = None, name: str = None) -> List[Dict]:
        """Search for instruments by symbol or name"""
        params = {"exchange": exchange}
        
        if symbol:
            params["symbol"] = symbol
        if name:
            params["name"] = name
            
        response = self._make_request('GET', 'market-quote/instruments', params=params)
        return response.get('data', [])
    
    def get_market_quote(self, instrument_keys: List[str]) -> Dict:
        """Get market quotes for instruments"""
        params = {"instrument_key": instrument_keys}
        return self._make_request('GET', 'market-quote/quotes', params=params)
    
    def get_ohlc(self, instrument_key: str, interval: str, from_date: str, to_date: str) -> Dict:
        """Get OHLC data for an instrument"""
        params = {
            "instrument_key": instrument_key,
            "interval": interval,
            "from": from_date,
            "to": to_date
        }
        return self._make_request('GET', 'historical-candle/intraday', params=params)
    
    def place_order(self, transaction_type: str, exchange: str, symbol: str, 
                   quantity: int, product: str, order_type: str, 
                   price: float = 0, trigger_price: float = 0, 
                   disclosed_quantity: int = 0, validity: str = "DAY", 
                   variety: str = "NORMAL") -> Dict:
        """Place a new order"""
        data = {
            "transaction_type": transaction_type,
            "exchange": exchange,
            "symbol": symbol,
            "quantity": quantity,
            "product": product,
            "order_type": order_type,
            "price": price,
            "trigger_price": trigger_price,
            "disclosed_quantity": disclosed_quantity,
            "validity": validity,
            "variety": variety
        }
        
        return self._make_request('POST', 'order/place', data=data)
    
    def modify_order(self, order_id: str, quantity: int = None, 
                    price: float = None, trigger_price: float = None, 
                    disclosed_quantity: int = None, validity: str = None) -> Dict:
        """Modify an existing order"""
        data = {"order_id": order_id}
        
        if quantity is not None:
            data["quantity"] = quantity
        if price is not None:
            data["price"] = price
        if trigger_price is not None:
            data["trigger_price"] = trigger_price
        if disclosed_quantity is not None:
            data["disclosed_quantity"] = disclosed_quantity
        if validity is not None:
            data["validity"] = validity
            
        return self._make_request('PUT', 'order/modify', data=data)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        data = {"order_id": order_id}
        return self._make_request('DELETE', 'order/cancel', data=data)
    
    def get_order_book(self) -> Dict:
        """Get the order book"""
        return self._make_request('GET', 'order/book')
    
    def get_trade_book(self) -> Dict:
        """Get the trade book"""
        return self._make_request('GET', 'trade/book')
    
    # WebSocket methods for live market data
    
    def _on_ws_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            feed_type = data.get('type')
            
            # Handle authentication response
            if feed_type == 'authenticate':
                if data.get('status') == 'success':
                    logger.info("WebSocket authentication successful")
                else:
                    logger.error(f"WebSocket authentication failed: {data.get('message')}")
            
            # Call registered callbacks for this feed type
            if feed_type in self.ws_callbacks:
                for callback in self.ws_callbacks[feed_type]:
                    callback(data)
                    
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")


    def _on_ws_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.ws_connected = False
    
    def _on_ws_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")
        self.ws_connected = True
        
        # Authenticate the WebSocket connection
        auth_data = {"type": "authenticate", "token": self.authenticator.access_token}
        ws.send(json.dumps(auth_data))
        # Add a small delay before sending subsequent messages
        time.sleep(0.5)
    
    def _run_websocket(self):
        """Run WebSocket connection in a loop with auto-reconnect"""
        while True:
            try:
                # Create WebSocket connection
                self.ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close
                )
                
                # Run WebSocket connection
                self.ws.run_forever()
                
                # If connection closed, wait before reconnecting
                if not self.ws_connected:
                    time.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                time.sleep(5)
    
    def connect_websocket(self):
        """Connect to the WebSocket feed"""
        if self.ws_thread is None or not self.ws_thread.is_alive():
            self.ws_thread = threading.Thread(target=self._run_websocket)
            self.ws_thread.daemon = True
            self.ws_thread.start()
    
    def subscribe_feeds(self, instrument_keys: List[str], feed_type: str = "full"):
        """Subscribe to market data feeds for specified instruments"""
        if not self.ws_connected:
            logger.warning("WebSocket not connected. Attempting to connect.")
            self.connect_websocket()
            # Wait for connection to establish
            time.sleep(2)
        
        if not self.ws_connected:
            logger.error("WebSocket connection failed. Cannot subscribe to feeds.")
            return
        
        # Subscribe to feeds
        subscribe_data = {
            "type": "subscribe",
            "instruments": instrument_keys,
            "feed_type": feed_type
        }
        
        self.ws.send(json.dumps(subscribe_data))
    
    def register_callback(self, feed_type: str, callback):
        """Register a callback function for a specific feed type"""
        if feed_type not in self.ws_callbacks:
            self.ws_callbacks[feed_type] = []
            
        self.ws_callbacks[feed_type].append(callback)
    
    def unregister_callback(self, feed_type: str, callback):
        """Unregister a callback function for a specific feed type"""
        if feed_type in self.ws_callbacks and callback in self.ws_callbacks[feed_type]:
            self.ws_callbacks[feed_type].remove(callback)