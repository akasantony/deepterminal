"""
Positions widget for DeepTerminal.

This module provides the widget for displaying and managing trading positions.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from textual.containers import Container, Vertical
from textual.widgets import DataTable, Button, Static, Rule, Label
from textual.widget import Widget
from textual.reactive import reactive
from textual.message import Message

from deepterminal.core.models.position import Position, PositionSide


class PositionDetailsPanel(Container):
    """Panel for displaying detailed information about a selected position."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the panel."""
        super().__init__(*args, **kwargs)
        self.position = None
    
    def compose(self):
        """Compose the panel."""
        yield Label("Position Details", classes="panel-title")
        yield Rule()
        yield Static("Select a position to view details", id="position_details_content")
        
        with Container(id="position_action_buttons"):
            yield Button("Close Position", variant="error", id="close_position_button", disabled=True)
            yield Button("Edit Stop Loss", variant="warning", id="edit_sl_button", disabled=True)
            yield Button("Edit Take Profit", variant="success", id="edit_tp_button", disabled=True)
    
    def update_position(self, position: Optional[Position]) -> None:
        """
        Update the panel with a new position.
        
        Args:
            position (Optional[Position]): The position to display, or None to clear.
        """
        self.position = position
        
        content = self.query_one("#position_details_content", Static)
        
        if not position:
            content.update("Select a position to view details")
            self.query_one("#close_position_button").disabled = True
            self.query_one("#edit_sl_button").disabled = True
            self.query_one("#edit_tp_button").disabled = True
            return
        
        # Enable action buttons
        self.query_one("#close_position_button").disabled = False
        self.query_one("#edit_sl_button").disabled = False
        self.query_one("#edit_tp_button").disabled = False
        
        # Format the position details
        symbol = position.instrument.symbol
        side = position.side.value.upper()
        side_color = "green" if side == "LONG" else "red"
        
        # Calculate time in position
        open_time = position.open_time
        now = datetime.utcnow()
        duration = now - open_time
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{int(hours)}h {int(minutes)}m"
        
        # Format P&L
        pnl = position.unrealized_pnl
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_pct = position.unrealized_pnl_percentage
        
        # Build the details text
        details = f"""[b]{symbol} - [color={side_color}]{side}[/color][/b]
Quantity: {position.quantity}
Entry Price: ${position.entry_price:.2f}
Current Price: ${position.current_price:.2f}
Time in Position: {time_str}

[b]P&L:[/b] [color={pnl_color}]${pnl:.2f} ({pnl_pct:.2f}%)[/color]

[b]Risk Management:[/b]
Stop Loss: {"$" + str(position.stop_loss) if position.stop_loss else "None"}
Take Profit: {"$" + str(position.take_profit) if position.take_profit else "None"}
Trailing Stop: {"$" + str(position.trailing_stop) if position.trailing_stop else "None"}

[b]Orders:[/b]
Entry Orders: {len(position.entry_order_ids)}
Exit Orders: {len(position.exit_order_ids)}
Stop Orders: {len(position.stop_order_ids)}

[b]Strategy:[/b] {position.strategy_id or "Manual"}
Open Time: {open_time.strftime("%Y-%m-%d %H:%M:%S UTC")}
"""
        
        # Update the content
        content.update(details)


class PositionsTable(DataTable):
    """Table for displaying positions."""
    
    class PositionSelected(Message):
        """Message sent when a position is selected."""
        
        def __init__(self, position: Position) -> None:
            """
            Initialize the message.
            
            Args:
                position (Position): The selected position.
            """
            self.position = position
            super().__init__()
    
    def __init__(self, *args, **kwargs):
        """Initialize the table."""
        super().__init__(*args, **kwargs)
        self.positions = []
    
    def on_mount(self) -> None:
        """Handle the mount event."""
        # Add columns
        self.add_columns(
            "Symbol",
            "Side",
            "Quantity",
            "Entry Price",
            "Current Price",
            "P&L",
            "P&L %",
            "Time",
        )
    
    def update_positions(self, positions: List[Position]) -> None:
        """
        Update the table with new positions.
        
        Args:
            positions (List[Position]): The positions to display.
        """
        self.positions = positions
        
        # Clear the table
        self.clear()
        
        # Add positions
        for position in positions:
            # Calculate P&L
            pnl = position.unrealized_pnl
            pnl_pct = position.unrealized_pnl_percentage
            
            # Format time in position
            duration = datetime.utcnow() - position.open_time
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{int(hours)}h {int(minutes)}m"
            
            # Format the row
            side = position.side.value.upper()
            side_cell = f"[green]{side}[/green]" if side == "LONG" else f"[red]{side}[/red]"
            
            pnl_cell = f"[green]${pnl:.2f}[/green]" if pnl >= 0 else f"[red]${pnl:.2f}[/red]"
            pnl_pct_cell = f"[green]{pnl_pct:.2f}%[/green]" if pnl >= 0 else f"[red]{pnl_pct:.2f}%[/red]"
            
            row = (
                position.instrument.symbol,
                side_cell,
                str(position.quantity),
                f"${position.entry_price:.2f}",
                f"${position.current_price:.2f}",
                pnl_cell,
                pnl_pct_cell,
                time_str,
            )
            
            self.add_row(*row, key=position.id)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """
        Handle row selection.
        
        Args:
            event (DataTable.RowSelected): The row selected event.
        """
        # Get the position ID from the row key
        position_id = event.row_key.value
        
        # Find the position
        position = next((p for p in self.positions if p.id == position_id), None)
        
        if position:
            # Emit the position selected message
            self.post_message(self.PositionSelected(position))


class PositionsWidget(Container):
    """Widget for displaying and managing positions."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the widget."""
        super().__init__(*args, **kwargs)
        self.positions_table = PositionsTable(id="positions_table")
        self.details_panel = PositionDetailsPanel(id="position_details_panel")
    
    def compose(self):
        """Compose the widget."""
        yield Label("Open Positions", classes="widget-title")
        yield Rule()
        
        with Vertical(id="positions_container"):
            yield self.positions_table
            yield self.details_panel
    
    def on_positions_table_position_selected(self, event: PositionsTable.PositionSelected) -> None:
        """
        Handle position selection.
        
        Args:
            event (PositionsTable.PositionSelected): The position selected event.
        """
        self.details_panel.update_position(event.position)
    
    def update_positions(self, positions: List[Position]) -> None:
        """
        Update the widget with new positions.
        
        Args:
            positions (List[Position]): The positions to display.
        """
        self.positions_table.update_positions(positions)
        
        # Clear the details panel if we have no positions
        if not positions:
            self.details_panel.update_position(None)
        
        # Update title based on number of positions
        self.query_one(".widget-title", Label).update(f"Open Positions ({len(positions)})")