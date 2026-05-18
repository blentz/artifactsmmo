"""Generic blocker (gated-dependency) registry.

Replaces the bank-specific `_bank_accessible / _bank_blocked_since / ...`
fields on `GamePlayer` with a uniform `dict[blocker_code, BlockerState]`.
New blockers (workshop gates, taskmaster level gates, map transitions)
register without code changes to player.
"""

from artifactsmmo_cli.ai.blockers.registry import BlockerRegistry, BlockerState

__all__ = ["BlockerRegistry", "BlockerState"]
