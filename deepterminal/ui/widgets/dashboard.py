"""
Dashboard widget for DeepTerminal.

This module provides the dashboard widget that displays account information,
strategy statistics, and system status.
"""

from datetime import datetime
from typing import Dict, Optional, Any

from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Label, Rule
from textual.widget import Widget
from textual.reactive import reactive


class InfoCard(Static):
    """A card for displaying information with a title and value."""
    
    def __init__(
        self,
        title: str,
        value: str = "",
        *,
        classes: Optional[str] = None,
        id: Optional[str] = None,
    ):
        """
        Initialize the card.
        
        Args:
            title (str): The card title.
            value (str): The card value.
            classes (Optional[str]): CSS classes.
            id (Optional[str]): Widget ID.
        """
        self.card_title = title
        self.card_value = value
        super().__init__("", classes=classes, id=id)
    
    def update_value(self, value: Any) -> None:
        """
        Update the card value.
        
        Args:
            value (Any): The new value.
        """
        self.card_value = str(value)
        self.update(self.get_content())
    
    def get_content(self) -> str:
        """
        Get the card content.
        
        Returns:
            str: The formatted content.
        """
        return f"[b]{self.card_title}[/b]\n{self.card_value}"
    
    def render(self) -> str:
        """
        Render the card.
        
        Returns:
            str: The rendered content.
        """
        return self.get_content()


class AccountPanel(Container):
    """Panel for displaying account information."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the panel."""
        super().__init__(*args, **kwargs)
        self.balance_card = InfoCard("Balance", "$0.00", id="balance_card")
        self.equity_card = InfoCard("Equity", "$0.00", id="equity_card")
        self.margin_used_card = InfoCard("Margin Used", "$0.00", id="margin_used_card")
        self.margin_available_card = InfoCard("Margin Available", "$0.00", id="margin_available_card")
        self.pnl_daily_card = InfoCard("Daily P&L", "$0.00", id="pnl_daily_card")
        self.pnl_total_card = InfoCard("Total P&L", "$0.00", id="pnl_total_card")
    
    def compose(self):
        """Compose the panel."""
        yield Label("Account Information", classes="panel-title")
        yield Rule()
        
        with Horizontal():
            yield self.balance_card
            yield self.equity_card
        
        with Horizontal():
            yield self.margin_used_card
            yield self.margin_available_card
        
        with Horizontal():
            yield self.pnl_daily_card
            yield self.pnl_total_card
    
    def update_data(self, account_info: Dict[str, Any]) -> None:
        """
        Update the panel with new account data.
        
        Args:
            account_info (Dict[str, Any]): Account information.
        """
        self.balance_card.update_value(f"${account_info.get('balance', 0.0):,.2f}")
        self.equity_card.update_value(f"${account_info.get('equity', 0.0):,.2f}")
        self.margin_used_card.update_value(f"${account_info.get('margin_used', 0.0):,.2f}")
        self.margin_available_card.update_value(f"${account_info.get('margin_available', 0.0):,.2f}")
        
        # Style P&L based on positive/negative
        pnl_daily = account_info.get('pnl_daily', 0.0)
        pnl_total = account_info.get('pnl_total', 0.0)
        
        daily_color = 'green' if pnl_daily >= 0 else 'red'
        total_color = 'green' if pnl_total >= 0 else 'red'
        
        self.pnl_daily_card.update_value(f"${pnl_daily:,.2f}")
        self.pnl_total_card.update_value(f"${pnl_total:,.2f}")
        
        self.pnl_daily_card.styles.color = daily_color
        self.pnl_total_card.styles.color = total_color


class StrategyPanel(Container):
    """Panel for displaying strategy statistics."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the panel."""
        super().__init__(*args, **kwargs)
        self.active_strategies_card = InfoCard("Active Strategies", "0", id="active_strategies_card")
        self.signals_today_card = InfoCard("Signals Today", "0", id="signals_today_card")
        self.win_rate_card = InfoCard("Win Rate", "0%", id="win_rate_card")
        self.avg_trade_card = InfoCard("Avg. Trade", "$0.00", id="avg_trade_card")
    
    def compose(self):
        """Compose the panel."""
        yield Label("Strategy Stats", classes="panel-title")
        yield Rule()
        
        with Horizontal():
            yield self.active_strategies_card
            yield self.signals_today_card
        
        with Horizontal():
            yield self.win_rate_card
            yield self.avg_trade_card
    
    def update_data(self, strategy_stats: Dict[str, Any]) -> None:
        """
        Update the panel with new strategy statistics.
        
        Args:
            strategy_stats (Dict[str, Any]): Strategy statistics.
        """
        self.active_strategies_card.update_value(str(strategy_stats.get('active_strategies', 0)))
        self.signals_today_card.update_value(str(strategy_stats.get('total_signals_today', 0)))
        self.win_rate_card.update_value(f"{strategy_stats.get('win_rate', 0.0):.1f}%")
        self.avg_trade_card.update_value(f"${strategy_stats.get('average_trade', 0.0):,.2f}")


class SystemPanel(Container):
    """Panel for displaying system status."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the panel."""
        super().__init__(*args, **kwargs)
        self.status_card = InfoCard("Status", "Stopped", id="status_card")
        self.last_update_card = InfoCard("Last Update", "-", id="last_update_card")
        self.orders_card = InfoCard("Pending Orders", "0", id="orders_card")
        self.connection_card = InfoCard("Connection", "Disconnected", id="connection_card")
    
    def compose(self):
        """Compose the panel."""
        yield Label("System Status", classes="panel-title")
        yield Rule()
        
        with Horizontal():
            yield self.status_card
            yield self.last_update_card
        
        with Horizontal():
            yield self.orders_card
            yield self.connection_card
    
    def update_data(self, system_stats: Dict[str, Any]) -> None:
        """
        Update the panel with new system statistics.
        
        Args:
            system_stats (Dict[str, Any]): System statistics.
        """
        status = system_stats.get('status', 'Stopped')
        connection = system_stats.get('connection', 'Disconnected')
        
        self.status_card.update_value(status)
        self.last_update_card.update_value(system_stats.get('last_update', '-'))
        self.orders_card.update_value(str(system_stats.get('orders_pending', 0)))
        self.connection_card.update_value(connection)
        
        # Style status based on running/stopped
        if status == "Running":
            self.status_card.styles.color = 'green'
        else:
            self.status_card.styles.color = 'red'
        
        # Style connection based on connected/disconnected
        if connection == "Connected":
            self.connection_card.styles.color = 'green'
        else:
            self.connection_card.styles.color = 'red'


class DashboardWidget(Container):
    """Dashboard widget displaying overall system information."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the dashboard."""
        super().__init__(*args, **kwargs)
        self.account_panel = AccountPanel(id="account_panel")
        self.strategy_panel = StrategyPanel(id="strategy_panel")
        self.system_panel = SystemPanel(id="system_panel")
    
    def compose(self):
        """Compose the dashboard."""
        with Horizontal():
            yield self.account_panel
            yield self.strategy_panel
            yield self.system_panel
    
    def update_data(
        self,
        account_info: Dict[str, Any],
        strategy_stats: Dict[str, Any],
        system_stats: Dict[str, Any]
    ) -> None:
        """
        Update the dashboard with new data.
        
        Args:
            account_info (Dict[str, Any]): Account information.
            strategy_stats (Dict[str, Any]): Strategy statistics.
            system_stats (Dict[str, Any]): System status.
        """
        self.account_panel.update_data(account_info)
        self.strategy_panel.update_data(strategy_stats)
        self.system_panel.update_data(system_stats)