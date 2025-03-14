"""
Execution engine for DeepTerminal.

This module provides the execution engine responsible for processing signals,
creating and managing orders, and handling the execution lifecycle.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

from deepterminal.core.models.instrument import Instrument
from deepterminal.core.models.order import Order, OrderStatus, OrderFactory, OrderSide, OrderType
from deepterminal.core.models.position import Position, PositionFactory, PositionSide
from deepterminal.core.models.signal import Signal, SignalStatus
from deepterminal.exchange.base import ExchangeBase
from deepterminal.risk.calculator import RiskCalculator


class ExecutionEngine:
    """Engine responsible for executing trading signals."""
    
    def __init__(
        self,
        exchange: ExchangeBase,
        risk_calculator: RiskCalculator,
        max_concurrent_orders: int = 10,
        enable_logging: bool = True
    ):
        """
        Initialize the execution engine.
        
        Args:
            exchange (ExchangeBase): The exchange interface for order execution.
            risk_calculator (RiskCalculator): The risk calculator for position sizing.
            max_concurrent_orders (int): Maximum number of concurrent orders.
            enable_logging (bool): Whether to enable logging.
        """
        self.exchange = exchange
        self.risk_calculator = risk_calculator
        self.max_concurrent_orders = max_concurrent_orders
        self.enable_logging = enable_logging
        
        # Execution state
        self.active_orders: Dict[str, Order] = {}  # Order ID -> Order
        self.active_positions: Dict[str, Position] = {}  # Position ID -> Position
        self.signal_order_map: Dict[str, List[str]] = {}  # Signal ID -> List of Order IDs
        self.processed_signals: Set[str] = set()  # Set of processed signal IDs
        
        # Logging
        self.logger = logging.getLogger("execution.engine")
        
        # Execution statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders = 0
        self.total_positions = 0
        
        # Event loop and tasks
        self.loop = None
        self.order_status_task = None
        self.running = False
    
    async def start(self) -> bool:
        """
        Start the execution engine.
        
        Returns:
            bool: True if started successfully, False otherwise.
        """
        if self.running:
            return True
        
        # Connect to the exchange
        connected = await self.exchange.connect()
        if not connected:
            if self.enable_logging:
                self.logger.error("Failed to connect to exchange")
            return False
        
        # Store the event loop
        self.loop = asyncio.get_event_loop()
        
        # Start the order status monitoring task
        self.order_status_task = asyncio.create_task(self._monitor_order_status())
        
        self.running = True
        
        if self.enable_logging:
            self.logger.info("Execution engine started")
        
        return True
    
    async def stop(self) -> bool:
        """
        Stop the execution engine.
        
        Returns:
            bool: True if stopped successfully, False otherwise.
        """
        if not self.running:
            return True
        
        # Cancel the order status task
        if self.order_status_task:
            self.order_status_task.cancel()
            try:
                await self.order_status_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect from the exchange
        disconnected = await self.exchange.disconnect()
        if not disconnected:
            if self.enable_logging:
                self.logger.error("Failed to disconnect from exchange")
            return False
        
        self.running = False
        
        if self.enable_logging:
            self.logger.info("Execution engine stopped")
        
        return True
    
    async def process_signal(self, signal: Signal) -> bool:
        """
        Process a trading signal.
        
        Args:
            signal (Signal): The signal to process.
            
        Returns:
            bool: True if the signal was processed successfully, False otherwise.
        """
        if not self.running:
            if self.enable_logging:
                self.logger.error("Cannot process signal: execution engine not running")
            return False
        
        # Check if the signal is still active
        if not signal.is_active():
            if self.enable_logging:
                self.logger.warning(f"Signal {signal.id} is not active")
            return False
        
        # Check if we've already processed this signal
        if signal.id in self.processed_signals:
            if self.enable_logging:
                self.logger.warning(f"Signal {signal.id} has already been processed")
            return False
        
        # Check if we can handle more orders
        if len(self.active_orders) >= self.max_concurrent_orders:
            if self.enable_logging:
                self.logger.warning("Cannot process signal: too many active orders")
            return False
        
        # Process the signal based on its type
        if signal.signal_type == "entry":
            success = await self._process_entry_signal(signal)
        elif signal.signal_type == "exit":
            success = await self._process_exit_signal(signal)
        else:
            if self.enable_logging:
                self.logger.warning(f"Unsupported signal type: {signal.signal_type}")
            return False
        
        # Mark the signal as processed
        if success:
            self.processed_signals.add(signal.id)
        
        return success
    
    async def _process_entry_signal(self, signal: Signal) -> bool:
        """
        Process an entry signal.
        
        Args:
            signal (Signal): The entry signal to process.
            
        Returns:
            bool: True if the signal was processed successfully, False otherwise.
        """
        # Get current account information
        account_info = await self.exchange.get_account_info()
        if not account_info:
            if self.enable_logging:
                self.logger.error("Failed to get account information")
            return False
        
        # Calculate position size
        account_balance = account_info.get("balance", 0.0)
        entry_price = signal.entry_price if signal.entry_price else await self._get_current_price(signal.instrument)
        stop_loss = signal.stop_loss
        
        if entry_price is None:
            if self.enable_logging:
                self.logger.error(f"Failed to determine entry price for {signal.instrument.symbol}")
            return False
        
        if stop_loss is None:
            if self.enable_logging:
                self.logger.error(f"No stop loss defined for signal {signal.id}")
            return False
        
        # Calculate the position size
        position_size = self.risk_calculator.calculate_position_size(
            account_balance=account_balance,
            entry_price=entry_price,
            stop_loss=stop_loss,
            instrument=signal.instrument,
            risk_percentage=0.01  # 1% risk per trade
        )
        
        if position_size <= 0:
            if self.enable_logging:
                self.logger.error(f"Invalid position size calculated: {position_size}")
            return False
        
        # Round the position size to the instrument's lot size
        lot_size = signal.instrument.lot_size
        position_size = round(position_size / lot_size) * lot_size
        
        if position_size < lot_size:
            position_size = lot_size
        
        # Create the order
        if signal.entry_price:
            # Create a limit order if an entry price is specified
            order = OrderFactory.create_limit_order(
                instrument=signal.instrument,
                side=signal.side,
                quantity=position_size,
                price=signal.entry_price,
                strategy_id=signal.strategy_id
            )
        else:
            # Create a market order if no entry price is specified
            order = OrderFactory.create_market_order(
                instrument=signal.instrument,
                side=signal.side,
                quantity=position_size,
                strategy_id=signal.strategy_id
            )
        
        # Place the order
        success, order_id = await self.exchange.place_order(order)
        if not success:
            if self.enable_logging:
                self.logger.error(f"Failed to place order for signal {signal.id}")
            self.failed_orders += 1
            return False
        
        # Update the order with the exchange order ID
        order.exchange_order_id = order_id
        
        # Store the order
        self.active_orders[order.id] = order
        
        # Link the signal to the order
        if signal.id not in self.signal_order_map:
            self.signal_order_map[signal.id] = []
        self.signal_order_map[signal.id].append(order.id)
        
        # Update signal status
        signal.execute([order.id])
        
        # Update statistics
        self.total_orders += 1
        self.successful_orders += 1
        
        if self.enable_logging:
            self.logger.info(
                f"Placed {order.order_type.value} {order.side.value} order for {order.quantity} "
                f"{order.instrument.symbol} at {order.price if order.price else 'market price'}"
            )
        
        return True
    
    async def _process_exit_signal(self, signal: Signal) -> bool:
        """
        Process an exit signal.
        
        Args:
            signal (Signal): The exit signal to process.
            
        Returns:
            bool: True if the signal was processed successfully, False otherwise.
        """
        # Get the position to exit
        position_id = signal.position_id
        if not position_id:
            if self.enable_logging:
                self.logger.error(f"No position ID specified in exit signal {signal.id}")
            return False
        
        # Check if we have the position
        position = self.active_positions.get(position_id)
        if not position:
            # Try to get the position from the exchange
            position = await self.exchange.get_position(signal.instrument)
            if not position:
                if self.enable_logging:
                    self.logger.error(f"Position {position_id} not found")
                return False
            
            # Store the position
            self.active_positions[position_id] = position
        
        # Create the exit order
        exit_side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        
        if signal.entry_price:  # Using entry_price field for exit price in exit signals
            # Create a limit order if an exit price is specified
            order = OrderFactory.create_limit_order(
                instrument=signal.instrument,
                side=exit_side,
                quantity=position.quantity,
                price=signal.entry_price,
                strategy_id=signal.strategy_id
            )
        else:
            # Create a market order if no exit price is specified
            order = OrderFactory.create_market_order(
                instrument=signal.instrument,
                side=exit_side,
                quantity=position.quantity,
                strategy_id=signal.strategy_id
            )
        
        # Place the order
        success, order_id = await self.exchange.place_order(order)
        if not success:
            if self.enable_logging:
                self.logger.error(f"Failed to place exit order for signal {signal.id}")
            self.failed_orders += 1
            return False
        
        # Update the order with the exchange order ID
        order.exchange_order_id = order_id
        
        # Store the order
        self.active_orders[order.id] = order
        
        # Link the signal to the order
        if signal.id not in self.signal_order_map:
            self.signal_order_map[signal.id] = []
        self.signal_order_map[signal.id].append(order.id)
        
        # Link the order to the position
        position.exit_order_ids.append(order.id)
        
        # Update signal status
        signal.execute([order.id], position_id)
        
        # Update statistics
        self.total_orders += 1
        self.successful_orders += 1
        
        if self.enable_logging:
            self.logger.info(
                f"Placed {order.order_type.value} {order.side.value} order to exit position {position_id} "
                f"for {order.quantity} {order.instrument.symbol} at "
                f"{order.price if order.price else 'market price'}"
            )
        
        return True
    
    async def _monitor_order_status(self) -> None:
        """
        Continuously monitor the status of active orders.
        """
        while True:
            try:
                # Get all active orders
                active_order_ids = list(self.active_orders.keys())
                
                for order_id in active_order_ids:
                    order = self.active_orders[order_id]
                    
                    # Skip orders that we know are no longer active
                    if not order.is_active():
                        continue
                    
                    # Get the current status from the exchange
                    status = await self.exchange.get_order_status(order.exchange_order_id)
                    
                    if status is None:
                        continue
                    
                    # Update the order status
                    if status != order.status:
                        old_status = order.status
                        order.update_status(status)
                        
                        if self.enable_logging:
                            self.logger.info(
                                f"Order {order_id} status changed from {old_status.value} to {status.value}"
                            )
                        
                        # Handle filled orders
                        if status == OrderStatus.FILLED or status == OrderStatus.PARTIALLY_FILLED:
                            await self._handle_filled_order(order)
                        
                        # Handle cancelled or rejected orders
                        elif status == OrderStatus.CANCELLED or status == OrderStatus.REJECTED:
                            await self._handle_failed_order(order)
                    
                    # Remove completed orders from active orders
                    if not order.is_active():
                        del self.active_orders[order_id]
            
            except asyncio.CancelledError:
                # Task was cancelled, exit the loop
                break
            except Exception as e:
                if self.enable_logging:
                    self.logger.error(f"Error monitoring order status: {e}")
            
            # Sleep for a short period before checking again
            await asyncio.sleep(1)
    
    async def _handle_filled_order(self, order: Order) -> None:
        """
        Handle a filled or partially filled order.
        
        Args:
            order (Order): The filled order.
        """
        # Check if this is an entry order
        if order.side == OrderSide.BUY or order.side == OrderSide.SELL:
            # This might be an entry or an exit, depending on whether it's linked to a position
            position = None
            
            # Check if the order is linked to a position (exit order)
            for pos_id, pos in self.active_positions.items():
                if order.id in pos.exit_order_ids:
                    position = pos
                    break
            
            if position:
                # This is an exit order
                await self._handle_exit_fill(order, position)
            else:
                # This is an entry order
                await self._handle_entry_fill(order)
    
    async def _handle_entry_fill(self, order: Order) -> None:
        """
        Handle a filled entry order.
        
        Args:
            order (Order): The filled entry order.
        """
        # Create a new position
        position_side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
        
        position = PositionFactory.create_position(
            instrument=order.instrument,
            side=order.side,
            quantity=order.filled_quantity,
            entry_price=order.average_fill_price,
            current_price=order.average_fill_price,
            strategy_id=order.strategy_id,
            stop_loss=order.stop_loss_price,
            take_profit=order.take_profit_price,
            entry_order_ids=[order.id]
        )
        
        # Store the position
        self.active_positions[position.id] = position
        
        # Update statistics
        self.total_positions += 1
        
        if self.enable_logging:
            self.logger.info(
                f"Created new {position.side.value} position {position.id} "
                f"for {position.quantity} {position.instrument.symbol} "
                f"at {position.entry_price}"
            )
        
        # If the order has a stop loss or take profit, place those orders
        if order.stop_loss_price:
            await self._place_stop_loss_order(position, order.stop_loss_price)
        
        if order.take_profit_price:
            await self._place_take_profit_order(position, order.take_profit_price)
    
    async def _handle_exit_fill(self, order: Order, position: Position) -> None:
        """
        Handle a filled exit order.
        
        Args:
            order (Order): The filled exit order.
            position (Position): The position being exited.
        """
        # Get the current price
        exit_price = order.average_fill_price
        
        # Close the position
        pnl = position.close(exit_price, order.filled_quantity)
        
        if self.enable_logging:
            self.logger.info(
                f"{'Partially' if position.is_open else 'Fully'} closed position {position.id}: "
                f"PnL = {pnl:.2f}, remaining quantity = {position.quantity}"
            )
        
        # If the position is fully closed, remove it from active positions
        if not position.is_open:
            del self.active_positions[position.id]
            
            # Cancel any remaining orders for this position
            await self._cancel_position_orders(position)
    
    async def _handle_failed_order(self, order: Order) -> None:
        """
        Handle a cancelled or rejected order.
        
        Args:
            order (Order): The failed order.
        """
        if self.enable_logging:
            self.logger.warning(
                f"Order {order.id} failed with status {order.status.value}: "
                f"{order.order_type.value} {order.side.value} {order.quantity} {order.instrument.symbol}"
            )
    
    async def _place_stop_loss_order(self, position: Position, stop_price: float) -> Optional[str]:
        """
        Place a stop loss order for a position.
        
        Args:
            position (Position): The position to place a stop loss for.
            stop_price (float): The stop loss price.
            
        Returns:
            Optional[str]: The order ID if successful, None otherwise.
        """
        # Determine the order side (opposite of position side)
        side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        
        # Create the stop order
        order = OrderFactory.create_stop_order(
            instrument=position.instrument,
            side=side,
            quantity=position.quantity,
            stop_price=stop_price,
            strategy_id=position.strategy_id
        )
        
        # Place the order
        success, order_id = await self.exchange.place_order(order)
        if not success:
            if self.enable_logging:
                self.logger.error(f"Failed to place stop loss order for position {position.id}")
            return None
        
        # Update the order with the exchange order ID
        order.exchange_order_id = order_id
        
        # Store the order
        self.active_orders[order.id] = order
        
        # Link the order to the position
        position.stop_order_ids.append(order.id)
        
        # Update statistics
        self.total_orders += 1
        self.successful_orders += 1
        
        if self.enable_logging:
            self.logger.info(
                f"Placed stop loss order for position {position.id} "
                f"at {stop_price}"
            )
        
        return order.id
    
    async def _place_take_profit_order(self, position: Position, take_profit_price: float) -> Optional[str]:
        """
        Place a take profit order for a position.
        
        Args:
            position (Position): The position to place a take profit for.
            take_profit_price (float): The take profit price.
            
        Returns:
            Optional[str]: The order ID if successful, None otherwise.
        """
        # Determine the order side (opposite of position side)
        side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        
        # Create the limit order
        order = OrderFactory.create_limit_order(
            instrument=position.instrument,
            side=side,
            quantity=position.quantity,
            price=take_profit_price,
            strategy_id=position.strategy_id
        )
        
        # Place the order
        success, order_id = await self.exchange.place_order(order)
        if not success:
            if self.enable_logging:
                self.logger.error(f"Failed to place take profit order for position {position.id}")
            return None
        
        # Update the order with the exchange order ID
        order.exchange_order_id = order_id
        
        # Store the order
        self.active_orders[order.id] = order
        
        # Link the order to the position
        position.exit_order_ids.append(order.id)
        
        # Update statistics
        self.total_orders += 1
        self.successful_orders += 1
        
        if self.enable_logging:
            self.logger.info(
                f"Placed take profit order for position {position.id} "
                f"at {take_profit_price}"
            )
        
        return order.id
    
    async def _cancel_position_orders(self, position: Position) -> None:
        """
        Cancel all orders associated with a position.
        
        Args:
            position (Position): The position to cancel orders for.
        """
        # Collect all order IDs
        order_ids = position.stop_order_ids + position.exit_order_ids
        
        for order_id in order_ids:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                
                # Only try to cancel active orders
                if order.is_active():
                    success = await self.exchange.cancel_order(order.exchange_order_id)
                    
                    if success:
                        order.update_status(OrderStatus.CANCELLED)
                        
                        if self.enable_logging:
                            self.logger.info(f"Cancelled order {order_id} for position {position.id}")
                    else:
                        if self.enable_logging:
                            self.logger.warning(f"Failed to cancel order {order_id} for position {position.id}")
    
    async def emergency_close_all_positions(self) -> bool:
        """
        Close all open positions immediately.
        
        Returns:
            bool: True if all positions were closed (or attempted to close), False otherwise.
        """
        if not self.running:
            if self.enable_logging:
                self.logger.error("Cannot close positions: execution engine not running")
            return False
        
        if self.enable_logging:
            self.logger.warning("Emergency closing all positions")
        
        # Get all open positions
        positions = list(self.active_positions.values())
        
        for position in positions:
            # Create a market order to close the position
            side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
            
            order = OrderFactory.create_market_order(
                instrument=position.instrument,
                side=side,
                quantity=position.quantity,
                strategy_id=position.strategy_id
            )
            
            # Place the order
            success, order_id = await self.exchange.place_order(order)
            if not success:
                if self.enable_logging:
                    self.logger.error(f"Failed to close position {position.id}")
                continue
            
            # Update the order with the exchange order ID
            order.exchange_order_id = order_id
            
            # Store the order
            self.active_orders[order.id] = order
            
            # Link the order to the position
            position.exit_order_ids.append(order.id)
            
            # Update statistics
            self.total_orders += 1
            self.successful_orders += 1
            
            if self.enable_logging:
                self.logger.info(f"Placed market order to close position {position.id}")
        
        return True
    
    async def _get_current_price(self, instrument: Instrument) -> Optional[float]:
        """
        Get the current price of an instrument.
        
        Args:
            instrument (Instrument): The instrument to get the price for.
            
        Returns:
            Optional[float]: The current price, or None if not available.
        """
        try:
            market_data = await self.exchange.get_market_data(instrument)
            return market_data.get("last_price") or market_data.get("close")
        except Exception as e:
            if self.enable_logging:
                self.logger.error(f"Error getting current price for {instrument.symbol}: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.
        
        Returns:
            Dict[str, Any]: Execution statistics.
        """
        return {
            "total_orders": self.total_orders,
            "successful_orders": self.successful_orders,
            "failed_orders": self.failed_orders,
            "total_positions": self.total_positions,
            "active_orders": len(self.active_orders),
            "active_positions": len(self.active_positions),
        }