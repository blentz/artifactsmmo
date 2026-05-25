"""Raised when a required field is absent from an API response."""


class MissingApiData(RuntimeError):
    """A required field was missing (absent or UNSET) from an API response.

    The AI player plans on real game data only; silently substituting a
    default would let API contract drift corrupt planning unnoticed. Raising
    surfaces the drift at the point of consumption instead.
    """
