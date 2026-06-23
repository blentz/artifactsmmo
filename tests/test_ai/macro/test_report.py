from artifactsmmo_cli.ai.macro.cost import CostStat
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.report import format_report, goal_repr_variants
from artifactsmmo_cli.ai.macro.scoring import MacroCandidate


def test_goal_repr_variants_dedupes_and_sorts():
    rows = [
        CycleRow("h", "s", 0, 1, "GatherMaterials(ring, {ore: 6})", "A", 1, False),
        CycleRow("h", "s", 1, 1, "GatherMaterials(ring, {ore: 3})", "A", 1, False),
        CycleRow("h", "s", 2, 1, "GatherMaterials(ring, {ore: 6})", "A", 1, False),
    ]
    v = goal_repr_variants(rows)
    assert v["GatherMaterials"] == [
        "GatherMaterials(ring, {ore: 3})", "GatherMaterials(ring, {ore: 6})",
    ]


def test_goal_repr_variants_skips_none_goal():
    rows = [
        CycleRow("h", "s", 0, 1, None, "A", 1, False),                 # skipped
        CycleRow("h", "s", 1, 1, "PursueTask(t1)", "A", 1, False),
    ]
    v = goal_repr_variants(rows)
    assert v == {"PursueTask": ["PursueTask(t1)"]}                      # no "<none>" key


def test_format_report_contains_sections():
    cost = [CostStat("PursueTask", 2, 4000, 2000.0, 1)]
    cand = [MacroCandidate("level", (("PursueTask", "CraftAction"),), 2, 2, 4000, 8000,
                           ("level=2",))]
    variants = {"PursueTask": ["PursueTask(t1)", "PursueTask(t2)"]}
    md = format_report(cost, cand, variants, top_n=10)
    assert "# Macro-candidate research" in md
    assert "PursueTask" in md and "4000" in md      # cost row
    assert "value" in md.lower()                     # candidate table header
    assert "8000" in md                              # candidate value
    assert "PursueTask(t1)" in md                    # variants section
