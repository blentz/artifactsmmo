"""Combat elements — re-exported from the schema-derived single source.

The canonical, API-derived `ELEMENTS` lives in `artifactsmmo_cli.ai.elements`
(a leaf module the base layers can import). This module re-exports it so the
existing `equipment.elements` consumers and the differential harness keep their
import path.
"""

from artifactsmmo_cli.ai.elements import ELEMENTS

__all__ = ["ELEMENTS"]
