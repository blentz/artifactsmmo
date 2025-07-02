""" ActionBase module  """

import logging
from typing import Any, Dict, Optional

from src.lib.action_context import ActionContext


class ActionBase:
    """ Base class for all GOAP actions """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self):
        """Initialize base action"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._context = None  # Will be set during execute

    def execute(self, client, context: 'ActionContext') -> Optional[Any]:
        """
        Execute the action using unified ActionContext.
        Subclasses MUST call super().execute(client, context) at the beginning of their execute method.
        
        Args:
            client: API client
            context: ActionContext containing all execution parameters
            
        Returns:
            Action result
        """
        # Store context for use in helper methods
        self._context = context
        # Subclasses will implement their own execute logic after calling super()


    def get_error_response(self, error_message: str, **additional_data) -> Dict:
        """Generate a standard error response"""
        result = {
            'success': False,
            'error': error_message,
            'action': self.__class__.__name__
        }
        result.update(additional_data)
        return result

    def get_success_response(self, **data) -> Dict:
        """Generate a standard success response"""
        result = {
            'success': True,
            'action': self.__class__.__name__
        }
        result.update(data)
        return result

    def log_execution_start(self, **context):
        """Log the start of action execution"""
        self.logger.info(f"Executing {self.__class__.__name__} with context: {context}")

    def log_execution_result(self, result):
        """Log the result of action execution"""
        if isinstance(result, dict) and 'success' in result:
            if result['success']:
                self.logger.info(f"{self.__class__.__name__} completed successfully")
            else:
                self.logger.warning(f"{self.__class__.__name__} failed: {result.get('error', 'Unknown error')}")
        else:
            self.logger.info(f"{self.__class__.__name__} completed with result: {type(result).__name__}")

    def __repr__(self):
        """Default string representation - can be overridden by subclasses"""
        return f"{self.__class__.__name__}()"
