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


def test_score_cross_char_precedes_higher_value_single_char():
    # chain X: 2 distinct characters, lower value (1 occ * 500 nodes = 500)
    band_x1 = _band("level=5", [_row("GatherMaterials(ash)", "GatherAction", 500)], char="alpha")
    band_x2 = _band("level=5", [_row("GatherMaterials(ash)", "GatherAction", 0, char="beta")], char="beta")
    # chain Y: 1 distinct character, higher value (3 occ * 400 nodes = 1200)
    band_y1 = _band("level=5", [_row("PursueTask(t)", "CraftAction", 400)], char="hero")
    band_y2 = _band("level=5", [_row("PursueTask(t)", "CraftAction", 400)], char="hero")
    band_y3 = _band("level=5", [_row("PursueTask(t)", "CraftAction", 400)], char="hero")
    cands = score_candidates([band_x1, band_x2, band_y1, band_y2, band_y3])
    # X has distinct_characters=2, Y has distinct_characters=1 — X must rank first
    assert cands[0].chain == (("GatherMaterials", "GatherAction"),)
    assert cands[0].distinct_characters == 2
    assert cands[1].chain == (("PursueTask", "CraftAction"),)
    assert cands[1].distinct_characters == 1
