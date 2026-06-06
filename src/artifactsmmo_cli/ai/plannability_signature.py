"""The state dimensions that unlock new plannability for the discretionary/skill
goals the doomed-memo governs. A skill/craft goal that is width-unfindable at a
given character + skill level stays unfindable until one of those levels changes;
inventory churns every gather and is deliberately excluded (the memo's K-cycle
re-probe covers material-driven changes). See
docs/superpowers/specs/2026-06-06-tiered-budget-gear-prioritization-design.md.
"""

from artifactsmmo_cli.ai.world_state import WorldState

Signature = tuple[int, tuple[tuple[str, int], ...]]


def plannability_signature(state: WorldState) -> Signature:
    """`(character level, sorted skill levels)` — the memo invalidation key."""
    return (state.level, tuple(sorted(state.skills.items())))
