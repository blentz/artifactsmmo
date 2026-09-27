"""Pick the in-skill item to craft NOW to gain XP toward a skill gate.

Among items that are same-skill, in-level, OBTAINABLE (every recipe input
feasible under `GRIND_POLICY`) and XP-POSITIVE (the craft is not in the
server's zero-xp band), prefer the highest XP RATE — `craft_level` per effective
action, where the effective actions are `acquire_steps` (counted over the whole
recipe closure) for an ordinary rung and ZERO for a `wanted` one — then `wanted`,
then the higher `craft_level`, then the fewer RAW `acquire_steps`; a full tie
keeps the FIRST-SEEN candidate (insertion order) — there is no
string/alphabetical tie-break. That ordering replaced "cheapest chain, then
highest level" on 2026-08-14; full rationale, and the measured domain over which
the `wanted` credit acts as a total pivot, on `skill_grind_selection._beats`.
`wanted` is not a property of the item: `_with_wanted` sets it per call from the
caller's `SelectionContext` (`ctx.near_term_targets`, the usable-now gear ∪ tool
SET, or `ctx.supply_target`, a sibling's published demand), so the same catalog
ranks differently under a different objective and identically — every `wanted`
False — under `NO_PROFILE_CONTEXT`. Returns None when no such in-skill recipe
exists — the caller (the LevelSkill action's is_applicable / grind expansion,
always same-skill, never cross-skill) then has no craftable rung. Inclusion is a
recipe-table + reachability fact, free of bank-freshness false positives (only
`acquire_steps` ordering reads holdings).

`reserved`: recipe-input codes of the COMMITTED objective that the grind must not
consume (Trace 2026-06-11 19:22: copper_helmet would have eaten the 5 bars held
for copper_legs_armor).

OBTAINABILITY (Trace 2026-06-13): `skill_grind_target("weaponcrafting")` used to
pick `wooden_staff` (needs un-gettable `wooden_stick`), whose GatherMaterials
GOAP-failed; the arbiter then fell CROSS-SKILL to a gearcrafting grind, abandoning
the committed weaponcrafting objective. The `is_obtainable` filter excludes
such items so the reachable `copper_dagger` wins.
"""

import dataclasses
from datetime import UTC, datetime

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.grind_probe_state import grind_probe_state
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)
from artifactsmmo_cli.ai.world_state import WorldState

GRIND_ALLOWS_GREY = True
"""The grind's standing exemption from the 2026-07-06 grey directive, named so
the oracle call below reads as a POLICY and not as a magic literal.

A skill grind fights a grey mob for the RUNG'S MATERIAL, not for its xp, so the
directive's preference — "grind the skill and craft the better item instead of
farming greys for a soon-obsolete one" — is not an alternative to suppress in
favour of: it is precisely what this walk is selecting. The exemption is the
same one `GatherMaterialsGoal(skill_grind=True)` passes on the emission side
(`ai/goals/gathering.py`), and it is deliberately NOT widened to any other
caller — see `ai/grey_farm.py`'s module docstring for the three structural
exemptions and the directive they bend around."""


GRIND_POLICY = Policy(all_gather_routes=True, gather_skill_gate=False, craft_skill_gate=False,
                      event_vendors=False, spawn_known=True, allow_grey=GRIND_ALLOWS_GREY,
                      vendor_routes=False, ge_routes=False, task_rewards=False)
"""What the grind counts as a way to get a rung's material, as an obtain-model
policy (step 4 of docs/PLAN_decision_architecture_redesign.md). Each switch
matches what the grind's descent can actually serve:

- every resource that drops the material (`gatherable_drop_items`, the FULL
  drop union: the primary map misses every secondary drop, e.g. the gem stones);
- neither skill gate is enforced, as before: a skill gate on the chain is a
  level the character can grind, and `gather_demand` reads the grind target to
  surface exactly that demand (D-M turns such a gate into a sub-goal);
- a spawn counts when routable, an underground `gold_rocks` included (the
  action factory builds a gather for it), and grey droppers count
  (`GRIND_ALLOWS_GREY`, the same rule `drop_obtainable` was given);
- no BUY or GE_FILL route, as before: `GatherMaterialsGoal(skill_grind=True)`
  buys a material only when no resource and no monster yields it at all, so an
  affordable vendor for a material a monster also drops would name a rung the
  descent never buys for;
- no TASK_REWARD route: the descent does not run the task loop.

What the model adds over the recursive walk it replaced: a material already in
the bag or the bank counts when there is enough of it (the descent withdraws
it), a craft needs a known workshop, and a resource with no spawn anywhere no
longer counts."""


def grind_model(state: WorldState, game_data: GameData) -> ObtainModel:
    """The obtain model the grind asks, built once per sweep over the rungs.

    Context-free on purpose: the candidate list is memoised without a
    `SelectionContext` (see `_cache_key`), so its verdicts must not read one."""
    return ObtainModel(state, game_data, NO_PROFILE_CONTEXT, datetime.now(UTC))


def is_obtainable(code: str, model: ObtainModel) -> bool:
    """Can the grind make `code`? A rung is crafted for its xp, so a craftable
    item counts only through its CRAFT route: that route must be ready, and
    every input must be feasible in the quantity the recipe needs (a copy of
    the rung already held does not serve the grind). Any other item is asked
    for one unit (`ObtainModel.feasible`).

    QUANTITY, NOT EXISTENCE. Unit feasibility would admit a rung whose material
    is one banked copy of something nothing makes: live 2026-09-27, the bank's
    single `hard_leather` (no recipe, no dropper) made `steel_ring` (needs 2),
    `mushmush_jacket` (3) and `hard_leather_armor` (6) grind targets that could
    never be crafted.

    The mob-drop arm is the gate set `drop_obtainable` enforces (shared in
    `obtain_model/drop_routes.py`), so selection cannot call a rung buildable
    while emission refuses the only fight that builds it: the wool/iron_ring
    livelock (see `drop_obtainability`'s docstring)."""
    crafts = [route for route in model.routes(code) if route.kind is SourceKind.CRAFT]
    if not crafts:
        return model.feasible(code, 1, GRIND_POLICY).ok
    return any(GRIND_POLICY.ready(route)
               and all(model.feasible(item, qty, GRIND_POLICY).ok
                       for item, qty in route.inputs.items())
               for route in crafts)


_CacheKey = tuple[str, int, tuple[tuple[str, str | None], ...],
                  tuple[tuple[str, int], ...], tuple[tuple[str, int], ...],
                  tuple[tuple[str, int], ...]]

CACHE_MAX_ENTRIES = 4096
"""Per-GameData LRU bound, mirroring `equipment/loadout_cache`: comfortably holds
one arbitration cycle's distinct search states while capping long-run growth."""

_CACHES: "CatalogueScope[_CacheKey, list[GrindCandidate]]" = CatalogueScope(CACHE_MAX_ENTRIES)
"""Scoped per GameData by `ai/catalogue_scope`, exactly as `loadout_cache` is —
GameData is an eq-dataclass and so unhashable, and that module owns the reason a
bare `id()` key is unsound on its own."""


def _cache_key(skill: str, state: WorldState) -> "_CacheKey":
    """The determinants of a candidate list, and nothing else.

    `level` and `equipment` drive `is_winnable` (hence obtainability and the DROP
    route); `inventory` and `bank_items` WITH COUNTS drive holdings, the WITHDRAW
    route's stock and the RECYCLE route's licensed surplus; `skills` drives the
    craft gates inside `obtain_sources` and the grind's obtain model. Quantities matter, so these are counted
    pairs rather than key sets.

    Same shape as `loadout_cache._CacheKey`, for the same reason: within one
    search almost every node shares these, so the memo turns a route walk into a
    lookup.

    HP IS DELIBERATELY ABSENT, AND THAT IS NOW SOUND. It was a recorded gap
    (noticed while profiling, 2026-08-13): the `obtainable` field this key guards
    reached `combat.predict_win` through the rung walk's drop arm ->
    `is_winnable`, and that predicate reads CURRENT hp, so
    two states differing ONLY in hp could share a candidate list whose verdicts
    differed — exactly the too-coarse-key failure
    `test_the_memo_key_notices_a_changed_inventory` calls "worse than no memo".
    The drop gates (`obtain_model/drop_routes.py`) evaluate winnability at
    RESTORABLE hp (since 2026-08-18), so the chain no longer reads `state.hp` at
    all and the key is complete as written."""
    return (
        skill,
        state.level,
        tuple(sorted(state.equipment.items())),
        tuple(sorted(state.inventory.items())),
        tuple(sorted((state.bank_items or {}).items())),
        tuple(sorted(state.skills.items())),
    )


def _with_wanted(candidates: list[GrindCandidate],
                 ctx: SelectionContext) -> list[GrindCandidate]:
    """`candidates` with `wanted` set from `ctx`, as a NEW list.

    APPLIED AFTER THE CACHE, deliberately. `_cache_key` is a function of the
    STATE — skill, level, equipment, inventory, bank, skills — and nothing else.
    Folding the context in would multiply the cache by objective state and undo
    the hoist that took this producer from 47.0s of a 67.3s search. `wanted` is
    a projection of the context onto an already-computed list, so it costs one
    rebuild of ~10 dataclasses per call and leaves the memo intact.

    A NEW LIST, never a mutation: `build_selectable_grind_candidates` returns
    the cached list BY REFERENCE, so writing `wanted` into it would poison every
    later reader — including `LevelSkill.is_applicable`, which passes no context
    at all and must keep seeing `wanted=False`.

    Two sources, both already on the context. `near_term_targets` is the
    usable-now gear ∪ tool target set — crafting one of those gains the SAME
    skill xp and yields a keeper instead of a throwaway (2026-06-24: pure
    cheapest-chain greed made the bot craft a value-10 `apprentice_gloves`
    while ignoring the committed value-83 `copper_dagger`). `supply_target[0]`
    is the item code a SIBLING published demand for this cycle, so the fleet's
    need counts the same as this character's own.
    """
    supply = ctx.supply_target[0] if ctx.supply_target is not None else None
    return [dataclasses.replace(
        c, wanted=(c.code in ctx.near_term_targets or c.code == supply))
        for c in candidates]


def build_selectable_grind_candidates(skill: str, state: WorldState,
                                      game_data: GameData,
                                      ctx: SelectionContext = NO_PROFILE_CONTEXT
                                      ) -> list[GrindCandidate]:
    """`skill_grind_target`'s private producer: every in-skill, IN-LEVEL
    craftable as a `GrindCandidate` (whole-chain `acquire_steps` against
    inventory+bank, recursive obtainability). No reservation filter — the caller
    applies its own single-set filter.

    NOT A GENERAL ENUMERATION OF THE SKILL'S RECIPES, which is why SELECTABLE is
    in the name. It was `build_grind_candidates` and returned every in-skill
    craftable until 2026-08-13; a caller wanting the pre-gate list — "what does
    this skill unlock next?" — must NOT use this and should walk
    `game_data.all_item_stats` itself. The rename is deliberate so that such a
    caller gets an ImportError rather than a quietly short answer.

    IN-LEVEL (`craft_level <= state.skills[skill]`) is a hoisted copy of the
    SECOND conjunct of `skill_grind_selection_pure`'s own filter (the four-way
    `if` there tests `craft_skill != skill` first, then `craft_level >
    current_level`; this said "FIRST clause" until 2026-08-13), evaluated here
    from the same `current_level` the selector is handed. Dropping those rows
    provably cannot change the selection: the core `continue`s on exactly this
    predicate before `_beats` ever sees the candidate, so the argmax over the
    filtered list equals the argmax over the full one. What it changes is the
    COST of building the list, and that is why it is here — an out-of-level rung
    still paid a full `acquisition_actions` route walk and a full recursive
    obtainability walk to be discarded one line later. Live shape (R2D2,
    weaponcrafting 9, real catalog): 69 in-skill craftables, 10 in-level, so 59
    of 69 were priced for nothing. Profile 2026-08-13 (from-scratch
    greater_wooden_staff): `LevelSkill.is_applicable` was 48.2s of a 67.3s
    search (72%), of which this function was 47.0s.

    Deliberately NOT hoisted: `xp_positive` and `obtainable`, the selector's
    other two filter clauses. `obtainable` is one of the expensive walks, so
    filtering on it here would save nothing, and `xp_positive` is already free —
    both stay FIELDS so a caller can still see WHY a rung is unusable.

    `acquire_steps` is `acquisition_cost.acquisition_actions` over every route the
    executor can currently serve. It was `min_gathers + min_crafts` until
    2026-08-09, and that priced a DROP as one gather: `apprentice_gloves`
    ({feather: 6}, a 1-in-8 chicken drop, ~48 kills) came out at 7 while
    `sticky_sword` came out at 51, so the grind picked the gloves and farmed
    chickens. Live R2D2 2026-08-08: 198 chicken fights, weaponcrafting stuck at
    6. The route-aware number is 75 vs 61 and inverts it. The same number also
    prices `wooden_staff` (needs the un-gettable `wooden_stick`) as unobtainable,
    which the `obtainable` filter was separately added to patch — one honest
    quantity replacing two proxies. The old text follows for the history:

    `acquire_steps` WAS `min_gathers + min_crafts` over the recipe CLOSURE, the
    same proved lower bound the planner's reachability gate uses. The old
    one-level `mats_missing` count is gone: it priced `sticky_sword` (5 missing
    `copper_bar`, really 51 actions) below `apprentice_gloves` (6 missing
    `feather`, really 7) and cost live R2D2 129 grind cycles at zero xp. Full
    rationale on `skill_grind_selection._beats`.

    `recipe_closure` is built ONCE per call and shared across candidates, so the
    added cost is one closure walk per rung rather than one per material."""
    cache = _CACHES.cache_for(game_data)
    key = _cache_key(skill, state)
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
        return _with_wanted(hit, ctx)
    candidates: list[GrindCandidate] = []
    # One model for the whole sweep: its routes are memoised per item, and the
    # rungs of one skill share most of their materials.
    model = grind_model(state, game_data)
    # The SAME `current_level` `skill_grind_target` hands the selection core.
    current_level = state.skills.get(skill, 0)
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill != skill:
            continue
        if stats.crafting_level > current_level:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        # Priced against a state with THIS rung's own copies removed. A grind
        # earns its xp from the CRAFT, so copies already carried, banked or
        # WORN are not a way to serve it — but `acquisition_actions` prices an
        # owned item at 0, which made a held rung unbeatable and re-selected
        # every cycle forever. Live Lor + HAL 2026-08-14: 3 held
        # `apprentice_gloves` priced at 0, so the grind farmed chickens for
        # feathers — 704 fights, 0 character xp, weaponcrafting 8 -> 8 over 757
        # grind cycles — while `sticky_dagger`/`fire_staff` sat at 59 unchosen.
        # `next_grind_goal`'s DESCENT already used this projection; the
        # selection did not. Same helper, so the two cannot drift apart.
        acquire_steps = acquisition_actions(
            code, 1, grind_probe_state(state, code), game_data,
            NO_PROFILE_CONTEXT, equip=False)
        candidates.append(GrindCandidate(
            code=code,
            craft_skill=stats.crafting_skill,
            craft_level=stats.crafting_level,
            acquire_steps=acquire_steps,
            obtainable=is_obtainable(code, model),
            # The context-free default. `_with_wanted` overwrites this from the
            # caller's ctx below; the CACHED list keeps False so a later
            # context-free reader (LevelSkill.is_applicable) is unaffected.
            wanted=False,
            # The server's level_penalty band: a rung more than
            # GREY_SKILL_GAP-1 levels below the current skill pays NO craft xp,
            # so grinding it can never reach the gate it was invoked to open
            # (rationale + the 14h livelock on `skill_grind_selection_pure`).
            xp_positive=skill_xp_positive(stats.crafting_level,
                                          state.skills.get(skill, 0)),
        ))
    _CACHES.remember(cache, key, candidates)
    return _with_wanted(candidates, ctx)


def has_grind_target(skill: str, state: WorldState,
                    game_data: GameData) -> bool:
    """Whether ANY rung qualifies to grind `skill` — existence, not the argmax.

    EXACTLY `skill_grind_target(skill, state, game_data) is not None`, and much
    cheaper. `skill_grind_selection_pure` admits a candidate on four conditions —
    same skill, in level, `obtainable`, `xp_positive` — and returns the
    `_beats`-maximal survivor, where a None incumbent "is always beaten". So it
    returns non-empty iff at least one candidate passes those four, and whether
    ANY passes is answerable without ranking anything.

    WHAT THAT SAVES IS THE WHOLE COST. `acquire_steps` — a full
    `acquisition_actions` walk per rung — is the RANKING key and appears in none
    of the four filters, so an existence check never needs it. Profiled on
    C3P0's `adventurer_pants` goal, `LevelSkill.is_applicable` was 13.3s of a
    15.1s planning budget, essentially all of it `acquisition_actions` under
    `build_selectable_grind_candidates`. This also stops at the FIRST qualifying
    rung instead of pricing every one of them.

    NOT MEMOISED, and it does not need to be. `build_selectable_grind_candidates`
    caches on a key that includes inventory and bank WITH COUNTS, which is
    correct and useless inside a search: the planner changes the bag on almost
    every node, so the memo misses structurally and pays for building the key as
    well. This walks game data and short-circuits instead.

    `reserved` is not a parameter because the caller that needs speed —
    `LevelSkill.is_applicable` — takes `skill_grind_target`'s default empty set.
    A caller that filters reserved materials wants the target itself anyway.
    """
    current = state.skills.get(skill, 0)
    model = grind_model(state, game_data)
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill != skill or stats.crafting_level > current:
            continue
        if not game_data.crafting_recipe(code):
            continue
        # Free arithmetic before the feasibility walk: a grey rung pays no craft
        # xp, so it can never open the gate this was invoked to open.
        if not skill_xp_positive(stats.crafting_level, current):
            continue
        if is_obtainable(code, model):
            return True
    return False


def skill_grind_target(skill: str, state: WorldState, game_data: GameData,
                       reserved: frozenset[str] = frozenset(),
                       ctx: SelectionContext = NO_PROFILE_CONTEXT) -> str | None:
    candidates = [
        c for c in build_selectable_grind_candidates(skill, state, game_data, ctx)
        if not any(mat in reserved for mat in (game_data.crafting_recipe(c.code) or {}))
    ]
    chosen = skill_grind_selection_pure(skill, state.skills.get(skill, 0), candidates)
    return chosen or None
