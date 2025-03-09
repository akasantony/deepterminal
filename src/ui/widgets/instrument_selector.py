"""
Instrument selector widget
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Input, Button, Label, Select, Static, DataTable
from textual.reactive import reactive
from textual import work
from textual.message import Message
from typing import Dict, List, Optional, Any, Tuple

from src.api.upstox_client import UpstoxClient
from src.models.instrument import Instrument
from src.utils.logger import logger

class InstrumentSelector(Container):
    """Widget for selecting trading instruments"""
    
    is_loading = reactive(False)
    error_message = reactive("")
    
    EXCHANGES = [
        ("NSE", "NSE"),
        ("BSE", "BSE"),
        ("NFO", "NSE Futures & Options"),
        ("BFO", "BSE Futures & Options"),
        ("MCX", "MCX Commodities"),
        ("CDS", "Currency Derivatives")
    ]
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.client = None
        self.search_results = []
        self.selected_instrument = None
    
    def initialize(self, client: UpstoxClient):
        """Initialize with API client"""
        self.client = client
    
    def compose(self) -> ComposeResult:
        """Compose the widget"""
        with Vertical(id="instrument_search_container"):
            with Horizontal(id="search_controls"):
                # Initialize the Select with options directly
                exchange_select = Select(self.EXCHANGES, id="exchange_select", prompt="Select Exchange")
                exchange_select.value = "NSE"  # Set default value
                yield exchange_select
                
                yield Input(placeholder="Search by symbol or name", id="search_input")
                yield Button("Search", id="search_button", variant="primary")
            
            with Container(id="results_container"):
                yield DataTable(id="search_results", zebra_stripes=True)
                yield Static("", id="status_message", classes="status_message")
    
    def on_mount(self):
        """Setup the widget on mount"""
        # Setup the search results table
        table = self.query_one("#search_results")
        table.add_columns("Symbol", "Name", "Type", "Exchange")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press event"""
        if event.button.id == "search_button":
            self.search_instruments()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission event"""
        if event.input.id == "search_input":
            self.search_instruments()
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in results table"""
        if event.data_table.id == "search_results" and event.row_key < len(self.search_results):
            # Get the selected instrument
            instrument = self.search_results[event.row_key]
            self.selected_instrument = instrument
            
            # Post message with selected instrument
            self.post_message(self.InstrumentSelected(instrument))
    
    def watch_is_loading(self, is_loading: bool) -> None:
        """Watch for changes in loading state"""
        status = self.query_one("#status_message")
        if is_loading:
            status.update("Searching...")
        else:
            status.update("")
    
    def watch_error_message(self, error_message: str) -> None:
        """Watch for changes in error message"""
        if error_message:
            self.query_one("#status_message").update(error_message)
    
    @work
    async def search_instruments(self) -> None:
        """Search for instruments"""
        if not self.client:
            self.error_message = "Client not initialized"
            return
        
        # Check if client is authenticated
        if not self.client.authenticator.is_authenticated():
            if not self.client.authenticator.authenticate():
                self.error_message = "Authentication required"
                return
        
        self.is_loading = True
        self.error_message = ""
        
        # Get search parameters
        exchange_select = self.query_one("#exchange_select")
        search_input = self.query_one("#search_input")
        
        if not exchange_select.value:
            self.is_loading = False
            self.error_message = "Please select an exchange"
            return
        
        exchange = exchange_select.value
        search_term = search_input.value.strip().upper()
        
        if not search_term:
            self.is_loading = False
            self.error_message = "Please enter a search term"
            return
        
        # Perform search
        try:
            # Try searching as symbol first
            results = self.client.search_instruments(exchange=exchange, symbol=search_term)
            
            # If no results, try searching as name
            if not results:
                results = self.client.search_instruments(exchange=exchange, name=search_term)
            
            self.search_results = [Instrument.from_api_response(item) for item in results]
            
            # Update results table
            table = self.query_one("#search_results")
            table.clear()
            
            for i, instrument in enumerate(self.search_results):
                option_info = f" {instrument.option_type} {instrument.strike}" if instrument.option_type else ""
                expiry_info = f" {instrument.expiry}" if instrument.expiry else ""
                
                table.add_row(
                    instrument.symbol,
                    instrument.name,
                    f"{instrument.instrument_type}{option_info}{expiry_info}",
                    instrument.exchange,
                    key=i
                )
            
            if not self.search_results:
                self.query_one("#status_message").update("No results found")
        
        except Exception as e:
            logger.error(f"Error searching instruments: {e}")
            self.error_message = f"Error searching instruments: {str(e)}"
        
        self.is_loading = False
    
    class InstrumentSelected(Message):
        """Message sent when an instrument is selected"""
        
        def __init__(self, instrument: Instrument):
            super().__init__()
            self.instrument = instrument