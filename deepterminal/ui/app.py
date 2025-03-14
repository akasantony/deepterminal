"""
DeepTerminal main application UI.

This module provides the main Textual application for DeepTerminal.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, DataTable, Rule, Placeholder, Input, Label
from textual import events, work

from deepterminal.core.models.signal import Signal
from deepterminal.core.models.order import Order
from deepterminal.core.models.position import Position
from deepterminal.ui.widgets.dashboard import DashboardWidget
from deepterminal.ui.widgets.positions import PositionsWidget
from deepterminal.ui.widgets.signals import SignalsWidget
from deepterminal.ui.screens.login import LoginScreen


class DeepTerminalApp(App):
    """Main DeepTerminal application."""
    
    TITLE = "DeepTerminal - Algorithmic Trading"
    SUB_TITLE = "Futures & Options Trader"
    
    CSS_PATH = "styles.css"
    
    BINDINGS = [
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "emergency_exit", "Emergency Exit"),
        Binding("s", "settings", "Settings"),
        Binding("h", "help", "Help"),
    ]
    
    def __init__(self, *args, **kwargs):
        """Initialize the application."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("ui.app")
        
        # Application state
        self.is_authenticated = False
        self.is_connected = False
        self.active_strategies = []
        self.positions = []
        self.signals = []
        self.orders = []
        
        # Data update interval (in seconds)
        self.update_interval = 5
    
    def compose(self) -> ComposeResult:
        """Compose the application UI."""
        yield Header()
        
        with Container(id="main"):
            # Top panel: Dashboard
            yield DashboardWidget(id="dashboard")
            
            yield Rule()
            
            # Middle panel: Positions and Signals
            with Horizontal():
                # Left: Positions
                yield PositionsWidget(id="positions")
                
                # Right: Signals
                yield SignalsWidget(id="signals")
            
            yield Rule()
            
            # Bottom panel: Controls
            with Horizontal(id="controls"):
                yield Button("Start", id="start_button", variant="success")
                yield Button("Stop", id="stop_button", variant="error", disabled=True)
                yield Button("Pause", id="pause_button", variant="warning")
                yield Button("Emergency Exit", id="emergency_button", variant="error")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Handle the mount event."""
        # Check if user is authenticated
        if not self.is_authenticated:
            self.push_screen(LoginScreen())
        
        # Start the periodic data update
        self.update_data_worker()
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark
    
    def action_refresh(self) -> None:
        """Manually refresh the data."""
        self.update_data()
    
    def action_emergency_exit(self) -> None:
        """Trigger an emergency exit of all positions."""
        self.exit_all_positions()
    
    def action_settings(self) -> None:
        """Open the settings screen."""
        from deepterminal.ui.screens.settings import SettingsScreen
        self.push_screen(SettingsScreen())
    
    def action_help(self) -> None:
        """Show the help screen."""
        from deepterminal.ui.screens.help import HelpScreen
        self.push_screen(HelpScreen())
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "start_button":
            self.start_trading()
        elif button_id == "stop_button":
            self.stop_trading()
        elif button_id == "pause_button":
            self.pause_trading()
        elif button_id == "emergency_button":
            self.exit_all_positions()
    
    @work(exclusive=True)
    async def update_data_worker(self) -> None:
        """Worker for periodically updating the data."""
        while True:
            self.update_data()
            await asyncio.sleep(self.update_interval)
    
    def update_data(self) -> None:
        """Update all data from the backend."""
        try:
            # Update dashboard data
            self.update_dashboard()
            
            # Update positions
            self.update_positions()
            
            # Update signals
            self.update_signals()
            
            # Update UI
            self.refresh_ui()
        except Exception as e:
            self.logger.error(f"Error updating data: {e}")
    
    def update_dashboard(self) -> None:
        """Update the dashboard data."""
        dashboard = self.query_one(DashboardWidget)
        
        # In a real implementation, this data would come from the backend
        # For now, we'll use dummy data
        account_info = {
            "balance": 100000.00,
            "equity": 102500.00,
            "margin_used": 25000.00,
            "margin_available": 75000.00,
            "pnl_daily": 2500.00,
            "pnl_total": 15000.00,
        }
        
        strategy_stats = {
            "active_strategies": len(self.active_strategies),
            "total_signals_today": 15,
            "win_rate": 65.0,
            "average_trade": 1250.00,
        }
        
        system_stats = {
            "status": "Running" if self.is_connected else "Disconnected",
            "last_update": datetime.now().strftime("%H:%M:%S"),
            "orders_pending": len([o for o in self.orders if o.status in ["pending", "open"]]),
            "connection": "Connected" if self.is_connected else "Disconnected",
        }
        
        dashboard.update_data(account_info, strategy_stats, system_stats)
    
    def update_positions(self) -> None:
        """Update positions data."""
        positions_widget = self.query_one(PositionsWidget)
        
        # In a real implementation, this data would come from the backend
        # For now, we'll assume self.positions is already populated
        
        positions_widget.update_positions(self.positions)
    
    def update_signals(self) -> None:
        """Update signals data."""
        signals_widget = self.query_one(SignalsWidget)
        
        # In a real implementation, this data would come from the backend
        # For now, we'll assume self.signals is already populated
        
        signals_widget.update_signals(self.signals)
    
    def refresh_ui(self) -> None:
        """Refresh all UI components."""
        # This will trigger a refresh of all widgets
        self.refresh()
    
    def start_trading(self) -> None:
        """Start the trading engine."""
        self.notify("Starting trading engine...")
        
        # In a real implementation, this would start the trading engine
        # For now, we'll just update the UI state
        
        self.query_one("#start_button").disabled = True
        self.query_one("#stop_button").disabled = False
        self.query_one("#pause_button").disabled = False
        
        self.is_connected = True
        self.update_dashboard()
    
    def stop_trading(self) -> None:
        """Stop the trading engine."""
        self.notify("Stopping trading engine...")
        
        # In a real implementation, this would stop the trading engine
        # For now, we'll just update the UI state
        
        self.query_one("#start_button").disabled = False
        self.query_one("#stop_button").disabled = True
        self.query_one("#pause_button").disabled = True
        
        self.is_connected = False
        self.update_dashboard()
    
    def pause_trading(self) -> None:
        """Pause the trading engine."""
        if self.query_one("#pause_button").label.plain == "Pause":
            self.notify("Pausing trading engine...")
            self.query_one("#pause_button").label = "Resume"
        else:
            self.notify("Resuming trading engine...")
            self.query_one("#pause_button").label = "Pause"
    
    def exit_all_positions(self) -> None:
        """Exit all open positions."""
        self.notify("EMERGENCY EXIT: Closing all positions!", severity="error")
        
        # In a real implementation, this would trigger an emergency exit
        # For now, we'll just show a notification