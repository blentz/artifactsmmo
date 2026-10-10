"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

from dataclasses import dataclass, replace
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
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grey_farm import grey_farm_allowed
from artifactsmmo_cli.ai.grind_heal_prep import heal_prep_goal
from artifactsmmo_cli.ai.grind_rung import grind_rung_goal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recipe_closure import closure_demand, recipe_closure
from artifactsmmo_cli.ai.region_edges import REGION_EDGE_TAG
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.objective import (
    GOLD,
    CharacterObjective,
)
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState

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
    events: frozenset[str] = frozenset()
    """Event codes live for this cell (USER 2026-10-10, "add event-active
    cells"); empty is the event-free world. See `event_cells`."""
    skills_at_level: bool = False
    """Every skill but the cell's own at the character's level (a character
    whose skills kept pace), not only the recipe's gathering prerequisites.
    The conditions census's rungs (`audit/craft_conditions`)."""
    gold: int = 0
    """Gold in the pocket (the census character's default is none)."""


def tier_of(craft_level: int) -> int:
    """The decade-inclusive tier bucket of a craft level: (L-1)//10+1, so
    craft_level=10 is the LAST level of tier 1, not the first of tier 2."""
    return (craft_level - 1) // 10 + 1


def nominal_char_level(craft_level: int) -> int:
    """The tier's nominal character level: 1 for tier 1 (L<=9), else 10*tier."""
    return 1 if craft_level <= 9 else 10 * tier_of(craft_level)


def craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]:
    """The level/skill census cells for `recipe` (spec grid): 3 character
    levels (decade-tier nominal + boundary offsets, clamped [1,50]) x 2
    skill levels (under-skill `craft_level-5` clamped >=1, and at-skill
    `craft_level`) = up to 6 cells. Skills start at level 1 in this game
    (min gatherable/craftable rung is level 1), so the under-skill floor is
    1, not 0 — a skill_level=0 cell is an impossible game state. Low-level
    recipes whose `craft_level-5 <= 1` collapse under-skill into at-skill,
    yielding fewer cells. `recipe`'s tier bucket is the decade its
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
    tier = tier_of(craft_level)
    nominal = nominal_char_level(craft_level)
    char_levels = sorted({
        max(1, min(50, lvl))
        for lvl in (nominal, 10 * tier - 2, 10 * tier + 2)
    })
    skill_levels = sorted({max(1, craft_level - 5), craft_level})
    return [CraftCell(cl, skill, sl)
            for cl in char_levels for sl in skill_levels]


def plan_craft(recipe: str, state: WorldState,
               game_data: GameData) -> list[Action]:
    """The plan the REAL production planner produces for obtaining `recipe`
    from `state`.

    Drives `StrategyArbiter._plans` — the EXACT per-goal planning seam the live
    bot runs: the `is_plannable` reachability gate, the route-driven fast path
    (`craft_plan_gen.decompose`, the one walk, nodes=0), AND the A* fallback, in
    that order. It deliberately does NOT call the raw `GOAPPlanner` (a
    sub-component the live bot never invokes directly): a census that re-planned
    through a lower layer, or re-implemented the generator/A* ordering itself,
    would be a SECOND implementation testing nothing that ships. The audit exists
    to answer "does the production planner meet spec for this recipe" — so it must
    call production.

    task_exchange_min_coins=0: task funding is irrelevant to craft planning."""
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(
        game_data, state, objective,
        bank_accessible=True, task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item=recipe, needed={recipe: 1})
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    ctx = SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=0, combat_monster=None,
    )
    return arbiter._plans(goal, state, game_data, actions, ctx,
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
    - the non-gold CURRENCY of every vendor selling a closure member: the
      kill that earns `cowhide` advances `mushmush_jacket` because the tailor
      sells its `hard_leather` for cowhide. Hidden until 2026-10-10, when the
      census character first could beat the cow. (`_closure_members` is the
      set without them: a currency is not a recipe LEAF — `_leaf_status`
      judges the purchase through `_permanently_buyable`.)
    """
    members = _closure_members(recipe, needed_resources, craftable_mats, game_data)
    currencies = {currency for item in members
                  for _npc, _price, currency in game_data.npc_purchases(item)
                  if currency != GOLD}
    return members | currencies


def _closure_members(recipe: str, needed_resources: set[str],
                     craftable_mats: set[str], game_data: GameData) -> frozenset[str]:
    """`_closure_item_set` without the purchase currencies."""
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


def first_work_leg(plan: list[Action]) -> Action | None:
    """The first leg that is not a region crossing. A crossing
    (`region_edges.REGION_EDGE_TAG`) is travel that serves the leg after it
    (`craft_plan_gen._bridge_regions`), so the verdict judges that leg: a plan
    `[Transition(mine), Gather(gold_rocks), ...]` is judged by its gather."""
    return next((leg for leg in plan if REGION_EDGE_TAG not in leg.tags), None)


def craft_cell_verdict(recipe: str, plan: list[Action],
                       game_data: GameData) -> CraftVerdict:
    """PASS iff `plan` is non-empty AND its FIRST action advances `recipe`'s
    recipe closure (see `_advances_closure`) — the only action that actually
    executes before the next replan cycle. FAIL reasons: "empty" (no plan at
    all — the census cell is unplannable), "wait" (the planner fell back to
    `WaitAction`, i.e. nothing else was applicable), or
    "unrelated:<repr(plan[0])>" (a plannable first leg that does not touch
    `recipe`'s closure or skill — e.g. a stray Rest or an off-closure Gather)."""
    work = first_work_leg(plan)
    if work is None:
        return CraftVerdict(False, "empty")
    first = work
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


def advances_a_closure_grind(recipe: str, first: Action, state: WorldState,
                             game_data: GameData) -> bool:
    """True iff `first` advances the grind of a skill `recipe`'s closure still
    lacks: a closure craftable whose crafting level, or a closure resource whose
    gathering level, is above the character's skill.

    Since Phase 2d-a the one walk opens such a gate as a sub-task and plans the
    grind's own legs (a gather or craft toward the rung `grind_rung_goal`
    picks) where it used to emit the opaque `LevelSkill` macro (deleted in
    Phase 2d-c). A leg is
    directional when it advances that rung's closure, judged by the same
    `_advances_closure` rules as the recipe itself, or, when the rung is gated
    in turn, the grind that opens it (maple_syrup at cooking 35: the cooking
    rung is cooked_bass, bass needs fishing 30, so the leg is the fishing
    grind's gudgeon)."""
    return _advances_grind_of(recipe, first, state, game_data, frozenset())


def _advances_grind_of(item: str, first: Action, state: WorldState, game_data: GameData,
                       grinding: frozenset[str]) -> bool:
    """`advances_a_closure_grind` for `item`, never re-entering a skill
    already being ground further up (`grinding`), as the walk does not."""
    needed_resources, craftable_mats = recipe_closure(game_data, [item])
    gated: set[str] = set()
    for mat in craftable_mats:
        stats = game_data.item_stats(mat)
        if (stats is not None and stats.crafting_skill
                and stats.crafting_level > state.skills.get(stats.crafting_skill, 1)):
            gated.add(stats.crafting_skill)
    for res in needed_resources:
        gate = game_data.resource_skill_level(res)
        if gate is not None and gate[1] > state.skills.get(gate[0], 1):
            gated.add(gate[0])
    for skill in sorted(gated - grinding):
        rung = grind_rung_goal(skill, state, game_data)
        if rung is None:
            continue
        for rung_item in rung.needed:
            rung_resources, rung_mats = recipe_closure(game_data, [rung_item])
            items = _closure_item_set(rung_item, rung_resources, rung_mats, game_data)
            if (_advances_closure(first, items, skill, state.skills.get(skill, 1), game_data)
                    or _advances_grind_of(rung_item, first, state, game_data, grinding | {skill})):
                return True
    return False


def advances_a_heal_prep(first: Action, plan: list[Action], state: WorldState,
                         game_data: GameData) -> bool:
    """True iff `first` stocks the food the plan's first fight will need: the
    plan holds a fight, and `first` advances the closure of the food carry
    `grind_heal_prep.heal_prep_goal` asks for against that fight's monster. The grind's decomposition puts
    that batch ahead of its legs (Phase 2d-a; since 2d-L3 for a fight anywhere
    in the committed plan), so it is the first step of a directional plan."""
    fight = next((a for a in plan if isinstance(a, FightAction)), None)
    if fight is None:
        return False
    prep = heal_prep_goal(state, game_data, NO_PROFILE_CONTEXT, fight.monster_code)
    if prep is None:
        return False
    for item in prep.needed:
        resources, mats = recipe_closure(game_data, [item])
        items = _closure_item_set(item, resources, mats, game_data)
        if _advances_closure(first, items, None, 0, game_data):
            return True
    return False


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
    GREY_FARM_SUPPRESSED = "grey_farm_suppressed"
    """A monster-drop leaf's only permanent dropper is GREY (zero xp-per-kill at
    the cell's char level) and `grey_farm_allowed` declines the farm because a
    near next-tier same-family recipe is the better skill-grind. Production
    deliberately grinds toward the better tier instead of farming the obsolete
    drop — the intended policy (grey_farm.py), not a planner hole."""
    PURCHASE_RECURSION = "purchase_recursion"
    """A leaf's ONLY source is buying it from a permanent vendor with a non-gold
    currency that is itself earned (a task/monster coin) — a recursive buy-edge
    (Fight/Task -> earn currency -> NpcBuy -> craft). The planner does not yet
    plan recursive currency purchases; it is the tracked npc_purchase_acquisition
    Phase 2-4 feature, a known scoped gap rather than an unexplained bug."""
    CROSSING_UNAFFORDABLE = "crossing_unaffordable"
    """A closure leaf grows or spawns only in a region reached through a
    crossing whose fee (gold or a key) the census character cannot pay — the
    1000-gold Sandwhisper Isle boat at the census's zero gold. The decomposition
    names it (`region:<from>-><to>:<leg>`); a funded character plans the round
    trip (boat in, gather, boat out, craft). Before 2026-10-08 these cells
    PASSED only because island content was mislabelled "overworld" and the walk
    ignored regions: a live character could not have run that plan."""
    PLANNER_BUG = "planner_bug"
    """The residual: every closure leaf is reachable AND the skill is
    grindable at the cell, yet the planner still produced no directional plan.
    THE actionable class — each is a systematic-debug fix (like GAP-9)."""


def _leaf_events(leaf: str, game_data: GameData) -> frozenset[str]:
    """The events that would source `leaf` when it has NO permanent source:
    the event codes of its event droppers, event vendors and event resources.
    Empty when any permanent source exists (a located gather, a task reward, a
    permanent spawn-known dropper or a permanent located vendor) — the event
    is then not what the recipe waits on."""
    permanent_drop = any(game_data.monster_spawn_known(m) and not game_data.is_event_monster(m)
                         for m, _r, _mn, _mx in game_data.monsters_dropping(leaf))
    permanent_vendor = any(not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None
                           for npc, _price, _currency in game_data.npc_purchases(leaf))
    if (_has_located_gather_source(leaf, game_data) or game_data.is_task_earnable(leaf)
            or permanent_drop or permanent_vendor):
        return frozenset()
    content = game_data.world.event_code_of_content
    codes = {content[m] for m, _r, _mn, _mx in game_data.monsters_dropping(leaf) if m in content}
    codes |= {content[r] for r, table in game_data.resource_drops_full.items()
              if r in content and any(item == leaf for item, _rate, _mn, _mx in table)}
    codes |= {code for npc, _price, _currency in game_data.npc_purchases(leaf)
              if (code := game_data.npc_event_code(npc)) is not None}
    return frozenset(codes)


def event_cells(recipe: str, game_data: GameData) -> list[CraftCell]:
    """The event-active cells for `recipe` (USER 2026-10-10, "add
    event-active cells"): its `craft_grid` again with every event live that
    sources an event-only closure leaf — all at once, since a recipe needing
    two event leaves banks one window's haul for the other's. Empty when no
    leaf waits on an event. The event-free cells stay: they answer "not now"."""
    events = frozenset().union(*(_leaf_events(leaf, game_data)
                                 for leaf in _closure_leaves(recipe, game_data)))
    if not events:
        return []
    return [replace(cell, events=events) for cell in craft_grid(recipe, game_data)]


def _closure_leaves(recipe: str, game_data: GameData) -> frozenset[str]:
    """The NON-craftable base materials of `recipe`'s full recipe tree — the
    items that must be sourced externally (gathered, dropped, bought, or
    task-earned) rather than crafted. Reuses `_closure_members` (the same
    plan[0]-target widening `craft_cell_verdict` uses, so a monster-only leaf
    like `feather` is visible) and keeps only the members with no crafting
    recipe: crafting a craftable member is always the planner's job, so only a
    base leaf can be a genuine acquisition dead end."""
    needed_resources, craftable_mats = recipe_closure(game_data, [recipe])
    closure_items = _closure_members(recipe, needed_resources,
                                     craftable_mats, game_data)
    return frozenset(item for item in closure_items
                     if not game_data.crafting_recipe(item))


def _event_live(content_code: str | None, game_data: GameData) -> bool:
    """`content_code` (an event monster or resource, or an event NPC's event)
    belongs to an event live in this cell's world."""
    return content_code is not None and content_code in game_data.active_event_codes


def _present_droppers(leaf: str, game_data: GameData) -> list[str]:
    """The droppers of `leaf` present in this cell's world: a permanent
    spawn-known monster, or an event monster whose event is live."""
    content = game_data.world.event_code_of_content
    return [m for m, _r, _mn, _mx in game_data.monsters_dropping(leaf)
            if (game_data.monster_spawn_known(m) and not game_data.is_event_monster(m))
            or (game_data.is_event_monster(m) and _event_live(content.get(m), game_data))]


def _present_vendor(npc: str, game_data: GameData) -> bool:
    """A located permanent vendor, or an event vendor whose event is live."""
    if game_data.is_event_npc(npc):
        return _event_live(game_data.npc_event_code(npc), game_data)
    return game_data.npc_location(npc) is not None


def _currency_directly_attainable(currency: str, state: WorldState,
                                  game_data: GameData) -> bool:
    """A purchase currency the planner can acquire with a DIRECT action edge:
    gold, a located gatherable, or a winnable permanent monster drop (the
    Fight×N → NpcBuy chain grey_farm.py already serves). Deliberately NARROWER
    than `is_attainable_now`, which also credits a TASK-earned currency
    (tasks_coin) — earning a task coin then exchanging it is a recursive
    buy-edge the planner does not yet plan (npc_purchase_acquisition Phase 2-4),
    so a task-only currency is NOT directly attainable here."""
    if currency == GOLD or _has_located_gather_source(currency, game_data):
        return True
    # A grey dropper is fought only under the grey-farm policy, as for a leaf
    # (`_leaf_status`): without this, a currency the policy refuses read as
    # attainable and its recipe was blamed on the planner.
    return any(is_winnable(state, game_data, m)
               and (game_data.xp_per_kill(m, state.level) > 0
                    or grey_farm_allowed(currency, state, game_data))
               for m in _present_droppers(currency, game_data))


def _permanently_buyable(leaf: str, state: WorldState,
                         game_data: GameData) -> bool:
    """`leaf` is purchasable from a PRESENT vendor (permanent and located, or
    an event vendor whose event is live in the cell) for gold or a
    currency the planner can DIRECTLY acquire (`_currency_directly_attainable`),
    restricted to non-event, located NPCs (an event vendor is handled by the
    EVENT_GATED arm; a task-only-currency vendor by the PURCHASE_RECURSION arm)."""
    for npc, _price, currency in game_data.npc_purchases(leaf):
        if not _present_vendor(npc, game_data):
            continue
        if _currency_directly_attainable(currency, state, game_data):
            return True
    return False


def _recursive_purchase_only(leaf: str, game_data: GameData) -> bool:
    """`leaf` has a PERMANENT, reachable, non-event vendor but only for a
    currency the planner cannot directly acquire (reached only after
    `_permanently_buyable` has already failed, so every such vendor's currency
    is task-earned) — the recursive buy-edge tracked as
    npc_purchase_acquisition Phase 2-4, a known scoped gap."""
    return any(not game_data.is_event_npc(npc)
               and game_data.npc_location(npc) is not None
               for npc, _price, _currency in game_data.npc_purchases(leaf))


def _sold_only_by_event_npc(leaf: str, game_data: GameData) -> bool:
    """`leaf` is sold by at least one event-window NPC (its permanent-vendor
    arm having already failed) — an event-gated purchase source."""
    return any(game_data.is_event_npc(npc)
               for npc, _price, _currency in game_data.npc_purchases(leaf))


def _has_located_gather_source(leaf: str, game_data: GameData) -> bool:
    """True iff some PLACED resource drops `leaf` — placed on ANY layer in a
    reachable region (`resource_spawn_known`, the production predicate).
    Asking only the overworld index (`all_resource_locations`) called the
    underground gold/mithril/adamantite rocks unsourced and blamed 204 cells
    on `event_gated` (2026-10-10). `gatherable_drop_items()`
    alone is theoretical — it counts a drop even when its resource has no
    location: `strange_rocks` (diamond_stone's sole source) carries a skill and
    a drop table but is UNPLACED in the bundle, so diamond_stone cannot actually
    be gathered. Treating such a leaf as reachable made `classify_gap` fall
    through to PLANNER_BUG for a MATERIAL dead end (live census 2026-07-11:
    diamond, adamantite gear). The gathering-SKILL requirement is handled
    upstream by `census_state` (it grants the recipe's prerequisite gathering
    skills), so LOCATION is the remaining check here."""
    for resource, table in game_data.resource_drops_full.items():
        if (any(item == leaf for item, _rate, _mn, _mx in table)
                and game_data.resource_spawn_known(resource)):
            return True
    return any(drop == leaf and game_data.resource_spawn_known(resource)
               for resource, drop in game_data.resource_drops.items())


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
    source nor an event source is MATERIAL_UNREACHABLE. In an event-active cell
    a live event's monster and vendor are present sources like permanent ones
    (`_present_droppers`, `_present_vendor`)."""
    if _has_located_gather_source(leaf, game_data):
        return None
    if game_data.is_task_earnable(leaf):
        return None
    if _permanently_buyable(leaf, state, game_data):
        return None
    droppers = game_data.monsters_dropping(leaf)
    present = _present_droppers(leaf, game_data)
    winnable = [m for m in present if is_winnable(state, game_data, m)]
    if winnable:
        # A winnable dropper only makes the leaf reachable if the planner would
        # actually FIGHT it. An xp-positive dropper always qualifies; a GREY
        # dropper (zero xp-per-kill, ≥11 levels below the character) is fought
        # only under `grey_farm_allowed`. When every winnable dropper is grey
        # AND the grey-farm policy declines it (a near next-tier same-family
        # recipe is the better skill-grind), production grinds toward that tier
        # instead — the drop is policy-suppressed, not a planner hole.
        if (any(game_data.xp_per_kill(m, state.level) > 0 for m in winnable)
                or grey_farm_allowed(leaf, state, game_data)):
            return None
        return GapClass.GREY_FARM_SUPPRESSED
    if present:
        return GapClass.COMBAT_BLOCKED
    if any(game_data.is_event_monster(m) for m, _r, _mn, _mx in droppers):
        return GapClass.EVENT_GATED
    if _sold_only_by_event_npc(leaf, game_data):
        return GapClass.EVENT_GATED
    if _recursive_purchase_only(leaf, game_data):
        return GapClass.PURCHASE_RECURSION
    return GapClass.MATERIAL_UNREACHABLE


def _skill_grindable(recipe: str, skill: str,
                     skill_level: int, game_data: GameData) -> bool:
    """The recipe's crafting skill can be leveled from the cell's `skill_level`
    up to the recipe's required `target_level`. The sole caller (`classify_gap`)
    invokes this ONLY for under-skill cells (`skill_level < target_level`), so
    the question is always non-trivial: there must be SOME grind rung STARTABLE
    AT THE CELL'S CURRENT `skill_level` — a craftable of the same
    `crafting_skill` at a level ≤ `skill_level`, or a gatherable resource of
    that skill at a level ≤ `skill_level` (this game reuses the raw-gathering
    skill name as the tier-1 processed good's `crafting_skill`). Bounding by
    `skill_level` (not `target_level`) is deliberate: a rung above the target is
    irrelevant either way, but a rung AT OR BELOW the target yet ABOVE the
    character's current skill is not actionable NOW — it is itself ungrindable
    from here. A skill whose lowest rung sits above `skill_level` cannot be
    bootstrapped from this cell at all — SKILL_UNREACHABLE (e.g. skill_level=1
    with only a level-2 rung: you need skill 2 just to act on it)."""
    for code, stats in game_data.all_item_stats.items():
        if (code != recipe and stats.crafting_skill == skill
                and 0 < (stats.crafting_level or 0) <= skill_level):
            return True
    return any(res_skill == skill and res_level <= skill_level
               for res_skill, res_level in game_data.resource_skills.values())


def _closure_gather_skills(recipe: str, game_data: GameData) -> dict[str, int]:
    """The prerequisite GATHERING skills (skill -> level) a character must have
    leveled to source `recipe`'s closure materials from a LOCATED resource — the
    cheapest (lowest-level) placed source per material fixes the level.

    A plausibly-progressed crafter of `recipe` HAS these skills: you cannot amass
    a recipe's raw materials without having leveled the skills that gather them,
    and the grid pairs each recipe's `char_level` with its own tier, so a
    tier-N recipe is only ever tried at a tier-N character — where a tier-N
    gathering skill is plausible. Without this, `census_state` granted ONLY the
    crafting skill, leaving every cross-skill material ungatherable (a
    weaponcrafting cell with mining 1 could never gather iron_ore) — a
    CENSUS-STATE artifact that mislabeled cross-skill recipes as PLANNER_BUG
    (live census 2026-07-11: iron_dagger, cooked_shrimp, water_bow). Unplaced
    or higher-than-tier sources are deliberately excluded — a material sourced
    only from an unplaced resource is genuinely unreachable (MATERIAL, via
    `_leaf_status`), not a skill the census should hand out."""
    chain: dict[str, int] = {}
    closure_demand(recipe, 1, game_data, chain, frozenset())
    skills: dict[str, int] = {}
    for leaf in chain:
        best: tuple[str, int] | None = None
        for resource, table in game_data.resource_drops_full.items():
            if (resource in game_data.all_resource_locations
                    and any(item == leaf for item, _rate, _mn, _mx in table)):
                req = game_data.resource_skills.get(resource)
                if req is not None and (best is None or req[1] < best[1]):
                    best = req
        for resource, drop in game_data.resource_drops.items():
            if drop == leaf and resource in game_data.all_resource_locations:
                req = game_data.resource_skills.get(resource)
                if req is not None and (best is None or req[1] < best[1]):
                    best = req
        if best is not None:
            skill, level = best
            skills[skill] = max(skills.get(skill, 0), level)
    return skills


def census_state(recipe: str, cell: CraftCell, game_data: GameData) -> WorldState:
    """The plausibly-GEARED, plausibly-SKILLED census character state for
    attempting `recipe` at `cell` (spec grid `State` definition,
    docs/superpowers/specs/2026-07-08-craft-planning-completeness-design.md):
    `cell.char_level` + `cell.skill_name` at `cell.skill_level` PLUS the
    prerequisite gathering skills the recipe's materials need (`_closure_gather_
    skills`), empty inventory AND bank, equipped with the best usable-NOW item
    per slot and combat stats DERIVED from that loadout — so `is_winnable`
    reflects a plausible starter/tier loadout, not zero stats.

    Prereq skills NEVER override `cell.skill_name`: the cell's crafting-skill
    level is the tested dimension (under- vs at-skill), so it stays exactly
    `cell.skill_level` even if the recipe also gathers with that skill.

    Gear source: a FIXED POINT of `CharacterObjective.near_term_gear` (the
    best attainable-now item per slot at `cell.char_level`): wear the pick,
    pick again, until no slot improves — a character progresses into the gear
    its gear lets it win. The gear is chosen for a character whose skills are
    all at its level (crafting kept pace); the returned PLANNING state keeps
    the cell's skills, the tested dimension. Before 2026-10-10 the pick ran
    ONCE from a bare character with every other skill at 1, so a level-30
    census character wore a copper dagger and lost to a level-8 cow — 570
    `combat_blocked` cells, most of them that loadout. The loadout is equipped
    with `derive_combat_stats=True`, which sums the equipped items' catalog
    stats into the server-total combat stats — what a live character wearing
    it would report.

    `cell.events` are live for the whole cell (`WorldState.active_events`);
    `cell.skills_at_level` and `cell.gold` are the conditions census's grants.

    Used by both `classify_gap` and `plan_craft`'s driving state, so the census
    and the classifier agree on the cell's plausible character."""
    skills = ({name: cell.char_level for name in SKILL_NAMES} if cell.skills_at_level
              else dict(_closure_gather_skills(recipe, game_data)))
    skills[cell.skill_name] = cell.skill_level
    events = tuple(sorted(cell.events))
    sc = ScenarioCharacter(name="craft_audit", level=cell.char_level, gold=cell.gold,
                           skills=dict(skills),
                           equipment=census_gear(cell.char_level, cell.events, game_data),
                           derive_combat_stats=True, active_events=events)
    return scenario_state(sc, game_data)


_GEAR_MEMO: list[tuple[GameData, dict[tuple[int, frozenset[str]], dict[str, str]]]] = []
"""One slot: the catalogue the memo was built on (HELD, so its identity cannot
be reused) and its loadouts. A census worker plans every cell over one
catalogue; a different catalogue replaces the slot."""


def census_gear(char_level: int, events: frozenset[str],
                game_data: GameData) -> dict[str, str]:
    """The census character's loadout at `char_level` with `events` live: the
    fixed point of `near_term_gear` for a character whose skills are all at
    its level (see `census_state`). Depends on nothing else, so it is
    memoized per catalogue."""
    if not _GEAR_MEMO or _GEAR_MEMO[0][0] is not game_data:
        _GEAR_MEMO[:] = [(game_data, {})]
    memo = _GEAR_MEMO[0][1]
    key = (char_level, events)
    if key not in memo:
        objective = CharacterObjective.from_game_data(game_data)
        skills = {name: char_level for name in SKILL_NAMES}
        live = tuple(sorted(events))
        gear: dict[str, str] = {}
        while True:
            worn = scenario_state(
                ScenarioCharacter(name="census_gear", level=char_level, skills=skills,
                                  equipment=dict(gear), derive_combat_stats=True,
                                  active_events=live),
                game_data)
            upgrades = objective.near_term_gear(worn)
            if not upgrades:
                break
            gear.update(upgrades)  # strict per-slot improvements: terminates
        memo[key] = gear
    return dict(memo[key])


def _crossing_unaffordable(recipe: str, state: WorldState, game_data: GameData) -> bool:
    """The production decomposition declines `recipe` for a region crossing it
    cannot make from `state` (`craft_plan_gen._bridge_regions`). A world with
    no transitions has no crossing to fail."""
    if not game_data.world.transition_edges:
        return False
    actions = build_actions(game_data, state, CharacterObjective.from_game_data(game_data),
                            bank_accessible=True, task_exchange_min_coins=0)
    ctx = SelectionContext(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                           initial_xp=0, task_exchange_min_coins=0, combat_monster=None)
    declined: list[str] = []
    decompose(GatherMaterialsGoal(target_item=recipe, needed={recipe: 1}), state, game_data,
              actions, ctx, declined)
    return any(reason.startswith("region:") for reason in declined)


def classify_gap(recipe: str, cell: CraftCell,
                 game_data: GameData) -> GapClass:
    """Classify a FAIL cell's root cause as an ORDERED cascade over `recipe`'s
    closure leaves, at a state rebuilt from the cell via `census_state`
    (`cell.char_level` + the single crafting skill at `cell.skill_level`,
    equipped with a plausible near-term loadout). Pure over
    (`recipe`, `cell`, `game_data`).

    Precedence — CROSSING_UNAFFORDABLE → EVENT_GATED → COMBAT_BLOCKED → MATERIAL_UNREACHABLE →
    GREY_FARM_SUPPRESSED → PURCHASE_RECURSION → SKILL_UNREACHABLE →
    PLANNER_BUG — runs most-specific-first. The first five are leaf-level (a
    specific closure leaf blocks); SKILL_UNREACHABLE is recipe-level (the
    crafting skill is below level AND cannot be bootstrapped from here);
    PLANNER_BUG is the residual. A GRINDABLE under-skill cell is NOT a gap class:
    the one walk opens the skill gate as a sub-grind, and the census PASSes the
    grind's first leg (`advances_a_closure_grind`) — it never reaches this
    cascade (a grindable under-skill FAIL would be an actionable PLANNER_BUG,
    not an expected limit):

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
    state = census_state(recipe, cell, game_data)
    if _crossing_unaffordable(recipe, state, game_data):
        # FIRST, because it is direct evidence: the production decomposition
        # found every source and declined only for a crossing fee (the island
        # boat, the Enchanted Forest's 5000-gold exit). A leaf-level reading of
        # the same cell calls those sources event-gated or unreachable.
        return GapClass.CROSSING_UNAFFORDABLE
    statuses = {_leaf_status(leaf, state, game_data)
                for leaf in _closure_leaves(recipe, game_data)}
    for gap in (GapClass.EVENT_GATED, GapClass.COMBAT_BLOCKED,
                GapClass.MATERIAL_UNREACHABLE, GapClass.GREY_FARM_SUPPRESSED,
                GapClass.PURCHASE_RECURSION):
        if gap in statuses:
            return gap
    stats = game_data.item_stats(recipe)
    skill = (stats.crafting_skill or "") if stats is not None else ""
    target_level = (stats.crafting_level or 0) if stats is not None else 0
    if (cell.skill_level < target_level
            and not _skill_grindable(recipe, skill, cell.skill_level, game_data)):
        # Under-skill AND the skill cannot be bootstrapped from here (no in-band
        # rung to grind on) — a genuine skill dead end, SKILL_UNREACHABLE.
        # A GRINDABLE under-skill cell is NOT classified here: the walk opens
        # the gate as a sub-grind and the census PASSes the grind's leg, so it
        # never reaches classify. If a grindable under-skill cell DOES fail, the
        # grind was in reach and should have been planned — that is the
        # actionable PLANNER_BUG residual (the fall-through below), not an
        # expected skill gap.
        return GapClass.SKILL_UNREACHABLE
    return GapClass.PLANNER_BUG
