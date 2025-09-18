"""Configuration management for ArtifactsMMO CLI."""

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    """CLI configuration."""

    token: str = Field(..., description="API authentication token")
    api_base_url: str = Field(default="https://api.artifactsmmo.com", description="API base URL")
    timeout: int = Field(default=30, description="API timeout in seconds")
    debug: bool = Field(default=False, description="Enable debug output")

    @classmethod
    def from_token_file(cls, token_path: Path | None = None) -> "Config":
        """Load config with token from file or environment variable."""
        if token_path is None:
            token_path = Path("TOKEN")

        # Try to load token from file first
        token = None
        if token_path.exists():
            token = token_path.read_text().strip()

        # Fall back to environment variable
        if not token:
            token = os.getenv("ARTIFACTSMMO_TOKEN")

        if not token:
            raise ValueError(
                f"No authentication token found. "
                f"Create a {token_path} file or set ARTIFACTSMMO_TOKEN environment variable."
            )

        return cls(token=token)

    def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        return {"Authorization": f"Bearer {self.token}"}
