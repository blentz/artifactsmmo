"""Requirement-walk parity census — Wave 0 of the unification epic.

`docs/superpowers/specs/2026-07-19-requirement-model-unification-epic.md`.

SIX walks answer "what does obtaining X require", and NO test anywhere asserts
that any two of them agree. This census is the missing oracle. It is
CHARACTERIZATION-FIRST: it records what each walk answers TODAY, disagreements
included, so that every later migration wave is binary — a diff is either an
intentional D1-D4 fix, or a regression.

Read the expectations below as PINS, not endorsements. Several of them encode
defects on purpose, each labelled with the defect it embodies.

The walks
---------
* `recipe_closure(gd, roots)`            -> (needed_resources, craftable_mats)
* `closure_demand(root, n, gd, out, ...)` -> mutates `out`: item -> qty
* `prerequisites(node, state, gd)`        -> direct prereq MetaGoals (ONE ply)
* `objective_needs(root, state, gd)`      -> NeedSet (unquantified)
* `_item_skill_gap(code, state, gd, seen)`-> worst unmet crafting-skill gap
* `obtain_sources(item, state, gd, ctx)`  -> [Source] in priority order

Two disagreements are LEGITIMATE and must survive unification as explicit
parameters (spec 4.2); the census asserts they are still TRUE, so a wave that
flattens them fails here:

* AXIS 1 edges-vs-closure — `prerequisites` is deliberately ONE PLY.
* AXIS 2 state truncation — `prerequisites` treats an item with any ready
  non-craft source as a LEAF and never descends its recipe, while
  `recipe_closure` descends regardless of what is held.

Four are DRIFT, and the census pins them so the fix is visible when it lands:

* D1 NAMESPACE SPLIT — `recipe_closure` returns RESOURCE-NODE codes
  (`copper_rocks`) for raw leaves; every other walk speaks ITEM codes
  (`copper_ore`).
* D2 DROP-LEAF BLINDNESS — the two-set return cannot represent a monster-drop
  leaf, so a drop-only material appears in the demand map and in NEITHER
  `recipe_closure` set.
* D3 SKILL-GATE DERIVATIONS DISAGREE — `objective_needs` yields skill NAMES,
  `_item_skill_gap` yields the single WORST `(skill, required, current)`.
* D4 ORDER DEPENDENCE — `_item_skill_gap` threads a shared mutable `seen`, so
  on a diamond its answer depends on `dict` iteration order. The census pins
  the CURRENT answer; Wave 7 is where it becomes order-independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.recipe_closure import closure_demand, recipe_closure
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_feasibility import _item_skill_gap
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState
from artifactsmmo_cli.audit.craft_census import craftable_recipes

#: Character level for every cell. High enough that no level gate suppresses a
#: source, so cells differ by the WALK under test and not by band.
CENSUS_LEVEL = 40
#: Every skill maxed for the same reason: a skill gate must not silently remove
#: a CRAFT source and make two walks agree for the wrong reason. `_item_skill_gap`
#: is measured against a SEPARATE low-skill state (see `_skill_probe_state`),
#: because at max skill every gap is trivially None and D3 would be invisible.
CENSUS_SKILL_LEVEL = 40
#: Skill level for the D3/D4 probe: low enough that real recipes are gated.
PROBE_SKILL_LEVEL = 1


@dataclass(frozen=True)
class WalkRow:
    """What every walk answered for one target. Flat and render-ready."""

    code: str
    #: `recipe_closure` -> needed_resources (RESOURCE namespace — see D1)
    closure_resources: tuple[str, ...]
    #: `recipe_closure` -> craftable_mats (item namespace)
    closure_craftables: tuple[str, ...]
    #: `closure_demand` keys (item namespace, quantified)
    demand_items: tuple[str, ...]
    #: items in the demand map that `recipe_closure` cannot represent — D2
    drop_blind_items: tuple[str, ...]
    #: `prerequisites` direct children (ONE ply — axis 1)
    prereq_reprs: tuple[str, ...]
    #: True when `prerequisites` leafed instead of descending — axis 2
    prereq_leafed: bool
    #: `objective_needs` skill NAMES (D3 output shape A)
    needs_skills: tuple[str, ...]
    #: `_item_skill_gap` worst gap, rendered (D3 output shape B)
    worst_skill_gap: str | None
    #: `obtain_sources` kinds, priority order
    source_kinds: tuple[str, ...]


def census_state(game_data: GameData, skill_level: int) -> WorldState:
    """Offline state for the walks that take one.

    Empty bag and bank on purpose: a held copy would make `prerequisites` leaf
    via WITHDRAW everywhere and axis 2 would stop being observable.
    """
    return scenario_state(
        ScenarioCharacter(
            name="requirement_parity_audit",
            level=CENSUS_LEVEL,
            gold=0,
            skills={skill: skill_level for skill in SKILL_NAMES},
            inventory={},
            bank={},
            derive_combat_stats=True,
        ),
        game_data,
    )


def _render_gap(gap: object) -> str | None:
    if gap is None:
        return None
    return f"{gap.skill}:{gap.current_level}->{gap.required_level}"  # type: ignore[attr-defined]


def run_target(code: str, game_data: GameData, state: WorldState,
               probe_state: WorldState) -> WalkRow:
    """Drive all six walks over one target and flatten the answers."""
    resources, craftables = recipe_closure(game_data, [code])

    demand: dict[str, int] = {}
    closure_demand(code, 1, game_data, demand, frozenset())

    # D2: a demand item that is neither a craftable nor the drop of a needed
    # resource is invisible to `recipe_closure`'s two-set return.
    representable = set(craftables) | {
        game_data.resource_drop_item(res) for res in resources
    }
    drop_blind = tuple(sorted(i for i in demand if i not in representable and i != code))

    prereqs = prerequisites(ObtainItem(code=code, quantity=1), state, game_data)
    recipe = game_data.crafting_recipe(code)
    # Axis 2: a craftable that returns NO prereqs was truncated at a ready
    # non-craft source rather than descended.
    leafed = bool(recipe) and not prereqs

    needs = objective_needs(ObtainItem(code=code, quantity=1), state, game_data)
    gap = _item_skill_gap(code, probe_state, game_data, set())
    sources = obtain_sources(code, state, game_data, NO_PROFILE_CONTEXT)

    return WalkRow(
        code=code,
        closure_resources=tuple(sorted(resources)),
        closure_craftables=tuple(sorted(craftables)),
        demand_items=tuple(sorted(demand)),
        drop_blind_items=drop_blind,
        prereq_reprs=tuple(sorted(repr(p) for p in prereqs)),
        prereq_leafed=leafed,
        needs_skills=tuple(sorted(needs.skill_xp)),
        worst_skill_gap=_render_gap(gap),
        source_kinds=tuple(s.kind.value for s in sources),
    )


def run_census(game_data: GameData) -> list[WalkRow]:
    """Every craftable recipe, in the craft census's deterministic order."""
    state = census_state(game_data, CENSUS_SKILL_LEVEL)
    probe_state = census_state(game_data, PROBE_SKILL_LEVEL)
    return [
        run_target(code, game_data, state, probe_state)
        for code in craftable_recipes(game_data)
    ]


# --------------------------------------------------------------------------
# Characterizations. Each names the defect or axis it pins.
# --------------------------------------------------------------------------

def d1_namespace_split(rows: list[WalkRow]) -> int:
    """D1: rows whose `recipe_closure` resources are NOT item codes.

    `copper_rocks` is a resource node; `copper_ore` is the item. Every other
    walk speaks items. Wave 3+ collapses this; until then it must stay > 0 or
    the census has stopped watching.
    """
    return sum(1 for r in rows if r.closure_resources and
               not set(r.closure_resources) & set(r.demand_items))


def d2_drop_blind(rows: list[WalkRow]) -> int:
    """D2: rows with a demand item `recipe_closure` cannot represent."""
    return sum(1 for r in rows if r.drop_blind_items)


def d3_skill_shape_disagreement(rows: list[WalkRow]) -> int:
    """D3: rows where the two skill derivations disagree in SHAPE.

    `objective_needs` reports skill names with no level; `_item_skill_gap`
    reports one worst `(skill, current, required)`. A row where one is empty
    and the other is not is the disagreement made concrete.
    """
    return sum(1 for r in rows
               if bool(r.needs_skills) != bool(r.worst_skill_gap))


def axis1_one_ply(rows: list[WalkRow], game_data: GameData) -> bool:
    """AXIS 1: `prerequisites` never returns more children than the recipe has
    direct ingredients — it is one ply, not a closure."""
    for r in rows:
        recipe = game_data.crafting_recipe(r.code) or {}
        if len(r.prereq_reprs) > len(recipe):
            return False
    return True


def axis2_truncates(rows: list[WalkRow]) -> int:
    """AXIS 2: rows where `prerequisites` leafed on a ready source instead of
    descending a recipe that `recipe_closure` walked right through."""
    return sum(1 for r in rows if r.prereq_leafed)


def summary_line(rows: list[WalkRow]) -> str:
    return (
        f"{len(rows)} targets; "
        f"D1 namespace-split {d1_namespace_split(rows)}; "
        f"D2 drop-blind {d2_drop_blind(rows)}; "
        f"D3 skill-shape {d3_skill_shape_disagreement(rows)}; "
        f"axis2 truncated {axis2_truncates(rows)}"
    )


def render_matrix(rows: list[WalkRow]) -> str:
    """Markdown characterization matrix. The generator owns the write."""
    out = [
        "# Requirement-walk parity — characterization matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_requirement_parity.py`.",
        "",
        "Wave 0 of the requirement-model unification epic. This records what the "
        "six requirement walks answer TODAY, **disagreements included**, so a "
        "later migration wave produces a binary signal: an intentional D-fix, or "
        "a regression. Rows are pins, not endorsements.",
        "",
        summary_line(rows),
        "",
        "| target | closure res | closure craft | demand | drop-blind (D2) | "
        "prereqs (1-ply) | leafed | needs skills | worst gap | sources |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def fmt(vals: tuple[str, ...]) -> str:
        return ", ".join(vals) if vals else "·"

    for r in rows:
        out.append(
            f"| {r.code} | {len(r.closure_resources)} | {len(r.closure_craftables)} "
            f"| {len(r.demand_items)} | {fmt(r.drop_blind_items)} "
            f"| {len(r.prereq_reprs)} | {'yes' if r.prereq_leafed else '·'} "
            f"| {fmt(r.needs_skills)} | {r.worst_skill_gap or '·'} "
            f"| {fmt(r.source_kinds)} |"
        )
    return "\n".join(out) + "\n"
