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
- `SPAWN_KNOWN`: a tile of the monster, live or on any layer, in a region the
  walk reaches from here now (`monster_reached` over
  `region_edges.reachable_regions_now`, ruling T14a-E: the one reachability
  authority, the crossings the walk's bridge can apply). A monster behind a
  crossing the character cannot pay for is no route: the pricer chose `dryad`
  behind a 5000-gold fee for the L48 rune's gold, and the walk declined
  `region:overworld->restricted:...` every cycle. The catalogue's own
  fixed point (`monster_spawn_known`) is not asked as well: a gather's
  SPAWN_KNOWN asks the same reach alone (ruling R3-M1), and the fixed point
  starts from the overworld, so it would refuse a monster in a pocket the
  character already stands in (one entered through an edge the catalogue
  does not model, such as `achievement_unlocked`). An unmet gate names the
  doors past which the monster stands (`Gate.doors`, Task 14e): the walk
  opens it by obtaining a door's key or fee, the pricer charges that as the
  route's unlock, so a key door is a route through its key, not a wall.
- `WINNABLE`: asked at RESTORABLE hp (route existence is not an hp question;
  resting is an action the planner has), cold (no LearningStore: the record's
  refusals arrive as `WorldState.lost_fights`, which voids both solo arms), and only for
  a monster that spawns under either predicate or past a door: one that spawns nowhere has no
  FightAction to serve it, so its verdict could never be used. The bare stats,
  or failing them some runnable utility-potion loadout
  (`loadout_win.wins_with_a_loadout`, USER 2026-10-10: "judge drop fights with
  the chosen loadout"): live C3P0 beat vampire 77/117 with a water boost while
  the bare gate called it unwinnable. Or a party of the character and one or
  two of `state.party` against a boss (`party_win.wins_as_a_party`,
  docs/PLAN_group_fights.md increment 2). Both drop paths read this one gate;
  the committed fight's own loadout is stocked by the CRAFT_POTIONS guard.
- `XP_POSITIVE`: `xp_per_kill` at the character's level. It reads the ORIGINAL
  state: grey is about level, which a rested copy shares.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING, win_gold
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.loadout_win import wins_with_a_loadout
from artifactsmmo_cli.ai.obtain_model.gate import Door, Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.party_win import wins_as_a_party
from artifactsmmo_cli.ai.region_edges import content_reached, doors_to
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

Fighter = WorldState | Callable[[str], WorldState]
"""Who a drop fight is judged against: one character for every monster, or a
function of the monster's code."""


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


def drop_fight_winnable(rested: WorldState, game_data: GameData, monster: str) -> bool:
    """The WINNABLE gate's verdict for a character at full HP: the bare stats
    or a stockable potion loadout, unless the learned record refuses the solo
    fight (`WorldState.lost_fights`), or a party (`party_win`)."""
    return ((monster not in rested.lost_fights
             and (is_winnable(rested, game_data, monster)
                  or wins_with_a_loadout(rested, game_data, monster)))
            or wins_as_a_party(rested, game_data, monster))


def monster_reached(monster: str, game_data: GameData, reach: frozenset[str]) -> bool:
    """Some tile of `monster`, live or on any layer, lies in a region of
    `reach` (`region_edges.content_reached`)."""
    return content_reached(monster, game_data.all_monster_locations.get(monster, []),
                           game_data, reach)


def monster_doors(monster: str, state: WorldState, game_data: GameData) -> tuple[Door, ...]:
    """The doors past which some tile of `monster` lies (`region_edges.doors_to`)."""
    return doors_to(monster, game_data.all_monster_locations.get(monster, []), state, game_data)


def _fight_gates(monster: str, state: WorldState, game_data: GameData,
                 rested: _Rested, reach: frozenset[str]) -> tuple[Gate, ...]:
    live = bool(game_data.all_monster_locations.get(monster))
    known = monster_reached(monster, game_data, reach)
    doors = () if known else monster_doors(monster, state, game_data)
    winnable = (live or known or bool(doors)) and drop_fight_winnable(rested.get(), game_data, monster)
    return (
        Gate(GateKind.SPAWN_LIVE, monster, live),
        Gate(GateKind.SPAWN_KNOWN, monster, known, doors=doors),
        Gate(GateKind.WINNABLE, monster, winnable),
        Gate(GateKind.XP_POSITIVE, monster, game_data.xp_per_kill(monster, state.level) > 0),
    )


def drop_routes(item: str, state: WorldState, game_data: GameData, reach: frozenset[str],
                fighter: Fighter | None = None) -> list[Route]:
    """One DROP route per monster that drops `item`, in drop-table order.

    `fighter`, when given, is who WINNABLE asks (rested), in place of `state`:
    a projected loadout rather than the worn gear (the global gear objective's
    fixed point, spec 2026-10-18 §2.3). A callable is asked once per dropping
    monster for the fighter that monster is judged against (its own target
    loadout: "beatable by SOME achievable loadout"). XP_POSITIVE still reads
    `state`'s level."""
    shared = _Rested(state if fighter is None or callable(fighter) else fighter)

    def rested(monster: str) -> _Rested:
        return _Rested(fighter(monster)) if callable(fighter) else shared

    return [Route(item, SourceKind.DROP, monster, 1, UNBOUNDED_CAPACITY,
                  _fight_gates(monster, state, game_data, rested(monster), reach))
            for monster, _rate, _mn, _mx in game_data.monsters_dropping(item)]


def gold_drop_routes(state: WorldState, game_data: GameData,
                     reach: frozenset[str]) -> list[Route]:
    """One GOLD_DROP route per monster whose win pays gold, in catalogue order.

    Gold is minted by fighting: every win pays between the monster's
    `min_gold` and `max_gold` (API data). The route yields the expected
    amount, `(min + max) // 2`, at least 1 (D-R: expected yields); a monster
    whose `max_gold` is 0 pays nothing and has no route.

    Only a monster the executor would fight (plan B Task 15, ruling T15a):
    at most `FIGHT_LEVEL_GAP_CEILING` above the character, `FightAction`'s
    suicide guard, the same ceiling `gear_objective._candidates` puts on `m*`.
    The gold a piece is priced by is the gold the fight that serves it earns:
    in `l20_dual_utility` the level-28 imp paid gold cheapest, and the level-20
    character could never fight it."""
    rested = _Rested(state)
    ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    out: list[Route] = []
    for monster in game_data.monsters.levels:
        top = game_data.monster_max_gold(monster)
        if top <= 0 or game_data.monster_level(monster) > ceiling:
            continue
        paid = max(1, win_gold(monster, game_data))
        out.append(Route(GOLD_CODE, SourceKind.GOLD_DROP, monster, paid, UNBOUNDED_CAPACITY,
                         _fight_gates(monster, state, game_data, rested, reach)))
    return out
