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

MEASURED since plan C Task 2 (ruling C2-one-model: both gear arms read `L*`,
the ACHIEVABLE loadout of the task monster): over the corpus' 44
`derive_combat_stats` characters against all 58 catalogue monsters (2,552 pairs),
560 have no reading, 160 read GEAR, 10 LEVEL_UP and 1,822 OUT_OF_REACH. Reading
`L*` instead of the catalogue deficit walk moved 117 pairs: 116 LEVEL_UP to
OUT_OF_REACH (the walk's level+1 chain was catalogue gear the character cannot
obtain) and one OUT_OF_REACH to LEVEL_UP (`l13_drop_recipe_grind` v mushmush).
Reading a task monster's `R` in task progress a second (ruling C2-grey: a grey
monster pays no XP, so in XP every gain was 0) moved 26 more to GEAR: 23 from
LEVEL_UP and 3 from no reading (fights the gate takes below SECURE_WIN). The
level-up arm reading `L*`'s own potion-aware gate (ruling C2-R m3) moved 113
OUT_OF_REACH to LEVEL_UP, 55 of them pairs the first move had taken from it.
Now 560 no reading, 160 GEAR, 123 LEVEL_UP, 1,709 OUT_OF_REACH.
"""

import dataclasses
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.gear_objective as go_mod
from artifactsmmo_cli.ai.combat import predict_win, secure_win
from artifactsmmo_cli.ai.decisions.root import _task_root
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective import (
    gear_closes_for,
    gear_fighter_for,
    gear_objective_for,
    task_rate,
    xp_rate,
)
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.learning.rung_state_core import HP_PER_LEVEL
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.progression.meta_goal import ObtainItem
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    HORIZON_LEVEL_UP,
    HORIZON_OUT_OF_REACH,
    TaskHorizon,
    next_level_state,
    resolve_task_horizon,
)
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

GEAR_CELL = "l13_drop_recipe_grind"       # cow: its `L*` closes it
GREY_CELL = "l32_held_task_closable"     # ogre: grey (0 XP), its `L*` closes it
OUT_OF_REACH_CELL = "l32_held_task_open"  # lich: nothing closes it
WORKABLE_CELL = "l32_held_task_workable"  # wolf: already winnable

BODY_CELL, BODY_MONSTER = "l15_midband", "pig"
"""One level wins `pig` here through the body alone: the gear pool is identical
at both levels, and the +5 HP flips the fight."""
POOL_CELL, POOL_MONSTER = "l19_band_edge", "skeleton"
"""One level wins `skeleton` here through the pool alone: the +5 HP does not,
the gear the next level admits does."""


@pytest.fixture(scope="module")
def gd() -> GameData:
    return load_bundle_game_data(BUNDLE)


def _state(name: str, game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], game_data)


def _horizon(state: WorldState, game_data: GameData) -> TaskHorizon | None:
    """The horizon on the offline context, store-less."""
    return resolve_task_horizon(state, game_data, TIMED_NO_PROFILE_CONTEXT, None)


def _with_task(state: WorldState, monster: str) -> WorldState:
    """The same character holding a monsters task for `monster`, 0/10."""
    return dataclasses.replace(
        state, task_code=monster, task_type="monsters",
        task_progress=0, task_total=10,
        task_lifecycle_phase=derive_task_lifecycle_phase(monster, 0, 10))


# --- the three verdicts ----------------------------------------------------

def test_gear_that_closes_the_fight_reads_gear(gd: GameData) -> None:
    """Clause 1: `L*` of the task monster secures the fight and a piece of it
    is unheld (plan C Task 2). The gear to build is `L*(cow)`'s first missing
    piece, which the task root asks (`test_held_task`)."""
    state = _state(GEAR_CELL, gd)
    horizon = _horizon(state, gd)
    assert horizon == TaskHorizon(monster="cow", verdict=HORIZON_GEAR)
    objective = gear_objective_for("cow", state, gd, TIMED_NO_PROFILE_CONTEXT, None, task_rate)
    assert len(objective.missing) > 1


@pytest.mark.parametrize(("cell", "monster"), [
    (GEAR_CELL, "cow"), (GREY_CELL, "ogre"), ("l10_copper_adequate", "pig"),
    (GEAR_CELL, "flying_snake")])
def test_the_verdict_reads_the_objectives_own_fighter_and_missing_pieces(
        gd: GameData, cell: str, monster: str) -> None:
    """Ruling C2-perf: the horizon prices no piece, but what it reads is
    `gear_objective_for`'s: the same fighter wearing `L*`, and a missing piece
    exactly when the objective has one (the cow's, the grey ogre's, the pig's
    nine; the flying snake's none: `L*` secures it, but every unheld piece
    gains exactly 0, so it is held-equivalent). Gear closes the fight exactly
    when that fighter secures it and a piece is missing."""
    state = _with_task(_state(cell, gd), monster)
    objective = gear_objective_for(monster, state, gd, TIMED_NO_PROFILE_CONTEXT, None, task_rate)
    fighter = gear_fighter_for(monster, state, gd, TIMED_NO_PROFILE_CONTEXT, None)
    assert objective.fighter is not None
    assert fighter.equipment == objective.fighter.equipment
    assert gear_closes_for(monster, state, gd, TIMED_NO_PROFILE_CONTEXT, None) is (
        secure_win(fighter, gd, monster) and bool(objective.missing))


def test_a_missing_l_star_that_still_loses_is_no_gear_verdict(gd: GameData) -> None:
    """`L*(pig)` has nine missing pieces at `l10_copper_adequate`, and the
    fighter wearing all of them is still below the secure bar: gear the
    character can build does not close the fight, so the horizon names none
    and reads one level up instead."""
    state = _with_task(_state("l10_copper_adequate", gd), "pig")
    objective = gear_objective_for("pig", state, gd, TIMED_NO_PROFILE_CONTEXT, None, task_rate)
    assert len(objective.missing) == 9
    horizon = _horizon(state, gd)
    assert horizon is not None
    assert horizon.verdict != HORIZON_GEAR


def test_a_grey_task_monster_roots_its_first_missing_piece(gd: GameData) -> None:
    """Ruling C2-grey. The ogre pays this level-32 character 0 XP, so `L*(ogre)`
    read in XP a second has `R = 0` and every piece gains 0: nothing missing,
    and the task asked for no gear. Read in the task's own unit, kills a second
    (`task_rate`: a monsters task pays per kill), the pieces gain, `L*`
    secures the fight, the verdict is GEAR and the task root is the first
    missing piece."""
    state = _state(GREY_CELL, gd)
    assert state.task_code == "ogre" and gd.xp_per_kill("ogre", state.level) == 0
    assert not gear_objective_for("ogre", state, gd, TIMED_NO_PROFILE_CONTEXT, None,
                                  xp_rate).missing
    missing = gear_objective_for("ogre", state, gd, TIMED_NO_PROFILE_CONTEXT, None,
                                 task_rate).missing
    assert (missing[0].code, missing[0].slot) == ("lifesteal_rune", "rune_slot")
    assert _horizon(state, gd) == TaskHorizon(monster="ogre", verdict=HORIZON_GEAR)
    ctx = attach_gear_objective(state, gd, TIMED_NO_PROFILE_CONTEXT, None)
    assert _task_root(state, gd, ctx, None) == ObtainItem("lifesteal_rune", 1, slot="rune_slot")


def test_one_level_plus_gear_closing_it_reads_level_up(gd: GameData) -> None:
    """Clause 2, and the whole reason the level+1 body has to be modelled, on a
    monster that pays XP (pig, 45 XP a kill at level 15). The gear the
    character can build does not secure it; `L*` one level up wins it (ruling
    C2-one-model: the level-up arm reads `L*`, not the catalogue deficit
    walk)."""
    state = _with_task(_state(BODY_CELL, gd), BODY_MONSTER)
    assert gd.xp_per_kill(BODY_MONSTER, state.level) > 0
    assert not gear_closes_for(BODY_MONSTER, state, gd, TIMED_NO_PROFILE_CONTEXT, None)
    assert not predict_win(dataclasses.replace(state, hp=state.max_hp), gd, BODY_MONSTER)
    assert predict_win(gear_fighter_for(BODY_MONSTER, next_level_state(state), gd,
                                        TIMED_NO_PROFILE_CONTEXT, None), gd, BODY_MONSTER)
    horizon = _horizon(state, gd)
    assert horizon is not None
    assert horizon.verdict == HORIZON_LEVEL_UP


def test_the_level_up_arm_reads_the_gate_l_star_s_candidates_pass(gd: GameData) -> None:
    """Ruling C2-R m3: the level-up arm asks `drop_fight_winnable`, the gate
    `L*`'s own candidates pass (`_rated`): the bare odds OR a stockable potion
    loadout. At `l10_copper_adequate` the pig is lost bare even in `L*` one
    level up, and won with the potions the character can stock, so the task is
    a level away, not out of reach."""
    state = _with_task(_state("l10_copper_adequate", gd), "pig")
    fighter = gear_fighter_for("pig", next_level_state(state), gd, TIMED_NO_PROFILE_CONTEXT, None)
    assert not predict_win(fighter, gd, "pig")
    assert drop_fight_winnable(fighter, gd, "pig")
    horizon = _horizon(state, gd)
    assert horizon is not None
    assert horizon.verdict == HORIZON_LEVEL_UP


def test_the_level_alone_arm_is_a_level_up_verdict_too() -> None:
    """The level WINS the fight with nothing to build: with no gear in the
    catalogue `L*` is the empty loadout, and the grown body alone wins. The
    cheapest instance of the rule; dropping it would have made a character one
    HP grant short of beating its own task monster read as OUT OF REACH.
    Hand-built: it isolates the arm from the catalogue."""
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
    fighter = gear_fighter_for("rat", next_level_state(state), game_data,
                               TIMED_NO_PROFILE_CONTEXT, None)
    assert set(fighter.equipment.values()) == {None}

    horizon = _horizon(state, game_data)
    assert horizon is not None
    assert horizon.verdict == HORIZON_LEVEL_UP


def test_nothing_within_one_level_reads_out_of_reach(gd: GameData) -> None:
    """Clause 3, and THE case this module exists for.

    Before it, `l32_held_task_open` armed the gear latch on the bare "this fight
    is lost" fact and `map_guard` fell through to the monster-blind value scan —
    measured, to the SAME goal the already-winnable cell produced
    (`test_the_task_triple_moves_the_gear_review_target`). A guard reviewing gear
    for a fight no gear it can name will win."""
    horizon = _horizon(_state(OUT_OF_REACH_CELL, gd), gd)
    assert horizon is not None
    assert horizon.monster == "lich"
    assert horizon.verdict == HORIZON_OUT_OF_REACH
    # ...and the lich is IN BAND (level 30 against a level-32 character), which is
    # exactly why `task_feasibility`'s level proxy called it feasible and
    # `task_decision` answered PURSUE. Out of reach is a fact about the FIGHT.
    assert gd.monster_level("lich") <= SCENARIOS[OUT_OF_REACH_CELL].level


def test_a_winnable_task_has_no_verdict_to_take(gd: GameData) -> None:
    """None is not a fourth verdict — it means there is no reading to take."""
    assert _horizon(_state(WORKABLE_CELL, gd), gd) is None


def test_no_held_task_has_no_verdict_to_take(gd: GameData) -> None:
    """Every caller distinguishes "no task" from "out of reach" through this."""
    state = _state(GEAR_CELL, gd)
    assert _horizon(
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


@pytest.mark.parametrize(("cell", "monster", "body", "pool"), [
    (BODY_CELL, BODY_MONSTER, True, False), (POOL_CELL, POOL_MONSTER, False, True)])
def test_the_level_up_evaluation_moves_the_body_and_the_pool(
        gd: GameData, cell: str, monster: str, body: bool, pool: bool) -> None:
    """CONSTRAINT: the level+1 reading must move all of what a level buys.
    `L*` one level up is picked from the gear the next level admits
    (`stats.level <= state.level`) and worn by the grown body (+5 Max HP).
    Either half alone is a shortcut, and each has a witness that only it
    flips: the pig falls to the body alone over an identical pool, the
    skeleton to the pool alone."""
    state = _with_task(_state(cell, gd), monster)
    rested = dataclasses.replace(state, hp=state.max_hp)
    nxt = next_level_state(state)

    def wins(probe: WorldState) -> bool:
        return predict_win(gear_fighter_for(monster, probe, gd, TIMED_NO_PROFILE_CONTEXT, None),
                           gd, monster)

    def pool_at(level: int) -> list[str]:
        return sorted(code for code, stats in gd.items.stats.items() if stats.level <= level)

    assert (pool_at(state.level) == pool_at(nxt.level)) is body
    assert not wins(rested)
    assert wins(nxt)
    assert wins(dataclasses.replace(rested, max_hp=nxt.max_hp, hp=nxt.max_hp)) is body
    assert wins(dataclasses.replace(rested, level=nxt.level)) is pool
    horizon = _horizon(state, gd)
    assert horizon is not None and horizon.verdict == HORIZON_LEVEL_UP


def test_a_task_the_gate_fights_with_no_gear_to_secure_it_has_no_verdict() -> None:
    """P 0.6308 clears a measured θ of 1/2, so the gate fights the task; it is
    below SECURE_WIN (a gear deficit), but the only item is a helmet with no
    combat stats, so no gear is named. The task is workable NOW: no horizon,
    rather than a level-up verdict for a fight the gate already takes
    (post-merge review 2026-10-16)."""
    gd = GameData()
    gd._item_stats = {"cloth_cap": ItemStats(code="cloth_cap", level=1, type_="helmet")}
    gd._monster_level = {"owlbear": 1}
    gd._monster_hp = {"owlbear": 1450}
    gd._monster_attack = {"owlbear": {"fire": 83}}
    gd._monster_resistance = {"owlbear": {}}
    fill_monster_stat_defaults(gd)
    gd._monster_critical_strike = {"owlbear": 5}
    gd._monster_initiative = {"owlbear": 10}
    state = make_state(level=1, hp=785, max_hp=785, attack={"fire": 141},
                       critical_strike=45, initiative=0, equipment={}, inventory={},
                       task_code="owlbear", task_type="monsters", task_total=10,
                       task_progress=0, win_thresholds={"owlbear": Fraction(1, 2)})
    assert predict_win(state, gd, "owlbear")
    assert _horizon(state, gd) is None


def test_a_cycle_reads_the_achievable_set_once(gd: GameData, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling C2-perf: inside one `search_cache` episode the task root's read
    and a task-worth probe of the same character (task progress reset, as
    `task_worth_for` builds it) share one achievable set; an episode-less store,
    a different context or a different holding computes afresh."""
    asked: list[int] = []
    real = go_mod.achievable

    def counted(state, game_data, ctx):  # type: ignore[no-untyped-def]
        asked.append(state.level)
        return real(state, game_data, ctx)

    monkeypatch.setattr(go_mod, "achievable", counted)
    store = LearningStore(str(tmp_path / "learning.db"), character="cow_farmer")
    state = _state(GEAR_CELL, gd)
    probe = dataclasses.replace(state, task_progress=0, task_total=state.task_total - state.task_progress)
    ctx = TIMED_NO_PROFILE_CONTEXT
    with store.search_cache():
        first = resolve_task_horizon(state, gd, ctx, store)
        assert resolve_task_horizon(probe, gd, ctx, store) == first
        assert len(asked) == 1
        resolve_task_horizon(state, gd, dataclasses.replace(ctx), store)
        assert len(asked) == 2
        richer = dataclasses.replace(state, gold=state.gold + 1)
        resolve_task_horizon(richer, gd, ctx, store)
        assert len(asked) == 3
    resolve_task_horizon(state, gd, ctx, store)
    resolve_task_horizon(state, gd, ctx, store)
    assert len(asked) == 5


def test_each_purpose_is_its_own_key(gd: GameData, tmp_path: Path) -> None:
    """Ruling C2-R2: the memo keys `L*(m)` on its purpose. Inside one
    `search_cache` episode the grey ogre read in XP a second misses nothing and
    read in kills a second misses its rune: the second read is never served
    the first's answer."""
    store = LearningStore(str(tmp_path / "learning.db"), character="grey")
    state = _state(GREY_CELL, gd)
    with store.search_cache():
        by_xp = gear_objective_for("ogre", state, gd, TIMED_NO_PROFILE_CONTEXT, store, xp_rate)
        by_kills = gear_objective_for("ogre", state, gd, TIMED_NO_PROFILE_CONTEXT, store,
                                      task_rate)
    assert not by_xp.missing
    assert by_kills.missing[0].code == "lifesteal_rune"


@pytest.mark.parametrize("task_type", ["items", "monsters"])
def test_a_task_the_keep_can_see_is_its_own_key(gd: GameData, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch,
                                                task_type: str) -> None:
    """Ruling C2-R m4: the memo clears only a task `L*` cannot see. A task
    whose code names an item (an items task, or any task on an item code) is
    kept by the keep (`inventory_keep._active_task`), so a probe holding it is
    computed afresh, never served the task-free character's answer."""
    asked: list[str | None] = []
    real = go_mod.achievable

    def counted(state, game_data, ctx):  # type: ignore[no-untyped-def]
        asked.append(state.task_code)
        return real(state, game_data, ctx)

    monkeypatch.setattr(go_mod, "achievable", counted)
    store = LearningStore(str(tmp_path / "learning.db"), character="keeper")
    free = dataclasses.replace(_state(GEAR_CELL, gd), task_code=None, task_type=None,
                               task_progress=0, task_total=0)
    held = dataclasses.replace(free, task_code="apprentice_gloves", task_type=task_type,
                               task_progress=0, task_total=5)
    assert gd.item_stats("apprentice_gloves") is not None
    with store.search_cache():
        gear_fighter_for("cow", free, gd, TIMED_NO_PROFILE_CONTEXT, store)
        gear_fighter_for("cow", held, gd, TIMED_NO_PROFILE_CONTEXT, store)
        gear_fighter_for("cow", held, gd, TIMED_NO_PROFILE_CONTEXT, store)
    assert asked == [None, "apprentice_gloves"]
