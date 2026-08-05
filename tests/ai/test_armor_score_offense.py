"""`armor_score` prices a non-weapon piece on BOTH halves of the combat swing.

Every item/monster stat below is verbatim from the live game API
(`/v3/items`, `/v3/monsters`, snapshot 2026-07-31) — no invented values.

The bug these lock: `armor_score` summed only `Σ mon_atk * armor_res` plus flat
utility, so for two resistance-free body armors the score collapsed to
`hp + wisdom` and a level-21 character swapped `mushmush_jacket` (dmg 10,
crit 3) for `adventurer_vest` (dmg 6) to buy 10 wisdom. The piece's damage %
and crit % — the only combat stats either one had — were invisible.

UNIT: both monster-relative terms are 1/20000 of one HP of damage swing per
combat turn (see `armor_score_pure`). The two tests that matter are the two
directions: an offensive piece must win when the fighter's own output is what
the piece multiplies, and a defensive piece must win when the monster's attack
makes resistance worth more. The SAME pair of real armors flips between those
two verdicts on the monster alone, which is what being in one unit buys.
"""

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import RULER_SCALE, armor_score
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.world_state import WorldState

# --- API items (effects verbatim from /v3/items) ---------------------------

_MUSHMUSH_JACKET = ItemStats(
    code="mushmush_jacket", level=15, type_="body_armor",
    hp_bonus=60, dmg=10, critical_strike=3, wisdom=10,
)
_ADVENTURER_VEST = ItemStats(
    code="adventurer_vest", level=10, type_="body_armor",
    hp_bonus=60, dmg=6, wisdom=20,
)
_PIGGY_ARMOR = ItemStats(
    code="piggy_armor", level=25, type_="body_armor",
    hp_bonus=150, dmg_elements={"fire": 22},
    resistance={"fire": 10, "earth": 5}, wisdom=30,
)
_NOVICE_GUIDE = ItemStats(
    code="novice_guide", level=10, type_="artifact",
    hp_bonus=25, wisdom=25, prospecting=25,
)
_IRON_ARMOR = ItemStats(
    code="iron_armor", level=10, type_="body_armor",
    hp_bonus=50, dmg_elements={"earth": 8, "fire": 8}, resistance={"water": 2, "air": 2},
)
_LEATHER_ARMOR = ItemStats(
    code="leather_armor", level=10, type_="body_armor",
    hp_bonus=50, dmg_elements={"air": 8, "water": 8}, resistance={"fire": 2, "earth": 2},
)

# --- API monsters (verbatim from /v3/monsters) -----------------------------

# mushmush (level 15): a light hitter the level-21 character grinds.
_MUSHMUSH_ATK = {"fire": 16, "earth": 0, "water": 16, "air": 0}
_MUSHMUSH_RES = {"fire": 20, "earth": 20, "water": 0, "air": -30}
# rosenblood (level 40): a heavy fire hitter — 400 attack vs mushmush's 32.
_ROSENBLOOD_ATK = {"fire": 400, "earth": 0, "water": 0, "air": 0}
_ROSENBLOOD_RES = {"fire": 10, "earth": 10, "water": 10, "air": 10}

# forest_whip (level 20 weapon): attack_air 40. The natural pick against
# mushmush, whose res_air is -30 (a weakness the clamp turns into 130%).
_FOREST_WHIP_ATTACK = {"air": 40}


def _gd(*items: ItemStats) -> GameData:
    gd = GameData()
    gd._item_stats = {it.code: it for it in items}
    return gd


def _state(level: int, inventory: dict[str, int],
           equipment: dict[str, str | None],
           attack: dict[str, int]) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=200, max_hp=200,
        gold=0, skills={}, x=0, y=0, inventory=dict(inventory), inventory_max=100,
        inventory_slots_max=100, equipment=dict(equipment), cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack=dict(attack), dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0,
    )


def test_mushmush_jacket_beats_adventurer_vest_against_mushmush() -> None:
    """THE OBSERVED BUG. Neither piece has any resistance, so the old formula
    reduced to hp + wisdom — 70 vs 80 — and the vest's 10 extra wisdom bought a
    downgrade of 4 global damage and 3 crit.

    With the offense term the jacket wins by the damage it actually adds to the
    fighter's output: against mushmush's res_air of -30 the forest_whip's 40 air
    attack clamps to 40*130 = 5200 centi-damage, and the jacket scales it by
    2*10+3 = 23 against the vest's 2*6+0 = 12.
    """
    jacket = armor_score(_MUSHMUSH_JACKET, _MUSHMUSH_ATK, _MUSHMUSH_RES,
                         _FOREST_WHIP_ATTACK)
    vest = armor_score(_ADVENTURER_VEST, _MUSHMUSH_ATK, _MUSHMUSH_RES,
                       _FOREST_WHIP_ATTACK)
    # RULER_SCALE * (40*130*23 + 200*(60+10)) vs RULER_SCALE * (40*130*12 + 200*(60+20))
    assert jacket == RULER_SCALE * 133600, jacket
    assert vest == RULER_SCALE * 78400, vest
    assert jacket > vest

    gd = _gd(_MUSHMUSH_JACKET, _ADVENTURER_VEST)
    state = _state(21, {"mushmush_jacket": 1}, {"body_armor_slot": "adventurer_vest"},
                   _FOREST_WHIP_ATTACK)
    loadout = pick_loadout(
        Combat(_MUSHMUSH_ATK, _MUSHMUSH_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert loadout["body_armor_slot"] == "mushmush_jacket", loadout


def test_worn_jacket_is_not_swapped_out_for_the_vest() -> None:
    """The live trace's exact direction: the jacket was EQUIPPED and the picker
    swapped it out. The no-downgrade rule keeps it now."""
    gd = _gd(_MUSHMUSH_JACKET, _ADVENTURER_VEST)
    state = _state(21, {"adventurer_vest": 1}, {"body_armor_slot": "mushmush_jacket"},
                   _FOREST_WHIP_ATTACK)
    loadout = pick_loadout(
        Combat(_MUSHMUSH_ATK, _MUSHMUSH_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert loadout["body_armor_slot"] == "mushmush_jacket", loadout


def test_defensive_piece_wins_when_the_monster_hits_hard() -> None:
    """Commensurability, the other direction. piggy_armor (res_fire 10) beats the
    pure-offense mushmush_jacket against rosenblood, whose 400 fire attack makes
    10% resistance worth 40 HP a turn — far more than the jacket adds to a 40-air
    output the monster resists. Dropping the 200x on the defense term (i.e. not
    putting the two on one denominator) reverses this."""
    piggy = armor_score(_PIGGY_ARMOR, _ROSENBLOOD_ATK, _ROSENBLOOD_RES,
                        _FOREST_WHIP_ATTACK)
    jacket = armor_score(_MUSHMUSH_JACKET, _ROSENBLOOD_ATK, _ROSENBLOOD_RES,
                         _FOREST_WHIP_ATTACK)
    # RULER_SCALE * (200*400*10 + 0 + 200*(150+30)) vs
    # RULER_SCALE * (0 + 40*90*23 + 200*(60+10))
    assert piggy == RULER_SCALE * 836000, piggy
    assert jacket == RULER_SCALE * 96800, jacket
    assert piggy > jacket

    gd = _gd(_PIGGY_ARMOR, _MUSHMUSH_JACKET)
    state = _state(25, {"piggy_armor": 1}, {"body_armor_slot": "mushmush_jacket"},
                   _FOREST_WHIP_ATTACK)
    loadout = pick_loadout(
        Combat(_ROSENBLOOD_ATK, _ROSENBLOOD_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert loadout["body_armor_slot"] == "piggy_armor", loadout


def test_same_pair_flips_on_the_monster_alone() -> None:
    """The pair that piggy_armor wins against rosenblood, mushmush_jacket wins
    against mushmush — same items, same fighter, only the monster changes. A
    score that ranked armor on one half of the swing could not do this."""
    gd = _gd(_PIGGY_ARMOR, _MUSHMUSH_JACKET)
    state = _state(25, {"piggy_armor": 1, "mushmush_jacket": 1},
                   {"body_armor_slot": None}, _FOREST_WHIP_ATTACK)
    vs_light = pick_loadout(
        Combat(_MUSHMUSH_ATK, _MUSHMUSH_RES, _FOREST_WHIP_ATTACK), state, gd)
    vs_heavy = pick_loadout(
        Combat(_ROSENBLOOD_ATK, _ROSENBLOOD_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert vs_light["body_armor_slot"] == "mushmush_jacket", vs_light
    assert vs_heavy["body_armor_slot"] == "piggy_armor", vs_heavy


def test_element_specialization_follows_the_fighters_element() -> None:
    """`dmg_elements` is how the game expresses element specialization on armor,
    and it is monster-relative through the same clamp: iron_armor (+8 earth/fire)
    and leather_armor (+8 air/water) are otherwise identical, so the pick must
    follow the FIGHTER's attack element. Dropping the `dmg_elements` read makes
    both score identically and the pick collapses to the code tiebreak."""
    gd = _gd(_IRON_ARMOR, _LEATHER_ARMOR)
    no_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    for attack, expected in (({"earth": 40}, "iron_armor"),
                             ({"air": 40}, "leather_armor")):
        state = _state(20, {"iron_armor": 1, "leather_armor": 1},
                       {"body_armor_slot": None}, attack)
        loadout = pick_loadout(Combat(no_res, no_res, attack), state, gd)
        assert loadout["body_armor_slot"] == expected, (attack, loadout)


def test_utility_artifact_still_scores_positive_and_is_pickable() -> None:
    """The empty-slot `> 0` gate must survive. novice_guide has no resistance and
    no damage %, so both monster-relative terms are 0 and only the flat utility
    (25+25+25, on the score's common 200x denominator) keeps it discoverable."""
    score = armor_score(_NOVICE_GUIDE, _MUSHMUSH_ATK, _MUSHMUSH_RES,
                        _FOREST_WHIP_ATTACK)
    assert score == RULER_SCALE * 200 * 75, score
    assert score > 0

    gd = _gd(_NOVICE_GUIDE)
    state = _state(21, {"novice_guide": 1}, {"artifact1_slot": None},
                   _FOREST_WHIP_ATTACK)
    loadout = pick_loadout(
        Combat(_MUSHMUSH_ATK, _MUSHMUSH_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert loadout["artifact1_slot"] == "novice_guide", loadout


def test_damage_percent_is_worthless_without_an_attack_to_scale() -> None:
    """The unit's honest consequence: a bare-handed fighter has no output, so a
    piece's damage % adds literally nothing and the score falls back to defense
    plus flat utility. This is what makes `player_attack` a REQUIRED input rather
    than a conversion constant — with no attack the offense term is 0, not
    'small'."""
    bare = armor_score(_MUSHMUSH_JACKET, _MUSHMUSH_ATK, _MUSHMUSH_RES, {})
    assert bare == RULER_SCALE * 200 * (60 + 10), bare
    armed = armor_score(_MUSHMUSH_JACKET, _MUSHMUSH_ATK, _MUSHMUSH_RES,
                        _FOREST_WHIP_ATTACK)
    assert armed > bare
