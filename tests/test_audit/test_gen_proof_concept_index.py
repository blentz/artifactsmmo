from artifactsmmo_cli.audit.proof_tags import IndexRow, render_index_markdown


def test_render_index_lists_modules_concepts_properties():
    rows = [IndexRow("PlannerDepthBound", ["planner", "core"], ["safety", "reachability"])]
    md = render_index_markdown(rows)
    assert "| Module | Concepts | Properties |" in md
    assert "PlannerDepthBound" in md
    assert "planner, core" in md
    assert "safety, reachability" in md
