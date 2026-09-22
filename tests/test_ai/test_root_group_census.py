"""The cycles table gains root attribution, and an old database gains it in place."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision, StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.root_group_census import GroupCounts, root_group_counts
from tests.test_ai.fixtures import LADDER_ITEM_STATS, make_state


def test_store_migrates_root_group_columns(tmp_path: Path) -> None:
    db = tmp_path / "learning.db"
    # A pre-existing cycles table with neither new column.
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE cycles (id INTEGER PRIMARY KEY, ts TEXT, session_id TEXT, "
            "cycle_index INTEGER, character TEXT, outcome TEXT)"
        )
    engine.dispose()

    LearningStore(str(db), character="C3P0")

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cycles)")}
    engine.dispose()
    assert "root_group" in cols
    assert "root_repr" in cols


def test_recent_cycles_returns_the_raw_stream_newest_first(tmp_path: Path) -> None:
    store = LearningStore(str(tmp_path / "learning.db"), character="C3P0")
    store.start_session()
    for index, group in enumerate(["trunk", "gear"]):
        store.record_cycle(Cycle(
            ts=f"2026-09-21T00:00:0{index}+00:00", session_id="placeholder",
            cycle_index=index, character="C3P0", outcome="ok",
            selected_goal="GrindCharacterXP(green_slime)", root_group=group,
            root_repr=f"Root{index}",
        ))
    rows = store.recent_cycles(window=10)
    # Newest first: the LAST recorded row leads.
    assert [r.root_group for r in rows] == ["gear", "trunk"]


def _record(store: LearningStore, decision: StrategyDecision) -> list[Cycle]:
    """Drive the REAL write site: `GamePlayer._record_learning_cycle` at
    player.py:4123, the same seam `test_cycle_error_text.py` uses for
    `error_text`. `_last_decision` is the StrategyDecision already in scope at
    that call site — there is no local variable named `decision` there, and the
    task-2 brief's binding ruling is that this seam, not a hand-built `Cycle`,
    is what proves the write site is actually populated in production."""
    player = GamePlayer(character="hero", dry_run=False, history=store)
    player._last_decision = decision
    prev = make_state(level=5)
    player._record_learning_cycle(
        prev_state=prev, new_state=make_state(level=5, xp=prev.xp + 10),
        action_repr="Fight(green_slime)", action_class="FightAction",
        outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
        predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=1, planner_depth=1, planner_timed_out=False,
        plan_len=1,
    )
    with Session(store._engine) as s:
        return list(s.exec(select(Cycle).where(
            Cycle.action_repr == "Fight(green_slime)")))


def _guard_world() -> GameData:
    """The smallest catalogue `_decide_band` can run against: one winnable
    monster so the walk has a trunk to resolve, a bank and a taskmaster so the
    selection context is buildable, and the shared ladder item stats."""
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 10}
    gd._monster_attack = {"chicken": {"fire": 1}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_critical_strike = {"chicken": 0}
    gd._monster_initiative = {"chicken": 0}
    gd._monster_type = {"chicken": "normal"}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = dict(LADDER_ITEM_STATS)
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    return gd


def _player_on(store: LearningStore, state: WorldState) -> GamePlayer:
    player = GamePlayer(character="hero", dry_run=False, history=store)
    gd = _guard_world()
    player.game_data = gd
    player._blockers.clear("bank")
    player.state = state
    player._objective = CharacterObjective.from_game_data(gd)
    player._strategy = StrategyEngine(player._objective)
    return player


def _decide_and_record(player: GamePlayer, store: LearningStore) -> list[Cycle]:
    """Run the REAL decision band — `StrategyEngine.decide` then
    `StrategyArbiter.select`, exactly as `_plan_or_reuse` runs them — and then
    the real cycle write site against whatever that produced."""
    assert player.state is not None
    assert player.game_data is not None
    selected_goal, _plan, _tried = player._decide_band(
        player.state, player.game_data, player._build_actions(), None)
    prev = player.state
    player._record_learning_cycle(
        prev_state=prev, new_state=prev,
        action_repr=repr(selected_goal), action_class="Probe",
        outcome="ok", selected_goal=repr(selected_goal),
        predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=1, planner_depth=1, planner_timed_out=False, plan_len=1,
    )
    with Session(store._engine) as s:
        return list(s.exec(select(Cycle)))


def test_write_site_records_guard_when_a_guard_actually_wins_the_cycle(
        tmp_path: Path) -> None:
    """THE GUARD LABEL, DRIVEN BY A REAL GUARD.

    `StrategyDecision.interrupt` — which the first version of this classifier
    read — is hardcoded `None` by `progression_tree.decide_tree`, the only
    production producer of a `StrategyDecision`. A test that hand-set
    `interrupt="RestoreHP"` therefore pinned a rule that could never fire, and
    every RestoreHP / DepositInventory / DiscardOverstock / GEAR_REVIEW cycle
    would have been filed under whatever root the walk last resolved.

    So this test makes a guard fire the way production does: hp below
    `CRITICAL_HP_FRACTION` raises `GuardKind.HP_CRITICAL` in `active_guards`,
    `_build_candidates` maps it to `RestoreHPGoal` in the GUARD band, and
    `select_pure` picks it ahead of the walk's root. Nothing is hand-set: the
    decision comes from `StrategyEngine.decide` and the selection from
    `StrategyArbiter.select`.
    """
    store = LearningStore(str(tmp_path / "guard.db"), character="hero")
    try:
        store.start_session()
        # 10/150 hp is far below CRITICAL_HP_FRACTION, so HP_CRITICAL fires.
        player = _player_on(store, make_state(hp=10, max_hp=150))
        rows = _decide_and_record(player, store)

        # The guard really did win the cycle — not merely fire.
        assert player._arbiter.last_selected_guard == "RestoreHP"
        assert len(rows) == 1
        assert rows[0].selected_goal == "RestoreHP"
        assert rows[0].root_group == "guard"
        # THE LOAD-BEARING HALF: production's own decision carries
        # `interrupt=None` on this very cycle — a guard cycle — so the rule this
        # test replaces could not have produced the label above from any real
        # run. The guard fact came from the arbiter, and only from there.
        assert player._last_decision is not None
        assert player._last_decision.interrupt is None
    finally:
        store.close()


def test_a_guard_cycle_clears_when_the_next_cycle_is_won_by_the_walk(
        tmp_path: Path) -> None:
    """`last_selected_guard` is assigned on EVERY `select`, so a healed
    character's next cycle is not still credited to the guard that ran before
    it. A field only written when a guard wins would smear one guard over every
    subsequent cycle until the next one fired.

    Both cycles run through the real `_decide_band`. The second one's group is
    `none`: this deliberately minimal catalogue (one chicken, no recipes, no
    gear targets) gives `resolve_root` nothing to resolve, so the walk returns
    no root. That is the honest reading of THIS world and the point stands —
    the guard label is gone the moment the guard stops winning. The
    trunk/gear/skill labels are pinned on production-shaped decisions below and
    in `test_root_group.py`."""
    store = LearningStore(str(tmp_path / "seq.db"), character="hero")
    try:
        store.start_session()
        player = _player_on(store, make_state(hp=10, max_hp=150))
        _decide_and_record(player, store)
        assert player._arbiter.last_selected_guard == "RestoreHP"

        player.state = make_state(hp=150, max_hp=150)
        rows = _decide_and_record(player, store)

        assert player._arbiter.last_selected_guard is None
        assert rows[1].selected_goal != "RestoreHP"
        with Session(store._engine) as s:
            groups = [c.root_group for c in s.exec(select(Cycle))]
        assert groups == ["guard", "none"]
        assert set(groups) <= ROOT_GROUPS
    finally:
        store.close()


def test_write_site_records_the_chosen_roots_group(tmp_path: Path) -> None:
    """A production-SHAPED decision: `decide_tree` emits `interrupt=None` on
    every cycle it produces, so this is the real field layout, unlike the
    `interrupt="RestoreHP"` state the deleted guard test hand-built."""
    store = LearningStore(str(tmp_path / "trunk.db"), character="hero")
    try:
        store.start_session()
        decision = StrategyDecision(
            interrupt=None, chosen_root=ReachCharLevel(level=10), chosen_step=None)
        rows = _record(store, decision)
        assert len(rows) == 1
        assert rows[0].root_group == "trunk"
        assert rows[0].root_repr == repr(ReachCharLevel(level=10))
    finally:
        store.close()


def test_write_site_groups_a_promoted_pick_by_the_walks_own_root(tmp_path: Path) -> None:
    """Servability promotion can walk the tree's gear pick to the trunk. The
    write site must record `gear` (what the walk chose) while `root_repr` keeps
    the trunk that actually ran — the pair is what makes the promotion legible
    afterwards, and counting it as `trunk` would state the opposite."""
    store = LearningStore(str(tmp_path / "promoted.db"), character="hero")
    try:
        store.start_session()
        decision = StrategyDecision(
            interrupt=None, chosen_root=ReachCharLevel(level=10), chosen_step=None,
            promoted_from=ObtainItem(code="copper_boots"))
        rows = _record(store, decision)
        assert len(rows) == 1
        assert rows[0].root_group == "gear"
        assert rows[0].root_repr == repr(ReachCharLevel(level=10))
    finally:
        store.close()


# ===== NEW TESTS FOR TASK 4: root_group_counts =====


def _grouped(character: str, group: str | None) -> Cycle:
    return Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="s", cycle_index=0,
        character=character, outcome="ok", root_group=group,
    )


def test_counts_by_group_per_character() -> None:
    rows = root_group_counts([
        _grouped("C3P0", "trunk"), _grouped("C3P0", "trunk"), _grouped("C3P0", "gear"),
        _grouped("R2D2", "orphan_skill"),
    ])
    by_char = {r.character: r for r in rows}
    assert by_char["C3P0"].counts == {"trunk": 2, "gear": 1}
    assert by_char["R2D2"].counts == {"orphan_skill": 1}


def test_pre_migration_rows_are_reported_as_unattributed_not_counted() -> None:
    rows = root_group_counts([_grouped("C3P0", "trunk"), _grouped("C3P0", None)])
    assert rows[0].attributed == 1
    assert rows[0].unattributed == 1
    assert rows[0].counts == {"trunk": 1}


def test_an_unknown_group_label_raises() -> None:
    # A label outside ROOT_GROUPS means the classifier and the census have
    # drifted. Counting it nowhere would hide that silently.
    with pytest.raises(ValueError, match="unknown root group"):
        root_group_counts([_grouped("C3P0", "made_up")])


def test_characters_are_ordered_by_name() -> None:
    rows = root_group_counts([_grouped("R2D2", "gear"), _grouped("C3P0", "gear")])
    assert [r.character for r in rows] == ["C3P0", "R2D2"]


def test_share_is_denominated_on_attributed_rows_only() -> None:
    counts = GroupCounts(character="C3P0", counts={"trunk": 1}, attributed=1, unattributed=9)
    assert counts.share("trunk") == 1.0
    assert counts.share("gear") == 0.0


def test_all_pre_migration_character_returns_none_share() -> None:
    # A character whose entire window is pre-migration NULLs (today IS the migration date).
    rows = root_group_counts([_grouped("C3P0", None), _grouped("C3P0", None)])
    assert len(rows) == 1
    assert rows[0].character == "C3P0"
    assert rows[0].counts == {}
    assert rows[0].attributed == 0
    assert rows[0].unattributed == 2
    # share() returns None when nothing was attributed, not 0.0.
    assert rows[0].share("trunk") is None
    assert rows[0].share("gear") is None
