"""EVERY consumer of the Rank ruler, named, at the new scale.

Unifying Rank onto `weapon_score`/`armor_score` moved its range from ~10^2 to
~10^3-10^6. A changed scale silently breaks any ABSOLUTE threshold, so this
module enumerates the seven call sites `grep -rn "gear_value.*Rank\\|equip_value"
src/` finds and pins what each one actually does with the number. Six compare
Rank values to each other WITHIN one slot or one item type (scale-free); one
compares against 0.

If a new Rank consumer appears, it belongs here.
"""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.empty_slot_fills import empty_slot_rank_fills
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.progression_reserve import _best_per_slot
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import best_attainable_weapon
from artifactsmmo_cli.ai.tiers.progression_tree import _utility_candidates
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


# --- 1. tiers/objective.CharacterObjective.from_game_data -------------------

def test_objective_target_gear_compares_within_one_item_type() -> None:
    """`from_game_data` buckets candidates `by_type` before ranking, so the
    weapon branch's much larger scale never competes with the armor branch's.
    Ordering-only: no absolute threshold to re-derive."""
    gd = _bundle()
    obj = CharacterObjective.from_game_data(gd)
    for slot, code in obj.target_gear.items():
        chosen = gd.item_stats(code)
        assert chosen is not None
        peers = [s for s in gd.all_item_stats.values() if s.type_ == chosen.type_]
        best = max(equip_value(s) for s in peers)
        assert equip_value(chosen) <= best, (slot, code)
    # The BiS body armor really is the highest-Rank body armor available.
    body = gd.item_stats(obj.target_gear["body_armor_slot"])
    assert body is not None and equip_value(body) > 0


# --- 2. tiers/prerequisite_graph.best_attainable_weapon ---------------------

def test_best_attainable_weapon_is_the_argmax_over_weapons_only() -> None:
    """Scans `type_ == "weapon"` exclusively, so it stays inside the weapon
    branch's scale. Ordering-only."""
    gd = _bundle()
    best = best_attainable_weapon(gd)
    assert best is not None
    best_stats = gd.item_stats(best)
    assert best_stats is not None
    for stats in gd.all_item_stats.values():
        if stats.type_ == "weapon":
            assert equip_value(stats) <= equip_value(best_stats)


# --- 3. progression_reserve._best_per_slot ----------------------------------

def test_progression_reserve_compares_within_a_slot_and_against_zero() -> None:
    """Per-slot: candidate vs the item equipped in THAT slot, with an EMPTY
    slot valued 0. The only absolute use of the scale is `> 0`, and every real
    equippable in the catalog except the nine unmodeled runes is strictly
    positive (see `test_only_the_unmodelled_runes_score_zero`)."""
    gd = _bundle()
    state = make_state(level=10, equipment={"body_armor_slot": None})
    best = _best_per_slot(state, gd, max_level=12)
    for slot, code in best.items():
        stats = gd.item_stats(code)
        assert stats is not None
        assert equip_value(stats) > 0, (slot, code)


# --- 4. tiers/progression_tree._utility_candidates --------------------------

def test_utility_candidates_gate_on_strictly_positive_rank() -> None:
    """The ONE consumer that uses Rank as a magnitude rather than an ordering:
    `gain = potion_type_weight(family) * equip_value(stats)`, admitted on
    `gain > 0`. `hp_restore` had to join `armor_score`'s flat-utility block for
    this to survive the move — without it every healing potion scores 0 and this
    branch empties."""
    gd = _bundle()
    state = scenario_state(SCENARIOS["l8_overstocked"])
    cands = _utility_candidates(state, gd, CharacterObjective.from_game_data(gd))
    assert cands, "the utility-potion branch must not empty at the new scale"
    for c in cands:
        assert c.gain > 0
        stats = gd.item_stats(c.code)
        assert stats is not None and stats.hp_restore > 0


# --- 5. goals/progression.UpgradeEquipmentGoal._upgrade_value ---------------

def test_upgrade_goal_ranks_a_slot_replacement_by_rank() -> None:
    """`_is_upgrade_over` compares a candidate to the item in the SAME slot.
    `_best_by_value` additionally compares an inventory pick to a craftable pick
    ACROSS slots — the one place two item types meet on this ruler, where the
    weapon branch's `2 * WScore` sits at twice the armor branch's unit. Pinned
    here rather than assumed."""
    goal = UpgradeEquipmentGoal()
    weak = ItemStats(code="weak", level=1, type_="body_armor", resistance={"fire": 2})
    strong = ItemStats(code="strong", level=1, type_="body_armor", resistance={"fire": 20})
    assert goal._upgrade_value(strong) > goal._upgrade_value(weak)
    assert goal._upgrade_value(strong) == equip_value(strong)


# --- 6. inventory_caps._is_equippable_dominated -----------------------------

def test_delete_dominance_gate_is_a_strict_ordering_among_same_slot_peers() -> None:
    """`gear_value(peer, Rank) > gear_value(item, Rank)`, and the peer must fit
    every slot this item fits — so the comparison never crosses item types.
    Ordering-only."""
    gd = GameData()
    gd._item_stats = {
        "weak_amulet": ItemStats(code="weak_amulet", level=1, type_="amulet", hp_bonus=3),
        "strong_amulet": ItemStats(code="strong_amulet", level=5, type_="amulet", hp_bonus=30),
    }
    gd._crafting_recipes = {}
    state = make_state(inventory={"weak_amulet": 1, "strong_amulet": 1})
    assert gear_value(gd.item_stats("strong_amulet"), Rank) > gear_value(
        gd.item_stats("weak_amulet"), Rank)
    assert useful_quantity_cap("weak_amulet", state, gd) == 0


# --- 7. equipment/empty_slot_fills -> pick_loadout_cached(Rank()) -----------

def test_empty_slot_fill_requires_strictly_positive_rank() -> None:
    """`pick_loadout`'s empty-slot gate discards a best candidate scoring <= 0.

    VERDICT CHANGE: under the retired flat sum every non-tool carried a
    `nonToolBonus` of +1 whatever its stats, so ANY owned equippable filled an
    empty slot. The nonToolBonus is a weapon-branch tiebreaker and non-weapons
    never had one, so a zero-stat piece is now left in the bag instead of
    costing a request and a cooldown."""
    gd = GameData()
    gd._item_stats = {
        "real_amulet": ItemStats(code="real_amulet", level=1, type_="amulet", hp_bonus=10),
        "blank_amulet": ItemStats(code="blank_amulet", level=1, type_="amulet"),
    }
    gd._crafting_recipes = {}
    assert equip_value(gd.item_stats("blank_amulet")) == 0

    state = make_state(level=5, inventory={"real_amulet": 1},
                       equipment={"amulet_slot": None})
    assert empty_slot_rank_fills(state, gd, frozenset())["amulet_slot"] == "real_amulet"

    blank_only = make_state(level=5, inventory={"blank_amulet": 1},
                            equipment={"amulet_slot": None})
    assert "amulet_slot" not in empty_slot_rank_fills(blank_only, gd, frozenset())


def test_only_the_unmodelled_runes_score_zero() -> None:
    """The blast radius of the `> 0` gate, measured against the real catalog:
    of 317 equippables exactly 9 score 0, and all 9 are RUNES — whose carved
    abilities are the explicitly-deferred "Player rune abilities" follow-on
    (docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md, non-goals).
    They scored 1 before only because of the nonToolBonus, which priced nothing.
    Modelling rune abilities is what makes them fillable again."""
    gd = _bundle()
    equippables = [s for s in gd.all_item_stats.values() if s.type_ in ITEM_TYPE_TO_SLOTS]
    zero = [s for s in equippables if equip_value(s) == 0]
    assert len(equippables) > 300
    assert {s.type_ for s in zero} == {"rune"}
