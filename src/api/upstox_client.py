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
from src.trading.websocket import UpstoxWebSocket  # Import the new WebSocket implementation

class UpstoxClient:
    """Client for interacting with Upstox API"""
    
    BASE_URL = "https://api.upstox.com/v2"
    
    def __init__(self, authenticator: UpstoxAuthenticator):
        """Initialize with an authenticator"""
        self.authenticator = authenticator
        self.ws = UpstoxWebSocket(authenticator)  # Initialize the WebSocket client
        self.ws_connected = False
        
        # Verify authentication
        if not self.authenticator.is_authenticated():
            logger.warning("Authenticator not initialized with valid tokens")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated headers for API requests"""
        return self.authenticator.get_auth_headers()
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make an authenticated request to the Upstox API"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            # Ensure the authenticator is authenticated
            if not self.authenticator.is_authenticated():
                if not self.authenticator.authenticate():
                    return {"status": "error", "message": "Failed to authenticate"}
            
            headers = self._get_headers()
            
            logger.debug(f"Making {method} request to {url}")
            
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
                response_data = response.json()
                logger.debug(f"API response: {response.status_code}")
                return response_data
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                # Check if authentication failed
                if response.status_code == 401:
                    # Try to reauthenticate
                    logger.info("Authentication token may have expired, attempting to refresh")
                    if self.authenticator.authenticate():
                        # Retry the request with new token
                        return self._make_request(method, endpoint, params, data)
                return {"status": "error", "message": response.text}
                
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
        # Updated endpoint as per Upstox API v2
        return self._make_request('GET', 'portfolio/short-term-positions')
    
    def get_holdings(self) -> Dict:
        """Get current holdings"""
        return self._make_request('GET', 'portfolio/long-term-holdings')
    
    def search_instruments(self, exchange: str, symbol: str = None, name: str = None) -> List[Dict]:
        """Search for instruments by symbol or name"""
        # Create a proper search query
        if symbol:
            search_query = symbol
        elif name:
            search_query = name
        else:
            search_query = ""
        
        # Updated endpoint and parameters
        params = {
            "exchange": exchange,
            "symbol": search_query
        }
            
        response = self._make_request('GET', 'market-quote/instruments', params=params)
        
        # Process the response - check if data is in the expected format
        instruments = []
        if response and isinstance(response, dict):
            data = response.get('data', [])
            if isinstance(data, list):
                instruments = data
            elif isinstance(data, dict):
                # Some APIs return data as an object with embedded results
                for key, value in data.items():
                    if isinstance(value, list):
                        instruments.extend(value)
        
        return instruments
    
    def get_market_quote(self, instrument_keys: List[str]) -> Dict:
        """Get market quotes for instruments"""
        params = {"instrument_key": ",".join(instrument_keys)}
        return self._make_request('GET', 'market-quote/quotes', params=params)
    
    def get_ohlc(self, instrument_key: str, interval: str, from_date: str, to_date: str) -> Dict:
        """Get OHLC data for an instrument"""
        params = {
            "instrument_key": instrument_key,
            "interval": interval,
            "from": from_date,
            "to": to_date
        }
        return self._make_request('GET', 'historical-candle/data', params=params)
    
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
        return self._make_request('GET', 'order/get-orders')
    
    def get_trade_book(self) -> Dict:
        """Get the trade book"""
        return self._make_request('GET', 'order/trades')
    
    # WebSocket methods for live market data
    
    def connect_websocket(self) -> bool:
        """Connect to the WebSocket feed"""
        success = self.ws.connect()
        self.ws_connected = success
        return success
    
    def subscribe_feeds(self, instrument_keys: List[str], feed_type: str = "full") -> bool:
        """Subscribe to market data feeds for specified instruments"""
        if not self.ws_connected:
            logger.warning("WebSocket not connected. Attempting to connect.")
            if not self.connect_websocket():
                logger.error("WebSocket connection failed. Cannot subscribe to feeds.")
                return False
        
        return self.ws.subscribe(instrument_keys, feed_type)
    
    def register_callback(self, feed_type: str, callback):
        """Register a callback function for a specific feed type"""
        self.ws.register_callback(feed_type, callback)
    
    def unregister_callback(self, feed_type: str, callback):
        """Unregister a callback function for a specific feed type"""
        self.ws.unregister_callback(feed_type, callback)