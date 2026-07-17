"""LogPane tests (no Textual app needed)."""

from unittest.mock import patch

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, PlanTreeNode, RootScoreView
from artifactsmmo_cli.tui.widgets.log_pane import LogPane, build_log_lines


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

    def test_why_line_shows_chosen_category_and_score(self):
        why = build_log_lines(_ranked_snap())[1]
        assert "why:" in why and "grind" in why and "1.80" in why

    def test_why_line_shows_top_two_alternatives(self):
        why = build_log_lines(_ranked_snap())[1]
        assert "copper_boots" in why and "1.00" in why
        assert "cooked_gudgeon" in why and "0.40" in why

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


class TestGrindExpansionLines:
    def test_grind_legs_appended_below_decision_line(self):
        legs = (PlanTreeNode(key="l0", label="GatherAsh()", kind="obtain", status="current"),
                PlanTreeNode(key="l1", label="CraftPlank()", kind="obtain", status="unmet"))
        lines = build_log_lines(_snap(action="LevelSkill(woodcutting)", grind_expansion=legs))
        chain = "\n".join(lines)
        assert "GatherAsh()" in chain and "CraftPlank()" in chain

    def test_no_grind_expansion_leaves_single_line(self):
        assert len(build_log_lines(_snap())) == 1
