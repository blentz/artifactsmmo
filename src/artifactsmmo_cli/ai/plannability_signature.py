"""The state dimensions `DoomedMemo` keys its window on: character level and skill
levels. The memo now serves only the player's rejected-action TTL (the arbiter's
goal memo was retired by Phase 3-1). Inventory churns every gather and is
deliberately excluded (the memo's K-cycle re-probe covers material-driven
changes). See
docs/superpowers/specs/2026-06-06-tiered-budget-gear-prioritization-design.md.
"""

from artifactsmmo_cli.ai.world_state import WorldState

Signature = tuple[int, tuple[tuple[str, int], ...]]


def plannability_signature(state: WorldState) -> Signature:
    """`(character level, sorted skill levels)` — the memo invalidation key."""
    return (state.level, tuple(sorted(state.skills.items())))
