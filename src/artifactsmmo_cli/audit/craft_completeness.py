"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_AUDIT_BUDGET_SECONDS = 10.0
"""Per-cell planner budget — the arbiter's cheap first-pass value; keeps the
~1900-cell offline census bounded (CPU memo + node cap do the rest)."""


@dataclass(frozen=True)
class CraftCell:
    """One planner-drive point in the level/skill census grid for a recipe:
    a character level paired with a crafting-skill level at which to attempt
    `recipe`."""

    char_level: int
    skill_name: str
    skill_level: int


def craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]:
    """The level/skill census cells for `recipe` (spec grid): 3 character
    levels (decade-tier nominal + boundary offsets, clamped [1,50]) x 2
    skill levels (under-skill `craft_level-5` clamped >=0, and at-skill
    `craft_level`) = up to 6 cells. `recipe`'s tier bucket is the decade its
    crafting_level falls into ((craft_level-1)//10+1, so crafting_level=10
    is the LAST level of tier 1, not the first of tier 2) — the boundary
    offsets `10*tier±2` straddle that decade line; for a tier-1 recipe
    (crafting_level<=9) the nominal cell is 1 (any starting character),
    while a decade-boundary recipe like crafting_level=10 gets nominal=10.
    Returns [] when `recipe` has no crafting recipe (not craftable)."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        return []
    craft_level = stats.crafting_level
    skill = stats.crafting_skill
    tier = (craft_level - 1) // 10 + 1
    nominal = 1 if craft_level <= 9 else 10 * tier
    char_levels = sorted({
        max(1, min(50, lvl))
        for lvl in (nominal, 10 * tier - 2, 10 * tier + 2)
    })
    skill_levels = sorted({max(0, craft_level - 5), craft_level})
    return [CraftCell(cl, skill, sl)
            for cl in char_levels for sl in skill_levels]


def plan_craft(recipe: str, state: WorldState,
               game_data: GameData) -> list[Action]:
    """The plan the production planner produces for obtaining `recipe` from
    `state` — the exact obtain-X path the tree's gear branch uses, aimed at
    any recipe. task_exchange_min_coins=0: task funding is irrelevant to
    craft planning."""
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(
        game_data, state, objective,
        bank_accessible=True, task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item=recipe, needed={recipe: 1})
    return GOAPPlanner().plan(state, goal, actions, game_data,
                              budget_seconds=CRAFT_AUDIT_BUDGET_SECONDS)


@dataclass(frozen=True)
class CraftVerdict:
    """The directional-planning verdict for one `craft_grid` cell: whether the
    plan `plan_craft` produced actually makes progress on `recipe`, judged by
    its FIRST action only (only `plan[0]` ever executes before a replan)."""

    passed: bool
    reason: str  # "" on pass; else "empty" | "wait" | "unrelated:<repr(plan[0])>"


def _closure_item_set(recipe: str, needed_resources: set[str],
                      craftable_mats: set[str], game_data: GameData) -> frozenset[str]:
    """The item codes that PRODUCING advances `recipe`'s closure.

    Starts from `recipe_closure`'s (needed_resources, craftable_mats) and
    widens to every item that can actually appear as a plan[0] target:

    - `craftable_mats` (every craftable item in the closure) and `recipe`
      itself (craftable_mats already includes the root, since `recipe` is
      always visited-and-craftable — kept explicit for defensiveness).
    - the DIRECT recipe ingredients of every closure craftable (`crafting_
      recipe(mat).keys()` for each `mat`). This recovers every closure LEAF
      material regardless of how it is sourced — a gathered ore (`copper_ore`)
      and a monster-drop-only material (`feather`, dropped by `chicken`, which
      has no resource node at all) are both direct recipe keys of some
      craftable ancestor, so both land here. `needed_resources`/
      `craftable_mats` alone cannot see `feather`: it is neither a resource
      code nor craftable, so `recipe_closure`'s two-set return is blind to it
      — the ingredient union is what makes a closure-leaf-dropping FightAction
      classifiable at all.
    - every drop item (primary AND secondary — gem-stone byproducts etc.) of
      each `needed_resources` entry via `resource_drop_table`, matching the
      brief's literal "DROP ITEMS of needed_resources" wording. This is
      provably a subset of the ingredient union above (a resource is only
      ever `needed` because one of its drops is a closure-visited material,
      and closure-visited materials are exactly the ingredient-union set —
      `resource_drops`/`resource_drops_full` don't feed `recipe_closure`'s
      visited-set computation, only which resources get flagged `needed`) —
      kept anyway for an explicit, literal reading of the spec.
    """
    closure_mats = frozenset(craftable_mats) | {recipe}
    ingredients: set[str] = set()
    for mat in closure_mats:
        ingredients |= (game_data.crafting_recipe(mat) or {}).keys()
    resource_drop_items: set[str] = set()
    for res in needed_resources:
        resource_drop_items |= {item for item, _rate, _min_q, _max_q
                                in game_data.resource_drop_table(res)}
    return frozenset(closure_mats | ingredients | resource_drop_items)


def _advances_closure(action: Action, closure_items: frozenset[str],
                      skill: str | None, skill_ceiling: int,
                      game_data: GameData) -> bool:
    """True iff `action` — as `plan[0]` — makes progress toward `recipe`'s
    closure (`closure_items`, from `_closure_item_set`) or grinds `skill`
    (`recipe`'s `crafting_skill`).

    Per action type:
    - `CraftAction`: PASS if `.code` is a closure member (crafts a closure
      material, including `recipe` itself); else PASS as a SKILL-GRIND leg
      iff the crafted item's OWN `crafting_skill` equals `skill` — crafting
      any other item of the same craft skill (typically a lower/adjacent
      tier, e.g. `copper_helmet` while gearcrafting toward `iron_boots`)
      levels the exact skill gate `recipe` needs, even though the item
      itself never enters `recipe`'s recipe tree.
    - `GatherAction`: PASS if the item it simulates producing
      (`drop_item_override` else `resource_drop_item`, mirroring
      `GatherAction.apply`) is a closure member; else PASS as a SKILL-GRIND
      leg iff the resource's OWN gathering skill equals `skill` — this game's
      data reuses the raw-gathering skill name (mining/woodcutting/fishing/
      alchemy) as the `crafting_skill` of its tier-1 processed good (e.g.
      `copper_bar.crafting_skill == "mining"`), so gathering ANY resource of
      that skill grinds the same gate a smelt/refine recipe needs.
    - `FightAction`: PASS iff ANY of the monster's drops
      (`game_data.monster_drops`) is a closure member. No separate
      fight-skill-grind arm: a kill never grants crafting-skill xp (only
      character/combat xp), so a Fight only ever advances `recipe` by
      dropping a closure material — which a `drop_farm`-flagged Fight
      targeting that material already satisfies via this same check.
    - `NpcBuyAction` / `WithdrawItemAction`: PASS iff `.item_code` /
      `.code` (respectively) is a closure member — no skill-grind arm
      (neither action produces skill xp).
    - anything else (Rest, Move, OptimizeLoadout, Wait — Wait is handled
      by the caller before `_advances_closure` is ever reached): FAIL.
    """
    if isinstance(action, CraftAction):
        if action.code in closure_items:
            return True
        stats = game_data.item_stats(action.code)
        # Tier-aware: a skill-grind craft must be AT OR BELOW the target's
        # craft level — you grind toward X by crafting items you can already
        # make, never a higher-tier same-skill item (which is itself
        # unreachable and not directional toward X).
        return (stats is not None and skill is not None
                and stats.crafting_skill == skill
                and stats.crafting_level <= skill_ceiling)
    if isinstance(action, GatherAction):
        produced = (action.drop_item_override
                   or game_data.resource_drop_item(action.resource_code)
                   or action.resource_code)
        if produced in closure_items:
            return True
        resource_skill = game_data.resource_skill_level(action.resource_code)
        # Tier-aware (same rule as the craft arm): the gathered resource's
        # required skill level must be at/below the target's craft level.
        return (resource_skill is not None and skill is not None
                and resource_skill[0] == skill
                and resource_skill[1] <= skill_ceiling)
    if isinstance(action, FightAction):
        return any(item in closure_items
                  for item, _rate, _min_q, _max_q
                  in game_data.monster_drops(action.monster_code))
    if isinstance(action, NpcBuyAction):
        return action.item_code in closure_items
    if isinstance(action, WithdrawItemAction):
        return action.code in closure_items
    return False


def craft_cell_verdict(recipe: str, plan: list[Action],
                       game_data: GameData) -> CraftVerdict:
    """PASS iff `plan` is non-empty AND its FIRST action advances `recipe`'s
    recipe closure (see `_advances_closure`) — the only action that actually
    executes before the next replan cycle. FAIL reasons: "empty" (no plan at
    all — the census cell is unplannable), "wait" (the planner fell back to
    `WaitAction`, i.e. nothing else was applicable), or
    "unrelated:<repr(plan[0])>" (a plannable first leg that does not touch
    `recipe`'s closure or skill — e.g. a stray Rest or an off-closure Gather)."""
    if not plan:
        return CraftVerdict(False, "empty")
    first = plan[0]
    if isinstance(first, WaitAction):
        return CraftVerdict(False, "wait")
    stats = game_data.item_stats(recipe)
    skill = stats.crafting_skill if stats is not None else None
    skill_ceiling = stats.crafting_level if stats is not None else 0
    needed_resources, craftable_mats = recipe_closure(game_data, [recipe])
    closure_items = _closure_item_set(recipe, needed_resources, craftable_mats, game_data)
    if _advances_closure(first, closure_items, skill, skill_ceiling, game_data):
        return CraftVerdict(True, "")
    return CraftVerdict(False, f"unrelated:{first!r}")
