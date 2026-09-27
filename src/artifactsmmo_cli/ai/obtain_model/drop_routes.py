"""The DROP routes to an item, with their gates: the one place drop gates are
evaluated.

Shared by `ObtainModel` (every route kind) and `drop_obtainability` (which asks
only about drops, and has no `SelectionContext`: no drop gate reads one).
Before this, the two evaluated liveness and grey on different predicates
(D-D in docs/PLAN_decision_architecture_redesign.md); now they evaluate the
same gates and differ only in which ones their `Policy` enforces.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import WorldState


def drop_routes(item: str, state: WorldState, game_data: GameData) -> list[Route]:
    """One route per monster that drops `item`, in drop-table order.

    - `SPAWN_LIVE`: a tile in `all_monster_locations`, which `factory.py` builds
      FightActions from (an event monster's tiles only while its event is live).
    - `SPAWN_KNOWN`: `monster_spawn_known`, which also admits layered tiles in a
      reachable region.
    - `WINNABLE`: asked at RESTORABLE hp (route existence is not an hp question;
      resting is an action the planner has), cold (no LearningStore), and only
      for a monster that spawns under either predicate: one that spawns nowhere
      has no FightAction to serve it, so its verdict could never be used.
    - `XP_POSITIVE`: `xp_per_kill` at the character's level. It reads the
      ORIGINAL state: grey is about level, which a rested copy shares."""
    rested: WorldState | None = None
    out: list[Route] = []
    for monster, _rate, _mn, _mx in game_data.monsters_dropping(item):
        live = bool(game_data.all_monster_locations.get(monster))
        known = game_data.monster_spawn_known(monster)
        winnable = False
        if live or known:
            if rested is None:
                rested = replace(state, hp=state.max_hp)
            winnable = is_winnable(rested, game_data, monster)
        gates = (
            Gate(GateKind.SPAWN_LIVE, monster, live),
            Gate(GateKind.SPAWN_KNOWN, monster, known),
            Gate(GateKind.WINNABLE, monster, winnable),
            Gate(GateKind.XP_POSITIVE, monster, game_data.xp_per_kill(monster, state.level) > 0),
        )
        out.append(Route(item, SourceKind.DROP, monster, 1, UNBOUNDED_CAPACITY, gates))
    return out
