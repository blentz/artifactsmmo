"""LogPane tests (no Textual app needed)."""

from pathlib import Path
from unittest.mock import patch

from artifactsmmo_cli.ai.cycle_snapshot import (
    CycleSnapshot,
    PlanTreeNode,
    RoleChange,
    RootScoreView,
)
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.tui.widgets.log_pane import LogPane, build_log_lines

# Same fixture `tests/test_ai/scenarios/test_band_liveness.py`'s `_decide` uses
# to drive `decide_tree` for real — imported by path rather than duplicated,
# so this file's one production-driven test (below) exercises the SAME
# committed game data every other `decide_tree` test in the suite does.
_BUNDLE = (Path(__file__).resolve().parent.parent / "test_ai" / "scenarios"
          / "fixtures" / "gamedata_bundle.json")

_FIGHT = FightRecord(
    started_at="2026-07-27T23:30:30.455000",
    result="win",
    turns=27,
    opponent="mushmush",
    logs=("Fight start: hero HP: 485/485 vs Mushmush HP: 350/350",),
    hp_before=485,
    hp_after=275,
    xp=45,
    gold=12,
    drops=(),
)


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=5,
        timestamp="2026-05-21T14:30:45Z",
        character="hero",
        x=0,
        y=0,
        level=3,
        xp=30,
        max_xp=300,
        hp=100,
        max_hp=100,
        gold=0,
        selected_goal="farm_wood",
        action="harvest(ash_tree)",
        outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


class TestLogPaneInit:
    def test_instantiates_without_error(self):
        pane = LogPane()
        assert pane is not None

    def test_auto_scroll_enabled(self):
        pane = LogPane()
        assert pane.auto_scroll is True

    def test_markup_enabled(self):
        pane = LogPane()
        assert pane.markup is True

    def test_wrap_disabled(self):
        pane = LogPane()
        assert pane.wrap is False


class TestLogPaneUpdateSnapshot:
    def test_update_snapshot_calls_write(self):
        pane = LogPane()
        with patch.object(pane, "write") as mock_write:
            snap = _snap()
            pane.update_snapshot(snap)
            mock_write.assert_called_once()

    def test_update_snapshot_contains_timestamp(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap())
        assert len(captured) == 1
        # The HH:MM:SS slice is 11:19 of the ISO timestamp
        assert "14:30:45" in captured[0]

    def test_update_snapshot_contains_cycle_index(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(cycle_index=42))
        assert "42" in captured[0]

    def test_update_snapshot_contains_goal(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(selected_goal="level_mining"))
        assert "level_mining" in captured[0]

    def test_update_snapshot_contains_action(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(action="move(3,4)"))
        assert "move(3,4)" in captured[0]

    def test_update_snapshot_contains_outcome(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="ok"))
        assert "ok" in captured[0]

    def test_outcome_no_plan_in_line(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="no_plan"))
        assert "no_plan" in captured[0]

    def test_outcome_error_in_line(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="api_error"))
        assert "api_error" in captured[0]

    def test_short_timestamp_uses_full_string(self):
        """Timestamps shorter than 19 chars use the whole string."""
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(timestamp="short"))
        assert "short" in captured[0]


def _ranked_snap(**overrides):
    base = dict(
        chosen_root="ReachCharLevel(level=6)",
        strategy_ranking=[
            RootScoreView(root_repr="ReachCharLevel(level=6)", category="grind", score=1.80,
                          step_repr="FightAction(chicken)"),
            RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                          category="gear", score=1.00, step_repr="UpgradeEquipment(copper_boots)"),
            RootScoreView(root_repr="ObtainItem(code='cooked_gudgeon', quantity=1)",
                          category="skill", score=0.40, step_repr="LevelSkill(cooking)"),
        ],
    )
    base.update(overrides)
    return _snap(**base)


class TestBuildLogLines:
    def test_no_chosen_root_is_single_line(self):
        lines = build_log_lines(_snap(chosen_root=None))
        assert len(lines) == 1

    def test_empty_ranking_is_single_line(self):
        lines = build_log_lines(_snap(chosen_root="ReachCharLevel(level=6)", strategy_ranking=[]))
        assert len(lines) == 1

    def test_why_line_shows_chosen_category(self):
        """No score: THE FLIP (wave 3a) freezes `RootScore.score` to a
        constant on every row, so it is not part of the answer any more —
        `category` is."""
        why = build_log_lines(_ranked_snap())[1]
        assert "why:" in why and "grind" in why
        assert "1.80" not in why

    def test_why_line_shows_top_two_alternatives(self):
        why = build_log_lines(_ranked_snap())[1]
        assert "copper_boots" in why and "gear" in why
        assert "cooked_gudgeon" in why and "skill" in why
        assert "1.00" not in why and "0.40" not in why

    def test_why_line_shortens_a_multi_hop_trail_to_its_last_node(self):
        """The chosen row's `category` can be an arrow-joined resolution
        trail three or four names long
        (`IsMyGearBehindMyTier → IsThereACombatTarget → CanIClearMyTier`) —
        room enough in the multi-line plan pane, not in one `RichLog` row.
        The log pane shows only the LAST node: the decision that actually
        produced this root."""
        why = build_log_lines(_ranked_snap(
            chosen_root="ReachCharLevel(level=6)",
            strategy_ranking=[RootScoreView(
                root_repr="ReachCharLevel(level=6)",
                category="IsMyGearBehindMyTier → IsThereACombatTarget → CanIClearMyTier",
                score=1.0, step_repr="")]))[1]
        assert "CanIClearMyTier" in why
        assert "IsMyGearBehindMyTier" not in why and "→" not in why

    def test_why_line_shortens_an_alternative_kind_to_drop_the_word_alternative(self):
        """Every row in the `alt:` list is an alternative by construction, so
        the word itself is noise — only the `<kind>` half of `"alternative ·
        <kind>"` (production's real shape for a non-chosen row, spec §5.2)
        survives."""
        why = build_log_lines(_ranked_snap(strategy_ranking=[
            RootScoreView(root_repr="ReachCharLevel(level=6)", category="grind", score=1.0,
                          step_repr=""),
            RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                          category="alternative · gear", score=1.0, step_repr=""),
        ]))[1]
        assert "gear" in why
        assert "alternative" not in why

    def test_why_line_names_the_chosen_root(self):
        """The chosen root's NAME, not just its resolution reason — otherwise
        a currency grind (GatherMaterials(event_ticket)) shows in the log with
        no link to the target it funds (lich_race_medal)."""
        why = build_log_lines(_ranked_snap(
            chosen_root="ObtainItem(code='lich_race_medal', quantity=1)",
            strategy_ranking=[RootScoreView(
                root_repr="ObtainItem(code='lich_race_medal', quantity=1)",
                category="gear", score=50.0, step_repr="")]))[1]
        assert "lich_race_medal" in why

    def test_why_line_omits_alt_segment_when_only_chosen(self):
        snap = _ranked_snap(strategy_ranking=[
            RootScoreView(root_repr="ReachCharLevel(level=6)", category="grind", score=1.80,
                          step_repr="FightAction(chicken)"),
        ])
        why = build_log_lines(snap)[1]
        assert "alt:" not in why

    def test_update_snapshot_writes_two_lines_when_ranked(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_ranked_snap())
        assert len(captured) == 2

    def test_chosen_root_not_in_ranking_returns_single_line(self):
        """Edge case: chosen_root doesn't appear in the ranking."""
        snap = _ranked_snap(chosen_root="NonexistentGoal")
        lines = build_log_lines(snap)
        assert len(lines) == 1

    def test_why_line_reflects_a_production_built_decision(self):
        """Every other test in this class hand-builds a `RootScoreView` with a
        distinct score per row — exactly the shape that let a whole-branch
        review finding go unnoticed: `decide_tree`'s real
        `_resolution_rows` (wave 3a, `progression_tree.py`) freezes
        `RootScore.score` to a constant on every row, and nothing in this
        file ever rendered what production actually writes there. This test
        drives the REAL `decide_tree` -> `StrategyDecision.ranking` ->
        `RootScoreView` conversion — the same one `player.py`'s
        `_emit_trace` performs — and asserts the log line it produces
        carries no numeric score and no un-shortened trail."""
        gd = load_bundle_game_data(_BUNDLE)
        state = scenario_state(SCENARIOS["l1_fresh"], gd)
        objective = CharacterObjective.from_game_data(gd)
        decision = decide_tree(state, gd, objective)
        assert decision.chosen_root is not None
        assert decision.ranking, "l1_fresh must produce a rendered descent"
        snap = _ranked_snap(
            chosen_root=repr(decision.chosen_root),
            strategy_ranking=[
                RootScoreView(root_repr=r.root_repr, category=r.category,
                              score=float(r.score), step_repr=r.step_repr)
                for r in decision.ranking
            ],
        )
        why = build_log_lines(snap)[1]
        assert "why:" in why
        assert "1.00" not in why
        assert "→" not in why


class TestGrindExpansionLines:
    def test_grind_legs_appended_below_decision_line(self):
        legs = (PlanTreeNode(key="l0", label="GatherAsh()", kind="obtain", status="current"),
                PlanTreeNode(key="l1", label="CraftPlank()", kind="obtain", status="unmet"))
        lines = build_log_lines(_snap(action="LevelSkill(woodcutting)", grind_expansion=legs))
        chain = "\n".join(lines)
        assert "GatherAsh()" in chain and "CraftPlank()" in chain

    def test_no_grind_expansion_leaves_single_line(self):
        assert len(build_log_lines(_snap())) == 1


class TestFightSummary:
    def test_fight_cycle_appends_a_summary_line(self):
        lines = build_log_lines(_snap(action="Fight(mushmush)", fight=_FIGHT))

        assert any("fight:" in line and "27t" in line for line in lines)

    def test_non_fight_cycle_appends_nothing(self):
        assert not any("fight:" in line for line in build_log_lines(_snap()))

    def test_summary_sits_below_the_decision_line(self):
        lines = build_log_lines(_snap(action="Fight(mushmush)", fight=_FIGHT))

        assert "Fight(mushmush)" in lines[0]
        assert "fight:" in lines[-1]

    def test_a_lost_fight_still_reports(self):
        """The cycle outcome is error:fight_lost, but the record is present."""
        lost = _FIGHT.model_copy(update={"result": "loss", "hp_after": 0})

        lines = build_log_lines(
            _snap(action="Fight(mushmush)", outcome="error:fight_lost", fight=lost))

        assert any("loss" in line for line in lines)


_SUPPLY = repr(("ash_wood", 62, 50))


class TestSpecializationIsQuietWhenNothingHappens:
    """The property most likely to regress: a character with no role and no
    sibling demand — every cycle of every single-character run — must render
    EXACTLY as it did before specialization existed."""

    def test_a_plain_cycle_is_still_one_line(self):
        assert len(build_log_lines(_snap())) == 1

    def test_a_ranked_cycle_is_still_two_lines(self):
        assert len(build_log_lines(_ranked_snap())) == 2

    def test_a_role_with_nothing_to_supply_adds_no_line(self):
        """Holding a role is not, by itself, an event: the log stays quiet
        until the character is actually producing for a sibling."""
        assert build_log_lines(_snap(role="logger")) == build_log_lines(_snap())

    def test_an_unparseable_supply_target_adds_no_line(self):
        """Degrade to silence, never to a partial or invented figure."""
        assert build_log_lines(_snap(role="logger", supply_target="ash_wood")) == \
            build_log_lines(_snap())


class TestSupplyContinuationLine:
    def test_a_supply_cycle_names_the_role_and_the_progress(self):
        lines = build_log_lines(_snap(role="logger", supply_target=_SUPPLY))
        assert len(lines) == 2
        assert "role: logger" in lines[1]
        assert "supplying ash_wood →62 banked, 50 unmet" in lines[1]

    def test_the_continuation_line_is_dim(self):
        """Same dim-continuation treatment as the `why` line above it."""
        line = build_log_lines(_snap(role="logger", supply_target=_SUPPLY))[1]
        assert line.startswith("[dim]   role:") and line.endswith("[/dim]")

    def test_it_sits_below_the_why_line(self):
        lines = build_log_lines(_ranked_snap(role="logger", supply_target=_SUPPLY))
        assert "why:" in lines[1]
        assert "role: logger" in lines[2]

    def test_a_supply_target_with_no_role_says_so_rather_than_None(self):
        """Unreachable in production (`_pick_supply_target` returns None
        without a role) — pinned so the rendering can never leak a bare
        `None` into the pane if that ever stops holding."""
        line = build_log_lines(_snap(supply_target=_SUPPLY))[1]
        assert "role: none" in line and "None" not in line


class TestRoleTransitionEvent:
    def test_a_claim_renders_an_event_line(self):
        change = RoleChange(previous=None, current="logger", reason="demand 50")
        lines = build_log_lines(_snap(role="logger", role_change=change))
        assert len(lines) == 2
        assert "* role: none -> logger" in lines[0]
        assert "(demand 50)" in lines[0]

    def test_a_release_renders_the_role_it_gave_up(self):
        change = RoleChange(previous="miner", current=None,
                            reason="no demand for 100 cycles")
        line = build_log_lines(_snap(role_change=change))[0]
        assert "* role: miner -> none" in line
        assert "(no demand for 100 cycles)" in line

    def test_the_event_sits_above_the_decision_line(self):
        """A peer event, not a note on the action — and the action it happened
        alongside is still shown."""
        change = RoleChange(previous=None, current="logger", reason="demand 50")
        lines = build_log_lines(_snap(role_change=change))
        assert "* role:" in lines[0]
        assert "harvest(ash_tree)" in lines[1]

    def test_the_event_carries_the_same_timestamp_gutter(self):
        change = RoleChange(previous=None, current="logger", reason="demand 50")
        lines = build_log_lines(_snap(cycle_index=45, role_change=change))
        assert lines[0].startswith("[dim]14:30:45[/dim] c 45")
        assert lines[1].startswith("[dim]14:30:45[/dim] c 45")

    def test_an_empty_reason_omits_the_clause_rather_than_inventing_one(self):
        change = RoleChange(previous=None, current="logger")
        line = build_log_lines(_snap(role_change=change))[0]
        assert "* role: none -> logger" in line
        assert "(" not in line

    def test_no_transition_adds_no_line(self):
        assert build_log_lines(_snap(role="logger", role_change=None)) == \
            build_log_lines(_snap())


class TestReplaceHistoryEquivalence:
    """A focus switch re-renders a whole list of snapshots. Because the role
    transition is carried ON the snapshot rather than diffed by this widget,
    the replay is the same function of the same data as the live append — the
    property a stateful widget could not hold, since the store's per-character
    buffer is a bounded deque and a replay may start mid-run."""

    _HISTORY = (
        _snap(cycle_index=44),
        _snap(cycle_index=45, role="logger",
              role_change=RoleChange(previous=None, current="logger",
                                     reason="demand 50")),
        _snap(cycle_index=46, role="logger", supply_target=_SUPPLY),
    )

    def test_replay_matches_line_by_line_appends(self):
        live = LogPane()
        live_lines = []
        with patch.object(live, "write", side_effect=live_lines.append):
            for snap in self._HISTORY:
                live.update_snapshot(snap)

        switched = LogPane()
        replayed = []
        with patch.object(switched, "write", side_effect=replayed.append):
            switched.replace_history(self._HISTORY)

        assert replayed == live_lines

    def test_replay_from_mid_run_does_not_invent_a_transition(self):
        """The buffer is bounded, so a switch can replay a suffix. Starting at
        cycle 46 must render cycle 46 exactly as it rendered live, even though
        the claim that put the character on `logger` has been evicted."""
        suffix = self._HISTORY[2:]
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.replace_history(suffix)

        assert captured == build_log_lines(suffix[0])
        assert not any("* role:" in line for line in captured)
