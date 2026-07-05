"""`LocationCatalog.region_of` restricted-component flood (P5b movement).

Restricted tiles belong to a connected component labelled by its lexicographic
anchor; non-restricted tiles share their layer's open region.
"""

from artifactsmmo_cli.ai.location_catalog import LocationCatalog


def test_non_restricted_tile_returns_layer() -> None:
    world = LocationCatalog()
    assert world.region_of(3, 4, "overworld") == "overworld"


def test_restricted_component_labelled_by_lexicographic_anchor() -> None:
    world = LocationCatalog()
    world.restricted_tiles = {(5, 5, "overworld"), (5, 6, "overworld"), (6, 5, "overworld")}
    # Every tile of the connected component maps to the same anchor label.
    assert world.region_of(6, 5, "overworld") == "restricted:overworld:5,5"
    assert world.region_of(5, 6, "overworld") == "restricted:overworld:5,5"
    assert world.region_of(5, 5, "overworld") == "restricted:overworld:5,5"


def test_disconnected_restricted_components_get_distinct_regions() -> None:
    world = LocationCatalog()
    world.restricted_tiles = {(0, 0, "underground"), (9, 9, "underground")}
    assert world.region_of(0, 0, "underground") == "restricted:underground:0,0"
    assert world.region_of(9, 9, "underground") == "restricted:underground:9,9"


def test_flood_stays_within_layer() -> None:
    """A same-coordinate tile on another layer is NOT part of the component."""
    world = LocationCatalog()
    world.restricted_tiles = {(1, 1, "overworld"), (1, 1, "underground"),
                              (1, 2, "underground")}
    assert world.region_of(1, 1, "overworld") == "restricted:overworld:1,1"
    assert world.region_of(1, 2, "underground") == "restricted:underground:1,1"
