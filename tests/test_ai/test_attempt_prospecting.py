"""The prospecting a drop's chance is read at is the attempt's loadout's
(`attempt_prospecting`, ruling T12n). Task 14d, census of ledger 253 (b): the
drop-fight picker read `state.prospecting`, the WORN total, while the
acquisition walk priced the same drop at the fight loadout's prospecting."""

from fractions import Fraction

import artifactsmmo_cli.ai.drop_fight_selection as drop_fight_selection_mod
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

K = LearnedDrops((), (), Fraction(1, 100))


def test_the_drop_fight_picker_reads_the_fight_loadouts_prospecting(monkeypatch):
    """Two monsters drop the feather: `near` 1 in 2, `far` surely. At the worn
    total `far` is picked; at the prospecting the fight's loadout carries (here
    +100 at `k = 1/100`, both chances capped at 1) they tie and the nearer one
    is picked."""
    gd = GameData()
    gd._monster_level = {"near": 1, "far": 1}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"near": 10, "far": 10}
    gd._monster_attack = {"near": {}, "far": {}}
    gd._monster_resistance = {"near": {}, "far": {}}
    gd._monster_locations = {"near": [(1, 0)], "far": [(9, 0)]}
    gd._monster_drops = {"near": [("feather", 2, 1, 1)], "far": [("feather", 1, 1, 1)]}
    state = make_state(level=5, attack={"fire": 50})
    fights = [FightAction(monster_code=code, locations=frozenset({tile}), learned_drops=K)
              for code, tile in (("near", (1, 0)), ("far", (9, 0)))]
    picked = select_drop_fight("feather", fights, state, gd, allow_grey=True)
    assert picked is not None and picked.monster_code == "far"
    monkeypatch.setattr(drop_fight_selection_mod, "fight_prospecting", lambda *_a: 100)
    picked = select_drop_fight("feather", fights, state, gd, allow_grey=True)
    assert picked is not None and picked.monster_code == "near"
