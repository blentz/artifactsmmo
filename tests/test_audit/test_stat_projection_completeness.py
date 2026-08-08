"""Stat-projection completeness census.

The census asserts that `J` can SEE every stat a worn item grants, or has said
in writing why it cannot. See
`src/artifactsmmo_cli/audit/stat_projection_completeness.py`.
"""

from artifactsmmo_cli.ai.equipment.projection import ProjectedStats
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.audit.stat_projection_completeness import (
    CONSUMABLE_FIELDS,
    METADATA_FIELDS,
    UNPRICED,
    WORN_EFFECT_TO_PROJECTED,
    StatProjectionCensus,
    format_census,
    run_census,
)


def test_every_item_stats_field_is_classified() -> None:
    """No `ItemStats` field may match zero buckets.

    THE POINT OF THE CENSUS. Five stats (wisdom, prospecting, inventory_space,
    haste, lifesteal) went unpriced for the whole life of the objective because
    nothing anywhere asserted the projection was total over the stats an item
    can grant. A field that matches no bucket is the shape of that bug, and it
    fails here rather than silently reading as zero in a ranking."""
    census = run_census()
    assert census.unclassified == frozenset(), format_census(census)


def test_no_stale_exclusions() -> None:
    """An `UNPRICED` entry that IS now projected fails.

    This is what forces the exclusion list to shrink: increment 3 adds `wisdom`
    to `ProjectedStats` and this test goes red until the `UNPRICED["wisdom"]`
    entry is deleted in the same commit. Without it the list becomes a parking
    lot, and a declared blind spot that nobody is obliged to revisit is just an
    undeclared one with extra words."""
    census = run_census()
    assert census.stale_exclusions == frozenset(), format_census(census)


def test_the_buckets_partition_item_stats() -> None:
    """The three buckets are disjoint AND cover `ItemStats` exactly.

    Overlap would let a field be 'classified' as both metadata and a worn
    effect, so removing it from one list would leave the census green while the
    stat went unprojected — the exhaustiveness this census sells would be
    fiction."""
    all_fields = frozenset(f.name for f in ItemStats.__dataclass_fields__.values())
    worn = frozenset(WORN_EFFECT_TO_PROJECTED) | frozenset(UNPRICED)
    assert not METADATA_FIELDS & CONSUMABLE_FIELDS
    assert not METADATA_FIELDS & worn
    assert not CONSUMABLE_FIELDS & worn
    assert METADATA_FIELDS | CONSUMABLE_FIELDS | worn == all_fields


def test_projected_names_all_exist_on_projected_stats() -> None:
    """Every value in `WORN_EFFECT_TO_PROJECTED` names a real `ProjectedStats`
    field. A typo would claim a stat is priced when it is not — the census's
    own version of the defect it exists to catch."""
    projected = frozenset(f.name for f in ProjectedStats.__dataclass_fields__.values())
    assert frozenset(WORN_EFFECT_TO_PROJECTED.values()) <= projected


def test_every_unpriced_entry_carries_a_justification() -> None:
    """A bare exclusion is not a decision. Each entry states why the stat is
    unpriced and, unless the exclusion is permanent, which increment removes
    it."""
    for name, reason in UNPRICED.items():
        assert len(reason) > 80, f"{name}: justification too thin to be a decision"


def test_haste_is_excluded_for_the_unit_reason() -> None:
    """Pins the ONE permanent exclusion to its actual argument.

    `haste` is not a scheduling oversight — it is denominated in seconds against
    an objective denominated in actions. If someone later 'fixes' it by adding
    haste to `ProjectedStats`, `test_no_stale_exclusions` fires and this
    docstring is what they should read before deleting the entry."""
    assert "PERMANENT" in UNPRICED["haste"]
    assert "SECONDS" in UNPRICED["haste"]
    assert "ACTIONS" in UNPRICED["haste"]


def test_the_census_currently_prices_seven_of_twelve_worn_stats() -> None:
    """Characterisation of the defect at `5a2d1b8d`, so the increments that fix
    it have a baseline that moves visibly. Expected to CHANGE — and the change
    is the deliverable, not a regression."""
    census = run_census()
    assert len(census.projected) == 7
    assert len(census.unpriced) == 5
    assert census.ok


def test_format_reports_both_failure_classes() -> None:
    """`format_census` must render an unclassified field and a stale exclusion,
    since those strings are the whole diagnostic a failing gate shows."""
    bad = StatProjectionCensus(
        projected=frozenset({"attack"}),
        unpriced=frozenset({"wisdom"}),
        unclassified=frozenset({"newly_added_stat"}),
        stale_exclusions=frozenset({"wisdom"}),
    )
    out = format_census(bad)
    assert not bad.ok
    assert "UNCLASSIFIED" in out and "newly_added_stat" in out
    assert "STALE" in out and "classify it" in out
    assert "verdict: FAIL" in out


def test_format_of_a_passing_census_is_quiet() -> None:
    """A green census prints the two rosters and nothing alarming."""
    out = format_census(run_census())
    assert "verdict: OK" in out
    assert "UNCLASSIFIED" not in out
    assert "STALE" not in out
    assert "wisdom" in out


def test_census_is_derived_from_the_live_dataclasses() -> None:
    """Adding a field to `ItemStats` must make the census notice.

    Guards against the roster being hand-copied at some later refactor: if
    `run_census` ever stopped reading `dataclasses.fields`, a field added to
    `ItemStats` would go unnoticed and the census would be describing a type
    that no longer exists. The vacuity of that claim was checked by temporarily
    adding a field to `ItemStats` — six tests in this file went red."""
    live = frozenset(f.name for f in ItemStats.__dataclass_fields__.values())
    census = run_census()
    covered = (METADATA_FIELDS | CONSUMABLE_FIELDS
               | frozenset(census.projected) | frozenset(census.unpriced))
    assert covered == live
