"""Differential test: the live Python loadout-profile cores
(`loadout_profiles_core.gear_demand` / `bank_space_cost`) must agree EXACTLY
with the proved Lean `Formal.LoadoutProfiles.gearDemand` / `bankSpaceCost`.

These cores implement bank-aware gear dedup: one loadout is worn at a time, so
the bank only ever holds, per code, the MAX over active loadouts of how many
slots that loadout fills with it (NOT the sum). `bank_space_cost` counts the
distinct active-loadout codes that are not currently equipped.

We feed random *active loadout sets* (lists of slot->code maps drawn from a small
code pool so codes deliberately COLLIDE — both across loadouts, exercising the
per-code MAX, and within a loadout, exercising the rings-count-2 case) plus a
random equipped set, to BOTH the live cores and the Lean oracle, and assert
equality.

NO `unique=True`: duplicate codes are the realistic dedup case and are precisely
what the MAX (across loadouts) and the count (within a loadout) are there to
handle. The oracle receives each loadout's `.values()` (the code list) since the
Lean model is over code lists, dropping the slot keys the Python map carries.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.loadout_profiles_core import bank_space_cost, gear_demand
from formal.diff.oracle_client import run_oracle_structured

# A small code pool so random draws collide (shared gear across loadouts; the
# same code in two slots of one loadout -> count 2). Slot names are arbitrary
# labels; only the resulting code MULTISET per loadout matters to the cores.
_CODES = ["copper_dagger", "copper_ring", "iron_helmet", "leather_boots", "steel_sword"]
_SLOTS = ["weapon", "ring1", "ring2", "helmet", "boots"]


def _check(loadouts: list[dict[str, str]], equipped: list[str]) -> None:
    # Live cores.
    py_demand = gear_demand(loadouts)
    py_cost = bank_space_cost(loadouts, set(equipped))

    # Oracle args: each loadout reduced to its code list (the map's values).
    code_lists = [list(ld.values()) for ld in loadouts]

    # gearDemand is per-code; query EVERY code appearing anywhere (so codes with
    # demand 0 are never silently skipped) AND a guaranteed-absent code (the
    # foldl-0 / dict.get default).
    query_codes = sorted({c for ld in code_lists for c in ld}) + ["__absent__"]
    demand_reqs = [[code_lists, c] for c in query_codes]
    lean_demand = run_oracle_structured("gear_demand", demand_reqs)
    for c, res in zip(query_codes, lean_demand, strict=True):
        assert py_demand.get(c, 0) == res["demand"], (c, py_demand.get(c, 0), res["demand"])

    lean_cost = run_oracle_structured("bank_space_cost", [[code_lists, equipped]])
    assert py_cost == lean_cost[0]["cost"], (py_cost, lean_cost[0]["cost"])


@st.composite
def _loadout(draw):
    """A slot->code map; each slot independently empty or a pooled code, so codes
    repeat across slots (rings) and the map may be empty."""
    out: dict[str, str] = {}
    for slot in _SLOTS:
        pick = draw(st.sampled_from([None, *_CODES]))
        if pick is not None:
            out[slot] = pick
    return out


@settings(max_examples=300, deadline=None)
@given(
    loadouts=st.lists(_loadout(), min_size=0, max_size=4),
    equipped=st.lists(st.sampled_from(_CODES), min_size=0, max_size=5),
)
def test_python_matches_lean(loadouts, equipped):
    _check(loadouts, equipped)


def test_shared_gear_held_once():
    """Two loadouts both wearing copper_dagger -> demand 1 (held once)."""
    loadouts = [
        {"weapon": "copper_dagger", "ring1": "copper_ring"},
        {"weapon": "copper_dagger", "helmet": "iron_helmet"},
    ]
    assert gear_demand(loadouts)["copper_dagger"] == 1
    _check(loadouts, [])


def test_dual_ring_demands_two():
    """One loadout wearing copper_ring in both ring slots -> demand 2."""
    loadouts = [{"ring1": "copper_ring", "ring2": "copper_ring"}]
    assert gear_demand(loadouts)["copper_ring"] == 2
    _check(loadouts, [])


def test_demand_is_max_not_sum():
    """Demand across loadouts is the MAX (2), never the SUM (3)."""
    loadouts = [
        {"ring1": "copper_ring", "ring2": "copper_ring"},
        {"ring1": "copper_ring"},
    ]
    assert gear_demand(loadouts)["copper_ring"] == 2
    _check(loadouts, [])


def test_bank_cost_subtracts_equipped():
    """distinct {copper_dagger, iron_helmet, leather_boots} minus equipped
    copper_dagger -> cost 2."""
    loadouts = [
        {"weapon": "copper_dagger", "helmet": "iron_helmet"},
        {"weapon": "copper_dagger", "boots": "leather_boots"},
    ]
    assert bank_space_cost(loadouts, {"copper_dagger"}) == 2
    _check(loadouts, ["copper_dagger"])


def test_empty_loadouts():
    """No active loadouts -> empty demand, zero bank cost."""
    assert gear_demand([]) == {}
    assert bank_space_cost([], set()) == 0
    _check([], [])
