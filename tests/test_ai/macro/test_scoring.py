from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.scoring import canonical_chain, score_candidates
from artifactsmmo_cli.ai.macro.segmentation import Band


def _row(goal, action, nodes, char="hero"):
    return CycleRow(char, "s1", 0, 1, goal, action, nodes, False)


def _band(key, rows, char="hero", kind="level"):
    return Band(char, "s1", kind, key, tuple(rows))


def test_canonical_chain_collapses_consecutive_dupes():
    band = _band("level=1", [
        _row("GrindCharacterXP(chicken)", "FightAction", 5),
        _row("GrindCharacterXP(chicken)", "FightAction", 5),
        _row("GatherMaterials(ash)", "GatherAction", 2),
    ])
    assert canonical_chain(band) == (
        ("GrindCharacterXP", "FightAction"),
        ("GatherMaterials", "GatherAction"),
    )


def test_score_groups_and_ranks_by_value():
    # chain A recurs across 2 characters (value = 2 * total_nodes)
    a_rows = [_row("PursueTask(t)", "CraftAction", 1000)]
    band_a1 = _band("level=2", a_rows, char="hero")
    band_a2 = _band("level=2", [_row("PursueTask(t)", "CraftAction", 1000, char="rob")], char="rob")
    # chain B occurs once, cheap
    band_b = _band("level=3", [_row("GrindCharacterXP(c)", "FightAction", 5)])
    cands = score_candidates([band_a1, band_a2, band_b])
    assert cands[0].chain == (("PursueTask", "CraftAction"),)
    assert cands[0].occurrences == 2
    assert cands[0].distinct_characters == 2
    assert cands[0].total_nodes == 2000
    assert cands[0].value == 4000          # 2 occ * 2000 nodes
    assert cands[1].value == 5             # cheap chain ranks last
