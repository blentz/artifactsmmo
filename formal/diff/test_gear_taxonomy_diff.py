"""Python gear-taxonomy core ≡ Lean oracle over random catalogs.

Feeds random `(type, combat_bearing, consumable)` catalogs to BOTH the live
Python `combat_gear_types` core and the kernel-proved `Formal.GearTaxonomy.
combatGearTypes` (via the oracle), asserting they classify the same set.

Duplicate-type rows are intentionally allowed (NO `unique=True`): the realistic
case is many items per type, which exercises the dedup AND the any-consumable
carve (one consumable item removes the whole type even when another item of that
type is combat-bearing).
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.gear_taxonomy_core import combat_gear_types
from formal.diff.oracle_client import run_oracle_structured

_types = st.sampled_from(["weapon", "ring", "amulet", "rune", "artifact",
                          "utility", "bag", "helmet"])
_rows = st.lists(st.tuples(_types, st.booleans(), st.booleans()), max_size=30)


def _call_oracle(catalog: list[tuple[str, bool, bool]]) -> list[str]:
    rows_json = [[t, cb, cons] for t, cb, cons in catalog]
    return run_oracle_structured("combat_gear", [[rows_json]])[0]


@settings(max_examples=400, deadline=None)
@given(_rows)
def test_combat_gear_matches_oracle(catalog: list[tuple[str, bool, bool]]) -> None:
    """Python core ≡ Lean model on random (possibly duplicate-type) catalogs."""
    py = sorted(combat_gear_types(catalog))
    oracle = sorted(_call_oracle(catalog))
    assert py == oracle, f"mismatch on {catalog!r}: py={py} oracle={oracle}"


def test_consumable_carves_duplicate_type() -> None:
    """Non-vacuity: a type with one combat item AND one consumable item is
    carved on BOTH sides (the realistic duplicate-type case)."""
    catalog = [("utility", True, False), ("utility", False, True)]
    assert combat_gear_types(catalog) == frozenset()
    assert _call_oracle(catalog) == []


def test_combat_and_noncombat_concrete() -> None:
    """Concrete spot-check binding both sides on a mixed catalog."""
    catalog = [("weapon", True, False), ("ring", True, False),
               ("utility", True, True), ("bag", False, False)]
    assert combat_gear_types(catalog) == frozenset({"weapon", "ring"})
    assert sorted(_call_oracle(catalog)) == ["ring", "weapon"]
