"""What the root walk actually chose, by branch, per character.

The question T1 cannot answer without this: under the character leaderboard's
`total_xp` ruler, skill XP and character XP weigh the same, yet skills sit
BEHIND the trunk in `resolve_root`'s fixed concatenation of alternatives.
Whether that ordering costs anything is a measurement, and this is it.

A NULL `root_group` is a row written before the column existed (2026-09-21). It
is reported as `unattributed` and counted in no group: treating it as a choice
would let pre-migration history decide a post-migration verdict.

The string label `"none"` is a MIXED bucket: `root_group_of` returns it when
`chosen_root is None`, which happens both when the walk found no root AND when
a session resumed from a plan cache where `_last_decision` was None but a root
was already executing (see `player.py:670-673`). So `counts["none"]` conflates
two cases and cannot distinguish them. Callers must not read it as a clean
"walk resolved no root" count.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS


@dataclass(frozen=True)
class GroupCounts:
    """One character's root choices over the window."""

    character: str
    counts: dict[str, int]
    attributed: int
    unattributed: int

    def share(self, group: str) -> float | None:
        """Fraction of ATTRIBUTED cycles that chose `group`. Denominated on
        attributed rows only, so a store that is mostly pre-migration reports a
        share of what it saw rather than one diluted by silence.

        Returns None when `attributed == 0`, meaning nothing was attributed and
        no share is defined. This is not 0.0 — the distinction between "measured
        as nothing" and "could not tell" is kept (same rule as `Cycle.delta_xp`)."""
        if self.attributed == 0:
            return None
        return self.counts.get(group, 0) / self.attributed


def root_group_counts(cycles: list[Cycle]) -> list[GroupCounts]:
    """Per-character group counts, ordered by character name.

    Raises `ValueError` on a group label outside `ROOT_GROUPS`: that means the
    classifier and this census have drifted, and a census that silently dropped
    the label would report a smaller world than the one that was recorded.
    """
    per_char: dict[str, dict[str, int]] = {}
    unattributed: dict[str, int] = {}
    for cycle in cycles:
        counts = per_char.setdefault(cycle.character, {})
        unattributed.setdefault(cycle.character, 0)
        if cycle.root_group is None:
            unattributed[cycle.character] += 1
            continue
        if cycle.root_group not in ROOT_GROUPS:
            raise ValueError(f"unknown root group: {cycle.root_group!r}")
        counts[cycle.root_group] = counts.get(cycle.root_group, 0) + 1
    return [
        GroupCounts(
            character=character,
            counts=counts,
            attributed=sum(counts.values()),
            unattributed=unattributed[character],
        )
        for character, counts in sorted(per_char.items())
    ]
