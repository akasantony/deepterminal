"""
Order management system
"""

import time
from typing import Dict, List, Optional, Callable, Any

from src.api.upstox_client import UpstoxClient
from src.models.order import Order
from src.models.instrument import Instrument
from src.utils.logger import logger

class OrderManager:
    """Manages order placement, modification, and tracking"""
    
    def __init__(self, client: UpstoxClient):
        """Initialize with API client"""
        self.client = client
        self.orders: Dict[str, Order] = {}
        self.order_callbacks: Dict[str, List[Callable[[Order], None]]] = {}
        self.default_quantity = 1
    
    def set_default_quantity(self, quantity: int):
        """Set default order quantity"""
        self.default_quantity = quantity
    
    def fetch_orders(self) -> List[Order]:
        """Fetch current orders from API"""
        response = self.client.get_order_book()
        
        if response.get('status') == 'error':
            logger.error(f"Failed to fetch orders: {response.get('message')}")
            return []
        
        orders = []
        for order_data in response.get('data', []):
            order = Order.from_api_response(order_data)
            self.orders[order.order_id] = order
            orders.append(order)
        
        return orders
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID"""
        # If not in local cache, try to fetch from API
        if order_id not in self.orders:
            self.fetch_orders()
        
        return self.orders.get(order_id)
    
    def place_market_order(self, instrument: Instrument, transaction_type: str, 
                          quantity: int = None, product: str = "INTRADAY") -> Optional[str]:
        """Place a market order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        
        response = self.client.place_order(
            transaction_type=transaction_type,
            exchange=instrument.exchange,
            symbol=instrument.symbol,
            quantity=actual_quantity,
            product=product,
            order_type="MARKET"
        )
        
        if response.get('status') == 'error':
            logger.error(f"Failed to place market order: {response.get('message')}")
            return None
        
        order_id = response.get('data', {}).get('order_id')
        if order_id:
            logger.info(f"Market order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol}")
            
            # Fetch order details to update local cache
            self._fetch_order_details(order_id)
            
            return order_id
        
        return None
    
    def place_limit_order(self, instrument: Instrument, transaction_type: str, 
                         price: float, quantity: int = None, 
                         product: str = "INTRADAY") -> Optional[str]:
        """Place a limit order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        
        response = self.client.place_order(
            transaction_type=transaction_type,
            exchange=instrument.exchange,
            symbol=instrument.symbol,
            quantity=actual_quantity,
            product=product,
            order_type="LIMIT",
            price=price
        )
        
        if response.get('status') == 'error':
            logger.error(f"Failed to place limit order: {response.get('message')}")
            return None
        
        order_id = response.get('data', {}).get('order_id')
        if order_id:
            logger.info(f"Limit order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol} @ {price}")
            
            # Fetch order details to update local cache
            self._fetch_order_details(order_id)
            
            return order_id
        
        return None
    
    def place_sl_order(self, instrument: Instrument, transaction_type: str, 
                      trigger_price: float, price: float = None, 
                      quantity: int = None, product: str = "INTRADAY") -> Optional[str]:
        """Place a stop-loss order"""
        actual_quantity = quantity if quantity is not None else self.default_quantity
        
        # Determine if SL or SL-M based on whether price is provided
        order_type = "SL" if price is not None else "SL-M"
        
        response = self.client.place_order(
            transaction_type=transaction_type,
            exchange=instrument.exchange,
            symbol=instrument.symbol,
            quantity=actual_quantity,
            product=product,
            order_type=order_type,
            price=price if price is not None else 0,
            trigger_price=trigger_price
        )
        
        if response.get('status') == 'error':
            logger.error(f"Failed to place SL order: {response.get('message')}")
            return None
        
        order_id = response.get('data', {}).get('order_id')
        if order_id:
            price_str = f" @ {price}" if price is not None else ""
            logger.info(f"SL order placed: {order_id} - {transaction_type} {actual_quantity} {instrument.symbol}{price_str} (Trigger: {trigger_price})")
            
            # Fetch order details to update local cache
            self._fetch_order_details(order_id)
            
            return order_id
        
        return None
    
    def modify_order(self, order_id: str, price: float = None, 
                    trigger_price: float = None, quantity: int = None) -> bool:
        """Modify an existing order"""
        response = self.client.modify_order(
            order_id=order_id,
            price=price,
            trigger_price=trigger_price,
            quantity=quantity
        )
        
        if response.get('status') == 'error':
            logger.error(f"Failed to modify order: {response.get('message')}")
            return False
        
        # Fetch updated order details
        self._fetch_order_details(order_id)
        
        logger.info(f"Order modified: {order_id}")
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        response = self.client.cancel_order(order_id)
        
        if response.get('status') == 'error':
            logger.error(f"Failed to cancel order: {response.get('message')}")
            return False
        
        # Fetch updated order details
        self._fetch_order_details(order_id)
        
        logger.info(f"Order cancelled: {order_id}")
        return True
    
    def _fetch_order_details(self, order_id: str) -> Optional[Order]:
        """Fetch details for a specific order"""
        # We need to fetch all orders since Upstox API doesn't have a single order fetch endpoint
        orders = self.fetch_orders()
        return self.get_order(order_id)
    
    def register_order_callback(self, order_id: str, callback: Callable[[Order], None]):
        """Register a callback for order updates"""
        if order_id not in self.order_callbacks:
            self.order_callbacks[order_id] = []
        
        self.order_callbacks[order_id].append(callback)
    
    def start_order_monitoring(self, refresh_interval: float = 5.0):
        """Start monitoring orders in a background thread"""
        import threading
        
        def monitor_loop():
            while True:
                try:
                    orders = self.fetch_orders()
                    
                    # Trigger callbacks for orders with registered callbacks
                    for order_id, callbacks in self.order_callbacks.items():
                        if order_id in self.orders:
                            order = self.orders[order_id]
                            for callback in callbacks:
                                try:
                                    callback(order)
                                except Exception as e:
                                    logger.error(f"Error in order callback: {e}")
                    
                    # Sleep until next check
                    time.sleep(refresh_interval)
                except Exception as e:
                    logger.error(f"Error in order monitoring: {e}")
                    time.sleep(refresh_interval)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()