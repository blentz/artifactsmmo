""" ActionBase module  """

from typing import Dict, Optional, Any
import logging

class ActionBase:
    """ Base class for all GOAP actions """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self):
        """Initialize base action"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute(self, client, **kwargs) -> Optional[Any]:
        """Execute the action - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement execute method")

    def validate_execution_context(self, client, **kwargs) -> bool:
        """Validate that the action can be executed with the given context"""
        return client is not None
    
    def validate_and_execute(self, client, **kwargs) -> Optional[Dict]:
        """
        Validate context and execute with standard error handling.
        This method provides a common pattern for action execution.
        
        Args:
            client: API client
            **kwargs: Additional context parameters
            
        Returns:
            Action result dictionary
        """
        # Validate client
        if not self.validate_execution_context(client, **kwargs):
            error_response = self.get_error_response("No API client provided")
            self.log_execution_result(error_response)
            return error_response
        
        try:
            # Execute the actual action logic
            return self.perform_action(client, **kwargs)
        except Exception as e:
            error_response = self.get_error_response(
                f"{self.__class__.__name__} failed: {str(e)}"
            )
            self.log_execution_result(error_response)
            return error_response
    
    def perform_action(self, client, **kwargs) -> Dict:
        """
        Perform the actual action logic.
        To be implemented by subclasses when using validate_and_execute pattern.
        
        Args:
            client: API client
            **kwargs: Additional context parameters
            
        Returns:
            Action result dictionary
        """
        raise NotImplementedError("Subclasses must implement perform_action method")

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
