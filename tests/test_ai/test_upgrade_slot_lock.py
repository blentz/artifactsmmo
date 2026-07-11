"""UpgradeEquipmentGoal must lock planning to the committed target's slot.

Regression: while gathering ash_plank for a wooden_shield (shield_slot), the
goal kept every CraftAction and OptimizeLoadoutAction, and is_satisfied fired on
any equipped-slot change. The planner therefore crafted a fishing_net (weapon
tool, same ash_plank recipe) and equipped it via OptimizeLoadout, consuming the
shield's materials. Lock to the slot: only the target item, target-slot crafts,
and recipe-chain materials survive.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield"),
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon"),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),  # material, no slot
    }
    gd._crafting_recipes = {
        "wooden_shield": {"ash_plank": 6},
        "fishing_net": {"ash_plank": 6},
        "ash_plank": {"ash_wood": 1},
    }
    return gd


def _goal() -> UpgradeEquipmentGoal:
    return UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))


def test_relevant_actions_locks_to_target_slot():
    gd = _gd()
    goal = _goal()
    state = make_state(inventory={"ash_plank": 6})
    actions = [
        CraftAction(code="wooden_shield", quantity=1),
        CraftAction(code="fishing_net", quantity=1),     # weapon — different slot
        CraftAction(code="ash_plank", quantity=1),       # material — recipe chain
        EquipAction(code="wooden_shield", slot="shield_slot"),
        EquipAction(code="fishing_net", slot="weapon_slot"),
        OptimizeLoadoutAction(target_monster_code="goblin"),
        GatherAction(resource_code="ash_wood", locations=frozenset({(0, 0)})),
        UnequipAction(slot="shield_slot"),
        RestAction(),  # recovery — always kept
    ]
    kept = {repr(a) for a in goal.relevant_actions(actions, state, gd)}
    assert "Craft(wooden_shield×1)" in kept
    assert "Craft(ash_plank×1)" in kept          # material survives the recipe chain
    assert "Equip(wooden_shield->shield_slot)" in kept
    assert any("Rest" in r for r in kept)        # recovery survives
    # Locked out: other-slot equippable craft, other-slot equip, arbitrary loadout, unequip
    assert "Craft(fishing_net×1)" not in kept
    assert "Equip(fishing_net->weapon_slot)" not in kept
    assert not any("OptimizeLoadout" in r for r in kept)
    assert not any("Unequip" in r for r in kept)


def test_relevant_actions_sizes_intermediate_craft_to_batch():
    """Intermediate crafts are sized by size_intermediate_craft to the
    inventory-bounded closure demand. Regression guard for Task-6
    (intermediate-craft batching in UpgradeEquipmentGoal).

    Setup: wooden_shield <- ash_plank (intermediate) <- ash_wood; empty inventory.
    Expected ash_plank quantity:
      closure_demand("wooden_shield", 1) -> chain: ash_plank: 6
      demand = 6 - 0 held = 6
      mats_per_unit = 1 (1 ash_wood per ash_plank, raw)
      fit = (inventory_free=20 + held_recipe=0 - 3) // 1 = 17
      result = max(1, min(6, 17, 10)) = 6
    """
    gd = _gd()
    goal = _goal()  # committed to wooden_shield
    state = make_state(inventory={}, inventory_max=20)
    actions = [
        CraftAction(code="wooden_shield", quantity=1),
        CraftAction(code="ash_plank", quantity=1),
    ]
    kept = goal.relevant_actions(actions, state, gd)
    intermediate = next(
        a for a in kept if isinstance(a, CraftAction) and a.code == "ash_plank"
    )
    assert intermediate.quantity == 6


def test_relevant_actions_unfiltered_when_no_target():
    """No upgrade target (nothing to craft/equip) — don't over-filter; the
    planner gets the full action set."""
    gd = GameData()  # empty: find_upgrade_target -> None
    goal = UpgradeEquipmentGoal()  # no commitment
    actions = [GatherAction(resource_code="ash_wood", locations=frozenset({(0, 0)}))]
    assert goal.relevant_actions(actions, make_state(), gd) == actions


def test_is_satisfied_requires_committed_item_in_slot():
    goal = _goal()
    # Wrong item equipped elsewhere does NOT satisfy a shield commitment.
    s_wrong = make_state(equipment={"weapon_slot": "fishing_net", "shield_slot": None})
    assert goal.is_satisfied(s_wrong) is False
    # Target item in its slot satisfies.
    s_ok = make_state(equipment={"shield_slot": "wooden_shield"})
    assert goal.is_satisfied(s_ok) is True


def test_is_satisfied_uncommitted_uses_initial_snapshot():
    """Without a committed target, any slot differing from the initial snapshot
    still counts (preserves the inventory-ready equip path)."""
    goal = UpgradeEquipmentGoal(initial_equipment={"weapon_slot": "copper_axe"})
    changed = make_state(equipment={"weapon_slot": "iron_sword"})
    assert goal.is_satisfied(changed) is True
    unchanged = make_state(equipment={"weapon_slot": "copper_axe"})
    assert goal.is_satisfied(unchanged) is False


# --- GAP-6 (2026-07-08): monster-drop acquisition for the goal's own target --


def _drop_gd(monster_level: int = 1, monster_hp: int = 60,
             monster_attack: int = 4) -> GameData:
    """spider drops old_boots — a recipe-less pure-drop equippable (the
    l35_artifact_fill GAP-6 shape, shrunk to a unit fixture)."""
    gd = GameData()
    gd._item_stats = {
        "old_boots": ItemStats(code="old_boots", level=20, type_="boots"),
    }
    gd._crafting_recipes = {}
    gd._monster_locations = {"spider": (1, 0)}
    gd._monster_level = {"spider": monster_level}
    gd._monster_hp = {"spider": monster_hp}
    gd._monster_attack = {"spider": {"air": monster_attack}}
    gd._monster_resistance = {"spider": {}}
    gd._monster_critical_strike = {"spider": 0}
    gd._monster_initiative = {"spider": 0}
    gd._monster_drops = {"spider": [("old_boots", 300, 1, 1)]}
    return gd


def _boots_goal() -> UpgradeEquipmentGoal:
    return UpgradeEquipmentGoal(committed_target=("old_boots", "boots_slot"))


class TestTargetDropFights:
    def test_grey_winnable_dropper_emits_drop_farm_fight_and_equip(self):
        """L12 vs L1 spider (grey: xp_per_kill == 0, >= 10 levels down): the
        target's sole winnable dropper arrives as the drop_farm variant, and
        the unowned recipe-less target gets its synthesized Equip leg (the
        factory only enumerates equips for craftable/owned items)."""
        gd = _drop_gd(monster_level=1)
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
        kept = _boots_goal().relevant_actions([fight], state, gd)
        fights = [a for a in kept if isinstance(a, FightAction)]
        assert [f.monster_code for f in fights] == ["spider"]
        assert fights[0].drop_farm is True
        equips = [a for a in kept if isinstance(a, EquipAction)]
        assert [repr(e) for e in equips] == ["Equip(old_boots->boots_slot)"]

    def test_xp_positive_dropper_emits_plain_fight(self):
        """L2 vs L1 spider (xp-positive): the plain fight, no drop_farm."""
        gd = _drop_gd(monster_level=1)
        state = make_state(level=2, attack={"air": 10}, dmg=10)
        fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
        kept = _boots_goal().relevant_actions([fight], state, gd)
        fights = [a for a in kept if isinstance(a, FightAction)]
        assert [f.monster_code for f in fights] == ["spider"]
        assert fights[0].drop_farm is False

    def test_unwinnable_dropper_emits_nothing(self):
        """Never plan a losing fight: an unwinnable sole dropper contributes
        no FightAction — and without an acquisition edge, no synthesized
        Equip either (the goal honestly stays dead)."""
        gd = _drop_gd(monster_level=1, monster_hp=100000, monster_attack=200)
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
        kept = _boots_goal().relevant_actions([fight], state, gd)
        assert not any(isinstance(a, FightAction) for a in kept)
        assert not any(isinstance(a, EquipAction) for a in kept)

    def test_owned_target_skips_the_fight(self):
        """Held/banked target: the withdraw+equip edges already serve it —
        no dropper fight is emitted."""
        gd = _drop_gd(monster_level=1)
        for stock in ({"inventory": {"old_boots": 1}},
                      {"bank_items": {"old_boots": 1}}):
            state = make_state(level=12, attack={"air": 10}, dmg=10, **stock)
            fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
            kept = _boots_goal().relevant_actions([fight], state, gd)
            assert not any(isinstance(a, FightAction) for a in kept)

    def test_dropper_without_base_fight_action_emits_nothing(self):
        """The emission narrows the base action set — it never invents a
        fight the factory did not enumerate."""
        gd = _drop_gd(monster_level=1)
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        kept = _boots_goal().relevant_actions([], state, gd)
        assert kept == []

    def test_unlocated_fight_uses_zero_distance(self):
        """A dropper fight with no known locations still qualifies (distance
        0 in the expected-kills metric, mirroring GatherMaterialsGoal)."""
        gd = _drop_gd(monster_level=1)
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        fight = FightAction(monster_code="spider", locations=frozenset())
        kept = _boots_goal().relevant_actions([fight], state, gd)
        fights = [a for a in kept if isinstance(a, FightAction)]
        assert [f.monster_code for f in fights] == ["spider"]
        assert fights[0].drop_farm is True

    def test_base_equip_action_is_not_duplicated(self):
        """When the base set already carries the target's equip (owned or
        craftable enumeration), the synthesized leg is skipped."""
        gd = _drop_gd(monster_level=1)
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        actions = [
            FightAction(monster_code="spider", locations=frozenset({(1, 0)})),
            EquipAction(code="old_boots", slot="boots_slot"),
        ]
        kept = _boots_goal().relevant_actions(actions, state, gd)
        equips = [a for a in kept if isinstance(a, EquipAction)]
        assert len(equips) == 1

    def test_winner_selection_skips_unwinnable_dropper(self):
        """Two droppers, the expected-kills-better one unwinnable: the
        winnable one is chosen (is_winnable gates BEFORE the argmin)."""
        gd = _drop_gd(monster_level=1)
        gd._monster_locations["ogre"] = (2, 0)
        gd._monster_level["ogre"] = 1
        gd._monster_hp["ogre"] = 100000
        gd._monster_attack["ogre"] = {"air": 200}
        gd._monster_resistance["ogre"] = {}
        gd._monster_critical_strike["ogre"] = 0
        gd._monster_initiative["ogre"] = 0
        # ogre's rate (1) beats spider's (300) on expected kills — but it is
        # unwinnable, so spider must win.
        gd._monster_drops["ogre"] = [("old_boots", 1, 1, 1)]
        state = make_state(level=12, attack={"air": 10}, dmg=10)
        actions = [
            FightAction(monster_code="spider", locations=frozenset({(1, 0)})),
            FightAction(monster_code="ogre", locations=frozenset({(2, 0)})),
        ]
        kept = _boots_goal().relevant_actions(actions, state, gd)
        fights = [a for a in kept if isinstance(a, FightAction)]
        assert [f.monster_code for f in fights] == ["spider"]


# --- Task 6c: the GAP-6 re-emitted dropper fight (above) needs its own
# companion OptimizeLoadout, or FightAction's hard optimal-loadout gate
# (Task 3) makes it unplannable while a suboptimal weapon is equipped and
# there is no swap action in this goal's own menu to fix it — the same
# stall Task 6b fixed for GatherMaterialsGoal's monster-drop emission.


def _weapon_gd(monster_level: int = 1) -> GameData:
    """`_drop_gd` (spider drops old_boots) plus two weapons of very different
    combat value against spider's flat (no-resistance) profile, so
    `pick_loadout` unambiguously prefers `iron_sword` whenever it is owned."""
    gd = _drop_gd(monster_level=monster_level)
    gd._item_stats["wooden_stick"] = ItemStats(
        code="wooden_stick", level=1, type_="weapon", attack={"air": 1})
    gd._item_stats["iron_sword"] = ItemStats(
        code="iron_sword", level=1, type_="weapon", attack={"air": 20})
    return gd


def _suboptimal_weapon_state(**overrides):
    # level=20 (== old_boots' item level, not the 12 used by the grey-dropper
    # tests above): EquipAction requires state.level >= item.level, so a
    # full swap->fight->equip plan needs a char who can actually wear the
    # target, not just one who can win the fight.
    equipment = {**make_state().equipment, "weapon_slot": "wooden_stick"}
    kwargs = dict(level=20, attack={"air": 10}, dmg=10,
                  equipment=equipment, inventory={"iron_sword": 1})
    kwargs.update(overrides)
    return make_state(**kwargs)


class TestDropFightCompanionSwap:
    """RED (pre-fix, documented): with `wooden_stick` equipped and
    `iron_sword` owned unequipped, `UpgradeEquipment(old_boots)`'s
    GAP-6-emitted `Fight(spider)` had no companion swap in the goal's own
    action menu — `FightAction.is_applicable` was permanently False under
    the Task-3 loadout gate (`equipped_matches_loadout` fails: wooden_stick
    != iron_sword) and A* had nothing to fix it, so the goal planned empty.
    Verified against `git show HEAD~1:src/artifactsmmo_cli/ai/goals/progression.py`'s
    GAP-6 block (lines ~283-289): it appends only `fight` and the synthesized
    `Equip`, never an `OptimizeLoadoutAction`. GREEN below is the fixed
    behavior (Task 6c)."""

    def test_relevant_actions_pairs_optimize_loadout_with_dropper_fight(self):
        """Unit-level companion-emission check: `relevant_actions` for the
        suboptimal-loadout state now contains an `OptimizeLoadoutAction`
        targeting the chosen dropper (`spider`) alongside its
        `FightAction` — the exact pairing Task 6c adds to the GAP-6
        monster-drop-target emission block."""
        gd = _weapon_gd()
        state = _suboptimal_weapon_state()
        fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
        kept = _boots_goal().relevant_actions([fight], state, gd)
        reprs = [repr(a) for a in kept]
        assert "Fight(spider)" in reprs, reprs
        swaps = [a for a in kept
                 if isinstance(a, OptimizeLoadoutAction)
                 and a.target_monster_code == "spider"]
        assert swaps, reprs

    def test_plan_sequences_optimize_loadout_before_dropper_fight_when_suboptimal(self):
        """GREEN: GOAPPlanner can now satisfy the hard optimal-loadout gate
        on the re-emitted dropper fight — a non-empty plan that arms
        iron_sword before fighting spider. Pre-fix (see class docstring)
        this planned empty."""
        gd = _weapon_gd()
        state = _suboptimal_weapon_state()
        actions = [FightAction(monster_code="spider", locations=frozenset({(1, 0)}))]
        plan = GOAPPlanner().plan(state, _boots_goal(), actions, gd,
                                   history=None, budget_seconds=10.0)
        reprs = [repr(a) for a in plan]
        assert reprs, "UpgradeEquipment(old_boots) planned empty even with the companion swap"
        assert "OptimizeLoadout(spider)" in reprs, reprs
        assert "Fight(spider)" in reprs, reprs
        assert reprs.index("Fight(spider)") > reprs.index("OptimizeLoadout(spider)"), reprs

    def test_no_swap_when_loadout_already_optimal(self):
        """Self-guarding control: iron_sword already equipped, no better
        weapon owned. `relevant_actions` still admits the companion
        `OptimizeLoadoutAction` unconditionally (mirrors Task 6b's
        gathering-goal emission) — the self-guard is
        `OptimizeLoadoutAction.is_applicable` (empty `_swap_plan`), not
        admission — so the PLAN fights directly with no swap step."""
        gd = _weapon_gd()
        equipment = {**make_state().equipment, "weapon_slot": "iron_sword"}
        state = _suboptimal_weapon_state(equipment=equipment, inventory={})
        fight = FightAction(monster_code="spider", locations=frozenset({(1, 0)}))
        swap = OptimizeLoadoutAction(target_monster_code="spider", game_data=gd)
        assert swap.is_applicable(state, gd) is False
        plan = GOAPPlanner().plan(state, _boots_goal(), [fight], gd,
                                   history=None, budget_seconds=10.0)
        plan_reprs = [repr(a) for a in plan]
        assert plan_reprs, "UpgradeEquipment(old_boots) planned empty from the optimal-loadout baseline"
        assert "Fight(spider)" in plan_reprs, plan_reprs
        assert not any("OptimizeLoadout" in r for r in plan_reprs), plan_reprs
