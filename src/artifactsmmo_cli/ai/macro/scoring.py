"""Canonicalize progression bands into goal/action chains and rank recurring
chains by macro value (recurrence x search-cost they incurred)."""

from collections import defaultdict
from dataclasses import dataclass

from artifactsmmo_cli.ai.macro.cost import parse_goal_type
from artifactsmmo_cli.ai.macro.segmentation import Band

_Chain = tuple[tuple[str, str], ...]


def canonical_chain(band: Band) -> _Chain:
    steps: list[tuple[str, str]] = []
    for r in band.rows:
        step = (parse_goal_type(r.selected_goal), r.action_class or "<none>")
        if not steps or steps[-1] != step:
            steps.append(step)
    return tuple(steps)


@dataclass(frozen=True)
class MacroCandidate:
    kind: str
    chain: _Chain
    occurrences: int
    distinct_characters: int
    total_nodes: int
    value: int
    example_keys: tuple[str, ...]


def score_candidates(bands: list[Band]) -> list[MacroCandidate]:
    groups: dict[tuple[str, _Chain], list[Band]] = defaultdict(list)
    for b in bands:
        groups[(b.kind, canonical_chain(b))].append(b)
    candidates: list[MacroCandidate] = []
    for (kind, chain), group in groups.items():
        total_nodes = sum((r.planner_nodes or 0) for b in group for r in b.rows)
        chars = {b.character for b in group}
        keys: list[str] = []
        for b in group:
            if b.key not in keys:
                keys.append(b.key)
        candidates.append(MacroCandidate(
            kind=kind, chain=chain, occurrences=len(group),
            distinct_characters=len(chars), total_nodes=total_nodes,
            value=len(group) * total_nodes, example_keys=tuple(keys[:3]),
        ))
    return sorted(candidates, key=lambda c: (c.value, c.occurrences), reverse=True)
