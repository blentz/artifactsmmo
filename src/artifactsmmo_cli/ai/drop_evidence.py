"""Why an item's drop route is absent, decomposed along `_drop_sources`' own
conjuncts.

MOVED OUT OF `audit/drop_wall_census.py`, unchanged. It was written there
because the drop-wall census was its only reader; `decisions/root` is now a
second, and production importing from `audit/` inverts the layering — the
audit package is a READER of production, and every other census in this repo
imports downwards only. The census keeps its own imports pointed here, so the
matrix it renders is byte-identical.

ONE FILE, TWO NAMES, AND THAT IS THE REPO'S OWN SHAPE: a frozen dataclass plus
the single function that produces it, exactly as `ai/combat_deficit.py` pairs
`CombatDeficit`/`DeficitStep` with `combat_deficit`. Neither name is usable
without the other and neither is a behavioural class.
"""

from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class DropEvidence:
    """Why an item has no drop route, decomposed along the exact conjuncts
    `obtain_sources._drop_sources` gates on.

    Carried per cell so the matrix can show WHY a verdict landed without the
    reader re-deriving it, and so a wall arm that stops being reachable is
    visible as a column of zeros rather than as an absent row."""

    item: str
    droppers: tuple[str, ...]
    on_live_tiles: tuple[str, ...]
    closes: tuple[str, ...]
    """Live droppers whose margin `combat_deficit` closes with a gear chain."""
    chain: tuple[str, ...]
    """The chain for the first closing dropper — the acquisitions that would
    open this route. Empty when nothing closes."""


def drop_evidence(item: str, state: WorldState, game_data: GameData) -> DropEvidence:
    """The three conjuncts plus `combat_deficit`'s verdict, for one item.

    `combat_deficit` is asked at restorable hp for the same reason
    `unwinnable_drop_items` is: it answers "what gear closes this fight", which is
    not a question about the character's current hp."""
    rested = replace(state, hp=state.max_hp)
    droppers = tuple(monster for monster, _rate, _min_q, _max_q
                     in game_data.monsters_dropping(item))
    live = tuple(monster for monster in droppers
                 if game_data.all_monster_locations.get(monster))
    closes: list[str] = []
    chain: tuple[str, ...] = ()
    for monster in live:
        deficit = combat_deficit(rested, game_data, monster)
        if deficit is not None and deficit.closes:
            closes.append(monster)
            if not chain:
                chain = tuple(step.code for step in deficit.chain)
    return DropEvidence(item=item, droppers=droppers, on_live_tiles=live,
                        closes=tuple(closes), chain=chain)
