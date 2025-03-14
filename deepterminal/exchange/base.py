"""
Base exchange interface for DeepTerminal.

This module defines the abstract base class for exchange integrations,
ensuring all exchange adapters follow a consistent interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import Order, OrderStatus
from deepterminal.core.models.position import Position


class ExchangeBase(ABC):
    """Abstract base class for exchange integrations."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish a connection to the exchange.
        
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the exchange.
        
        Returns:
            bool: True if disconnection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if the exchange connection is active.
        
        Returns:
            bool: True if connected, False otherwise.
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """
        Retrieve account information from the exchange.
        
        Returns:
            Dict[str, Any]: Account information including balance, margin, etc.
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Retrieve all current positions.
        
        Returns:
            List[Position]: List of current positions.
        """
        pass
    
    @abstractmethod
    async def get_position(self, instrument: Instrument) -> Optional[Position]:
        """
        Retrieve a specific position for an instrument.
        
        Args:
            instrument (Instrument): The instrument to get the position for.
            
        Returns:
            Optional[Position]: The position if it exists, None otherwise.
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> Tuple[bool, str]:
        """
        Place an order on the exchange.
        
        Args:
            order (Order): The order to place.
            
        Returns:
            Tuple[bool, str]: A tuple containing a success flag and an order ID or error message.
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id (str): The ID of the order to cancel.
            
        Returns:
            bool: True if cancellation was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, **kwargs) -> Tuple[bool, str]:
        """
        Modify an existing order.
        
        Args:
            order_id (str): The ID of the order to modify.
            **kwargs: Order parameters to modify.
            
        Returns:
            Tuple[bool, str]: A tuple containing a success flag and an updated order ID or error message.
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Get the current status of an order.
        
        Args:
            order_id (str): The ID of the order to check.
            
        Returns:
            Optional[OrderStatus]: The order status if the order exists, None otherwise.
        """
        pass
    
    @abstractmethod
    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """
        Get all orders, optionally filtered by status.
        
        Args:
            status (Optional[OrderStatus]): The status to filter by.
            
        Returns:
            List[Order]: List of orders.
        """
        pass
    
    @abstractmethod
    async def get_market_data(self, instrument: Instrument) -> Dict[str, Any]:
        """
        Get current market data for an instrument.
        
        Args:
            instrument (Instrument): The instrument to get market data for.
            
        Returns:
            Dict[str, Any]: Market data including price, volume, etc.
        """
        pass
    
    @abstractmethod
    async def get_historical_data(
        self, 
        instrument: Instrument, 
        timeframe: str, 
        start_time: str, 
        end_time: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get historical market data for an instrument.
        
        Args:
            instrument (Instrument): The instrument to get historical data for.
            timeframe (str): The timeframe (e.g., "1m", "5m", "1h", "1d").
            start_time (str): The start time in ISO format.
            end_time (Optional[str]): The end time in ISO format. If None, use current time.
            limit (Optional[int]): Maximum number of candles to return.
            
        Returns:
            Dict[str, Any]: Historical market data.
        """
        pass
    
    @abstractmethod
    async def subscribe_to_market_data(
        self, 
        instrument: Instrument, 
        callback: callable
    ) -> bool:
        """
        Subscribe to real-time market data for an instrument.
        
        Args:
            instrument (Instrument): The instrument to subscribe to.
            callback (callable): Function to call with new market data.
            
        Returns:
            bool: True if subscription was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def unsubscribe_from_market_data(self, instrument: Instrument) -> bool:
        """
        Unsubscribe from real-time market data for an instrument.
        
        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            
        Returns:
            bool: True if unsubscription was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get information about the exchange.
        
        Returns:
            Dict[str, Any]: Exchange information including trading pairs, limits, etc.
        """
        pass
    
    @abstractmethod
    async def get_instrument_info(self, instrument: Instrument) -> Dict[str, Any]:
        """
        Get detailed information about an instrument.
        
        Args:
            instrument (Instrument): The instrument to get information for.
            
        Returns:
            Dict[str, Any]: Instrument information including tick size, lot size, etc.
        """
        pass