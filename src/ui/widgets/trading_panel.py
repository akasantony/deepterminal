"""
Trading panel widget
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container, Grid
from textual.widgets import Button, Input, Label, Static, Select
from textual.reactive import reactive
from textual import work
from typing import Optional, List, Tuple

from src.api.upstox_client import UpstoxClient
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.models.instrument import Instrument
from src.utils.logger import logger


class TradingPanel(Container):
    """Widget for trading operations"""
    
    current_price = reactive(0.0)
    bid_price = reactive(0.0)
    ask_price = reactive(0.0)
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.client = None
        self.order_manager = None
        self.position_tracker = None
        self.instrument: Optional[Instrument] = None
        self.last_order_id = None
    
    def initialize(self, client: UpstoxClient, order_manager: OrderManager, position_tracker: PositionTracker):
        """Initialize with dependencies"""
        self.client = client
        self.order_manager = order_manager
        self.position_tracker = position_tracker
    
    def compose(self) -> ComposeResult:
        """Compose the widget"""
        with Vertical(id="trading_container"):
            # Instrument info section
            with Container(id="instrument_info", classes="no_instrument"):
                yield Static("No instrument selected", id="instrument_display")
                
                with Horizontal(id="price_display", classes="hidden"):
                    yield Static("LTP:", classes="price_label")
                    yield Static("0.00", id="ltp_value", classes="price_value")
                    
                    yield Static("Bid:", classes="price_label")
                    yield Static("0.00", id="bid_value", classes="price_value")
                    
                    yield Static("Ask:", classes="price_label")
                    yield Static("0.00", id="ask_value", classes="price_value")
            
                # Order entry section
                with Container(id="order_entry", classes="no_instrument"):
                    with Horizontal(id="order_controls"):
                        # Define Select widgets without pre-setting value
                        yield Select(
                            [
                                ("DELIVERY", "Delivery"),
                                ("INTRADAY", "Intraday")
                            ],
                            id="product_type",
                            prompt="Product Type"
                        )
                        
                        yield Select(
                            [
                                ("MARKET", "Market"),
                                ("LIMIT", "Limit"),
                                ("SL", "Stop Loss"),
                                ("SL-M", "SL-Market")
                            ],
                            id="order_type",
                            prompt="Order Type"
                        )
                    
                with Grid(id="order_params", classes="hidden"):
                    yield Label("Quantity:")
                    yield Input(value="1", id="quantity_input", classes="order_input")
                    
                    yield Label("Price:", id="price_label", classes="hidden")
                    yield Input(value="0.00", id="price_input", classes="order_input hidden")
                    
                    yield Label("Trigger:", id="trigger_label", classes="hidden")
                    yield Input(value="0.00", id="trigger_input", classes="order_input hidden")
                
                with Horizontal(id="order_buttons"):
                    yield Button("BUY", id="buy_button", variant="success", disabled=True)
                    yield Button("SELL", id="sell_button", variant="error", disabled=True)
            
            # Order status
            yield Static("", id="order_status", classes="order_status")
    
    def on_mount(self) -> None:
        """Setup the widget on mount"""
        # Set default values for selects after they are mounted
        try:
            self.set_timer(0.1, self._set_default_values)
        except Exception as e:
            logger.error(f"Error setting up on_mount timer: {e}")
    
    def _set_default_values(self) -> None:
        """Set default values for widgets safely"""
        try:
            # Set default values for select widgets
            product_type = self.query_one("#product_type", Select)
            order_type = self.query_one("#order_type", Select)
            
            product_type.value = product_type.options[1][0]  # INTRADAY
            order_type.value = order_type.options[0][0]     # MARKET
            
            logger.info("Default values set for select widgets")
        except Exception as e:
            logger.error(f"Error setting default values: {e}")
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select widget changes"""
        if event.select.id == "order_type":
            self._on_order_type_change(event.value)
    
    def _on_order_type_change(self, value: str) -> None:
        """Handle order type changes"""
        try:
            # Show/hide price fields based on order type
            price_label = self.query_one("#price_label")
            price_input = self.query_one("#price_input")
            trigger_label = self.query_one("#trigger_label")
            trigger_input = self.query_one("#trigger_input")
            
            if value == "MARKET":
                price_label.add_class("hidden")
                price_input.add_class("hidden")
                trigger_label.add_class("hidden")
                trigger_input.add_class("hidden")
            
            elif value == "LIMIT":
                price_label.remove_class("hidden")
                price_input.remove_class("hidden")
                trigger_label.add_class("hidden")
                trigger_input.add_class("hidden")
                
                # Set default price to current price if available
                if self.current_price > 0:
                    price_input.value = f"{self.current_price:.2f}"
            
            elif value in ["SL", "SL-M"]:
                trigger_label.remove_class("hidden")
                trigger_input.remove_class("hidden")
                
                # For SL, also show price input
                if value == "SL":
                    price_label.remove_class("hidden")
                    price_input.remove_class("hidden")
                else:
                    price_label.add_class("hidden")
                    price_input.add_class("hidden")
                
                # Set default trigger price to current price if available
                if self.current_price > 0:
                    # For buy, trigger above current, for sell trigger below current
                    trigger_input.value = f"{self.current_price:.2f}"
        except Exception as e:
            logger.error(f"Error in _on_order_type_change: {e}")
    
    def set_instrument(self, instrument: Instrument) -> None:
        """Set the current instrument"""
        self.instrument = instrument
        
        # Update UI to show instrument is selected
        instrument_display = self.query_one("#instrument_display")
        instrument_info = self.query_one("#instrument_info")
        order_entry = self.query_one("#order_entry")
        price_display = self.query_one("#price_display")
        order_params = self.query_one("#order_params")
        
        # Update instrument display
        instrument_display.update(str(instrument))
        
        # Show price display and order params
        instrument_info.remove_class("no_instrument")
        order_entry.remove_class("no_instrument")
        price_display.remove_class("hidden")
        order_params.remove_class("hidden")
        
        # Enable order buttons
        self.query_one("#buy_button").disabled = False
        self.query_one("#sell_button").disabled = False
        
        # Reset price displays
        self.query_one("#ltp_value").update("Loading...")
        self.query_one("#bid_value").update("Loading...")
        self.query_one("#ask_value").update("Loading...")
        
        # Subscribe to market data
        if self.client:
            try:
                # Unsubscribe from previous feeds if any
                self._unsubscribe_from_previous_feeds()
                
                # Subscribe to new instrument feed
                self.client.subscribe_feeds([instrument.instrument_key])
                self.client.register_callback('full', self._on_market_data)
                self.client.register_callback('ltpc', self._on_market_data)
                
                # Set a timeout to check if we received data
                self._start_market_data_timeout()
            except Exception as e:
                logger.error(f"Error subscribing to market data: {e}")
                self.query_one("#order_status").update(f"Error: Could not subscribe to market data")
                self.query_one("#ltp_value").update("ERROR")
                self.query_one("#bid_value").update("ERROR")
                self.query_one("#ask_value").update("ERROR")

    def _unsubscribe_from_previous_feeds(self):
        """Unsubscribe from previous market data feeds"""
        # This would depend on the actual API implementation
        # If upstox client supports unsubscribing, implement it here
        pass

    def _start_market_data_timeout(self):
        """Start a timeout to check if market data was received"""
        import threading
        
        def check_data_received():
            # If after 5 seconds we still have default prices, show error
            if self.current_price == 0.0:
                self.app.call_from_thread(self._handle_market_data_timeout)
        
        # Start a timer to check if data was received
        timer = threading.Timer(5.0, check_data_received)
        timer.daemon = True
        timer.start()

    def _handle_market_data_timeout(self):
        """Handle case where market data wasn't received"""
        if self.current_price == 0.0:
            self.query_one("#ltp_value").update("NO DATA")
            self.query_one("#bid_value").update("NO DATA")
            self.query_one("#ask_value").update("NO DATA")
            self.query_one("#order_status").update("Warning: No market data received")

    def _on_market_data(self, data: dict) -> None:
        """Handle market data updates"""
        if not self.instrument:
            return
            
        if data.get('instrument_key') != self.instrument.instrument_key:
            return
        
        try:
            # Update prices if available in data
            if 'ltp' in data and data['ltp'] is not None:
                self.current_price = float(data['ltp'])
                self.query_one("#ltp_value").update(f"{self.current_price:.2f}")
                
                # Also update the price input if it's visible and hasn't been modified
                price_input = self.query_one("#price_input")
                if not price_input.has_class("hidden") and float(price_input.value) == 0.0:
                    price_input.value = f"{self.current_price:.2f}"
            
            if 'bid' in data and data['bid'] is not None:
                self.bid_price = float(data['bid'])
                self.query_one("#bid_value").update(f"{self.bid_price:.2f}")
            
            if 'ask' in data and data['ask'] is not None:
                self.ask_price = float(data['ask'])
                self.query_one("#ask_value").update(f"{self.ask_price:.2f}")
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error processing market data: {e}, data: {data}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press event"""
        if not self.instrument:
            return
        
        if event.button.id in ["buy_button", "sell_button"]:
            transaction_type = "BUY" if event.button.id == "buy_button" else "SELL"
            self.place_order(transaction_type)
    
    @work
    async def place_order(self, transaction_type: str) -> None:
        """Place an order"""
        if not self.instrument or not self.order_manager:
            self.query_one("#order_status").update("Error: System not initialized")
            return
        
        try:
            # Get order parameters
            product_type = self.query_one("#product_type").value
            order_type = self.query_one("#order_type").value
            
            # Validate values
            if not product_type or not order_type:
                self.query_one("#order_status").update("Error: Product type or order type not selected")
                return
                
            quantity = int(self.query_one("#quantity_input").value)
            
            price = None
            trigger_price = None
            
            if order_type in ["LIMIT", "SL"]:
                price = float(self.query_one("#price_input").value)
            
            if order_type in ["SL", "SL-M"]:
                trigger_price = float(self.query_one("#trigger_input").value)
            
            # Update status
            self.query_one("#order_status").update(f"Placing {transaction_type} order...")
            
            # Place order based on type
            order_id = None
            
            if order_type == "MARKET":
                order_id = self.order_manager.place_market_order(
                    instrument=self.instrument,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    product=product_type
                )
            
            elif order_type == "LIMIT":
                order_id = self.order_manager.place_limit_order(
                    instrument=self.instrument,
                    transaction_type=transaction_type,
                    price=price,
                    quantity=quantity,
                    product=product_type
                )
            
            elif order_type in ["SL", "SL-M"]:
                order_id = self.order_manager.place_sl_order(
                    instrument=self.instrument,
                    transaction_type=transaction_type,
                    trigger_price=trigger_price,
                    price=price if order_type == "SL" else None,
                    quantity=quantity,
                    product=product_type
                )
            
            if order_id:
                self.last_order_id = order_id
                self.query_one("#order_status").update(f"Order placed successfully. ID: {order_id}")
                
                # Register for order updates
                self.order_manager.register_order_callback(order_id, self._on_order_update)
            else:
                self.query_one("#order_status").update("Order placement failed")
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            self.query_one("#order_status").update(f"Error: {str(e)}")
    
    def _on_order_update(self, order) -> None:
        """Handle order updates"""
        self.query_one("#order_status").update(f"Order update: {order.status} - {order}")