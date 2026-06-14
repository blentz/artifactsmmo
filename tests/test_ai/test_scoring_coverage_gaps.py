"""Behavior tests closing coverage gaps in equipment/scoring.pick_loadout.

Covers armor-slot optimization and the empty-slot (no current stats) path.
"""

from artifactsmmo_cli.ai.equipment.scoring import (
    pick_gather_loadout,
    pick_loadout,
    weapon_score,
    weapon_score_raw,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
        "water_robe": ItemStats(code="water_robe", level=1, type_="body_armor",
                                resistance={"water": 20}),
        "iron_armor": ItemStats(code="iron_armor", level=1, type_="body_armor",
                                resistance={"earth": 40}),
    }
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
    }
    return gd


class TestArmorSlotLoadout:
    def test_equips_armor_into_empty_slot(self):
        """No armor equipped (current_stats is None) -> best owned armor is
        slotted in (lines 88-89)."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"leather_armor": 1, "water_robe": 1},
            equipment={"body_armor_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # vs earth-attacking slime, leather (res earth 10) reduces damage;
        # water_robe (res water) does nothing -> leather chosen.
        assert loadout["body_armor_slot"] == "leather_armor"

    def test_swaps_armor_when_candidate_reduces_more_damage(self):
        """Equipped leather is beaten by iron_armor against an earth attacker
        (armor-slot upgrade comparison, lines 81 + 94-95)."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"iron_armor": 1},
            equipment={"body_armor_slot": "leather_armor"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["body_armor_slot"] == "iron_armor"

    def test_keeps_armor_when_no_candidate_improves(self):
        """Equipped iron_armor already best -> no downgrade to leather."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"leather_armor": 1},
            equipment={"body_armor_slot": "iron_armor"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["body_armor_slot"] == "iron_armor"


def _gd_rings() -> GameData:
    """Two ring types with EQUAL earth-resistance (so they tie on armor_score)
    plus a strictly-better ring; slime attacks earth only."""
    gd = GameData()
    gd._item_stats = {
        "alpha_ring": ItemStats(code="alpha_ring", level=1, type_="ring",
                                resistance={"earth": 20}),
        "beta_ring": ItemStats(code="beta_ring", level=1, type_="ring",
                               resistance={"earth": 20}),  # ties alpha_ring
        "weak_ring": ItemStats(code="weak_ring", level=1, type_="ring",
                               resistance={"earth": 5}),
    }
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
    }
    return gd


class TestMultiSlotContention:
    def test_keeps_current_ring_on_score_tie(self):
        """When the argmax candidate ties the current ring on armor_score, the
        swap is NOT taken (strict `>` improvement) and the slot keeps its
        current code."""
        gd = _gd_rings()
        # ring1 holds alpha_ring; beta_ring (equal score) is in inventory.
        # The argmax may surface beta_ring, but it doesn't strictly improve, so
        # ring1 keeps alpha_ring.
        state = make_state(
            level=1,
            inventory={"beta_ring": 1},
            equipment={"ring1_slot": "alpha_ring", "ring2_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["ring1_slot"] == "alpha_ring"
        # ring2 (empty current) then takes beta_ring — it sits nowhere else
        # in the projected result, so it is feasible there.
        assert loadout["ring2_slot"] == "beta_ring"

    def test_worn_ring_never_stolen_by_sibling_empty_slot(self):
        """ONE SLOT PER CODE (server HTTP 485): a code worn in ring2 is in the
        projected result at another slot, so it is INFEASIBLE for the empty
        ring1 — the old "steal the last copy" shuffle is gone. ring1 has no
        feasible candidate and stays empty; ring2 keeps its ring."""
        gd = _gd_rings()
        # Exactly ONE physical alpha_ring, equipped on ring2, nothing in
        # inventory -> alpha_ring sits in the projected result at ring2.
        state = make_state(
            level=1,
            inventory={},
            equipment={"ring1_slot": None, "ring2_slot": "alpha_ring"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["ring1_slot"] is None
        assert loadout["ring2_slot"] == "alpha_ring"

    def test_sibling_empty_slot_takes_a_different_code_only(self):
        """The worn alpha_ring is infeasible for the empty ring1 (one slot per
        code), but a DIFFERENT code in inventory is fair game: ring1 fills
        with weak_ring; ring2 keeps the better alpha_ring (no swap-shuffle)."""
        gd = _gd_rings()
        state = make_state(
            level=1,
            # One spare weak_ring in inventory; the single alpha_ring is only
            # equipped on ring2.
            inventory={"weak_ring": 1},
            equipment={"ring1_slot": None, "ring2_slot": "alpha_ring"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # ring1's feasible pool excludes the worn alpha_ring; weak_ring scores
        # 8 * 5 = 40 > 0 against the earth attacker, so it fills the slot.
        assert loadout["ring1_slot"] == "weak_ring"
        assert loadout["ring2_slot"] == "alpha_ring"

    def test_dual_ring_spare_copy_fills_sibling_slot(self):
        """THE 2026-06-14 DUAL-RING TRACE LOCK (flipped from the old 485
        livelock): copper_ring worn in ring1 plus a SECOND copper_ring in
        inventory (ownership 2) — the spare IS assigned to ring2. The live
        server returns HTTP 200 for a duplicate ring (probe 2026-06-14), so the
        rings carve-out fills the sibling up to physical ownership. Lean:
        `pickLoadout_dual_ring_fills_when_two_owned`."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     resistance={"earth": 10}),
        }
        gd._monster_attack = {
            "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        }
        gd._monster_resistance = {
            "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
        }
        state = make_state(
            level=1,
            inventory={"copper_ring": 1},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["ring1_slot"] == "copper_ring"
        assert loadout["ring2_slot"] == "copper_ring"

    def test_zero_score_candidate_never_fills_empty_slot(self):
        """An empty slot is only filled at a STRICTLY POSITIVE score: a ring
        whose resistances are irrelevant to this monster (score 0) stays in
        inventory rather than burning its one legal slot on a no-op equip."""
        gd = GameData()
        gd._item_stats = {
            # water resistance vs an earth-only attacker -> armor_score == 0.
            "water_ring": ItemStats(code="water_ring", level=1, type_="ring",
                                    resistance={"water": 20}),
        }
        gd._monster_attack = {
            "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        }
        gd._monster_resistance = {
            "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
        }
        state = make_state(
            level=1,
            inventory={"water_ring": 1},
            equipment={"ring1_slot": None, "ring2_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["ring1_slot"] is None
        assert loadout["ring2_slot"] is None


    def test_keeps_level_gated_current_when_no_feasible_candidate(self):
        """A slot's current item is above the player's level (so it's filtered
        out of the candidate pool) yet still physically owned -> the slot keeps
        it (the no-feasible branch leaves the slot as-is)."""
        gd = GameData()
        gd._item_stats = {
            # Equipped ring requires level 10; player is level 1, so it is NOT a
            # candidate, leaving the slot with no feasible candidate.
            "high_ring": ItemStats(code="high_ring", level=10, type_="ring",
                                   resistance={"earth": 50}),
        }
        gd._monster_attack = {
            "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        }
        gd._monster_resistance = {
            "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
        }
        state = make_state(
            level=1, inventory={},
            equipment={"ring1_slot": "high_ring", "ring2_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # No candidate fits, but the player still owns the ring -> it stays.
        assert loadout["ring1_slot"] == "high_ring"

    def test_keeps_current_when_only_feasible_candidate_is_a_downgrade(self):
        """The equipped ring is level-gated out of the candidate pool, but a
        weaker (still-owned, in-level) ring IS feasible. Since that candidate
        does not improve on the equipped ring, the slot keeps its current item
        deterministically — no score-tie involved."""
        gd = GameData()
        gd._item_stats = {
            "high_ring": ItemStats(code="high_ring", level=10, type_="ring",
                                   resistance={"earth": 50}),
            "weak_ring": ItemStats(code="weak_ring", level=1, type_="ring",
                                   resistance={"earth": 5}),
        }
        gd._monster_attack = {
            "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        }
        gd._monster_resistance = {
            "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
        }
        state = make_state(
            level=1, inventory={"weak_ring": 1},
            equipment={"ring1_slot": "high_ring", "ring2_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # weak_ring is the only feasible candidate but scores worse than the
        # equipped (level-gated) high_ring, so high_ring is retained.
        assert loadout["ring1_slot"] == "high_ring"


class TestWeaponScoreRawWrapper:
    def test_raw_wscore_and_composite_relationship(self):
        """The `weapon_score_raw` wrapper (the diff-gate export) delegates to
        the extracted pure core: clamp at res > 100 zeroes the term, and the
        composite `weapon_score` is exactly ``2 * raw + nonToolBonus`` (P4b)."""
        sword = ItemStats(code="sword", level=1, type_="weapon",
                          attack={"fire": 5, "earth": 3})
        net = ItemStats(code="net", level=1, type_="weapon", subtype="tool",
                        attack={"water": 5})
        res = {"fire": 120, "earth": 50, "water": 0, "air": 0}
        # fire term clamps to 0 (res 120 > 100); earth term is 3 * 50; both
        # items have crit 0, so the crit factor is exactly 200.
        assert weapon_score_raw(sword, res) == 3 * 50 * 200
        assert weapon_score(sword, res) == 2 * (3 * 50 * 200) + 1   # non-tool bonus
        assert weapon_score_raw(net, res) == 5 * 100 * 200
        assert weapon_score(net, res) == 2 * (5 * 100 * 200)        # tool: no bonus


class TestGatherLoadout:
    def test_returns_unchanged_when_no_weapon_candidates(self):
        """No owned weapon-slot item -> gather loadout is the current
        equipment unchanged (line 82-83)."""
        gd = GameData()
        gd._item_stats = {}
        state = make_state(
            level=1, inventory={}, equipment={"weapon_slot": None},
        )
        loadout = pick_gather_loadout("mining", state, gd)
        assert loadout["weapon_slot"] is None
