"""The one requirement model — Wave 2 of the unification epic.

`docs/superpowers/specs/2026-07-19-requirement-model-unification-epic.md` §4.

Six walks answer "what does obtaining X require" and disagree (D1-D4). This is
the single model they migrate onto in Waves 3-8. **Nothing consumes it yet** —
Wave 2 is additive by design, so the Wave 0 parity oracle stays green trivially
and every later wave produces a binary signal.

What it fixes BY CONSTRUCTION
-----------------------------
* **D1 namespace split** — item codes throughout. `recipe_closure` returns
  RESOURCE codes (`copper_rocks`) while every other walk speaks ITEMS
  (`copper_ore`); `requirement_closure` here speaks only items.
* **D2 drop-leaf blindness** — `leaves` is a set of `SourceKind`, so a
  monster-drop leaf is representable. The two-set return it replaces could not
  say "obtainable, but only by killing something", which is why three separate
  workarounds grew for the one hole.
* **D3 four skill-gate derivations** — `skill_gates` is the single one.

Built ON TOP of the mechanically-extracted core, never in place of it (§4.5):
`_closure_demand` does the quantity math here, so the Lean in
`Extracted/RecipeClosure.lean` still bites and `check_extraction.sh` still holds.

Three points where this deviates from the spec, each deliberate
--------------------------------------------------------------
1. **`gather_skill` is keyed by ITEM, not by resource.** §4.1's headline says
   "item namespace throughout" but its field comment says `resource -> ...` —
   the spec contradicts itself. Item-keying is what actually expresses the
   livelock cause it cites: the P3b hole is "obtaining `iron_ore` requires
   mining 10", and `iron_ore` is the item. Where several resources drop one
   item, the EASIEST (lowest required level) wins — that is the binding
   constraint on whether the item is gatherable at all, and it is a semantic
   key rather than a repr tiebreak.
2. **`leaves` carries only STATE-FREE kinds** — CRAFT, GATHER, DROP, BUY.
   WITHDRAW and RECYCLE depend on what is banked or licensed right now, and the
   graph is state-free (§4.1). They belong to the axis-2 truncation pass, which
   §4.2 makes "a separate truncation pass over the graph, not a property baked
   into the walk". Baking them in here would re-create axis 2 inside the model.
3. **`need_set` is NOT built in this wave.** §4.3 lists it as a projection of
   `DemandSet`, but `NeedSet` carries `buy_only` and `char_xp`, which are not
   functions of demand alone — they need `WorldState`. It migrates in Wave 3
   with `objective_needs`, where those semantics are in scope. Half-building it
   here would guess at them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.source_kind import SourceKind


class _HasRequirementData(Protocol):
    """Structural subset of GameData the graph build reads.

    A Protocol rather than a GameData import, for the same reason
    `recipe_closure._HasRecipes` is one: GameData imports the memo, which
    imports this module, so importing GameData here would close a cycle. Every
    concrete caller passes a GameData, which satisfies this structurally.
    """

    @property
    def crafting_recipes(self) -> Mapping[str, dict[str, int]]: ...

    @property
    def craft_yields(self) -> Mapping[str, int]: ...

    @property
    def resource_drops(self) -> Mapping[str, str]: ...

    @property
    def resource_drops_full(self) -> Mapping[str, list[tuple[str, int, int, int]]]: ...

    @property
    def all_item_stats(self) -> Mapping[str, ItemStats]: ...

    def crafting_recipe(self, code: str) -> dict[str, int] | None: ...

    def item_stats(self, code: str) -> ItemStats | None: ...

    def gatherable_drop_items(self) -> frozenset[str]: ...

    def monster_drop_items(self) -> frozenset[str]: ...

    def purchasable_items(self) -> frozenset[str]: ...

    def resource_skill_level(self, code: str) -> tuple[str, int] | None: ...

    def monsters_dropping(self, item: str) -> list[tuple[str, int, int, int]]: ...

    def npcs_selling_item(self, item_code: str) -> list[tuple[str, int]]: ...


@dataclass(frozen=True)
class RequirementGraph:
    """State-free, item-namespace, quantity-carrying, drop-aware requirement model.

    One cycle policy: the per-path revisit guard of the extracted core.
    """

    #: item -> direct ingredient -> qty (ONE ply; axis 1 lives in the projection).
    #: Inner is `dict` not `Mapping` so it feeds the extracted `_closure_demand`
    #: (whose signature is pinned) without a defensive per-call copy.
    edges: Mapping[str, dict[str, int]]
    #: item -> the state-free ways it can be obtained (see deviation 2)
    leaves: Mapping[str, frozenset[SourceKind]]
    #: item -> (craft skill, required level)
    craft_skill: Mapping[str, tuple[str, int]]
    #: ITEM -> (gather skill, required level) — see deviation 1.
    #: Populated but UNCONSUMED this epic (scope A, §3): a model that cannot
    #: express a known livelock cause is not a unification.
    gather_skill: Mapping[str, tuple[str, int]]
    #: item -> craft output quantity per run (the ⌈demand/Y⌉ batch divisor).
    #: The bundle carries 31 items with Y>1, so a demand walk that ignores this
    #: over-orders their materials at any multiplier >1 — `demand_set` reads it
    #: by default so the projection matches the live `closure_demand` exactly.
    yields: Mapping[str, int]

    def sources(self, item: str) -> frozenset[SourceKind]:
        """The state-free obtain routes for `item`; empty when unobtainable."""
        return self.leaves.get(item, frozenset())

    def is_obtainable(self, item: str) -> bool:
        """True when SOME state-free route exists. An item with no route is a
        genuine dead end — the condition `recipe_closure`'s two-set return could
        not distinguish from "raw resource" (D2)."""
        return bool(self.leaves.get(item))


def _gather_skill_by_item(game_data: _HasRequirementData) -> dict[str, tuple[str, int]]:
    """Resolve resource-keyed gather gates into ITEM-keyed ones.

    An item dropped by several resources takes the EASIEST gate: if any resource
    dropping it is reachable at a lower skill level, that is the level at which
    the item becomes gatherable. Taking the max would over-report the gate and
    make an obtainable item look walled.
    """
    out: dict[str, tuple[str, int]] = {}

    def record(item: str, resource: str) -> None:
        gate = game_data.resource_skill_level(resource)
        if gate is None:
            return
        prior = out.get(item)
        if prior is None or gate[1] < prior[1]:
            out[item] = gate

    for resource, item in game_data.resource_drops.items():
        record(item, resource)
    # Secondary drops gather the same way and are gated identically; omitting
    # them would mis-report a secondary-only item as having no gather gate.
    for resource, table in game_data.resource_drops_full.items():
        for row in table:
            record(row[0], resource)
    return out


def _leaf_kinds(game_data: _HasRequirementData, item: str,
                gatherable: frozenset[str]) -> frozenset[SourceKind]:
    """Which state-free routes can produce `item`."""
    kinds: set[SourceKind] = set()
    if game_data.crafting_recipe(item) is not None:
        kinds.add(SourceKind.CRAFT)
    if item in gatherable:
        kinds.add(SourceKind.GATHER)
    if game_data.monsters_dropping(item):
        kinds.add(SourceKind.DROP)
    if game_data.npcs_selling_item(item):
        kinds.add(SourceKind.BUY)
    return frozenset(kinds)


def build_requirement_graph(game_data: _HasRequirementData) -> RequirementGraph:
    """Build the whole-table requirement graph. Pure in `game_data`.

    Every item the model can say anything about gets a `leaves` entry — recipe
    keys, every ingredient of every recipe, every gatherable drop item, and
    every item with stats. Ingredients matter especially: a material that is
    itself neither craftable nor a recipe key still needs a verdict, and it is
    exactly the drop-only material D2 lost.
    """
    recipes = game_data.crafting_recipes
    gatherable = game_data.gatherable_drop_items()

    known: set[str] = set(recipes)
    for ingredients in recipes.values():
        known.update(ingredients)
    known.update(gatherable)
    # Every route that can be an item's ONLY one must contribute its items, or
    # that item never enters the model and reports UNOBTAINABLE despite being
    # reachable — D2 left half-fixed. Recipe keys and ingredients cover CRAFT,
    # `gatherable` covers GATHER; these two cover DROP and BUY.
    known.update(game_data.monster_drop_items())
    known.update(game_data.purchasable_items())
    known.update(game_data.all_item_stats)

    craft_skill: dict[str, tuple[str, int]] = {}
    for code in known:
        stats = game_data.item_stats(code)
        if stats is not None and stats.crafting_skill:
            craft_skill[code] = (stats.crafting_skill, stats.crafting_level)

    return RequirementGraph(
        edges={item: dict(ingredients) for item, ingredients in recipes.items()},
        leaves={code: _leaf_kinds(game_data, code, gatherable) for code in known},
        craft_skill=craft_skill,
        gather_skill=_gather_skill_by_item(game_data),
        yields=dict(game_data.craft_yields),
    )


@dataclass(frozen=True)
class DemandSet:
    """Quantified transitive demand for a set of roots. Item namespace.

    Replaces the `closure_demand` out-parameter protocol: 11 call sites thread a
    caller-owned dict, and two of them accumulate MULTIPLE calls into one shared
    dict, which is why Wave 5 is the risky one. A value type makes the merge
    explicit instead of incidental.
    """

    quantities: Mapping[str, int]
    roots: frozenset[str]

    @property
    def items(self) -> frozenset[str]:
        """Every item in the closure, roots included."""
        return frozenset(self.quantities)

    def quantity(self, item: str) -> int:
        return self.quantities.get(item, 0)

    def merge(self, other: DemandSet) -> DemandSet:
        """Combine two demand sets, taking the MAX per item.

        Max, not sum, matches `_closure_demand`'s own cumulative-across-paths
        semantics: a material needed 3x via one root and 5x via another is
        needed 5x, not 8x, because the same units serve both.
        """
        merged = dict(self.quantities)
        for item, qty in other.quantities.items():
            if qty > merged.get(item, 0):
                merged[item] = qty
        return DemandSet(quantities=merged, roots=self.roots | other.roots)
