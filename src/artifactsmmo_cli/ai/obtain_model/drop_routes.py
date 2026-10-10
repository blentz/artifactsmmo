"""The routes that come from winning a fight, with their gates: the one place
fight gates are evaluated.

Shared by `ObtainModel` (every route kind) and `drop_obtainability` (which asks
only about item drops, and has no `SelectionContext`: no fight gate reads one).
Before this, the two evaluated liveness and grey on different predicates
(D-D in docs/PLAN_decision_architecture_redesign.md); now they evaluate the
same gates and differ only in which ones their `Policy` enforces.

The gates on a fight, whatever it pays:

- `SPAWN_LIVE`: a tile in `all_monster_locations`, which `factory.py` builds
  FightActions from (an event monster's tiles only while its event is live).
- `SPAWN_KNOWN`: `monster_spawn_known`, which also admits layered tiles in a
  reachable region.
- `WINNABLE`: asked at RESTORABLE hp (route existence is not an hp question;
  resting is an action the planner has), cold (no LearningStore), and only for
  a monster that spawns under either predicate: one that spawns nowhere has no
  FightAction to serve it, so its verdict could never be used. The bare stats,
  or failing them some runnable utility-potion loadout
  (`loadout_win.wins_with_a_loadout`, USER 2026-10-10: "judge drop fights with
  the chosen loadout"): live C3P0 beat vampire 77/117 with a water boost while
  the bare gate called it unwinnable. Both drop paths read this one gate; the
  committed fight's own loadout is stocked by the CRAFT_POTIONS guard.
- `XP_POSITIVE`: `xp_per_kill` at the character's level. It reads the ORIGINAL
  state: grey is about level, which a rested copy shares.
"""

from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.loadout_win import wins_with_a_loadout
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState


@dataclass
class _Rested:
    """The character at full hp, built on the first winnability question and
    shared by every later one in the same call."""

    state: WorldState
    copy: WorldState | None = None

    def get(self) -> WorldState:
        if self.copy is None:
            self.copy = replace(self.state, hp=self.state.max_hp)
        return self.copy


def _fight_gates(monster: str, state: WorldState, game_data: GameData,
                 rested: _Rested) -> tuple[Gate, ...]:
    live = bool(game_data.all_monster_locations.get(monster))
    known = game_data.monster_spawn_known(monster)
    winnable = (live or known) and (
        is_winnable(rested.get(), game_data, monster)
        or wins_with_a_loadout(rested.get(), game_data, monster))
    return (
        Gate(GateKind.SPAWN_LIVE, monster, live),
        Gate(GateKind.SPAWN_KNOWN, monster, known),
        Gate(GateKind.WINNABLE, monster, winnable),
        Gate(GateKind.XP_POSITIVE, monster, game_data.xp_per_kill(monster, state.level) > 0),
    )


def drop_routes(item: str, state: WorldState, game_data: GameData) -> list[Route]:
    """One DROP route per monster that drops `item`, in drop-table order."""
    rested = _Rested(state)
    return [Route(item, SourceKind.DROP, monster, 1, UNBOUNDED_CAPACITY,
                  _fight_gates(monster, state, game_data, rested))
            for monster, _rate, _mn, _mx in game_data.monsters_dropping(item)]


def gold_drop_routes(state: WorldState, game_data: GameData) -> list[Route]:
    """One GOLD_DROP route per monster whose win pays gold, in catalogue order.

    Gold is minted by fighting: every win pays between the monster's
    `min_gold` and `max_gold` (API data). The route yields the expected
    amount, `(min + max) // 2`, at least 1 (D-R: expected yields); a monster
    whose `max_gold` is 0 pays nothing and has no route."""
    rested = _Rested(state)
    out: list[Route] = []
    for monster in game_data.monsters.levels:
        top = game_data.monster_max_gold(monster)
        if top <= 0:
            continue
        paid = max(1, (game_data.monster_min_gold(monster) + top) // 2)
        out.append(Route(GOLD_CODE, SourceKind.GOLD_DROP, monster, paid, UNBOUNDED_CAPACITY,
                         _fight_gates(monster, state, game_data, rested)))
    return out
