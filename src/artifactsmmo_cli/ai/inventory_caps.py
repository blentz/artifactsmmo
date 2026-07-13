"""Compute per-item "useful quantity cap" — beyond which inventory is overstock.

Caps are pragmatic: max recipe demand × batch buffer, plus task demand, plus a
safety floor for items currently in use. Anything held over the cap is wasted
inventory space.

PURE CORES (mechanical-extraction P3b): the cap/overstock decisions are pure
functions over plain data (scalar state fields, a `recipes` mapping, per-peer
dominance verdicts) so they can be mechanically extracted to Lean
(`formal/Formal/Extracted/InventoryCaps.lean`) and bridged against the hand
models `formal/Formal/InventoryCaps.lean` / `formal/Formal/InventoryProfile.lean`.
The public wrappers preserve the original GameData/WorldState-taking API
exactly, reading the accessors and forwarding.

The recipe-chain recursion is FUEL-BOUNDED (the recipe_closure precedent):
`_task_chain_demand_pure` threads an explicit `fuel` seeded with
`len(recipes) + 1`, which no input can exhaust — every recursing frame marks a
DISTINCT key in its per-path visited map first, so recursion depth never
exceeds `len(recipes) + 1` even on cyclic recipe graphs. Visited sets are
insertion-ordered `dict[str, int]` membership maps (`code -> 1`): the
extracted image is an association list, and all reads go through
order-independent `dict.get`.

EXACT VALUE SEAM (P3c, updated Task 2 2026-06-28): the dominance gate routes
through `gear_value(stats, Rank)` (leaf module `ai/gear_value.py`), which
returns `int` — every summand is an int, so the strictly-higher dominance
criterion is EXACT integer arithmetic with no float seam. `_is_equippable_dominated`
evaluates each peer's criteria into plain bools and hands `_is_dominated_pure`
the verdict list, exactly the hand model's `Peer` encoding — the hand model has
always taken the verdicts as Bools. Spec:
docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md.
"""

from collections.abc import Mapping, Sequence

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat_targets import combat_target_monsters
from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates
from artifactsmmo_cli.ai.equipment.scoring import armor_score, weapon_score
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_DEN, PRESSURE_HIGH_NUM
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

def _score_vector(stats: ItemStats, monsters: list[str], game_data: GameData) -> list[int]:
    """Per-monster combat score for a weapon (offense) or armor (defense) piece."""
    if stats.type_ == "weapon":
        return [weapon_score(stats, game_data.monster_resistance(m)) for m in monsters]
    return [armor_score(stats, game_data.monster_attack(m)) for m in monsters]

BATCH_BUFFER = 5
"""How many craft batches worth of material to keep on hand. With BATCH=5 and
a recipe needing 6 of a mat, the cap is 30."""

SAFETY_FLOOR = 3
"""Always keep at least this many of any item that has any recipe use, so the
bot doesn't immediately re-gather what it just discarded."""

RECIPE_SKILL_HORIZON = 2
"""A consuming recipe whose crafting-skill requirement is more than this many
levels above the character's CURRENT level in that skill is NOT near-term
craftable, so its material demand does not count toward the material's useful
inventory cap. The material becomes deposit-eligible rather than reserved bag
space the bot can't use yet — e.g. level-20 gemstones (cut at mining@20), mined
as byproducts of low-level nodes, get banked instead of clogging a level-10
bag. See docs/PLAN_gem_inventory_strategy.md."""

# The high watermark, kept as an EXACT integer ratio (17/20 = 0.85). The
# overstock decision compares `used / cap >= num / den` by cross-multiplication
# over integers — exact, no float drift at the boundary (mirrored by the proved
# Lean core overstockExcess in formal/Formal/InventoryProfile.lean).
DISCARD_WATERMARK_NUM = PRESSURE_HIGH_NUM  # canonical value lives in thresholds.py
DISCARD_WATERMARK_DEN = PRESSURE_HIGH_DEN
DISCARD_WATERMARK = DISCARD_WATERMARK_NUM / DISCARD_WATERMARK_DEN
"""inventory_used/inventory_max at or above which an over-floor item becomes
overstock (== 0.85). Below this watermark the bag has real free slots, so
NOTHING is overstock — the per-item `useful_quantity_cap` stops being a
space-blind dump trigger. At/above the watermark, `useful_quantity_cap` (the
useful floor) and the active goal's profile target (the protected floor)
jointly decide what may be shed. Space-driven half of the per-goal
inventory-profile design (spec 2026-06-07): deposit/discard fire only under
genuine space pressure."""


def overstock_excess(
    held: int, profile_target: int, useful_floor: int,
    used: int, cap: int,
    watermark_num: int = PRESSURE_HIGH_NUM,
    watermark_den: int = PRESSURE_HIGH_DEN,
) -> int:
    """Pure space-driven overstock decision (proved in
    formal/Formal/InventoryProfile.lean as `overstockExcess`; mechanically
    extracted to formal/Formal/Extracted/InventoryCaps.lean and bridged).

    An item is overstock only when the bag is under real space pressure
    (`used / cap >= watermark_num / watermark_den`, compared by exact integer
    cross-multiplication) AND `held` exceeds the protected floor
    `max(profile_target, useful_floor)`. Below the watermark — with free slots
    — nothing is overstock, so an active-goal material accumulating toward its
    profile target is never shed. The excess returned is
    `held - max(profile_target, useful_floor)`; otherwise 0.

    `profile_target` is the SOFT floor the active goal wants on hand;
    `useful_floor` is the per-item `useful_quantity_cap`, which now only
    tiebreaks WHICH overstock to shed once the bag is genuinely full. An item
    at or below `profile_target` is NEVER overstock, regardless of pressure.
    A non-positive `cap` reads as no pressure (no overstock)."""
    if cap <= 0 or used * watermark_den < cap * watermark_num:
        return 0
    floor = profile_target if profile_target > useful_floor else useful_floor
    if held > floor:
        return held - floor
    return 0

EQUIPPABLE_KEEP = 1
"""Keep at least one of any equippable item Robby can wear — even if not
currently equipped — so the equipment optimizer has it as a swap candidate.
DROPS TO ZERO when the item is DOMINATED by another owned item that fills
the same equipment slot AND has strictly higher equip_value AND covers
every skill_effect of the dominated item with equal-or-better magnitude.
Without this dominance gate, the bot keeps `wooden_stick` (starter, attack
0) forever even after crafting `copper_dagger` (attack 12) — both occupy
weapon_slot and `EQUIPPABLE_KEEP=1` protects each individually. The
dominated stick should be the FIRST thing the discard ladder picks when
inventory pressure forces a delete."""

CONSUMABLE_KEEP = 999
"""Keep effectively unlimited HP-restoring consumables (apple,
cooked_chicken, potion, etc.). Consumables STACK in a single inventory
slot regardless of quantity — capping low frees zero slots while
throwing away healing stock with real survival value. Trace 2026-06-05
16:13: bot deleted 19 apples in one Delete(apple×19) action because the
prior cap of 10 declared excess=19; 19 apples is 19 RestAction-class
heals worth of insurance lost for zero slot benefit. Same fix pattern
as tasks_coin (602f7b4) — raise the cap past any plausible accumulation
since stacking-items don't cost slots per unit. Original prior cap was
0 (everything deleted, fixed in f1f8941) → 10 (insufficient, still
delete-heavy) → 999 (stack-aware floor)."""

CURRENCY_KEEP = 999
"""Keep effectively unlimited of any CURRENCY-type item (tasks_coin,
event_ticket, corrupted_gem, sandwhisper_coin, …). Currencies are pure economic
value spent at NPCs / events; auto-deleting or bank-draining them as "junk" is
an unrecoverable loss. API `type`-driven (see `_non_recipe_keep_floor`) so EVERY
current and future currency the server defines is protected — not a hardcoded
code list (the bug: only tasks_coin was protected, by code, so the other three
live currencies fell to cap 0 and were delete-eligible)."""

# Items consumed by API actions (not recipes). Keep enough to use them.
ACTION_CONSUMABLES_CAP = {
    # Tasks-coins stack in a single inventory slot regardless of quantity,
    # so capping low (was 9 = 3 batches) frees no actual slots — it just
    # throws away TaskExchange currency. Trace 2026-06-05T02:55: Robby
    # deleted 3 tasks_coin (out of 12 he'd grinded for) because the cap
    # rule kicked in during a DiscardOverstock cycle. Each coin is worth
    # one third of a random-item exchange; deleting them is a real
    # economic loss with no slot benefit. Set to a value larger than any
    # plausible accumulation; the keep-set still ensures coins are
    # protected from bank-deposit too.
    TASKS_COIN_CODE: 999,
}


def _non_recipe_keep_floor(item_code: str, stats: ItemStats | None) -> int:
    """Keep-floor for an item whose value is NOT captured by the recipe /
    equippable / task / hp-consumable components — driven by the API item
    `type` so categorization is GENERIC across every item the server defines
    (not a hardcoded code list):

      * `type == "currency"`   -> CURRENCY_KEEP   (never auto-delete currency)
      * `type == "consumable"` -> CONSUMABLE_KEEP (heals AND non-hp consumables
                                  like teleport / gold-bag potions are used
                                  deliberately, never junked — `hp_restore`
                                  alone missed the non-hp ones)
      * otherwise              -> ACTION_CONSUMABLES_CAP code override, else 0

    Raw `resource`-type materials get 0 here — their cap comes from recipe
    demand — so a far-skill-gated byproduct stays drain-eligible from the bag.
    The bank-side keep (see `ai/bank_drain`) additionally protects a material's
    eventual recipe demand so future-useful mats are not deleted from the bank.
    `stats is None` (item missing from the catalog) falls through to the code
    override / 0; the bot fails loud elsewhere if it must act on an unknown item."""
    if stats is not None:
        if stats.type_ == "currency":
            return CURRENCY_KEEP
        if stats.type_ == "consumable":
            return CONSUMABLE_KEEP
    return ACTION_CONSUMABLES_CAP.get(item_code, 0)


LEVEL_BAND_NEAR = 5
"""`|item.level - character.level|` strictly below this is "currently useful" —
no level-distance ceiling, the base keep-cap stands."""
LEVEL_BAND_FAR = 10
"""At/above this level distance the item is far out of band — tightest ceiling."""
KEEP_CEILING_MID = 10
"""Max kept of a NON-UNIQUE item 5..9 levels above/below the character."""
KEEP_CEILING_FAR = 5
"""Max kept of a NON-UNIQUE item 10+ levels above/below the character."""


def level_distance_keep_ceiling(stats: ItemStats | None, char_level: int) -> int | None:
    """Upper bound on how many of an item to keep, scaled by how far its level
    sits from the character's — "only keep currently useful items". Returns
    `None` for NO ceiling (the base cap stands):

      * UNIQUE items (`tradeable is False` — the API's only bound/unique signal:
        currencies + a few bound gear) are exempt — keep per the base rules.
      * `|item.level - char_level| >= LEVEL_BAND_FAR (10)`  -> KEEP_CEILING_FAR (5)
      * `|item.level - char_level| >= LEVEL_BAND_NEAR (5)`  -> KEEP_CEILING_MID (10)
      * within LEVEL_BAND_NEAR (currently useful)           -> None (no ceiling)

    A missing catalog entry yields `None` (the bot fails loud elsewhere if it
    must act on an unknown item; here we do not impose a ceiling we cannot
    justify). Applied as a `min` clamp ON TOP of the base cap by the cap shell
    and the bank keep-floor — never lifts a cap, only lowers it, and never
    below an equipped/currency floor (those exceed the ceilings)."""
    if stats is None or stats.tradeable is False:
        return None
    distance = abs(stats.level - char_level)
    if distance >= LEVEL_BAND_FAR:
        return KEEP_CEILING_FAR
    if distance >= LEVEL_BAND_NEAR:
        return KEEP_CEILING_MID
    return None


def _is_dominated_pure(peers: Sequence[tuple[bool, bool, bool, int]],
                       slot_count: int) -> bool:
    """Pure core of the dominance walk (the hand model's `Peer` fold,
    formal/Formal/InventoryCaps.lean `isDominatedBy`): each peer carries its
    three criteria verdicts (fits-all-slots, strictly-higher equip value,
    covers-skill-effects) plus its owned count; the item is DOMINATED when
    the qualifying peers' summed owned count meets or exceeds `slot_count`.

    Order-independent by construction (a commutative sum compared to the
    threshold once, at the end): the wrapper iterates an unordered candidate
    SET, and with the production-invariant non-negative owned counts the
    original prefix-sum early return computed exactly this total-sum
    threshold — the full sum is the faithful deterministic semantics."""
    dominator_owned = 0
    for fits, higher, covers, owned in peers:
        if fits and higher and covers:
            dominator_owned = dominator_owned + owned
    return dominator_owned >= slot_count


def useful_quantity_cap(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
    gear_keep: dict[str, int] | None = None,
) -> int:
    """Return the maximum count of `item_code` worth keeping.

    Anything in inventory beyond this is overstock — safe to sell or delete.
    Considers:
      - Largest recipe-demand for this item across all known recipes
      - Current task demand (`state.task_code == item_code` means keep enough
        for completion)
      - Equipped items (always keep at least 1 of each equipped code)

    `gear_keep` is the active-profile gear-demand keep map (spec
    2026-06-28-gear-loadout-profiles): when supplied (profiles-aware mode), the
    EQUIPPABLE keep component is REPLACED by `gear_keep.get(item_code, 0)` — the
    deduped per-code demand across active loadout profiles plus the +1 in-flight
    spare — instead of the blanket `EQUIPPABLE_KEEP=1`. Equippable gear that is
    in no active profile and not in-flight then has keep 0 (becomes reclaimable).
    `None` (the default) keeps the legacy blanket-1 + dominance behavior so every
    pre-migration caller is unchanged.
    """
    # Equipped items: never count below 1
    equipped = {code for code in state.equipment.values() if code}
    return _cap_from_state(item_code, state, game_data, batch_buffer,
                           safety_floor, item_code in equipped, gear_keep)


def _is_equippable_dominated(item_code: str, state: WorldState,
                              game_data: GameData) -> bool:
    """True when strictly-better same-slot peers are owned in numbers
    sufficient to fill every slot this item could fill.

    Dominance is per-(slot, skill-effect-set). A pure combat weapon
    (attack-only, no skill_effects) is dominated by a higher-attack
    pure-combat weapon for the same slot — `wooden_stick` by
    `copper_dagger`. A tool (skill_effects non-empty) is dominated only
    by an item that ALSO carries those same skill_effects at equal-or-
    better magnitude; a combat weapon never dominates a tool because the
    tool's `skill_effects[mining]` is unmatched.

    Multi-slot types (ring×2, artifact×3, utility×2) require enough
    dominator copies to occupy EVERY slot — 1 iron_ring doesn't
    dominate a copper_ring while the bot still needs a second ring to
    wear. The summed owned count (inventory + bank + equipped) of
    qualifying peers must be >= len(slots_for_type).

    This wrapper evaluates each candidate peer's three criteria (the
    strictly-higher test goes through the exact int-typed `gear_value(Rank)`;
    the per-peer GameData stats reads keep it outside the extracted core)
    and hands the verdict list to the extracted `_is_dominated_pure` fold.
    """
    stats = game_data.item_stats(item_code)
    if stats is None:
        return False
    slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
    if not slots:
        return False
    monsters = combat_target_monsters(state, game_data)
    per_monster = bool(monsters) and stats.type_ in game_data.combat_gear_types
    item_vec = _score_vector(stats, monsters, game_data) if per_monster else []
    my_value = gear_value(stats, Rank)
    my_effects = stats.skill_effects or {}
    candidates: set[str] = set(state.inventory)
    if state.bank_items:
        candidates |= set(state.bank_items)
    candidates |= {c for c in state.equipment.values() if c is not None}
    candidates.discard(item_code)
    equipped_codes = [c for c in state.equipment.values() if c is not None]
    bank_items = state.bank_items or {}
    peers: list[tuple[bool, bool, bool, int]] = []
    for peer_code in candidates:
        peer = game_data.item_stats(peer_code)
        if peer is None:
            continue
        peer_slots = ITEM_TYPE_TO_SLOTS.get(peer.type_, [])
        # Peer must fit every slot this item fits (so it can substitute everywhere).
        fits = all(s in peer_slots for s in slots)
        if per_monster and fits:
            higher = pareto_dominates(_score_vector(peer, monsters, game_data), item_vec)
        else:
            higher = gear_value(peer, Rank) > my_value
        # Peer must cover this item's skill_effects (else dropping a tool
        # in favor of a higher-attack weapon would silently lose a skill
        # bonus the bot relies on). Skill effect values are NEGATIVE
        # cooldown-reduction percentages — bigger magnitude wins, so we
        # compare on `abs` (mirrors `tools.tool_value`). A peer without the
        # skill key contributes 0, which fails the abs comparison and
        # disqualifies the peer as a dominator for tool roles.
        peer_effects = peer.skill_effects or {}
        covers = not any(abs(peer_effects.get(skill, 0)) < abs(magnitude)
                         for skill, magnitude in my_effects.items())
        peer_count = (
            state.inventory.get(peer_code, 0)
            + bank_items.get(peer_code, 0)
            + sum(1 for c in equipped_codes if c == peer_code)
        )
        peers.append((fits, higher, covers, peer_count))
    return _is_dominated_pure(peers, len(slots))


def _task_chain_demand_pure(fuel: int, target_item: str, root_item: str,
                            root_qty: int, recipes: Mapping[str, dict[str, int]],
                            visited: dict[str, int]) -> int:
    """Recursive count of `target_item` needed to craft `root_qty` of
    `root_item`. Returns 0 when target isn't reachable from root via the
    recipe chain. Cycle-safe via the `visited` membership map (PER-PATH:
    each child walk gets a copy extended with `root_item`) — without it a
    self-referential recipe (e.g. recycle loops) would recurse forever.
    Fuel-bounded for the extracted Lean image; the `len(recipes) + 1` seed
    is unreachable (every recursing frame marks a distinct key first)."""
    if fuel <= 0:
        return 0
    if target_item == root_item:
        return root_qty
    if visited.get(root_item, 0) == 1:
        return 0
    recipe = recipes.get(root_item, {})
    sub = dict(visited)
    sub[root_item] = 1
    total = 0
    for mat, qty_per in recipe.items():
        total = total + _task_chain_demand_pure(fuel - 1, target_item, mat,
                                                qty_per * root_qty, recipes, sub)
    return total


def useful_quantity_cap_excl_equipped_pure(
    item_code: str, recipe_max: int, batch_buffer: int, safety_floor: int,
    task_type: str, task_code: str, task_total: int, task_progress: int,
    recipes: Mapping[str, dict[str, int]], action_cap: int,
    is_equippable: bool, is_dominated: bool, hp_restore: int,
) -> int:
    """Pure core of `useful_quantity_cap_excl_equipped` over plain data:
    the max of the five cap components (hand model `capExclWith`)."""
    recipe_cap = recipe_max * batch_buffer if recipe_max > 0 else 0
    if recipe_max > 0:
        recipe_cap = max(recipe_cap, safety_floor)

    # Active items-task demand: keep enough to finish the task. Covers two
    # cases: (a) item_code IS the task item (direct match) and (b) item_code
    # is a transitive recipe input for the task item. Without (b) the bot
    # discards mid-chain materials it could have crafted into the task item
    # — e.g. 67 ash_wood deleted while the active task wants 10 more
    # ash_plank that 1:1 require ash_wood (trace 2026-06-05 inv build-up
    # following the apple-delete bug f1f8941). Bank's _keep_codes already
    # protected the chain; DiscardOverstock must apply the same discipline
    # or the two caps diverge and one or the other wastes resources.
    task_cap = 0
    if task_type == "items" and task_code != "":
        remaining = max(0, task_total - task_progress)
        if remaining > 0:
            no_visited: dict[str, int] = {}
            task_cap = _task_chain_demand_pure(len(recipes) + 1, item_code,
                                               task_code, remaining, recipes,
                                               no_visited)

    # Equippable items: keep one of each for the equipment optimizer's
    # candidate pool — unless this code is DOMINATED by another owned
    # item that fills every slot it could and scores strictly higher on
    # equip_value while covering every skill_effect. A dominated item
    # (wooden_stick once copper_dagger is owned) becomes delete-eligible
    # so the discard ladder picks the least-useful redundant weapon
    # first, instead of one-of-each-blindly.
    equippable_cap = 0
    consumable_cap = 0
    if is_equippable and not is_dominated:
        equippable_cap = EQUIPPABLE_KEEP
    if hp_restore > 0:
        consumable_cap = CONSUMABLE_KEEP

    return max(recipe_cap, task_cap, action_cap, equippable_cap, consumable_cap)


def useful_quantity_cap_pure(
    item_code: str, recipe_max: int, batch_buffer: int, safety_floor: int,
    task_type: str, task_code: str, task_total: int, task_progress: int,
    recipes: Mapping[str, dict[str, int]], action_cap: int,
    is_equippable: bool, is_dominated: bool, hp_restore: int,
    equipped: bool,
) -> int:
    """Pure core of `useful_quantity_cap`: the equipped floor of 1 on top of
    the five-component max (hand model `capWith`)."""
    base = useful_quantity_cap_excl_equipped_pure(
        item_code, recipe_max, batch_buffer, safety_floor,
        task_type, task_code, task_total, task_progress,
        recipes, action_cap, is_equippable, is_dominated, hp_restore)
    if equipped:
        return max(1, base)
    return base


def reachable_recipe_demand(item_code: str, state: WorldState, game_data: GameData,
                            horizon: int = RECIPE_SKILL_HORIZON) -> int:
    """The transitive recipe demand for `item_code` (`max_recipe_demand`), EXCEPT
    0 when EVERY direct consumer's recipe is skill-gated more than `horizon`
    levels above the character's current level in that skill — i.e. the material
    has no near-term use and should not reserve inventory space (it becomes
    deposit-eligible). Returns the FULL transitive demand (unchanged behavior)
    for any item with at least one reachable or ungated consumer, so only
    far-future skill-gated materials (gemstones cut at mining@20 while the bot is
    mining@10) are affected."""
    full = game_data.max_recipe_demand(item_code)
    if full <= 0:
        return 0
    for consumer, recipe in game_data.crafting_recipes.items():
        if recipe.get(item_code, 0) <= 0:
            continue
        stats = game_data.item_stats(consumer)
        if stats is None or not stats.crafting_skill:
            return full  # an ungated consumer keeps the material near-term useful
        if stats.crafting_level <= state.skills.get(stats.crafting_skill, 1) + horizon:
            return full  # a skill-reachable consumer keeps it useful
    return 0  # every consumer is gated far above current skill -> not near-term useful


def _cap_from_state(item_code: str, state: WorldState, game_data: GameData,
                    batch_buffer: int, safety_floor: int, equipped: bool,
                    gear_keep: dict[str, int] | None = None) -> int:
    """Assemble the plain-data inputs of `useful_quantity_cap_pure` from the
    GameData/WorldState accessors (the impure shell of the cap decision).

    `gear_keep` (active-profile gear-demand keep map) reroutes the equippable
    keep component: in profiles-aware mode the blanket EQUIPPABLE_KEEP + the
    dominance gate are suppressed (`is_equippable`/`is_dominated` set False) and
    the profile demand `gear_keep.get(item_code, 0)` is injected as a keep floor
    through the `action_cap` slot of the unchanged pure core — un-profiled,
    not-in-flight gear thus drops to keep 0 (reclaimable). Legacy when None."""
    hp_restore = 0
    stats = game_data.item_stats(item_code)
    if stats is not None:
        hp_restore = stats.hp_restore
    action_cap = _non_recipe_keep_floor(item_code, stats)
    if gear_keep is None:
        is_equippable = False
        is_dominated = False
        if stats is not None and ITEM_TYPE_TO_SLOTS.get(stats.type_):
            is_equippable = True
            is_dominated = _is_equippable_dominated(item_code, state, game_data)
    else:
        # Profiles-aware: the active-profile gear demand (+1 in-flight spare)
        # replaces the blanket equippable keep, injected via the action-cap floor.
        is_equippable = False
        is_dominated = False
        gear_floor = gear_keep.get(item_code, 0)
        if gear_floor > action_cap:
            action_cap = gear_floor
    base = useful_quantity_cap_pure(
        item_code, reachable_recipe_demand(item_code, state, game_data), batch_buffer,
        safety_floor, state.task_type or "", state.task_code or "",
        state.task_total, state.task_progress, game_data.crafting_recipes,
        action_cap,
        is_equippable, is_dominated, hp_restore, equipped)
    # "Only keep currently useful items": clamp the base cap by the level-distance
    # ceiling for non-unique items far above/below the character's level.
    ceiling = level_distance_keep_ceiling(stats, state.level)
    if ceiling is not None and base > ceiling:
        return ceiling
    return base


def useful_quantity_cap_excl_equipped(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
    gear_keep: dict[str, int] | None = None,
) -> int:
    """useful_quantity_cap without the equipped-floor adjustment.

    `gear_keep` reroutes the equippable keep to the active-profile gear demand
    (see `useful_quantity_cap`); None keeps the legacy behavior."""
    return _cap_from_state(item_code, state, game_data, batch_buffer,
                           safety_floor, False, gear_keep)


def overstocked_items(
    state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
    watermark: tuple[int, int] = (DISCARD_WATERMARK_NUM, DISCARD_WATERMARK_DEN),
) -> dict[str, int]:
    """Return {item_code: excess_quantity} for every item held beyond its USEFUL
    quantity, under genuine space pressure.

    SPACE-DRIVEN (spec 2026-06-07). An item is overstock only when the bag is under
    real space pressure (`inventory_used / inventory_max >= watermark`) AND `held`
    exceeds `useful_quantity_cap`. Below the watermark — with free slots — NOTHING is
    overstock, so the per-item cap is not a space-blind dump trigger.

    THIS IS A GATE, NOT A PROTECTION (item-protection-authority epic, Task 9). It
    answers "WHEN is the bag full enough to start shedding, and which items are past
    their useful quantity" — the useful cap is a heuristic, and the `profile` code-set
    closure that used to be merged in here (`guards.active_profile`, rooted on the
    `target_gear | target_tools` blanket) is GONE. WHAT may actually be shed, and HOW
    MANY copies, is the keep authority's answer alone: `ai/discard_surplus`
    intersects this gate with `min(bankable, destroyable)`.
    """
    used = state.inventory_used
    cap = state.inventory_max
    # SLOTS-FULL livelock fix (Task 7, slot-aware-inventory-room): 20/20
    # distinct stacks full but low total QUANTITY never crosses the
    # `used/cap >= watermark` pressure gate on quantity alone, so overstock
    # relief never engages even though slots are the binding constraint.
    # Rather than adding a new branch to the proven `overstock_excess` core
    # (formal/Formal/InventoryProfile.lean `overstockExcess`/`underPressure`,
    # differentially tested in formal/diff/test_inventory_profile_diff.py),
    # feed it `used = cap` — forcing its ALREADY-PROVEN full-pressure branch
    # via a substitution within the core's existing universally-quantified
    # `used`/`cap` domain. No Lean mirror change needed.
    if cap > 0 and state.inventory_slots_free == 0:
        used = cap
    watermark_num, watermark_den = watermark
    excess: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        useful_floor = useful_quantity_cap(code, state, game_data, batch_buffer, safety_floor)
        over = overstock_excess(qty, 0, useful_floor,
                                used, cap, watermark_num, watermark_den)
        if over > 0:
            excess[code] = over
    return excess
