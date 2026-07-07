from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.tracer import Tracer
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


class _CaptureTracer(Tracer):
    def __init__(self) -> None:
        self.records: list[dict] = []

    def write_cycle(self, record: dict) -> None:
        self.records.append(record)

    def close(self) -> None:
        pass


def _gd() -> GameData:
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    return gd


def test_emit_trace_includes_strategy_without_changing_selected_goal():
    player = GamePlayer(character="hero")
    player.game_data = _gd()
    player.state = make_state(level=3)
    player._objective = CharacterObjective.from_game_data(player.game_data)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player.tracer = _CaptureTracer()

    player._emit_trace(action_name="Gather(x)", goal_name="FarmItems",
                       outcome="ok", planner_stats={})

    rec = player.tracer.records[0]
    assert rec["selected_goal"] == "FarmItems"   # unchanged — shadow only
    assert "strategy" in rec
    assert "chosen_root" in rec["strategy"]


def test_emit_trace_omits_strategy_when_engine_absent():
    player = GamePlayer(character="hero")
    player.state = make_state(level=3)
    player.tracer = _CaptureTracer()
    player._emit_trace(action_name="a", goal_name="g", outcome="ok", planner_stats={})
    assert "strategy" not in player.tracer.records[0]


def test_emit_trace_includes_tree_shadow_without_changing_selected_goal():
    player = GamePlayer(character="hero")
    player.game_data = _gd()
    player.state = make_state(level=3)
    player._objective = CharacterObjective.from_game_data(player.game_data)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player.tracer = _CaptureTracer()

    player._emit_trace(action_name="Gather(x)", goal_name="FarmItems",
                       outcome="ok", planner_stats={})

    rec = player.tracer.records[0]
    assert rec["selected_goal"] == "FarmItems"   # unchanged — shadow only
    assert "tree" in rec
    assert "chosen_root" in rec["tree"]


def test_emit_trace_omits_tree_when_engine_absent():
    player = GamePlayer(character="hero")
    player.state = make_state(level=3)
    player.tracer = _CaptureTracer()
    player._emit_trace(action_name="a", goal_name="g", outcome="ok", planner_stats={})
    assert "tree" not in player.tracer.records[0]


def test_emit_trace_marks_enacted_legacy_when_flag_off():
    """Phase 4a Task 1: `record["enacted"]` names which engine drove
    selection. Flag-off (default) is always "legacy", and `strategy`/`tree`
    keys are NOT swapped — they stay legacy/tree respectively regardless of
    the flip (symmetric shadow, so divergence stats keep their meaning)."""
    player = GamePlayer(character="hero")
    player.game_data = _gd()
    player.state = make_state(level=3)
    player._objective = CharacterObjective.from_game_data(player.game_data)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player.tracer = _CaptureTracer()

    player._emit_trace(action_name="Gather(x)", goal_name="FarmItems",
                       outcome="ok", planner_stats={})

    rec = player.tracer.records[0]
    assert rec["enacted"] == "legacy"
    assert "chosen_root" in rec["strategy"]
    assert "chosen_root" in rec["tree"]


def test_emit_trace_marks_enacted_tree_when_flag_on():
    """Flag-on with a computable shadow: `record["enacted"] == "tree"`, but
    `record["strategy"]` is still the LEGACY decision's trace and
    `record["tree"]` is still the TREE decision's trace — roles NOT
    swapped."""
    player = GamePlayer(character="hero", progression_tree=True)
    player.game_data = _gd()
    player.state = make_state(level=3)
    player._objective = CharacterObjective.from_game_data(player.game_data)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player.tracer = _CaptureTracer()

    player._emit_trace(action_name="Gather(x)", goal_name="FarmItems",
                       outcome="ok", planner_stats={})

    rec = player.tracer.records[0]
    assert rec["enacted"] == "tree"
    assert "chosen_root" in rec["strategy"]
    assert "chosen_root" in rec["tree"]


def test_emit_trace_omits_enacted_when_engine_absent():
    """No strategy engine seeded: neither `strategy`/`tree` nor `enacted`
    are emitted — absent means unobserved, never a guessed default."""
    player = GamePlayer(character="hero", progression_tree=True)
    player.state = make_state(level=3)
    player.tracer = _CaptureTracer()
    player._emit_trace(action_name="a", goal_name="g", outcome="ok", planner_stats={})
    assert "enacted" not in player.tracer.records[0]


def test_compute_tree_shadow_none_when_unseeded():
    """A freshly constructed player (no seed_offline/_initialize) has no
    state/game_data/strategy/objective — the shadow must be None, not raise
    (totality per the repo's no-try/except rule)."""
    player = GamePlayer(character="hero")
    assert player._compute_tree_shadow() is None
