"""
Strategy registry for DeepTerminal.

This module provides the registry for managing available trading strategies.
"""

import importlib
import inspect
import logging
import os
from typing import Dict, Type, List, Optional, Any

from deepterminal.strategies.base import StrategyBase


class StrategyRegistry:
    """Registry for managing available trading strategies."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one registry exists."""
        if cls._instance is None:
            cls._instance = super(StrategyRegistry, cls).__new__(cls)
            cls._instance._strategies = {}
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the registry."""
        # Only initialize once
        if not self._initialized:
            self.logger = logging.getLogger("strategy.registry")
            self._strategies = {}
            self._initialized = True
            
            # Auto-discover strategies
            self.discover_strategies()
    
    def register_strategy(self, strategy_class: Type[StrategyBase]) -> bool:
        """
        Register a strategy class.
        
        Args:
            strategy_class (Type[StrategyBase]): The strategy class to register.
            
        Returns:
            bool: True if registration was successful, False otherwise.
        """
        # Check if it's a valid strategy class
        if not inspect.isclass(strategy_class) or not issubclass(strategy_class, StrategyBase):
            self.logger.error(f"Invalid strategy class: {strategy_class}")
            return False
        
        # Get the strategy name
        name = strategy_class.__name__
        
        # Check if the strategy is already registered
        if name in self._strategies:
            self.logger.warning(f"Strategy '{name}' is already registered")
            return False
        
        # Register the strategy
        self._strategies[name] = strategy_class
        self.logger.info(f"Registered strategy: {name}")
        
        return True
    
    def unregister_strategy(self, name: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            name (str): The name of the strategy to unregister.
            
        Returns:
            bool: True if unregistration was successful, False otherwise.
        """
        if name not in self._strategies:
            self.logger.warning(f"Strategy '{name}' is not registered")
            return False
        
        # Unregister the strategy
        del self._strategies[name]
        self.logger.info(f"Unregistered strategy: {name}")
        
        return True
    
    def get_strategy_class(self, name: str) -> Optional[Type[StrategyBase]]:
        """
        Get a strategy class by name.
        
        Args:
            name (str): The name of the strategy.
            
        Returns:
            Optional[Type[StrategyBase]]: The strategy class, or None if not found.
        """
        return self._strategies.get(name)
    
    def get_all_strategies(self) -> Dict[str, Type[StrategyBase]]:
        """
        Get all registered strategies.
        
        Returns:
            Dict[str, Type[StrategyBase]]: Dictionary of strategy names to classes.
        """
        return self._strategies.copy()
    
    def discover_strategies(self) -> None:
        """Discover and register all available strategies."""
        # Define the base package for strategies
        base_package = "deepterminal.strategies"
        
        # Get the base directory for strategies
        strategy_dir = os.path.dirname(__file__)
        
        # Recursively walk through all subdirectories
        for root, dirs, files in os.walk(strategy_dir):
            # Skip __pycache__ directories
            if "__pycache__" in root:
                continue
            
            # Process Python files
            for file in files:
                if file.endswith(".py") and file != "__init__.py" and file != "base.py" and file != "registry.py":
                    # Determine the module path
                    rel_path = os.path.relpath(os.path.join(root, file), os.path.dirname(strategy_dir))
                    module_path = os.path.splitext(rel_path)[0].replace(os.sep, ".")
                    
                    # Import the module
                    try:
                        module = importlib.import_module(f"{base_package}.{module_path}")
                        
                        # Find strategy classes in the module
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                issubclass(obj, StrategyBase) and 
                                obj != StrategyBase and
                                obj.__module__ == module.__name__):
                                # Register the strategy
                                self.register_strategy(obj)
                    except Exception as e:
                        self.logger.error(f"Error importing strategy module {module_path}: {e}")
    
    def create_strategy(
        self,
        name: str,
        instruments: List[Any],
        timeframe: str = "1h",
        parameters: Optional[Dict[str, Any]] = None,
        risk_per_trade: float = 0.01
    ) -> Optional[StrategyBase]:
        """
        Create a strategy instance.
        
        Args:
            name (str): The name of the strategy.
            instruments (List[Any]): List of instruments to trade.
            timeframe (str): Timeframe for analysis.
            parameters (Optional[Dict[str, Any]]): Strategy-specific parameters.
            risk_per_trade (float): Maximum risk per trade as a fraction of account.
            
        Returns:
            Optional[StrategyBase]: The strategy instance, or None if creation failed.
        """
        # Get the strategy class
        strategy_class = self.get_strategy_class(name)
        if not strategy_class:
            self.logger.error(f"Strategy '{name}' not found")
            return None
        
        # Create the strategy instance
        try:
            strategy = strategy_class(
                instruments=instruments,
                timeframe=timeframe,
                parameters=parameters,
                risk_per_trade=risk_per_trade
            )
            return strategy
        except Exception as e:
            self.logger.error(f"Error creating strategy '{name}': {e}")
            return None