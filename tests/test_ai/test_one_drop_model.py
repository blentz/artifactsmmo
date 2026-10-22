"""One drop model feeds every consumer (plan B Task 16, ruling T16a).

Spec 2026-10-18 §2.8: the learned drop chance "feeds every consumer". The
acquisition walk priced a rare drop at the learned chance (Task 12a) while the
planner's gather and every source picker read the static API rate, so for
`small_pearls` off `trout_spot` the walk said 683/3 gathers a pearl and A* said
300. These tests put both plan producers (the `craft_plan_gen` fast path and
A*) and the walk on the SAME `LearnedDrops` value and check they agree, on the
price and on the source.
"""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import acquisition_options
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.drop_observations import learned_drops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, LEGACY
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures"
           / "gamedata_bundle.json")

_PEARLS_383_FOR_2 = [
    ("Gather(trout_spot)", "GatherAction", '{"trout": 1}', 381),
    ("Gather(trout_spot->small_pearls)", "GatherAction",
     '{"trout": 1, "small_pearls": 1}', 2),
]
"""The live 2026-10-19 trigger: 383 gathers at `trout_spot` for 2 pearls."""

_SALMON_1000_DRY = [("Gather(salmon_spot)", "GatherAction", '{"salmon": 1}', 1000)]
"""1,000 gathers at `salmon_spot` (pearls at 1 in 100 by the API) without one."""


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


@pytest.fixture(scope="module")
def state(game_data):  # type: ignore[no-untyped-def]
    """An L12 character who may fish every pearl spot (salmon_spot is fishing 40)."""
    base = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    return replace(base, skills={**base.skills, "fishing": 40})


def _evidence(path: Path, game_data, rows) -> LearnedDrops:  # type: ignore[no-untyped-def]
    """The cycle's `LearnedDrops` built from a real store holding `rows` of
    `(action_repr, action_class, drops_json, count)` ok cycles."""
    store = LearningStore(db_path=str(path), character="drop_probe")
    store.start_session()
    for action_repr, action_class, drops, count in rows:
        for _ in range(count):
            store.record_cycle(Cycle(ts="2026-10-21T00:00:00+00:00", cycle_index=0,
                                     action_repr=action_repr, action_class=action_class,
                                     outcome="ok", drops_json=drops))
    return learned_drops(store, game_data)


def _walk_gathers(state, game_data, evidence, policy=DECOMPOSE_POLICY):  # type: ignore[no-untyped-def]
    """The acquisition walk's GATHER routes to a pearl under `policy`:
    `{resource: gathers a pearl}`. DECOMPOSE_POLICY (the fast path's) offers
    every pearl spot; LEGACY only the primary one."""
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, learned_drops=evidence)
    options = acquisition_options("small_pearls", state, game_data, ctx, policy=policy)
    return {o.venue: o.actions_per_application for o in options["small_pearls"]
            if o.kind == "gather"}


def _pearl_gather(actions, resource: str) -> GatherAction:  # type: ignore[no-untyped-def]
    return next(a for a in actions if isinstance(a, GatherAction)
                and a.resource_code == resource and a.drop_item_override == "small_pearls")


def _producers(state, game_data, evidence):  # type: ignore[no-untyped-def]
    """The pearl gather each plan producer serves a one-pearl goal with: the
    fast path (`decompose`) and A* (`GOAPPlanner.plan`), over one action pool
    built with `evidence`, beside the context carrying the same value."""
    actions = build_actions(game_data, state, CharacterObjective.from_game_data(game_data),
                            bank_accessible=True, task_exchange_min_coins=1,
                            learned_drops=evidence)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, learned_drops=evidence)
    goal = GatherMaterialsGoal(target_item="small_pearls", needed={"small_pearls": 1})
    fast = decompose(goal, state, game_data, actions, ctx)
    searched = GOAPPlanner().plan(state, goal, actions, game_data)
    assert fast is not None and searched
    gather_of = [next(a for a in plan if isinstance(a, GatherAction)) for plan in (fast, searched)]
    return actions, gather_of


def test_the_planner_and_the_walk_price_a_drop_alike(tmp_path, state, game_data) -> None:
    """With the fleet's 383 trout gathers for 2 pearls (and 1,000 dry salmon
    gathers, so trout is the cheapest pearl spot), the walk, the fast path and
    A* all serve the pearl from `trout_spot`, and the planner's gather charges
    the walk's own figure: `(300 + 383) / (1 + 2)` gathers a pearl."""
    evidence = _evidence(tmp_path / "learn.db", game_data, _PEARLS_383_FOR_2 + _SALMON_1000_DRY)
    walk = _walk_gathers(state, game_data, evidence)
    assert walk == {"trout_spot": Fraction(683, 3), "bass_spot": 300, "salmon_spot": 1100}
    actions, (fast, searched) = _producers(state, game_data, evidence)
    assert fast.resource_code == searched.resource_code == "trout_spot"
    for gather in (fast, searched):
        assert gather.gathers(state, game_data) / gather.quantity == walk["trout_spot"]
    assert _pearl_gather(actions, "trout_spot").gathers(state, game_data) == Fraction(683, 3)


def test_no_store_prices_the_prior(state, game_data) -> None:
    """With nothing observed (`LearnedDrops.empty()`) the walk and the
    planner's gather both price a pearl off `trout_spot` at its API rate, 300."""
    walk = _walk_gathers(state, game_data, LearnedDrops.empty())
    assert walk["trout_spot"] == 300
    actions = build_actions(game_data, state, CharacterObjective.from_game_data(game_data),
                            bank_accessible=True, task_exchange_min_coins=1,
                            learned_drops=LearnedDrops.empty())
    assert _pearl_gather(actions, "trout_spot").gathers(state, game_data) == 300


def test_observations_flip_the_gather_source(tmp_path, state, game_data) -> None:
    """`salmon_spot` drops pearls at 1 in 100, `trout_spot` and `bass_spot` at
    1 in 300: under the prior every producer fishes salmon. 1,000 dry salmon
    gathers make it the dearest (1,100 a pearl) and the trout observations the
    cheapest, and every producer flips to `trout_spot` together."""
    _, prior = _producers(state, game_data, LearnedDrops.empty())
    assert [g.resource_code for g in prior] == ["salmon_spot", "salmon_spot"]
    assert _walk_gathers(state, game_data, LearnedDrops.empty(), LEGACY) == {"salmon_spot": 100}
    evidence = _evidence(tmp_path / "learn.db", game_data, _PEARLS_383_FOR_2 + _SALMON_1000_DRY)
    _, learned = _producers(state, game_data, evidence)
    assert [g.resource_code for g in learned] == ["trout_spot", "trout_spot"]
    # The legacy walk's one gather (its `primary`) is the learned-cheapest spot too.
    assert _walk_gathers(state, game_data, evidence, LEGACY) == {"trout_spot": Fraction(683, 3)}


def test_observations_flip_the_dropper(tmp_path, state, game_data) -> None:
    """`apple` drops off `yellow_slime` and `green_slime` alike, 1 in 12, so
    the prior is a tie the nearer slime wins. 120 wins against that one without
    an apple make it the dearer source, and the pick moves to the other."""
    def pick(evidence: LearnedDrops) -> str:
        fights = [FightAction(monster_code=code, locations=frozenset(tiles),
                              learned_drops=evidence)
                  for code in ("yellow_slime", "green_slime")
                  for tiles in [game_data.all_monster_locations[code]]]
        chosen = select_drop_fight("apple", list(fights), state, game_data, allow_grey=True)
        assert chosen is not None
        return chosen.monster_code

    near = pick(LearnedDrops.empty())
    far = ({"yellow_slime", "green_slime"} - {near}).pop()
    dry = _evidence(tmp_path / "learn.db", game_data,
                    [(f"Fight({near})", "FightAction", '{"slime": 1}', 120)])
    assert dry.attempts_per_unit(near, "apple", 12, 1, 1, 0) == 132
    assert pick(dry) == far


def _store(path: Path, rows) -> LearningStore:  # type: ignore[no-untyped-def]
    store = LearningStore(db_path=str(path), character="drop_probe")
    store.start_session()
    for action_repr, action_class, drops, count in rows:
        for _ in range(count):
            store.record_cycle(Cycle(ts="2026-10-21T00:00:00+00:00", cycle_index=0,
                                     action_repr=action_repr, action_class=action_class,
                                     outcome="ok", drops_json=drops))
    return store


def _player(state, game_data, history) -> GamePlayer:  # type: ignore[no-untyped-def]
    player = GamePlayer(character="drop_probe", history=history)
    player._offline_timing = committed_timing()
    player.state = state
    player.game_data = game_data
    return player


def test_the_player_hands_one_evidence_to_the_actions_and_the_context(
        tmp_path, state, game_data) -> None:
    """Built once a cycle from the store (`_refresh_learned_drops`), the very
    value the factory's gathers and fights carry and the pricing context
    (`_band_context`) reads, so the planner and the walk read one model."""
    store = _store(tmp_path / "learn.db", _PEARLS_383_FOR_2)
    player = _player(state, game_data, store)
    with pytest.raises(ValueError, match="no drop evidence"):
        player._build_actions()
    player._refresh_learned_drops()
    evidence = player._cycle_learned_drops()
    assert evidence == learned_drops(store, game_data)
    assert evidence.counts("trout_spot", "small_pearls") == (383, 2)
    carried = [a.learned_drops for a in player._build_actions()
               if isinstance(a, GatherAction | FightAction)]
    assert carried and all(drops is evidence for drops in carried)
    assert player._band_context("chicken").learned_drops is evidence


def test_a_player_without_history_prices_the_prior(state, game_data) -> None:
    player = _player(state, game_data, None)
    player._refresh_learned_drops()
    assert player._cycle_learned_drops() == LearnedDrops.empty()


def test_a_context_without_evidence_refuses_to_price_a_drop() -> None:
    """No silent prior (ruling T16a): a context nobody gave drop evidence
    raises when a consumer reads it; the prior is passed explicitly."""
    with pytest.raises(ValueError, match="no drop evidence"):
        replace(TIMED_NO_PROFILE_CONTEXT, learned_drops=None).drops()
