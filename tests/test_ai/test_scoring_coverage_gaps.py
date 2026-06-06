"""Behavior tests closing coverage gaps in equipment/scoring.pick_loadout.

Covers armor-slot optimization and the empty-slot (no current stats) path.
"""

from artifactsmmo_cli.ai.equipment.scoring import (
    pick_gather_loadout,
    pick_loadout,
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
        swap is NOT taken (strict `>` improvement) and the current code is
        re-claimed (lines 230-231)."""
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
        # ring2 (empty current) then takes the unclaimed beta_ring.
        assert loadout["ring2_slot"] == "beta_ring"

    def test_slot_falls_back_to_none_when_last_copy_stolen(self):
        """A single physical alpha_ring shared across both ring slots: ring1
        claims it; ring2 has no feasible candidate and no remaining copy of its
        own code -> falls back to None (lines 205-206)."""
        gd = _gd_rings()
        # Exactly ONE physical alpha_ring, equipped on ring2, nothing in
        # inventory -> ownership(alpha_ring) == 1.
        state = make_state(
            level=1,
            inventory={},
            equipment={"ring1_slot": None, "ring2_slot": "alpha_ring"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # ring1 (empty) claims the single alpha_ring; ring2's alpha_ring copy is
        # gone and it has no other candidate -> None.
        assert loadout["ring1_slot"] == "alpha_ring"
        assert loadout["ring2_slot"] is None

    def test_downgrade_taken_when_current_code_stolen(self):
        """ring2's current alpha_ring is stolen by ring1, but a worse feasible
        weak_ring remains -> ring2 downgrades rather than emptying (233-237)."""
        gd = _gd_rings()
        state = make_state(
            level=1,
            # One spare weak_ring in inventory; the single alpha_ring is only
            # equipped on ring2 (ownership 1).
            inventory={"weak_ring": 1},
            equipment={"ring1_slot": None, "ring2_slot": "alpha_ring"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # ring1 swaps in the single alpha_ring (best). ring2's alpha_ring is
        # consumed; weak_ring remains feasible -> ring2 downgrades to weak_ring.
        assert loadout["ring1_slot"] == "alpha_ring"
        assert loadout["ring2_slot"] == "weak_ring"


    def test_keeps_level_gated_current_when_no_feasible_candidate(self):
        """A slot's current item is above the player's level (so it's filtered
        out of the candidate pool) yet still physically owned -> the slot keeps
        it via the no-feasible / current-available claim (line 204)."""
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
        (lines 230-231) deterministically — no score-tie involved."""
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
