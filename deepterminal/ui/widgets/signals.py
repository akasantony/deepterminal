"""
Signals widget for DeepTerminal.

This module provides the widget for displaying and acting on trading signals.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from textual.containers import Container, Vertical
from textual.widgets import DataTable, Button, Static, Rule, Label
from textual.widget import Widget
from textual.reactive import reactive
from textual.message import Message

from deepterminal.core.models.signal import Signal, SignalStrength, SignalType, SignalStatus
from deepterminal.core.models.order import OrderSide


class SignalDetailsPanel(Container):
    """Panel for displaying detailed information about a selected signal."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the panel."""
        super().__init__(*args, **kwargs)
        self.signal = None
    
    def compose(self):
        """Compose the panel."""
        yield Label("Signal Details", classes="panel-title")
        yield Rule()
        yield Static("Select a signal to view details", id="signal_details_content")
        
        with Container(id="signal_action_buttons"):
            yield Button("Execute Signal", variant="success", id="execute_signal_button", disabled=True)
            yield Button("Ignore Signal", variant="error", id="ignore_signal_button", disabled=True)
    
    def update_signal(self, signal: Optional[Signal]) -> None:
        """
        Update the panel with a new signal.
        
        Args:
            signal (Optional[Signal]): The signal to display, or None to clear.
        """
        self.signal = signal
        
        content = self.query_one("#signal_details_content", Static)
        
        if not signal:
            content.update("Select a signal to view details")
            self.query_one("#execute_signal_button").disabled = True
            self.query_one("#ignore_signal_button").disabled = True
            return
        
        # Only enable execution for active signals
        is_active = signal.status == SignalStatus.ACTIVE
        self.query_one("#execute_signal_button").disabled = not is_active
        self.query_one("#ignore_signal_button").disabled = not is_active
        
        # Format the signal details
        symbol = signal.instrument.symbol
        signal_type = signal.signal_type.value.upper()
        side = signal.side.value.upper()
        side_color = "green" if side == "BUY" else "red"
        strength = signal.strength.value.title()
        strength_colors = {
            "Weak": "yellow",
            "Moderate": "yellow",
            "Strong": "green",
            "Very_strong": "green"
        }
        
        # Format times
        timestamp = signal.timestamp
        expiration = signal.expiration
        now = datetime.utcnow()
        
        if expiration:
            time_left = expiration - now
            if time_left.total_seconds() > 0:
                hours, remainder = divmod(time_left.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                expiry_str = f"{int(hours)}h {int(minutes)}m remaining"
            else:
                expiry_str = "Expired"
        else:
            expiry_str = "No expiration"
        
        # Build the indicators table
        indicators_str = ""
        for name, value in signal.indicators.items():
            indicators_str += f"{name}: {value}\n"
        
        # Build the details text
        details = f"""[b]{symbol} - {signal_type} - [color={side_color}]{side}[/color][/b]
            Strength: [color={strength_colors.get(strength, 'white')}]{strength}[/color]
            Confidence: {signal.confidence * 100:.1f}%
            Win Probability: {signal.win_probability * 100:.1f}%

            [b]Prices:[/b]
            Entry: {"$" + str(signal.entry_price) if signal.entry_price else "Market"}
            Stop Loss: {"$" + str(signal.stop_loss) if signal.stop_loss else "None"}
            Take Profit: {"$" + str(signal.take_profit) if signal.take_profit else "None"}
            Risk/Reward: {signal.risk_reward_ratio:.2f} if signal.risk_reward_ratio else "N/A"

            [b]Timing:[/b]
            Generated: {timestamp.strftime("%H:%M:%S")}
            {expiry_str}

            [b]Status:[/b] {signal.status.value.title()}

            [b]Indicators:[/b]
            {indicators_str}

            [b]Strategy:[/b] {signal.strategy_id}
            """
        
        # Update the content
        content.update(details)


class SignalsTable(DataTable):
    """Table for displaying signals."""
    
    class SignalSelected(Message):
        """Message sent when a signal is selected."""
        
        def __init__(self, signal: Signal) -> None:
            """
            Initialize the message.
            
            Args:
                signal (Signal): The selected signal.
            """
            self.signal = signal
            super().__init__()
    
    def __init__(self, *args, **kwargs):
        """Initialize the table."""
        super().__init__(*args, **kwargs)
        self.signals = []
    
    def on_mount(self) -> None:
        """Handle the mount event."""
        # Add columns
        self.add_columns(
            "Symbol",
            "Type",
            "Side",
            "Strength",
            "Probability",
            "Entry",
            "R/R",
            "Expiry",
            "Status"
        )
    
    def update_signals(self, signals: List[Signal]) -> None:
        """
        Update the table with new signals.
        
        Args:
            signals (List[Signal]): The signals to display.
        """
        self.signals = signals
        
        # Clear the table
        self.clear()
        
        # Sort signals by timestamp (newest first) and status (active first)
        sorted_signals = sorted(
            signals,
            key=lambda s: (s.status != SignalStatus.ACTIVE, -s.timestamp.timestamp())
        )
        
        # Add signals
        for signal in sorted_signals:
            # Format expiry time
            if signal.expiration:
                now = datetime.utcnow()
                time_left = signal.expiration - now
                if time_left.total_seconds() > 0:
                    hours, remainder = divmod(time_left.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    expiry_str = f"{int(hours)}h {int(minutes)}m"
                else:
                    expiry_str = "Expired"
            else:
                expiry_str = "None"
            
            # Format side
            side = signal.side.value.upper()
            side_cell = f"[green]{side}[/green]" if side == "BUY" else f"[red]{side}[/red]"
            
            # Format strength
            strength = signal.strength.value.title()
            strength_colors = {
                "Weak": "yellow",
                "Moderate": "yellow",
                "Strong": "green",
                "Very_strong": "green"
            }
            strength_cell = f"[{strength_colors.get(strength, 'white')}]{strength}[/]"
            
            # Format status
            status = signal.status.value.title()
            status_colors = {
                "Active": "green",
                "Executed": "blue",
                "Expired": "grey",
                "Cancelled": "red",
                "Invalidated": "red"
            }
            status_cell = f"[{status_colors.get(status, 'white')}]{status}[/]"
            
            # Format entry price
            entry = f"${signal.entry_price:.2f}" if signal.entry_price else "Market"
            
            # Format risk/reward
            rr = f"{signal.risk_reward_ratio:.1f}" if signal.risk_reward_ratio else "N/A"
            
            row = (
                signal.instrument.symbol,
                signal.signal_type.value.title(),
                side_cell,
                strength_cell,
                f"{signal.win_probability * 100:.1f}%",
                entry,
                rr,
                expiry_str,
                status_cell
            )
            
            self.add_row(*row, key=signal.id)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """
        Handle row selection.
        
        Args:
            event (DataTable.RowSelected): The row selected event.
        """
        # Get the signal ID from the row key
        signal_id = event.row_key.value
        
        # Find the signal
        signal = next((s for s in self.signals if s.id == signal_id), None)
        
        if signal:
            # Emit the signal selected message
            self.post_message(self.SignalSelected(signal))


class SignalsWidget(Container):
    """Widget for displaying and acting on trading signals."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the widget."""
        super().__init__(*args, **kwargs)
        self.signals_table = SignalsTable(id="signals_table")
        self.details_panel = SignalDetailsPanel(id="signal_details_panel")
    
    def compose(self):
        """Compose the widget."""
        yield Label("Trading Signals", classes="widget-title")
        yield Rule()
        
        with Vertical(id="signals_container"):
            yield self.signals_table
            yield self.details_panel
    
    def on_signals_table_signal_selected(self, event: SignalsTable.SignalSelected) -> None:
        """
        Handle signal selection.
        
        Args:
            event (SignalsTable.SignalSelected): The signal selected event.
        """
        self.details_panel.update_signal(event.signal)
    
    def update_signals(self, signals: List[Signal]) -> None:
        """
        Update the widget with new signals.
        
        Args:
            signals (List[Signal]): The signals to display.
        """
        self.signals_table.update_signals(signals)
        
        # Clear the details panel if we have no signals
        if not signals:
            self.details_panel.update_signal(None)
        
        # Count active signals
        active_signals = sum(1 for s in signals if s.status == SignalStatus.ACTIVE)
        
        # Update title based on number of signals
        self.query_one(".widget-title", Label).update(
            f"Trading Signals ({active_signals} active, {len(signals)} total)"
        )