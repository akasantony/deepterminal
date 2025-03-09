"""
Main application UI
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tab, TabPane, TabbedContent
from textual.css.query import NoMatches

from src.auth.authenticator import UpstoxAuthenticator
from src.api.upstox_client import UpstoxClient
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.ui.widgets.auth_screen import AuthScreen
from src.ui.widgets.instrument_selector import InstrumentSelector
from src.ui.widgets.trading_panel import TradingPanel
from src.ui.widgets.pnl_display import PnLDisplay
from src.utils.config import load_config
from src.utils.logger import logger


class TradingApp(App):
    """Main trading application"""
    
    CSS_PATH = "styles.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("ctrl+t", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load configuration
        self.config = load_config()
        
        # Initialize components
        self.authenticator = UpstoxAuthenticator(
            api_key=self.config["API_KEY"],
            api_secret=self.config["API_SECRET"],
            redirect_uri=self.config["REDIRECT_URI"]
        )
        
        self.client = None
        self.order_manager = None
        self.position_tracker = None
        self.initialized = False
    
    def compose(self) -> ComposeResult:
        """Compose the initial UI"""
        yield Header()
        
        # Initially show the auth screen
        yield AuthScreen(self.authenticator)
        
        # Main content (hidden initially)
        with TabbedContent(id="main_content", classes="hidden"):
            with TabPane("Trading", id="trading_tab"):
                yield InstrumentSelector(id="instrument_selector")
                yield TradingPanel(id="trading_panel")
            
            with TabPane("Positions & P&L", id="positions_tab"):
                yield PnLDisplay(id="pnl_display")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Handle app mount event"""
        # Set dark mode
        self.dark = True

    def on_auth_screen_authenticated(self) -> None:
        """Handle authentication success"""
        try:
            # Initialize API client
            self.client = UpstoxClient(self.authenticator)
            
            # Move UI updates first
            try:
                self.query_one(AuthScreen).add_class("hidden")
                self.query_one("#main_content").remove_class("hidden")
            except NoMatches:
                logger.error("UI elements not found")
                return
            
            # Initialize components with dependencies but WAIT before starting services
            self.order_manager = OrderManager(self.client)
            self.position_tracker = PositionTracker(self.client)
            
            # Set default values for order manager
            self.order_manager.set_default_quantity(self.config["DEFAULT_QUANTITY"])
            
            # Initialize UI components
            self.query_one(InstrumentSelector).initialize(self.client)
            self.query_one(TradingPanel).initialize(
                client=self.client, 
                order_manager=self.order_manager,
                position_tracker=self.position_tracker
            )
            self.query_one(PnLDisplay).initialize(
                client=self.client, 
                position_tracker=self.position_tracker
            )
            
            # Give the UI a moment to update before starting services
            def start_services():
                # Setup websocket connection FIRST
                self.client.connect_websocket()
                # Wait a short time for WebSocket to initialize
                def start_monitoring():
                    # Start position monitoring AFTER WebSocket is connected
                    self.position_tracker.start_monitoring()
                    self.initialized = True
                    logger.info("Application fully initialized with services")
                
                # Schedule position monitoring to start after WebSocket connection
                self.set_timer(2.0, start_monitoring)
            
            # Delay service start to allow UI to render first
            self.set_timer(0.5, start_services)
            
            logger.info("Application initialized successfully")
        
        except Exception as e:
            logger.error(f"Error initializing application: {e}")
            self.exit(message=f"Error: {str(e)}")
 
    def on_instrument_selector_instrument_selected(self, message) -> None:
        """Handle instrument selection event"""
        if self.initialized:
            # Pass the selected instrument to the trading panel
            self.query_one(TradingPanel).set_instrument(message.instrument)
    
    def action_refresh(self) -> None:
        """Refresh data"""
        if self.initialized:
            # Refresh positions
            self.position_tracker.fetch_positions()
            
            # Refresh PnL display
            self.query_one(PnLDisplay).refresh_positions()
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode"""
        self.dark = not self.dark