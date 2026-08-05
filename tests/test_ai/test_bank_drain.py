"""Bank-drain: over-cap BANK junk detection + DrainBankJunkGoal (idle bank drain).

The drain is the ONE disposal path whose copies live in the BANK, so it is bounded by
the keep authority's OWNERSHIP cap ALONE (`destroyable`), never by `keep_in_bag`: a
bag copy is not a bank copy, and `bankable` for a code held 0-in-bag is 0 — a `min`
with it would freeze the drain of exactly the hoard the drain exists to clear. See
`ai/bank_drain`.

The worth-hoarding cap survives as a POLICY — the analogue of SELL's ratio gate —
but it is now `ai/keep_valuation.worth_keeping`, the SAME number
`ai/disposal_route`'s DEPOSIT arm reads (useful cap OR the eventual demand of a
REACHABLE consumer). It is what keeps a far-skill-gated-but-future-useful material
out of the withdraw -> discard pipeline, and its being shared is what makes this
module's "no withdraw/redeposit cycle" claim true.
"""

from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.drain_bank_junk import DrainBankJunkGoal
from artifactsmmo_cli.ai.keep_valuation import MAX_ATTAINABLE_SKILL_LEVEL
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # Far-skill-gated byproduct with no recipe use -> useful cap 0 (drain all).
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        # Equippable craftable -> useful cap = EQUIPPABLE_KEEP (1) when not dominated.
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        # A second helmet, so a profile can SPEAK FOR the helmet slot while naming a
        # different code — the difference between gear a profile SUPERSEDED (keep 0)
        # and a slot the profile never covered at all (keep 1).
        "iron_helmet": ItemStats(code="iron_helmet", level=1, type_="helmet",
                                 hp_bonus=40, crafting_skill="gearcrafting",
                                 crafting_level=1),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        # The woodcutting tool at the heart of the hoard bug — and of the DESTRUCTION
        # hole Task 7b closed (WORKING_KIT / COMBAT_WEAPON feed OWNED_REASONS).
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_boots": {"copper_bar": 8}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    gd._bank_location = (4, 0)
    return gd


# --------------------------------------------------------------------------- #
# THE HOLE: a tool whose every copy sits in the BANK (item-protection-authority
# epic, Task 9). `keep_in_bag` has nothing to protect there — the OWNERSHIP cap is
# the only thing between the character's only axe and the withdraw->discard pipeline.
# --------------------------------------------------------------------------- #

def test_last_tool_survives_when_every_copy_is_in_the_bank():
    """0 in the bag, 18 in the bank, profiles active and the axe in no profile.

    The old code-set protection (`guards._gear_protected` = the `gear_keep` KEYS,
    else `target_gear | target_tools`) protected NOTHING here: the axe is not a
    `gear_keep` key, so the whole 18 drained — straight into DiscardOverstock's
    mouth. `keep_owned` is 1 (WORKING_KIT / COMBAT_WEAPON, ownership-scoped since
    Task 7b), so at most 17 may ever leave. NEVER 18."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       bank_items={"copper_axe": 18})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert bank_drain_excess(state, gd, ctx) == {"copper_axe": 17}


def test_the_last_owned_tool_is_never_drained_at_all():
    """The floor case: ONE copy owned, and it is in the bank. `destroyable` is 0."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       bank_items={"copper_axe": 1})
    assert bank_drain_excess(state, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}


def test_a_bag_copy_does_not_widen_the_bank_licence():
    """1 in the bag + 17 in the bank: `keep_owned` 1 is satisfied by the BAG copy, so
    all 17 bank copies are drainable — the ownership cap counts copies wherever they
    are. (`bankable` here is 0; bounding the drain by it would freeze the hoard.)"""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 17},
                       inventory_max=200)
    assert bank_drain_excess(state, gd,
                             _ctx(gear_keep={"copper_helmet": 1})) == {"copper_axe": 17}


# --------------------------------------------------------------------------- #
# The worth-hoarding POLICY (unchanged).
# --------------------------------------------------------------------------- #

def test_excess_drains_truly_useless_bank_junk():
    """sap (no recipe consumer in this catalog, useful cap 0) held only in the
    bank -> genuine junk, drain all of it."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 50})
    assert bank_drain_excess(state, gd, _ctx()) == {"sap": 50}


def test_excess_keeps_eventual_recipe_demand_for_far_gated_material():
    """A far-skill-gated material that a recipe WILL consume must NOT be pulled out
    for deletion: the bank keeps its full eventual recipe demand
    (`max_recipe_demand`), draining only the surplus beyond it. Protects a level-10+
    drop (gold_ore, jasper_crystal) banked while the crafting skill is still too low —
    and stops the withdraw<->deposit churn `disposal_route` would otherwise cause
    (a recipe-demanded material routes back to DEPOSIT)."""
    gd = GameData()
    gd._item_stats = {
        "rare_ore": ItemStats(code="rare_ore", level=1, type_="resource"),
        "rare_bar": ItemStats(code="rare_bar", level=20, type_="resource",
                              crafting_skill="mining", crafting_level=20),
    }
    gd._crafting_recipes = {"rare_bar": {"rare_ore": 8}}
    state = make_state(level=5, skills={"mining": 5}, bank_items={"rare_ore": 50})
    # cap = max(useful_cap=0, max_recipe_demand=8) = 8 -> drain 50 - 8 = 42.
    assert bank_drain_excess(state, gd, _ctx()) == {"rare_ore": 42}
    # At/under the eventual demand, nothing drains.
    within = make_state(level=5, skills={"mining": 5}, bank_items={"rare_ore": 8})
    assert bank_drain_excess(within, gd, _ctx()) == {}


def test_far_level_material_is_kept_at_its_reachable_demand_not_a_distance_proxy():
    """VERDICT CHANGE 2026-08-05 (unified valuation, part 1). This case used to
    assert `level_distance_keep_ceiling`: char level 5 vs item level 20 -> |Δ|=15
    -> keep 5 -> drain 95, and 20 only once the character came into band.

    The ceiling is a PROXY: it answers "how far from my level is this" when the
    question is "will anything ever consume this, and how many". The keep is now
    the eventual demand of a REACHABLE consumer (`keep_valuation`), so the answer
    is 80 at BOTH character levels — level distance is not evidence about
    consumption. Draining 75 more of a material a reachable recipe needs 80 of is
    the over-shedding the ceiling caused."""
    gd = GameData()
    gd._item_stats = {
        "future_ore": ItemStats(code="future_ore", level=20, type_="resource"),
        "future_bar": ItemStats(code="future_bar", level=20, type_="resource",
                                crafting_skill="mining", crafting_level=20),
    }
    gd._crafting_recipes = {"future_bar": {"future_ore": 80}}
    state = make_state(level=5, bank_items={"future_ore": 100})
    assert bank_drain_excess(state, gd, _ctx()) == {"future_ore": 20}
    in_band = make_state(level=18, bank_items={"future_ore": 100})
    assert bank_drain_excess(in_band, gd, _ctx()) == {"future_ore": 20}


def test_material_whose_only_consumer_is_unreachable_fully_drains():
    """The other half of the same swap: a recipe gated ABOVE the API's
    progression cap can never be crafted by anyone, so the material it consumes
    has NO reachable consumer and the whole bank stock is junk. The distance
    proxy could not express this — it would still have hoarded 5."""
    gd = GameData()
    gd._item_stats = {
        "never_ore": ItemStats(code="never_ore", level=20, type_="resource"),
        "never_bar": ItemStats(code="never_bar", level=20, type_="resource",
                               crafting_skill="mining",
                               crafting_level=MAX_ATTAINABLE_SKILL_LEVEL + 1),
    }
    gd._crafting_recipes = {"never_bar": {"never_ore": 80}}
    state = make_state(level=18, bank_items={"never_ore": 100})
    assert bank_drain_excess(state, gd, _ctx()) == {"never_ore": 100}


def test_excess_never_drains_currency_or_consumable_from_bank():
    """Currency (KEEP_ALL on the OWNED ladder) and (non-hp) consumables are never
    pulled out of the bank as junk."""
    gd = GameData()
    gd._item_stats = {
        "event_ticket": ItemStats(code="event_ticket", level=1, type_="currency"),
        "recall_potion": ItemStats(code="recall_potion", level=1, type_="consumable"),
    }
    gd._crafting_recipes = {}
    state = make_state(level=5, bank_items={"event_ticket": 30, "recall_potion": 30})
    assert bank_drain_excess(state, gd, _ctx()) == {}


def test_excess_keeps_useful_cap_in_bank():
    """An equippable (useful cap 1) is allowed to keep 1 in the bank; only the
    overflow above the cap is excess."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_helmet": 5})
    assert bank_drain_excess(state, gd, _ctx()) == {"copper_helmet": 4}


def test_the_policy_cap_bounds_the_BANK_stock_not_total_holdings():
    """VERDICT CHANGE 2026-08-05 (unified valuation, part 1). This case used to
    assert an inventory-CREDITED cap: 1 in the bag against a keep of 1 left the
    bank allowance at 0, so all 5 banked copies drained.

    That credit is incompatible with the anti-livelock invariant. With it, a code
    held 10-in-bag / 3-in-bank against a keep of 5 is simultaneously drainable
    (bank 3 > headroom 0) AND deposit-eligible (bank 3 < keep 5) — the exact
    disagreement `keep_valuation` exists to kill. `worth_keeping` therefore caps
    the BANK's own stock: 5 banked, keep 1 -> 4 drain, bag copy or no bag copy.
    The BAG has its own space cap (`overstocked_items` / `keep_in_bag`) and
    DESTRUCTION is still bounded by `destroyable` over bag+bank."""
    gd = _gd()
    state = make_state(level=5, inventory={"copper_helmet": 1},
                       bank_items={"copper_helmet": 5})
    assert bank_drain_excess(state, gd, _ctx()) == {"copper_helmet": 4}


def test_excess_empty_when_bank_unknown_or_within_cap():
    gd = _gd()
    assert bank_drain_excess(make_state(level=5), gd, _ctx()) == {}
    within = make_state(level=5, bank_items={"copper_helmet": 1})
    assert bank_drain_excess(within, gd, _ctx()) == {}


def test_zero_quantity_bank_entry_is_skipped():
    """A spent bank stack (`{code: 0}`) is not a holding — it is never drainable, and
    it must not reach the authority (a 0-qty stack has nothing to license)."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 0})
    assert bank_drain_excess(state, gd, _ctx()) == {}


# --------------------------------------------------------------------------- #
# GEAR protection is a QUANTITY (the active-profile demand), never a code-SET.
# --------------------------------------------------------------------------- #

def test_excess_keeps_the_active_profile_gear_demand():
    """The gear the profile demands is kept at its DEMAND. This replaces the old
    `protected_codes` frozenset (whose profile-less arm was `target_gear |
    target_tools`, i.e. keep EVERY copy of every BiS code)."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_boots": 5})
    assert bank_drain_excess(state, gd, _ctx(gear_keep={"copper_boots": 5})) == {}


def test_objective_target_gear_no_longer_blankets_the_bank():
    """`target_gear` / `target_tools` are ACQUISITION targets — they name what to
    PURSUE, not what to hoard. Naming copper_boots there keeps NOT ONE extra copy:
    the authority's EQUIPPABLE_KEEP=1 (via RECIPE_DEMAND, profile-less mode) is the
    whole protection, so 4 of the 5 banked spares drain."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_boots": 5})
    assert bank_drain_excess(
        state, gd, _ctx(target_gear=frozenset({"copper_boots"}))) == {"copper_boots": 4}


def test_bank_drain_superseded_gear_drains_fully_with_gear_keep():
    """Gear the active profile SUPERSEDED (it names the slot, and picks someone else)
    has demand 0 and no ownership demand at all -> drains completely from the bank.
    Without gear_keep (legacy), EQUIPPABLE_KEEP=1 (via RECIPE_DEMAND) protects one
    spare."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_helmet": 5})
    assert bank_drain_excess(state, gd, _ctx()) == {"copper_helmet": 4}
    assert bank_drain_excess(
        state, gd, _ctx(gear_keep={"iron_helmet": 1}),  # the helmet slot, not this code
    ) == {"copper_helmet": 5}


def test_bank_drain_keeps_one_of_gear_in_a_slot_the_profile_never_names():
    """The other side of the same coin (whole-branch review, finding 4): a profile is
    `pick_loadout` under a Combat or Gather purpose and NEITHER fills every slot, so
    a boots-only profile is SILENT about helmets — it never had the chance to want
    one. Silence is not a licence to drain the character's only helmet into the
    discard ladder's mouth; the slot-silence floor keeps 1 and drains the rest."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_helmet": 5})
    assert bank_drain_excess(
        state, gd, _ctx(gear_keep={"copper_boots": 1})) == {"copper_helmet": 4}


def test_bank_drain_profiled_gear_keeps_demand():
    """With gear_keep, bank equippable gear is kept UP TO the profile demand (not
    just the blanket EQUIPPABLE_KEEP=1 spare)."""
    gd = _gd()
    state = make_state(level=5, bank_items={"copper_helmet": 5})
    assert bank_drain_excess(
        state, gd, _ctx(gear_keep={"copper_helmet": 2})) == {"copper_helmet": 3}
    assert bank_drain_excess(
        state, gd, _ctx(gear_keep={"copper_helmet": 5})) == {}


def test_excess_never_drains_the_active_task_item_below_its_demand():
    """ACTIVE_TASK is an OWNED reason: the copies the task still owes are never
    withdrawn into the discard ladder."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 50},
                       task_code="sap", task_type="items",
                       task_progress=0, task_total=20)
    assert bank_drain_excess(state, gd, _ctx()) == {"sap": 30}


# --------------------------------------------------------------------------- #
# Goal + ladder wiring.
# --------------------------------------------------------------------------- #

def test_goal_relevant_actions_withdraws_excess_sized_to_free_space():
    """DrainBankJunkGoal emits a WithdrawItemAction pulling the licensed excess
    into the bag, sized to fit free slots."""
    gd = _gd()
    state = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    a = actions[0]
    assert isinstance(a, WithdrawItemAction)
    assert a.code == "sap"
    assert a.bank_location == (4, 0)
    assert 1 <= a.quantity <= 50
    assert a.is_applicable(state, gd)


def test_goal_relevant_actions_caps_quantity_at_free_slots():
    """Free slots smaller than the excess clamp the withdraw quantity."""
    gd = _gd()
    # inventory_max 10, 6 slots used -> 4 free; excess sap is 50 -> withdraw 4.
    state = make_state(level=5, inventory={"filler": 6},
                       bank_items={"sap": 50}, inventory_max=10)
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    assert actions[0].quantity == 4


def test_goal_no_actions_when_bank_location_unknown():
    gd = _gd()
    gd._bank_location = None
    state = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    assert goal.relevant_actions([], state, gd) == []


def test_fires_on_idle_bank_junk_not_under_pressure_or_protected():
    gd = _gd()
    idle = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, idle, gd, None, _ctx()) is True
    # Under space pressure (>=0.85 full): no room to withdraw -> does NOT fire.
    pressured = make_state(level=5, inventory={"filler": 180},
                           bank_items={"sap": 50}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, pressured, gd, None, _ctx()) is False
    # The bank stock IS the active profile's gear demand -> the authority keeps
    # every copy -> does NOT fire.
    profiled = make_state(level=5, bank_items={"copper_boots": 5}, inventory_max=200)
    assert _fires(MeansKind.DRAIN_BANK_JUNK, profiled, gd, None,
                  _ctx(gear_keep={"copper_boots": 5})) is False


def test_map_means_returns_drain_goal():
    g = map_means(MeansKind.DRAIN_BANK_JUNK, _gd(), _ctx(), make_state())
    assert isinstance(g, DrainBankJunkGoal)


def test_goal_satisfied_and_metadata():
    gd = _gd()
    empty = make_state(level=5, bank_items={"copper_helmet": 1})
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    assert goal.is_satisfied(empty) is True
    assert goal.value(empty, gd) == 0.0
    surplus = make_state(level=5, bank_items={"sap": 50}, inventory_max=200)
    assert goal.is_satisfied(surplus) is False
    assert goal.value(surplus, gd) == 15.0
    assert goal.desired_state(surplus, gd) == {"bank_junk_drained": True}
    assert repr(goal) == "DrainBankJunk"
