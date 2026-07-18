from artifactsmmo_cli.ai.macro.cost import cost_by_goal_type, parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


def _row(goal, nodes, timed_out=False):
    return CycleRow("hero", "s1", 0, 1, goal, "A", nodes, timed_out)


def test_parse_goal_type():
    assert parse_goal_type("GatherMaterials(copper_ring, {x: 6})") == "GatherMaterials"
    assert parse_goal_type("PursueTask") == "PursueTask"
    assert parse_goal_type(None) == "<none>"


def test_cost_by_goal_type_aggregates_and_sorts():
    rows = [
        _row("PursueTask(t1)", 1000, True),
        _row("PursueTask(t2)", 3000),
        _row("GrindCharacterXP(chicken)", 10),
        _row("GrindCharacterXP(chicken)", 30),
        _row("GatherMaterials(x)", None),   # None nodes treated as 0
    ]
    stats = cost_by_goal_type(rows)
    assert stats[0].goal_type == "PursueTask"          # highest total_nodes first
    assert stats[0].total_nodes == 4000
    assert stats[0].n_cycles == 2 and stats[0].timeouts == 1
    assert stats[0].mean_nodes == 2000.0
    gm = next(s for s in stats if s.goal_type == "GatherMaterials")
    assert gm.total_nodes == 0 and gm.mean_nodes == 0.0
