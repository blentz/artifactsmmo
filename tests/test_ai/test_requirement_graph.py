"""Tests for the unified requirement model — Wave 2 of the unification epic.

The model is ADDITIVE this wave: nothing in production consumes it. These tests
are therefore the only thing standing between it and rot, so they pin the three
defects it is supposed to fix BY CONSTRUCTION (D1/D2/D3) and the two legitimate
axes it must PRESERVE — not merely that the functions return something.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.requirement_graph import (
    DemandSet,
    RequirementGraph,
    build_requirement_graph,
)
from artifactsmmo_cli.ai.requirement_graph_memo import RequirementGraphMemo
from artifactsmmo_cli.ai.requirement_projections import (
    demand_set,
    requirement_closure,
    requirement_craftables,
    requirement_edges,
    requirement_gather_skills,
    skill_gates,
)
from artifactsmmo_cli.ai.source_kind import SourceKind


def _gd(recipes=None, drops=None, drops_full=None, resource_skill=None,
        item_stats=None, monster_drops=None, npc_stock=None, yields=None):
    gd = GameData()
    gd._crafting_recipes = recipes or {}
    if yields is not None:
        gd._craft_yields = yields
    gd._resource_drops = drops or {}
    if drops_full is not None:
        gd._resource_drops_full = drops_full
    if resource_skill is not None:
        gd._resource_skill = resource_skill
    if item_stats is not None:
        gd._item_stats = item_stats
    if monster_drops is not None:
        gd._monster_drops = monster_drops
    if npc_stock is not None:
        gd._npc_stock = npc_stock
    return gd


def _dagger_gd():
    """copper_dagger <- copper_bar x6 <- copper_ore x10, ore from copper_rocks."""
    return _gd(
        recipes={"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}},
        drops={"copper_rocks": "copper_ore"},
        resource_skill={"copper_rocks": ("mining", 1)},
        item_stats={
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       crafting_skill="weaponcrafting", crafting_level=1),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="mining", crafting_level=1),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        },
    )


# --- D1: the namespace split is GONE ---------------------------------------

def test_d1_closure_speaks_items_not_resource_nodes():
    """`recipe_closure` returns `copper_rocks` (a RESOURCE node); every other
    walk speaks items. The unified closure speaks items only, so its answer
    composes with the other walks without a translation step."""
    g = build_requirement_graph(_dagger_gd())
    closure = requirement_closure(g, ["copper_dagger"])
    assert closure == {"copper_dagger", "copper_bar", "copper_ore"}
    assert "copper_rocks" not in closure


# --- D2: drop leaves are representable --------------------------------------

def test_d2_monster_drop_leaf_is_representable():
    """The two-set return could not say "obtainable, but only by killing
    something" — `feather` was neither a resource code nor craftable, so it fell
    out of the model entirely and three separate workarounds grew. Here it is a
    first-class leaf."""
    gd = _gd(recipes={"quiver": {"feather": 4}},
             monster_drops={"chicken": [("feather", 1, 1, 2)]})
    g = build_requirement_graph(gd)
    assert g.sources("feather") == frozenset({SourceKind.DROP})
    assert g.is_obtainable("feather")
    assert "feather" in requirement_closure(g, ["quiver"])


def test_d2_unobtainable_item_is_distinguishable_from_a_leaf():
    """The distinction the two-set return could not make: a dead end has NO
    routes, which is not the same as being a raw gathered resource."""
    gd = _gd(recipes={"mystery_blade": {"unobtainium": 1}},
             drops={"copper_rocks": "copper_ore"})
    g = build_requirement_graph(gd)
    assert g.sources("unobtainium") == frozenset()
    assert not g.is_obtainable("unobtainium")
    assert g.is_obtainable("copper_ore")


def test_all_four_state_free_kinds_are_detected():
    gd = _gd(recipes={"craftable": {"x": 1}},
             drops={"rocks": "gatherable"},
             monster_drops={"mob": [("droppable", 1, 1, 1)]},
             npc_stock={"vendor": {"buyable": 10}})
    g = build_requirement_graph(gd)
    assert g.sources("craftable") == frozenset({SourceKind.CRAFT})
    assert g.sources("gatherable") == frozenset({SourceKind.GATHER})
    assert g.sources("droppable") == frozenset({SourceKind.DROP})
    assert g.sources("buyable") == frozenset({SourceKind.BUY})


def test_leaves_exclude_state_dependent_kinds():
    """Deviation 2: WITHDRAW and RECYCLE depend on what is banked or licensed
    RIGHT NOW. Baking them into a state-free graph would re-create axis 2 inside
    the model, which §4.2 explicitly makes a separate pass."""
    g = build_requirement_graph(_dagger_gd())
    every_kind = set().union(*g.leaves.values())
    assert SourceKind.WITHDRAW not in every_kind
    assert SourceKind.RECYCLE not in every_kind


# --- D3: ONE skill-gate derivation ------------------------------------------

def test_d3_skill_gates_reports_unmet_gates_over_the_closure():
    g = build_requirement_graph(_dagger_gd())
    assert skill_gates(g, ["copper_dagger"], {}) == {"weaponcrafting": 1, "mining": 1}


def test_d3_met_gates_are_omitted():
    g = build_requirement_graph(_dagger_gd())
    assert skill_gates(g, ["copper_dagger"],
                       {"weaponcrafting": 5, "mining": 5}) == {}


def test_d3_takes_the_highest_requirement_per_skill():
    """Two items gate the same skill at different levels: the binding one is the
    higher. A name-set (one of the four shapes D3 replaces) could not say this."""
    gd = _gd(
        recipes={"top": {"mid": 1}, "mid": {"ore": 1}},
        item_stats={
            "top": ItemStats(code="top", level=1, type_="weapon",
                             crafting_skill="weaponcrafting", crafting_level=20),
            "mid": ItemStats(code="mid", level=1, type_="resource",
                             crafting_skill="weaponcrafting", crafting_level=5),
        },
    )
    g = build_requirement_graph(gd)
    assert skill_gates(g, ["top"], {}) == {"weaponcrafting": 20}


def test_d4_skill_gates_is_order_independent():
    """D4 is a live determinism bug in `_item_skill_gap`: it threads a shared
    mutable `seen`, so on a diamond its answer depends on dict iteration order.
    A max over a set cannot have that property — assert it directly by feeding
    the same diamond with the roots in both orders."""
    gd = _gd(
        recipes={"ring": {"left": 1, "right": 1},
                 "left": {"shared": 1}, "right": {"shared": 1},
                 "shared": {"ore": 2}},
        item_stats={
            "shared": ItemStats(code="shared", level=1, type_="resource",
                                crafting_skill="jewelrycrafting", crafting_level=15),
        },
    )
    g = build_requirement_graph(gd)
    assert skill_gates(g, ["left", "right"], {}) == \
        skill_gates(g, ["right", "left"], {}) == {"jewelrycrafting": 15}


# --- the two LEGITIMATE axes must SURVIVE ------------------------------------

def test_axis1_edges_are_one_ply_not_a_closure():
    """`tiers/strategy.py` does its own traversal on top; collapsing this into a
    closure breaks `act_step`."""
    g = build_requirement_graph(_dagger_gd())
    assert requirement_edges(g, "copper_dagger") == {"copper_bar": 6}
    assert len(requirement_closure(g, ["copper_dagger"])) == 3


def test_axis2_truncation_is_a_caller_predicate():
    """State-awareness is a pass OVER the graph, not a property baked into it —
    so the same graph answers both the truncated and untruncated question."""
    g = build_requirement_graph(_dagger_gd())
    held = {"copper_bar"}.__contains__
    assert requirement_edges(g, "copper_bar") == {"copper_ore": 10}
    assert requirement_edges(g, "copper_bar", truncate_at=held) == {}
    assert requirement_closure(g, ["copper_dagger"], truncate_at=held) == \
        {"copper_dagger", "copper_bar"}


def test_closure_dedupes_overlapping_roots():
    """Two roots whose closures overlap: the shared subtree is queued twice and
    must be walked once. This is the multi-root shape the synergy design needs —
    it asks how much two objectives' requirements coincide, which is only
    meaningful if the shared part is not double-walked."""
    g = build_requirement_graph(_dagger_gd())
    both = requirement_closure(g, ["copper_bar", "copper_dagger"])
    assert both == {"copper_dagger", "copper_bar", "copper_ore"}


def test_closure_terminates_on_a_cycle():
    gd = _gd(recipes={"a": {"b": 1}, "b": {"a": 1}})
    g = build_requirement_graph(gd)
    assert requirement_closure(g, ["a"]) == {"a", "b"}


# --- Wave 4 projections: the recipe_closure two-set replacement --------------

def test_requirement_craftables_is_the_recipe_closure_second_return():
    """`recipe_closure`'s `craftable_mats` = closure items with a recipe. The
    projection that replaced its five callers must give exactly that set."""
    g = build_requirement_graph(_dagger_gd())
    # closure = {copper_dagger, copper_bar, copper_ore}; only the first two craft.
    assert requirement_craftables(g, ["copper_dagger"]) == {"copper_dagger", "copper_bar"}


def test_requirement_craftables_excludes_raw_leaves():
    g = build_requirement_graph(_dagger_gd())
    assert "copper_ore" not in requirement_craftables(g, ["copper_dagger"])


def test_requirement_gather_skills_reads_item_keyed_gates():
    """Replaces the old resource-node loop. copper_ore is gatherable at mining 1,
    so mining is a needed gather skill for the dagger closure."""
    g = build_requirement_graph(_dagger_gd())
    assert requirement_gather_skills(g, ["copper_dagger"]) == {"mining"}


def test_requirement_gather_skills_empty_when_nothing_gatherable():
    gd = _gd(recipes={"a": {"b": 1}})  # b has no gather source
    g = build_requirement_graph(gd)
    assert requirement_gather_skills(g, ["a"]) == frozenset()


# --- quantities --------------------------------------------------------------

def test_demand_set_carries_multiplied_quantities():
    g = build_requirement_graph(_dagger_gd())
    d = demand_set(g, ["copper_dagger"])
    assert d.quantity("copper_bar") == 6
    assert d.quantity("copper_ore") == 60
    assert d.items == {"copper_dagger", "copper_bar", "copper_ore"}
    assert d.roots == frozenset({"copper_dagger"})


def test_demand_set_honours_per_root_multipliers():
    g = build_requirement_graph(_dagger_gd())
    d = demand_set(g, ["copper_dagger"], quantities={"copper_dagger": 2})
    assert d.quantity("copper_ore") == 120


def test_demand_set_is_yield_aware_with_no_partial_batches():
    """Delegated to the extracted core's ceil-batch math: demand is
    ⌈wanted / Y⌉ BATCHES, each consuming a full recipe's worth.

    Y=2 therefore does NOT halve the cost of wanting one potion — you still
    craft one whole batch and pay 4 herb for it. The saving appears at the
    second potion, which comes free out of the same batch. Asserting the naive
    "Y halves demand" would under-order materials for every odd quantity.
    """
    gd = _gd(recipes={"potion": {"herb": 4}})
    g = build_requirement_graph(gd)
    y2 = {"potion": 2}

    def herb(want, yields=None):
        return demand_set(g, ["potion"], quantities={"potion": want},
                          yields=yields).quantity("herb")

    assert herb(1) == 4 and herb(2) == 8          # Y=1: linear
    assert herb(1, y2) == 4                        # one batch, no partial
    assert herb(2, y2) == 4                        # second potion is free
    assert herb(3, y2) == 8                        # ⌈3/2⌉ = 2 batches


def test_demand_set_unknown_quantity_is_zero():
    g = build_requirement_graph(_dagger_gd())
    assert demand_set(g, ["copper_dagger"]).quantity("nothing_here") == 0


def test_graph_carries_craft_yields():
    """Wave 5: the graph now carries yields so `demand_set` is yield-correct by
    default. Without this field the projection ignored the bundle's 31 Y>1 items
    and over-ordered their materials at any multiplier >1."""
    gd = _gd(recipes={"potion": {"herb": 4}}, yields={"potion": 2})
    g = build_requirement_graph(gd)
    assert g.yields["potion"] == 2


def test_demand_set_default_is_yield_aware():
    """The load-bearing Wave 5 fix. `demand_set(g, roots, {root: mult})` with NO
    explicit yields must still apply the graph's yields — this is what makes it
    match the live `closure_demand`, whose default reads `craft_yields`. A prior
    version defaulted to an empty map and silently ignored Y>1 at mult>1."""
    gd = _gd(recipes={"potion": {"herb": 4}}, yields={"potion": 2})
    g = build_requirement_graph(gd)
    # want 3 potions, Y=2 -> ceil(3/2)=2 batches -> 2*4 = 8 herb, NOT 3*4=12.
    assert demand_set(g, ["potion"], {"potion": 3}).quantity("herb") == 8
    # an explicit yields arg still overrides the graph default.
    assert demand_set(g, ["potion"], {"potion": 3},
                      yields={"potion": 1}).quantity("herb") == 12


def test_demand_merge_takes_max_not_sum():
    """The same units serve both roots — `_closure_demand` is cumulative-across-
    paths, so summing would double-count and inflate every shared material."""
    a = DemandSet(quantities={"ore": 3, "wood": 1}, roots=frozenset({"x"}))
    b = DemandSet(quantities={"ore": 5}, roots=frozenset({"y"}))
    merged = a.merge(b)
    assert merged.quantities == {"ore": 5, "wood": 1}
    assert merged.roots == frozenset({"x", "y"})


# --- gather_skill: item-keyed (deviation 1) ---------------------------------

def test_gather_skill_is_keyed_by_item_and_expresses_the_p3b_hole():
    """The livelock the spec cites is "obtaining iron_ore requires mining 10",
    and `iron_ore` is the ITEM. Resource-keying could not state it in the same
    namespace as everything else."""
    gd = _gd(drops={"iron_rocks": "iron_ore"},
             resource_skill={"iron_rocks": ("mining", 10)})
    g = build_requirement_graph(gd)
    assert g.gather_skill["iron_ore"] == ("mining", 10)


def test_gather_skill_takes_the_easiest_of_several_resources():
    """Taking the max would over-report the gate and make an item reachable at
    mining 1 look walled behind mining 20."""
    gd = _gd(drops={"hard_rocks": "ore", "easy_rocks": "ore"},
             resource_skill={"hard_rocks": ("mining", 20),
                             "easy_rocks": ("mining", 1)})
    g = build_requirement_graph(gd)
    assert g.gather_skill["ore"] == ("mining", 1)


def test_gather_skill_covers_secondary_drops():
    """A secondary-only item would otherwise be mis-reported as having no gate."""
    gd = _gd(drops={"bass_spot": "bass"},
             drops_full={"bass_spot": [("bass", 1, 1, 1), ("small_pearls", 300, 1, 1)]},
             resource_skill={"bass_spot": ("fishing", 30)})
    g = build_requirement_graph(gd)
    assert g.gather_skill["small_pearls"] == ("fishing", 30)


def test_gather_skill_skips_resources_with_no_known_gate():
    gd = _gd(drops={"mystery_rocks": "ore"}, resource_skill={})
    g = build_requirement_graph(gd)
    assert "ore" not in g.gather_skill


# --- the memo ----------------------------------------------------------------

def test_memo_caches_by_identity():
    memo = RequirementGraphMemo(_dagger_gd())
    assert memo.graph() is memo.graph()


def test_memo_rebuilds_when_inputs_grow():
    """The improvement on the `RecipeCostMemo` precedent. That memo invalidates
    only on REBINDING `_crafting_recipes`, but `_build_items` populates it by
    IN-PLACE assignment — so a load mutates the source without tripping the
    hook. A size fingerprint catches exactly that."""
    gd = _dagger_gd()
    memo = RequirementGraphMemo(gd)
    first = memo.graph()
    gd.crafting_recipes["iron_dagger"] = {"iron_bar": 6}   # in place, no setter
    second = memo.graph()
    assert second is not first
    assert "iron_dagger" in second.edges


def test_memo_clear_forces_a_rebuild():
    memo = RequirementGraphMemo(_dagger_gd())
    first = memo.graph()
    memo.clear()
    assert memo.graph() is not first


def test_gamedata_accessor_is_lazy_and_stable():
    gd = _dagger_gd()
    assert gd.requirement_graph is gd.requirement_graph
    assert isinstance(gd.requirement_graph.graph(), RequirementGraph)


def test_rebinding_recipes_invalidates_through_gamedata():
    """The precedent's own hook still works — this wave adds to it, not replaces."""
    gd = _dagger_gd()
    first = gd.requirement_graph.graph()
    gd._crafting_recipes = {"steel_dagger": {"steel_bar": 6}}
    assert gd.requirement_graph.graph() is not first


def test_source_kind_extraction_left_exactly_one_enum():
    """`obtain_sources` re-exports the extracted enum. Two enums would compare
    unequal and silently break every `kind is SourceKind.X` check."""
    from artifactsmmo_cli.ai.obtain_sources import SourceKind as Reexported
    assert Reexported is SourceKind
