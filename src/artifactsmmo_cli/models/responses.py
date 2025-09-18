"""Response wrapper models for CLI operations."""

from pydantic import BaseModel, Field


class CLIResponse[T](BaseModel):
    """Wrapper for API responses with CLI formatting."""

    success: bool = Field(..., description="Whether the operation was successful")
    data: T | None = Field(None, description="Response data if successful")
    error: str | None = Field(None, description="Error message if failed")
    message: str | None = Field(None, description="Additional message")
    cooldown_remaining: float | None = Field(None, description="Cooldown remaining in seconds")

    @classmethod
    def success_response(cls, data: T, message: str | None = None) -> "CLIResponse[T]":
        """Create a successful response."""
        return cls(success=True, data=data, message=message, error=None, cooldown_remaining=None)

    @classmethod
    def error_response(cls, error: str, cooldown_remaining: float | None = None) -> "CLIResponse[T]":
        """Create an error response."""
        return cls(success=False, error=error, cooldown_remaining=cooldown_remaining, data=None, message=None)

    @classmethod
    def cooldown_response(cls, cooldown_remaining: float) -> "CLIResponse[T]":
        """Create a cooldown response."""
        return cls(
            success=False,
            error=f"Action on cooldown for {cooldown_remaining} seconds",
            cooldown_remaining=cooldown_remaining,
            data=None,
            message=None,
        )
