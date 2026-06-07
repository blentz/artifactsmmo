"""derive_content_tiers clusters level-gated game content into capability-unlock tiers."""
from artifactsmmo_cli.audit.content_tiers import ContentTier, derive_content_tiers


def test_groups_items_monsters_resources_by_level_band():
    # Inputs are plain (code -> level) maps, as extracted from GameData.
    items = {"copper_dagger": 1, "iron_dagger": 10, "steel_dagger": 20}
    monsters = {"chicken": 1, "wolf": 10, "ogre": 20}
    resources = {"copper_rocks": 1, "iron_rocks": 10}
    tiers = derive_content_tiers(items, monsters, resources, band=10)
    # band=10 ⇒ tiers [1..10], [11..20], [21..30]
    assert [t.min_level for t in tiers] == [1, 11, 21]
    assert tiers[0].items == ["copper_dagger"]
    assert tiers[0].monsters == ["chicken"]
    assert tiers[0].resources == ["copper_rocks"]
    assert tiers[1].items == ["iron_dagger"]
    assert tiers[2].items == ["steel_dagger"]


def test_tier_is_sorted_and_named_by_band():
    tiers = derive_content_tiers({"a": 5}, {}, {}, band=10)
    assert len(tiers) == 1
    assert tiers[0].name == "T1 (levels 1-10)"
    assert tiers[0].min_level == 1 and tiers[0].max_level == 10


def test_empty_inputs_yield_no_tiers():
    assert derive_content_tiers({}, {}, {}, band=10) == []
