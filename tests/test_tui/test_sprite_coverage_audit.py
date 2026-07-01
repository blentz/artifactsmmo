from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.sprite_coverage_audit import SpriteCoverageAudit
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, NPC_SPRITES


def _gd(monster_codes, npc_codes):
    gd = GameData()
    gd._monster_locations = {c: [(0, 0)] for c in monster_codes}
    gd.world.npc_tiles = {c: (0, 0) for c in npc_codes}
    return gd


def test_uncurated_monster_warns(capsys):
    curated = next(iter(MONSTER_SPRITES))
    SpriteCoverageAudit().run(_gd([curated, "made_up_beast"], []))
    out = capsys.readouterr().out
    assert "made_up_beast" in out and "uncurated monsters" in out
    assert curated not in out


def test_uncurated_npc_warns(capsys):
    curated = next(iter(NPC_SPRITES))
    SpriteCoverageAudit().run(_gd([], [curated, "made_up_vendor"]))
    out = capsys.readouterr().out
    assert "made_up_vendor" in out and "uncurated npcs" in out


def test_fully_covered_is_silent(capsys):
    SpriteCoverageAudit().run(_gd(list(MONSTER_SPRITES), list(NPC_SPRITES)))
    assert capsys.readouterr().out == ""
