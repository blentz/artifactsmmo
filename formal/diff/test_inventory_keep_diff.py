"""Differential test: the REAL Python keep authority
(`artifactsmmo_cli.ai.inventory_keep.keep_in_bag` / `keep_owned` / `bankable` /
`destroyable`) must agree with the proved Lean combinator
`Formal.InventoryKeep.keepInBag` / `keepOwned` / `bankable` / `destroyable`
(Oracle keys `keep_in_bag` / `keep_owned`) on EVERY row.

**What is bound, and how.** The per-reason FUNCTIONS are opaque in Lean (a
best-tool selector, a greedy aggregate heal fill, a fuel-bounded recipe-chain
walk — no scalar to mirror), exactly like `hasGrindRung` in
`Formal.ActionApplicability`. So this harness calls the REAL
`inventory_keep.reason_quantity` for every member of the REAL `IN_BAG_REASONS` /
`OWNED_REASONS` registries and feeds the resulting quantity vector to the
oracle. Nothing is reimplemented here: the Python side of every row is the
production `keep_in_bag`/`keep_owned`/`bankable`/`destroyable`, and the Lean side
is the proved combinator over the SAME contributions. A divergence therefore
means the Python combinator (max, the bag/bank arithmetic) drifted from the
proof — which is exactly where all seven hoard bugs lived.

The properties the rows exercise:
* max DOMINATES every reason and the cap IS one of them (never their SUM);
* `bankable = bag - keep_in_bag`, so surplus above the cap is ALWAYS positive —
  the property a `frozenset[str]` blanket (`keep == held`) destroyed;
* `destroyable = (bag + bank) - keep_owned` — bank copies satisfy OWNERSHIP.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import (
    IN_BAG_REASONS,
    OWNED_REASONS,
    KeepReason,
    bankable,
    destroyable,
    keep_in_bag,
    keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle
from tests.test_ai.fixtures import make_state

# Deterministic contribution order (the registries are frozensets; `max` does not
# care about order, but a stable vector keeps the oracle payload reproducible).
IN_BAG_ORDER = tuple(sorted(IN_BAG_REASONS, key=lambda r: r.value))
OWNED_ORDER = tuple(sorted(OWNED_REASONS, key=lambda r: r.value))

CODES = ("copper_axe", "copper_bar", "copper_ore", "copper_dagger",
         "cooked_chicken", "apple", "tasks_coin")


def _gd() -> GameData:
    """A REAL GameData with a two-level craft chain (`copper_axe <- 6 copper_bar
    <- 6 copper_ore`) plus a SECOND, DISJOINT root over the same leaf
    (`copper_dagger <- 8 copper_ore`), two heal codes of different strength, and
    a currency. That is enough for every registry reason to be non-zero on some
    row: WORKING_KIT (the axe is a woodcutting tool), COMBAT_WEAPON (the dagger),
    HEALING_CONSUMABLE (the greedy aggregate fill across chicken/apple),
    COMMITTED_RECIPE (the transitive chain walk over both roots), CURRENCY,
    ACTIVE_TASK, GOAL_MATERIALS, EQUIPPED, GEAR_DEMAND and RECIPE_DEMAND."""
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   subtype="dagger", attack={"attack_fire": 12}),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=50),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=20),
        "tasks_coin": ItemStats(code="tasks_coin", level=1, type_="currency"),
    }
    gd._crafting_recipes = {
        "copper_axe": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 6},
        "copper_dagger": {"copper_ore": 8},
    }
    gd._workshop_locations = {"weaponcrafting": (3, 1), "mining": (1, 5)}
    return gd


GD = _gd()


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _args(code: str, state: WorldState, ctx: SelectionContext,
          order: tuple[KeepReason, ...]) -> list[int]:
    """`[bag, bank, N, q0..q(N-1)]` — the quantities come from the REAL
    per-reason functions, which stay opaque on the Lean side."""
    bag = state.inventory.get(code, 0)
    bank = (state.bank_items or {}).get(code, 0)
    contribs = [reason_quantity(r, code, state, GD, ctx) for r in order]
    return [bag, bank, len(contribs), *contribs]


def _check(code: str, state: WorldState, ctx: SelectionContext) -> None:
    in_bag = run_oracle("keep_in_bag", [_args(code, state, ctx, IN_BAG_ORDER)])[0]
    owned = run_oracle("keep_owned", [_args(code, state, ctx, OWNED_ORDER)])[0]
    assert keep_in_bag(code, state, GD, ctx) == in_bag["keep"], (code, in_bag)
    assert bankable(code, state, GD, ctx) == in_bag["bankable"], (code, in_bag)
    assert keep_owned(code, state, GD, ctx) == owned["keep"], (code, owned)
    assert destroyable(code, state, GD, ctx) == owned["destroyable"], (code, owned)


# Named rows: one per live incident this authority exists to stop.
def test_axe_hoard_row_matches_lean():
    """The headline bug: 18 copper_axe, WORKING_KIT wants ONE. 17 bank."""
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    _check("copper_axe", state, ctx)
    assert bankable("copper_axe", state, GD, ctx) == 17


def test_currency_blanket_row_matches_lean():
    """The ONE legal blanket (KEEP_ALL): nothing destroyable."""
    state = make_state(level=10, inventory={"tasks_coin": 40})
    ctx = _ctx()
    _check("tasks_coin", state, ctx)
    assert destroyable("tasks_coin", state, GD, ctx) == 0


def test_bank_copies_satisfy_owned_row_matches_lean():
    """1 in the bag + 5 in the bank against a gear demand of 2 -> 4 destroyable
    (the Lean `destroyable_counts_bank_copies` row)."""
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 5})
    ctx = _ctx(gear_keep={"copper_axe": 2})
    _check("copper_axe", state, ctx)
    assert destroyable("copper_axe", state, GD, ctx) == 4


def test_two_live_reasons_take_the_MAX_not_the_SUM():
    """The combinator row with NOTHING to hide behind: COMMITTED_RECIPE (36 ore
    for the items-task axe) and GOAL_MATERIALS (a 50-ore step profile) are BOTH
    live, so the cap is 50 — a `sum` combinator would keep 86 and bank nothing
    of the 60 held."""
    state = make_state(level=10, inventory={"copper_ore": 60},
                       task_code="copper_axe", task_type="items",
                       task_total=1, task_progress=0)
    ctx = _ctx(step_profile={"copper_ore": 50})
    contribs = [reason_quantity(r, "copper_ore", state, GD, ctx) for r in IN_BAG_ORDER]
    assert sorted(q for q in contribs if q) == [36, 50]
    _check("copper_ore", state, ctx)
    assert keep_in_bag("copper_ore", state, GD, ctx) == 50
    assert bankable("copper_ore", state, GD, ctx) == 10


def test_healing_greedy_fill_row_matches_lean():
    """The aggregate heal target filled across two heal codes: the surplus above
    it banks (it never leaves ownership -- HEALING_CONSUMABLE is bag-only)."""
    state = make_state(level=10, inventory={"cooked_chicken": 3, "apple": 10})
    ctx = _ctx()
    _check("cooked_chicken", state, ctx)
    _check("apple", state, ctx)
    assert bankable("apple", state, GD, ctx) == 8


def test_empty_bag_row_matches_lean():
    state = make_state(level=10, inventory={})
    ctx = _ctx()
    for code in CODES:
        _check(code, state, ctx)


_QTY = st.integers(min_value=0, max_value=60)


@settings(max_examples=300, deadline=None)
@given(
    inv=st.dictionaries(st.sampled_from(CODES), _QTY, max_size=len(CODES)),
    bank=st.dictionaries(st.sampled_from(CODES), _QTY, max_size=len(CODES)),
    crafting_target=st.sampled_from((None, "copper_axe", "copper_bar", "copper_dagger")),
    task=st.sampled_from((
        (None, None, 0, 0),
        ("items", "copper_axe", 5, 0),
        ("items", "copper_axe", 5, 3),
        ("items", "copper_bar", 10, 4),
        ("items", "cooked_chicken", 3, 0),
        ("monsters", "chicken", 5, 5),
    )),
    gear_keep=st.dictionaries(st.sampled_from(CODES), st.integers(min_value=0, max_value=9),
                              max_size=3),
    step_profile=st.dictionaries(st.sampled_from(CODES), st.integers(min_value=0, max_value=40),
                                 max_size=3),
    equipped=st.sampled_from((None, "copper_dagger", "copper_axe")),
    code=st.sampled_from(CODES),
)
def test_keep_caps_match_lean(inv, bank, crafting_target, task, gear_keep,
                              step_profile, equipped, code):
    task_type, task_code, task_total, task_progress = task
    state = make_state(
        level=10, skills={"weaponcrafting": 2, "woodcutting": 2, "mining": 2},
        inventory=inv, inventory_max=200, inventory_slots_max=60,
        bank_items=bank or None,
        crafting_target=crafting_target,
        task_type=task_type, task_code=task_code,
        task_total=task_total, task_progress=task_progress,
        equipment={"weapon_slot": equipped} if equipped else {},
    )
    ctx = _ctx(gear_keep=gear_keep, step_profile=step_profile)
    _check(code, state, ctx)


@settings(max_examples=300, deadline=None)
@given(
    bag=st.integers(min_value=0, max_value=99),
    bank=st.integers(min_value=0, max_value=99),
    contribs=st.lists(st.integers(min_value=0, max_value=99), min_size=1, max_size=7),
)
def test_combinator_properties_hold_on_the_lean_side(bag, bank, contribs):
    """The COMBINATOR contract, straight against the oracle: the cap dominates
    every reason, the cap IS one of the reasons (never their sum), and the
    surplus above it is disposable. Reason vectors here are arbitrary, so the
    properties are pinned beyond the reason functions the fixtures can realize."""
    args = [bag, bank, len(contribs), *contribs]
    in_bag = run_oracle("keep_in_bag", [args])[0]
    owned = run_oracle("keep_owned", [args])[0]
    keep = in_bag["keep"]
    assert keep == owned["keep"] == max(contribs)      # same combinator, both caps
    assert all(keep >= q for q in contribs)            # dominates each reason
    assert keep in contribs                            # IS a reason -- never a sum
    assert in_bag["bankable"] == max(0, bag - keep)
    assert owned["destroyable"] == max(0, bag + bank - keep)
    if bag > keep:                                     # surplus_is_disposable
        assert in_bag["bankable"] > 0
    if in_bag["bankable"] == 0:                        # blanket_requires_keep_ge_held
        assert keep >= bag
