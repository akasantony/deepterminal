"""
P&L display widget
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Static
from textual.reactive import reactive
from textual import work
from typing import Dict, Optional

from src.api.upstox_client import UpstoxClient
from src.trading.position_tracker import PositionTracker


class PnLDisplay(Container):
    """Widget for displaying position and P&L information"""
    
    is_loading = reactive(False)
    total_pnl = reactive(0.0)
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.client = None
        self.position_tracker = None
    
    def initialize(self, client: UpstoxClient, position_tracker: PositionTracker):
        """Initialize with dependencies"""
        self.client = client
        self.position_tracker = position_tracker
        
        # Register for position updates
        if self.position_tracker:
            self.position_tracker.register_global_callback(self._on_positions_update)
            
            # Initial position fetch
            self.refresh()
    
    def compose(self) -> ComposeResult:
        """Compose the widget"""
        with Vertical(id="pnl_container"):
            with Container(id="pnl_summary"):
                yield Static("Total P&L:", classes="summary_label")
                yield Static("₹0.00", id="total_pnl_value", classes="summary_value")
            
            yield DataTable(id="positions_table", zebra_stripes=True)
            
            with Container(id="positions_status"):
                yield Static("", id="status_message", classes="status_message")
    
    def on_mount(self):
        """Setup the widget on mount"""
        # Setup the positions table
        table = self.query_one("#positions_table")
        table.add_columns(
            "Symbol", "Exchange", "Type", "Quantity", "Avg Price", 
            "LTP", "Unrealized P&L", "Realized P&L", "Total P&L"
        )
    
    def watch_is_loading(self, is_loading: bool) -> None:
        """Watch for changes in loading state"""
        status = self.query_one("#status_message")
        if is_loading:
            status.update("Loading positions...")
        else:
            status.update("")
    
    def watch_total_pnl(self, total_pnl: float) -> None:
        """Watch for changes in total P&L"""
        pnl_value = self.query_one("#total_pnl_value")
        pnl_value.update(f"₹{total_pnl:.2f}")
        
        # Add color class based on P&L
        if total_pnl > 0:
            pnl_value.remove_class("negative")
            pnl_value.add_class("positive")
        elif total_pnl < 0:
            pnl_value.remove_class("positive")
            pnl_value.add_class("negative")
        else:
            pnl_value.remove_class("positive")
            pnl_value.remove_class("negative")
    
    @work
    async def refresh_positions(self) -> None:
        """Refresh positions data"""
        if not self.position_tracker:
            self.query_one("#status_message").update("Position tracker not initialized")
            return
        
        self.is_loading = True
        
        try:
            positions = self.position_tracker.fetch_positions()
            self._update_positions_table(positions)
        except Exception as e:
            self.query_one("#status_message").update(f"Error: {str(e)}")
        
        self.is_loading = False
    
    def _on_positions_update(self, positions_dict: Dict) -> None:
        """Handle position updates"""
        if positions_dict:
            positions = list(positions_dict.values())
            self._update_positions_table(positions)
    
    def _update_positions_table(self, positions) -> None:
        """Update the positions table with new data"""
        if not positions:
            self.query_one("#status_message").update("No positions found")
            self.total_pnl = 0.0
            
            # Clear the table
            table = self.query_one("#positions_table")
            table.clear()
            return
        
        # Update the table
        table = self.query_one("#positions_table")
        table.clear()
        
        # Calculate total P&L
        total_unrealized = 0.0
        total_realized = 0.0
        
        for position in positions:
            # Skip positions with zero quantity
            if position.quantity == 0:
                continue
            
            # Add to totals
            total_unrealized += position.unrealized_pnl
            total_realized += position.realized_pnl
            
            # Format P&L values
            unrealized_pnl = f"₹{position.unrealized_pnl:.2f}"
            realized_pnl = f"₹{position.realized_pnl:.2f}"
            total_pnl = f"₹{position.total_pnl:.2f}"
            
            # Add row to table
            table.add_row(
                position.symbol,
                position.exchange,
                position.product,
                str(position.quantity),
                f"₹{position.average_price:.2f}",
                f"₹{position.last_price:.2f}",
                unrealized_pnl,
                realized_pnl,
                total_pnl
            )
        
        # Update total P&L
        self.total_pnl = total_unrealized + total_realized