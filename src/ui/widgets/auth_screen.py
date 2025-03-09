"""
Authentication screen widget
"""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Button, LoadingIndicator
from textual.reactive import reactive
from textual import work
from textual.message import Message
import time
import os
import json

from src.auth.authenticator import UpstoxAuthenticator
from src.utils.logger import logger

class AuthScreen(Container):
    """Authentication screen widget"""
    
    is_authenticating = reactive(False)
    error_message = reactive("")
    
    def __init__(self, authenticator: UpstoxAuthenticator, id: str = None):
        super().__init__(id=id)
        self.authenticator = authenticator
    
    def compose(self) -> ComposeResult:
        """Compose the widget"""
        yield Static("Upstox Trading Terminal", id="auth_title")
        yield Static("Please authenticate with your Upstox account", id="auth_subtitle")
        yield Button("Login", id="login_button", variant="primary")
        
        with Container(id="auth_status", classes="hidden"):
            yield LoadingIndicator(id="auth_loading")
            yield Static("", id="auth_message")
        
        if self.error_message:
            yield Static(self.error_message, id="auth_error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press event"""
        if event.button.id == "login_button":
            self.authenticate()
    
    def watch_is_authenticating(self, is_authenticating: bool) -> None:
        """Watch for changes in authentication state"""
        status_container = self.query_one("#auth_status")
        if is_authenticating:
            status_container.remove_class("hidden")
            self.query_one("#login_button").add_class("hidden")
        else:
            status_container.add_class("hidden")
            self.query_one("#login_button").remove_class("hidden")
    
    def watch_error_message(self, error_message: str) -> None:
        """Watch for changes in error message"""
        if error_message:
            try:
                error_widget = self.query_one("#auth_error")
                error_widget.update(error_message)
            except:
                self.mount(Static(error_message, id="auth_error"))
        else:
            try:
                error_widget = self.query_one("#auth_error")
                error_widget.remove()
            except:
                pass
    
    def manually_verify_token(self) -> bool:
        """Manually verify token by checking the token file"""
        try:
            # Check for token file
            token_file = os.path.expanduser("~/.upstox_tokens.json")
            if not os.path.exists(token_file):
                logger.error("Token file not found")
                return False
                
            # Read token file
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            # Check token data
            access_token = token_data.get('access_token')
            token_expiry = token_data.get('expiry', 0)
            
            # Verify token is valid
            if access_token and token_expiry > time.time() + 60:
                logger.info("Manual token verification successful")
                
                # Update authenticator with token data
                self.authenticator.access_token = access_token
                self.authenticator.refresh_token = token_data.get('refresh_token')
                self.authenticator.token_expiry = token_expiry
                
                return True
            else:
                logger.error("Token invalid or expired during manual verification")
                return False
                
        except Exception as e:
            logger.error(f"Error during manual token verification: {e}")
            return False
    
    @work
    async def authenticate(self) -> None:
        """Authenticate with Upstox"""
        self.is_authenticating = True
        self.error_message = ""
        self.query_one("#auth_message").update("Authenticating with Upstox...")
        
        # Check if already authenticated
        if self.authenticator.is_authenticated():
            self.query_one("#auth_message").update("Already authenticated!")
            self.is_authenticating = False
            self.post_message(self.Authenticated())
            return
        
        # Attempt to authenticate
        try:
            result = self.authenticator.authenticate()
            logger.info(f"Authentication result: {result}")
            if result:
                logger.info("Authentication successful")
                self.query_one("#auth_message").update("Authentication successful!")
                
                # Use set_timer instead of sleep to add delay
                def verify_and_continue():
                    # First check if authenticated through normal method
                    if self.authenticator.is_authenticated():
                        logger.info("Normal authentication verification successful")
                        self.is_authenticating = False
                        self.post_message(self.Authenticated())
                    else:
                        # Try manual verification as backup
                        logger.warning("Normal verification failed, attempting manual verification")
                        if self.manually_verify_token():
                            self.is_authenticating = False
                            self.post_message(self.Authenticated())
                        else:
                            self.is_authenticating = False
                            self.error_message = "Authentication verification failed. Please try again."
                
                # Add a longer delay to ensure token is fully processed and saved
                self.set_timer(5, verify_and_continue)
            else:
                self.is_authenticating = False
                self.error_message = "Authentication failed. Please try again."
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            self.is_authenticating = False
            self.error_message = f"Authentication error: {str(e)}"
    
    class Authenticated(Message):
        """Message sent when authentication is successful"""
        pass
    """Authentication screen widget"""
    
    is_authenticating = reactive(False)
    error_message = reactive("")
    
    def __init__(self, authenticator: UpstoxAuthenticator, id: str = None):
        super().__init__(id=id)
        self.authenticator = authenticator
    
    def compose(self) -> ComposeResult:
        """Compose the widget"""
        yield Static("Upstox Trading Terminal", id="auth_title")
        yield Static("Please authenticate with your Upstox account", id="auth_subtitle")
        yield Button("Login", id="login_button", variant="primary")
        
        with Container(id="auth_status", classes="hidden"):
            yield LoadingIndicator(id="auth_loading")
            yield Static("", id="auth_message")
        
        if self.error_message:
            yield Static(self.error_message, id="auth_error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press event"""
        if event.button.id == "login_button":
            self.authenticate()
    
    def watch_is_authenticating(self, is_authenticating: bool) -> None:
        """Watch for changes in authentication state"""
        status_container = self.query_one("#auth_status")
        if is_authenticating:
            status_container.remove_class("hidden")
            self.query_one("#login_button").add_class("hidden")
        else:
            status_container.add_class("hidden")
            self.query_one("#login_button").remove_class("hidden")
    
    def watch_error_message(self, error_message: str) -> None:
        """Watch for changes in error message"""
        if error_message:
            try:
                error_widget = self.query_one("#auth_error")
                error_widget.update(error_message)
            except:
                self.mount(Static(error_message, id="auth_error"))
        else:
            try:
                error_widget = self.query_one("#auth_error")
                error_widget.remove()
            except:
                pass
    
    @work
    async def authenticate(self) -> None:
        """Authenticate with Upstox"""
        self.is_authenticating = True
        self.error_message = ""
        self.query_one("#auth_message").update("Authenticating with Upstox...")
        
        # Check if already authenticated
        if self.authenticator.is_authenticated():
            self.query_one("#auth_message").update("Already authenticated!")
            self.is_authenticating = False
            self.post_message(self.Authenticated())
            return
        
        # Attempt to authenticate
        try:
            result = self.authenticator.authenticate()
            logger.info(f"Authentication result: {result}")
            if result:
                logger.info("*****In result block*****")
                self.query_one("#auth_message").update("Authentication successful!")
                
                # Use set_timer instead of sleep to add delay
                def verify_and_continue():
                    # Verify authentication status
                    if self.authenticator.is_authenticated():
                        self.is_authenticating = False
                        self.post_message(self.Authenticated())
                    else:
                        self.is_authenticating = False
                        self.error_message = "Authentication verification failed. Please try again.1"
                
                # Add a delay to ensure token is fully processed and saved
                self.set_timer(5, verify_and_continue)
            else:
                self.is_authenticating = False
                self.error_message = "Authentication failed. Please try again.2"
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            self.is_authenticating = False
            self.error_message = f"Authentication error: {str(e)}"
    
    class Authenticated(Message):
        """Message sent when authentication is successful"""
        pass