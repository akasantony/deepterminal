"""
Authentication module for Upstox API
"""

import json
import logging
import os
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Dict, Optional, Callable
from urllib.parse import parse_qs, urlparse

import requests

from src.utils.logger import logger

class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    def __init__(self, *args, callback_fn: Callable[[str], None], **kwargs):
        self.callback_fn = callback_fn
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests to the callback URL"""
        # Parse query parameters
        query = parse_qs(urlparse(self.path).query)
        
        # Extract code or error
        if 'code' in query:
            code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication successful! You can close this window.")
            self.callback_fn(code)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication failed! Please try again.")
            self.callback_fn(None)

def create_callback_handler(callback_fn):
    """Create a callback handler with the specified callback function"""
    return lambda *args, **kwargs: CallbackHandler(*args, callback_fn=callback_fn, **kwargs)

class UpstoxAuthenticator:
    """Handles authentication with Upstox API"""
    
    BASE_URL = "https://api.upstox.com/v2"
    AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
    TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
    
    def __init__(self, api_key: str, api_secret: str, redirect_uri: str):
        """Initialize authenticator with API credentials"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        
        # Try to load saved tokens
        self._load_tokens()
    
    def _load_tokens(self) -> bool:
        """Load saved tokens from file if available"""
        token_file = os.path.expanduser(".upstox_tokens.json")
        
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    token_data = json.load(f)
                
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_expiry = token_data.get('expiry', 0)
                
                # Check if token is still valid
                if self.token_expiry > time.time() + 60:
                    logger.info("Loaded valid tokens from file")
                    return True
                else:
                    logger.info("Loaded tokens are expired")
            except Exception as e:
                logger.error(f"Error loading tokens: {e}")
        
        return False
    
    def _save_tokens(self) -> None:
        """Save tokens to file for later use"""
        token_file = os.path.expanduser(".upstox_tokens.json")
        
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expiry': self.token_expiry
        }
        
        try:
            with open(token_file, 'w') as f:
                json.dump(token_data, f)
            
            # Set permissions to restrict access
            os.chmod(token_file, 0o600)
            logger.info("Saved tokens to file")
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid tokens"""
        # Check if we have a token and it's not expired
        return (
            self.access_token is not None and 
            self.token_expiry > time.time() + 60
        )
    
    def authenticate(self) -> bool:
        """Perform OAuth authentication flow"""
        # If already authenticated, return True
        if self.is_authenticated():
            return True
        
        # Try to refresh token if we have one
        if self.refresh_token:
            if self._refresh_access_token():
                return True
        
        # Otherwise, initiate OAuth flow
        return self._oauth_flow()
    
    def _refresh_access_token(self, max_retries=3) -> bool:
        """Refresh the access token using the refresh token"""
        if not self.refresh_token:
            return False
        
        retries = 0
        while retries < max_retries:
            try:
                data = {
                    'client_id': self.api_key,
                    'client_secret': self.api_secret,
                    'refresh_token': self.refresh_token,
                    'grant_type': 'refresh_token'
                }
                
                response = requests.post(self.TOKEN_URL, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get('access_token')
                    
                    # Check if we got a new refresh token too
                    new_refresh_token = token_data.get('refresh_token')
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token
                    
                    self.token_expiry = time.time() + token_data.get('expires_in', 0)
                    
                    # Save updated tokens
                    self._save_tokens()
                    
                    logger.info("Successfully refreshed access token")
                    return True
                elif response.status_code == 401:
                    # Invalid refresh token - can't recover
                    logger.error("Refresh token is invalid. Re-authentication required.")
                    self.refresh_token = None
                    self._save_tokens()  # Save cleared tokens
                    return False
                else:
                    # Temporary error - can retry
                    logger.warning(f"Failed to refresh token: {response.text}. Retry {retries+1}/{max_retries}")
                    retries += 1
                    time.sleep(1)  # Wait before retrying
            except (requests.RequestException, ConnectionError) as e:
                # Network error - can retry
                logger.warning(f"Network error refreshing token: {e}. Retry {retries+1}/{max_retries}")
                retries += 1
                time.sleep(2)  # Longer wait for network issues
            except Exception as e:
                logger.error(f"Unexpected error refreshing token: {e}")
                return False
        
        logger.error(f"Failed to refresh token after {max_retries} attempts")
        return False
    
    def _oauth_flow(self) -> bool:
        """Initiate OAuth authentication flow"""
        # Generate auth URL
        auth_url = f"{self.AUTH_URL}?client_id={self.api_key}&redirect_uri={self.redirect_uri}&response_type=code"
        
        # Open browser for user to authenticate
        webbrowser.open(auth_url)
        
        # Create a server to listen for the callback
        code = [None]  # Use a list to store the code (mutable)
        
        def callback_fn(auth_code):
            code[0] = auth_code
        
        # Start a local server to receive the callback
        handler = create_callback_handler(callback_fn)
        
        # Parse the redirect_uri to get the port
        parsed_uri = urlparse(self.redirect_uri)
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 8000
        
        server = HTTPServer((host, port), handler)
        
        # Run server in a separate thread
        server_thread = Thread(target=server.handle_request)
        server_thread.daemon = True
        server_thread.start()
        
        logger.info(f"Waiting for authentication at {self.redirect_uri}")
        
        # Wait for the callback to complete
        server_thread.join(timeout=300)
        
        # If we got a code, exchange it for tokens
        if code[0]:
            return self._exchange_code_for_token(code[0])
        else:
            logger.error("Authentication failed or timed out")
            return False
    
    def _exchange_code_for_token(self, code: str) -> bool:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                'code': code,
                'client_id': self.api_key,
                'client_secret': self.api_secret,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post(self.TOKEN_URL, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_expiry = time.time() + token_data.get('expires_in', 0)
                
                # Save tokens
                self._save_tokens()
                
                logger.info("Successfully obtained access token")
                return True
            else:
                logger.error(f"Failed to obtain token: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication token"""
        if not self.is_authenticated():
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }