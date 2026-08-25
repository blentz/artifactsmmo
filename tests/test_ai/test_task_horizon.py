"""The ONE-LEVEL PLANNING HORIZON — `ai/task_horizon.py`, all three verdicts.

USER (2026-08-25): *"cancel tasks that we can't meet through gear upgrade, or
(level-up by exactly 1 level and gear upgrade). anything beyond a 1-level horizon
is too far out to be a reasonable near-term planning target."*

Every case below is a REAL character from the scenario corpus against a REAL
monster from the committed catalogue bundle. Two of them retarget the held task
onto a different catalogue monster (`_with_task`) rather than editing the
scenario: the horizon is a property of the (character, monster) PAIR, and the
scenario set's own six held tasks happen to populate only two of the three
verdicts — a level-up witness has to be named explicitly or the middle clause has
no test at all.

MEASURED, and it is the reason the middle clause is nearly dead weight: over the
corpus' 32 `derive_combat_stats` characters against all 58 catalogue monsters
there are 1,493 losing pairs — 118 close on gear, 6 close at level+1, and 1,369
are out of reach. The clause fires for 0.44 % of the futile cases. It is not
vacuous (six pairs, and `test_the_level_up_arm_has_real_witnesses` pins them),
but nobody should expect it to carry the rule.
"""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.rung_state_core import HP_PER_LEVEL
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    HORIZON_LEVEL_UP,
    HORIZON_OUT_OF_REACH,
    next_level_state,
    resolve_task_horizon,
)
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

GEAR_CELL = "l32_held_task_closable"      # ogre: a chain closes it
OUT_OF_REACH_CELL = "l32_held_task_open"  # lich: nothing closes it
WORKABLE_CELL = "l32_held_task_workable"  # pig: already winnable

LEVEL_UP_CELL = "l13_drop_recipe_grind"
LEVEL_UP_MONSTER = "mushmush"
"""The level-up witness. At 13 no chain closes `mushmush`; at 14 `iron_dagger`
does — and the catalogue pool is IDENTICAL at both levels (102 items either
side), so the flip is the +5 Max HP and nothing else. See
`test_the_level_up_evaluation_moves_the_body_not_only_the_pool`."""


@pytest.fixture(scope="module")
def gd() -> GameData:
    return load_bundle_game_data(BUNDLE)


def _state(name: str, game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], game_data)


def _with_task(state: WorldState, monster: str) -> WorldState:
    """The same character holding a monsters task for `monster`, 0/10."""
    return dataclasses.replace(
        state, task_code=monster, task_type="monsters",
        task_progress=0, task_total=10,
        task_lifecycle_phase=derive_task_lifecycle_phase(monster, 0, 10))


# --- the three verdicts ----------------------------------------------------

def test_gear_that_closes_the_fight_reads_gear(gd: GameData) -> None:
    """Clause 1. Unchanged behaviour, pinned so the other two cannot swallow it."""
    horizon = resolve_task_horizon(_state(GEAR_CELL, gd), gd)
    assert horizon is not None
    assert horizon.monster == "ogre"
    assert horizon.verdict == HORIZON_GEAR
    assert horizon.gear_target == ("perfect_bow", "weapon_slot")


def test_one_level_plus_gear_closing_it_reads_level_up(gd: GameData) -> None:
    """Clause 2, and the whole reason the level+1 body has to be modelled."""
    state = _with_task(_state(LEVEL_UP_CELL, gd), LEVEL_UP_MONSTER)
    assert combat_deficit(dataclasses.replace(state, hp=state.max_hp),
                          gd, LEVEL_UP_MONSTER).closes is False
    horizon = resolve_task_horizon(state, gd)
    assert horizon is not None
    assert horizon.verdict == HORIZON_LEVEL_UP
    assert horizon.gear_target is None


def test_the_level_alone_arm_is_a_level_up_verdict_too() -> None:
    """`combat_deficit(next_level_state(...))` is None: the level WINS the fight
    with nothing acquired, so there is no chain to ask `closes` of.

    A TOTALITY requirement before it is a feature — `.closes` on a None would
    raise — but it is also the cheapest instance of the rule, and dropping it
    would have made a character one HP grant short of beating its own task
    monster read as OUT OF REACH.

    Hand-built rather than taken from the corpus, and the search that says so is
    in the record: across all 42 scenarios x 58 catalogue monsters there are FOUR
    pairs where the level alone flips `predict_win`, and in all four a gear chain
    ALREADY closes the fight at the current level (verdict GEAR, which is the
    right answer — gear is faster than a level). The arm is reachable only where
    no helpful gear exists at all, which is what the empty item catalogue below
    says. Recorded so a future reader does not mistake "no corpus witness" for
    "dead code"."""
    game_data = GameData()
    game_data._item_stats = {}
    game_data._crafting_recipes = {}
    game_data._monster_level = {"rat": 1}
    fill_monster_stat_defaults(game_data)
    game_data._monster_hp = {"rat": 60}
    game_data._monster_attack = {"rat": {"earth": 6}}
    game_data._monster_resistance = {"rat": {}}
    # 62 max HP loses; the published +5 grant wins. Found by search, not chosen.
    state = make_state(level=1, hp=62, max_hp=62, attack={"earth": 5},
                       task_code="rat", task_type="monsters",
                       task_total=10, task_progress=0)

    assert predict_win(state, game_data, "rat") is False
    assert predict_win(next_level_state(state), game_data, "rat") is True
    assert combat_deficit(state, game_data, "rat").closes is False
    assert combat_deficit(next_level_state(state), game_data, "rat") is None

    horizon = resolve_task_horizon(state, game_data)
    assert horizon is not None
    assert horizon.verdict == HORIZON_LEVEL_UP


def test_nothing_within_one_level_reads_out_of_reach(gd: GameData) -> None:
    """Clause 3, and THE case this module exists for.

    Before it, `l32_held_task_open` armed the gear latch on the bare "this fight
    is lost" fact and `map_guard` fell through to the monster-blind value scan —
    measured, to the SAME goal the already-winnable cell produced
    (`test_the_task_triple_moves_the_gear_review_target`). A guard reviewing gear
    for a fight no gear it can name will win."""
    horizon = resolve_task_horizon(_state(OUT_OF_REACH_CELL, gd), gd)
    assert horizon is not None
    assert horizon.monster == "lich"
    assert horizon.verdict == HORIZON_OUT_OF_REACH
    assert horizon.gear_target is None
    # ...and the lich is IN BAND (level 30 against a level-32 character), which is
    # exactly why `task_feasibility`'s level proxy called it feasible and
    # `task_decision` answered PURSUE. Out of reach is a fact about the FIGHT.
    assert gd.monster_level("lich") <= SCENARIOS[OUT_OF_REACH_CELL].level


def test_a_winnable_task_has_no_verdict_to_take(gd: GameData) -> None:
    """None is not a fourth verdict — it means there is no reading to take."""
    assert resolve_task_horizon(_state(WORKABLE_CELL, gd), gd) is None


def test_no_held_task_has_no_verdict_to_take(gd: GameData) -> None:
    """Every caller distinguishes "no task" from "out of reach" through this."""
    state = _state(GEAR_CELL, gd)
    assert resolve_task_horizon(
        dataclasses.replace(state, task_code=None, task_type=None,
                            task_progress=0, task_total=0), gd) is None


# --- the level+1 body ------------------------------------------------------

def test_next_level_state_grows_the_body_by_the_published_grant(gd: GameData) -> None:
    """+5 Max HP per level, asked of `rung_state_core` rather than restated.

    A second copy of a game-rule constant is how the two halves of a rule drift
    apart, and this project has paid for that four times."""
    state = _state(GEAR_CELL, gd)
    nxt = next_level_state(state)
    assert nxt.level == state.level + 1
    assert nxt.max_hp == state.max_hp + HP_PER_LEVEL
    assert nxt.hp == nxt.max_hp, "the question is 'can I win', and rest is an action"


def test_the_level_up_evaluation_moves_the_body_not_only_the_pool(gd: GameData) -> None:
    """CONSTRAINT: a +1 evaluation that only widened the candidate pool would be
    the half-modelled shortcut, and here it is measured to find NOTHING.

    `combat_deficit._pool` filters `stats.level <= state.level`, so bumping the
    level admits more gear. That is the obvious effect and it is not the one that
    matters: over all ten LEVEL_UP pairs in the corpus, the HP growth alone flips
    10 of 10 and the pool widening alone flips 0 of 10. This case is the cleanest
    of them — the pool is byte-identical at both levels, so the pool arm cannot
    even be argued for."""
    state = _with_task(_state(LEVEL_UP_CELL, gd), LEVEL_UP_MONSTER)
    rested = dataclasses.replace(state, hp=state.max_hp)
    nxt = next_level_state(state)

    def pool_at(level: int) -> list[str]:
        return sorted(code for code, stats in gd.items.stats.items()
                      if stats.level <= level)

    assert pool_at(state.level) == pool_at(nxt.level), "pool must be the control here"

    hp_only = dataclasses.replace(rested, max_hp=nxt.max_hp, hp=nxt.max_hp)
    pool_only = dataclasses.replace(rested, level=nxt.level)

    assert combat_deficit(nxt, gd, LEVEL_UP_MONSTER).closes is True
    assert combat_deficit(hp_only, gd, LEVEL_UP_MONSTER).closes is True
    assert combat_deficit(pool_only, gd, LEVEL_UP_MONSTER).closes is False


def test_the_level_up_arm_has_real_witnesses(gd: GameData) -> None:
    """Six of 1,375 futile pairs, and the clause is worth exactly that much.

    Recorded as a test rather than a comment because "nearly dead weight" and
    "dead weight" are different findings, and only a measurement tells them
    apart. If a catalogue change ever takes this to zero the middle clause has
    become unreachable and should be deleted, not left as decoration."""
    def closes_only_at_next_level(state: WorldState, monster: str) -> bool:
        if predict_win(state, gd, monster):
            return False
        if combat_deficit(state, gd, monster).closes:
            return False
        at_next = combat_deficit(next_level_state(state), gd, monster)
        return at_next is None or at_next.closes

    witnesses = []
    for name, sc in SCENARIOS.items():
        if not sc.derive_combat_stats:
            continue
        state = scenario_state(sc, gd)
        state = dataclasses.replace(state, hp=state.max_hp)
        witnesses += [(name, monster) for monster in sorted(gd.monster_levels)
                      if closes_only_at_next_level(state, monster)]
    assert len(witnesses) == 6, witnesses
    assert (LEVEL_UP_CELL, LEVEL_UP_MONSTER) in witnesses


# --- one reading per cycle --------------------------------------------------

def test_the_verdict_is_resolved_once_per_state(gd: GameData) -> None:
    """The gear latch, the GEAR_REVIEW mapper and the TASK_CANCEL rung all ask
    within one cycle. They must not be able to disagree, and the walk costs a
    catalogue sweep per chain step — `combat_deficit`'s own docstring says a
    per-cycle caller must memoise."""
    state = _state(GEAR_CELL, gd)
    first = resolve_task_horizon(state, gd)
    assert resolve_task_horizon(state, gd) is first
    # A DIFFERENT state object recomputes — identity, never equality, so a stale
    # answer can never be served for a state that has moved on.
    assert resolve_task_horizon(dataclasses.replace(state), gd) is not first
