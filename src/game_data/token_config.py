"""
Token Configuration

This module provides token validation and loading functionality for ArtifactsMMO API
authentication. Handles token file reading with Pydantic validation.
"""

from pathlib import Path

from pydantic import BaseModel, Field


class TokenConfig(BaseModel):
    """Pydantic model for token validation"""
    token: str = Field(min_length=32, description="ArtifactsMMO API token")

    @classmethod
    def from_file(cls, token_file: str = "TOKEN") -> 'TokenConfig':
        """Load and validate token from file.
        
        Parameters:
            token_file: Path to file containing API token (default: "TOKEN")
            
        Return values:
            TokenConfig instance with validated token
            
        This method loads an API token from the specified file path and validates
        it using Pydantic constraints to ensure proper format before use
        in API authentication.
        """
        token_path = Path(token_file)
        if not token_path.exists():
            raise FileNotFoundError(f"Token file not found: {token_file}")

        token = token_path.read_text().strip()
        if not token:
            raise ValueError(f"Token file is empty: {token_file}")

        return cls(token=token)