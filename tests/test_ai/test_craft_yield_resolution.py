"""Tests for resolve_craft_yields (Task 3)."""


def test_resolve_craft_yields_learned_overrides_prior():
    from artifactsmmo_cli.ai.craft_yield_resolution import resolve_craft_yields

    class _GD:
        crafting_recipes = {"potion": {"herb": 1}, "bar": {"ore": 2}}

        def craft_yield(self, code):
            return {"potion": 2, "bar": 1}.get(code, 1)

    class _Hist:
        def observed_craft_yield(self, code):
            return (3, 99) if code == "potion" else None  # learned potion=3

    assert resolve_craft_yields(_GD(), _Hist()) == {"potion": 3, "bar": 1}
    assert resolve_craft_yields(_GD(), None) == {"potion": 2, "bar": 1}  # priors only


def test_resolve_craft_yields_all_priors_no_history():
    """With no history, returns the prior for every recipe."""
    from artifactsmmo_cli.ai.craft_yield_resolution import resolve_craft_yields

    class _GD:
        crafting_recipes = {"sword": {"iron": 3}, "shield": {"iron": 5}}

        def craft_yield(self, code):
            return 1  # all Y=1 (today's live state)

    assert resolve_craft_yields(_GD(), None) == {"sword": 1, "shield": 1}


def test_resolve_craft_yields_empty_recipes():
    """Empty recipes map → empty result regardless of history."""
    from artifactsmmo_cli.ai.craft_yield_resolution import resolve_craft_yields

    class _GD:
        crafting_recipes = {}

        def craft_yield(self, code):
            return 1

    class _Hist:
        def observed_craft_yield(self, code):
            return (5, 10)

    assert resolve_craft_yields(_GD(), _Hist()) == {}
    assert resolve_craft_yields(_GD(), None) == {}


def test_resolve_craft_yields_none_observed_keeps_prior():
    """When observed_craft_yield returns None, the prior is kept."""
    from artifactsmmo_cli.ai.craft_yield_resolution import resolve_craft_yields

    class _GD:
        crafting_recipes = {"potion": {"herb": 1}}

        def craft_yield(self, code):
            return 2

    class _Hist:
        def observed_craft_yield(self, code):
            return None  # nothing observed

    assert resolve_craft_yields(_GD(), _Hist()) == {"potion": 2}
