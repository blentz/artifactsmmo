"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import (
    GOLD,
    CharacterObjective,
    is_attainable_now,
)
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


class GapClass(Enum):
    """Why a FAIL cell produced no directional plan — one class per root cause,
    ordered from the most-specific/expected game limit to the actionable
    residual (see `classify_gap`'s cascade)."""

    EVENT_GATED = "event_gated"
    """A closure leaf's ONLY acquisition source is an event-active monster/NPC
    — unreachable in the event-free audit state (an expected, timed limit)."""
    COMBAT_BLOCKED = "combat_blocked"
    """A closure leaf's only source is a permanently-spawning monster that is
    not `is_winnable` at the cell's level/loadout (a strength limit)."""
    MATERIAL_UNREACHABLE = "material_unreachable"
    """A closure leaf is none of gatherable / drop-winnable / buyable /
    task-earnable and has no event source either — a static-catalog dead end."""
    SKILL_UNREACHABLE = "skill_unreachable"
    """Every leaf is reachable, but the recipe's crafting skill cannot be
    leveled to its required level at the cell (no in-band craftable/gatherable
    of that skill to grind on)."""
    PLANNER_BUG = "planner_bug"
    """The residual: every closure leaf is reachable AND the skill is
    grindable at the cell, yet the planner still produced no directional plan.
    THE actionable class — each is a systematic-debug fix (like GAP-9)."""


def _closure_leaves(recipe: str, game_data: GameData) -> frozenset[str]:
    """The NON-craftable base materials of `recipe`'s full recipe tree — the
    items that must be sourced externally (gathered, dropped, bought, or
    task-earned) rather than crafted. Reuses `_closure_item_set` (the same
    plan[0]-target widening `craft_cell_verdict` uses, so a monster-only leaf
    like `feather` is visible) and keeps only the members with no crafting
    recipe: crafting a craftable member is always the planner's job, so only a
    base leaf can be a genuine acquisition dead end."""
    needed_resources, craftable_mats = recipe_closure(game_data, [recipe])
    closure_items = _closure_item_set(recipe, needed_resources,
                                      craftable_mats, game_data)
    return frozenset(item for item in closure_items
                     if not game_data.crafting_recipe(item))


def _permanently_buyable(leaf: str, state: WorldState,
                         game_data: GameData) -> bool:
    """`leaf` is purchasable from a PERMANENT, reachable vendor for gold or a
    currency that is itself attainable now — the buyable arm of
    `is_attainable_now`, restricted to non-event, located NPCs (an event
    vendor is handled by the EVENT_GATED arm)."""
    for npc, _price, currency in game_data.npc_purchases(leaf):
        if game_data.is_event_npc(npc) or game_data.npc_location(npc) is None:
            continue
        if currency == GOLD or is_attainable_now(currency, state, game_data):
            return True
    return False


def _sold_only_by_event_npc(leaf: str, game_data: GameData) -> bool:
    """`leaf` is sold by at least one event-window NPC (its permanent-vendor
    arm having already failed) — an event-gated purchase source."""
    return any(game_data.is_event_npc(npc)
               for npc, _price, _currency in game_data.npc_purchases(leaf))


def _leaf_status(leaf: str, state: WorldState,
                 game_data: GameData) -> GapClass | None:
    """The blocker class for a single closure leaf at the cell state, or None
    when the leaf is reachable now. Mirrors `is_attainable_now`'s leaf walk
    (gatherable → drop-winnable → task-earnable → buyable) but reports WHICH
    limit blocks an unreachable leaf so `classify_gap` can rank causes.

    Drop sources are split by spawn provenance: a leaf with a PERMANENT dropper
    (known static spawn, not event) that is simply unwinnable here is
    COMBAT_BLOCKED (a strength limit at a real, always-present source), whereas
    a leaf whose only dropper is an event monster is EVENT_GATED (the source
    itself is absent in the event-free audit). A leaf with neither a reachable
    source nor an event source is MATERIAL_UNREACHABLE."""
    if leaf in game_data.gatherable_drop_items():
        return None
    if game_data.is_task_earnable(leaf):
        return None
    if _permanently_buyable(leaf, state, game_data):
        return None
    droppers = game_data.monsters_dropping(leaf)
    permanent = [m for m, _r, _mn, _mx in droppers
                 if game_data.monster_spawn_known(m)
                 and not game_data.is_event_monster(m)]
    if any(is_winnable(state, game_data, m) for m in permanent):
        return None
    if permanent:
        return GapClass.COMBAT_BLOCKED
    if any(game_data.is_event_monster(m) for m, _r, _mn, _mx in droppers):
        return GapClass.EVENT_GATED
    if _sold_only_by_event_npc(leaf, game_data):
        return GapClass.EVENT_GATED
    return GapClass.MATERIAL_UNREACHABLE


def _skill_grindable(recipe: str, skill: str, target_level: int,
                     skill_level: int, game_data: GameData) -> bool:
    """The recipe's crafting skill can be leveled from the cell's `skill_level`
    up to the recipe's required `target_level`. Trivially true when already at
    or above target; otherwise there must be SOME other item of that skill to
    grind on within the band — a craftable of the same `crafting_skill` at a
    level ≤ target, or a gatherable resource of that skill at a level ≤ target
    (this game reuses the raw-gathering skill name as the tier-1 processed
    good's `crafting_skill`). A recipe that is the sole item of its skill at
    its level, with the character below it, cannot be reached — SKILL_UNREACHABLE."""
    if skill_level >= target_level:
        return True
    for code, stats in game_data.all_item_stats.items():
        if (code != recipe and stats.crafting_skill == skill
                and 0 < (stats.crafting_level or 0) <= target_level):
            return True
    return any(res_skill == skill and res_level <= target_level
               for res_skill, res_level in game_data.resource_skills.values())


def census_state(cell: CraftCell, game_data: GameData) -> WorldState:
    """The plausibly-GEARED census character state for `cell` (spec grid
    `State` definition, docs/superpowers/specs/2026-07-08-craft-planning-
    completeness-design.md): `cell.char_level` + `cell.skill_name` at
    `cell.skill_level`, empty inventory AND bank, equipped with the best
    usable-NOW item per slot and combat stats DERIVED from that loadout —
    so `is_winnable` reflects a plausible starter/tier loadout, not zero
    stats.

    Gear source: a bare (ungeared) state at the cell seeds `CharacterObjective
    .near_term_gear`, which picks the best attainable-now item per equipment
    slot at `cell.char_level` (empty-slot baseline, so every positive-value
    attainable item wins its slot). That `{slot: code}` loadout is then
    equipped on the real census character with `derive_combat_stats=True`,
    which sums the equipped items' catalog stats into the server-total
    combat stats (attack/dmg/resistance/critical_strike/initiative) and the
    derived max_hp — exactly what a live character wearing this loadout
    would report.

    Used by both `classify_gap` (the `is_winnable` reachability check) and
    the Phase-2 generator (`plan_craft`'s driving state), so the census and
    the classifier agree on what "plausible loadout" means for a cell."""
    bare = scenario_state(
        ScenarioCharacter(name="census_bare", level=cell.char_level,
                          skills={cell.skill_name: cell.skill_level}),
        game_data)
    gear = CharacterObjective.from_game_data(game_data).near_term_gear(bare)
    sc = ScenarioCharacter(name="craft_audit", level=cell.char_level,
                           skills={cell.skill_name: cell.skill_level},
                           equipment=gear, derive_combat_stats=True)
    return scenario_state(sc, game_data)


def classify_gap(recipe: str, cell: CraftCell,
                 game_data: GameData) -> GapClass:
    """Classify a FAIL cell's root cause as an ORDERED cascade over `recipe`'s
    closure leaves, at a state rebuilt from the cell via `census_state`
    (`cell.char_level` + the single crafting skill at `cell.skill_level`,
    equipped with a plausible near-term loadout). Pure over
    (`recipe`, `cell`, `game_data`).

    Precedence — EVENT_GATED → COMBAT_BLOCKED → MATERIAL_UNREACHABLE →
    SKILL_UNREACHABLE → PLANNER_BUG — runs most-specific-first:

    - EVENT_GATED is the most specific and most EXPECTED limit (a leaf whose
      only source is a timed event, deliberately absent from the event-free
      audit); if any leaf is event-gated the FAIL is fully explained by it.
    - COMBAT_BLOCKED (a real, permanent source the character just can't beat
      yet) outranks MATERIAL_UNREACHABLE: a beatable-later source is a softer
      limit than a genuine catalog dead end, but both are game limits, not
      planner holes.
    - SKILL_UNREACHABLE is checked only once every leaf is reachable — it is a
      property of the recipe's skill ladder, not of any one leaf.
    - PLANNER_BUG is the RESIDUAL: every leaf reachable AND the skill grindable,
      yet no directional plan. That is exactly the actionable class — the gap
      the census exists to surface, since everything the planner needed was in
      reach. Making it the fall-through (never a positive match) means a cell
      is only ever blamed on the planner after every game-limit explanation is
      ruled out.

    A leaf's own status is decided by `_leaf_status`; the cascade then ranks
    the leaf statuses by the precedence above."""
    state = census_state(cell, game_data)
    statuses = {_leaf_status(leaf, state, game_data)
                for leaf in _closure_leaves(recipe, game_data)}
    for gap in (GapClass.EVENT_GATED, GapClass.COMBAT_BLOCKED,
                GapClass.MATERIAL_UNREACHABLE):
        if gap in statuses:
            return gap
    stats = game_data.item_stats(recipe)
    skill = (stats.crafting_skill or "") if stats is not None else ""
    target_level = (stats.crafting_level or 0) if stats is not None else 0
    if not _skill_grindable(recipe, skill, target_level,
                            cell.skill_level, game_data):
        return GapClass.SKILL_UNREACHABLE
    return GapClass.PLANNER_BUG
