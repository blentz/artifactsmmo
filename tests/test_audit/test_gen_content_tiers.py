from artifactsmmo_cli.audit.content_tiers import derive_content_tiers, render_markdown


def test_render_markdown_has_header_and_one_row_per_tier():
    tiers = derive_content_tiers({"copper_dagger": 1}, {"chicken": 1}, {"copper_rocks": 1}, band=10)
    md = render_markdown(tiers)
    assert "| Tier | Levels | Items | Monsters | Resources |" in md
    assert "T1 (levels 1-10)" in md
    assert "copper_dagger" in md and "chicken" in md and "copper_rocks" in md
