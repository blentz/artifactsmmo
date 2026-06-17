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

EXACT VALUE SEAM (P3c, closing the P3b float-boundary note): `_equip_value`
now returns `int` — every summand (attack, resistance, hp_restore) is an int,
so the strictly-higher dominance criterion is EXACT integer arithmetic with no
float seam. It still stays OUTSIDE the extracted core as data plumbing
(`_is_equippable_dominated` evaluates each peer's criteria into plain bools
and hands `_is_dominated_pure` the verdict list, exactly the hand model's
`Peer` encoding — the hand model has always taken the verdicts as Bools).
The tiers-side `tiers/equip_value.equip_value` (augmented combat formula) and
the wider float-typed equipment-scoring system are deliberately NOT cascaded —
see the P3c scope note in docs/PLAN_mechanical_extraction.md.
"""

from collections.abc import Mapping, Sequence

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

BATCH_BUFFER = 5
"""How many craft batches worth of material to keep on hand. With BATCH=5 and
a recipe needing 6 of a mat, the cap is 30."""

SAFETY_FLOOR = 3
"""Always keep at least this many of any item that has any recipe use, so the
bot doesn't immediately re-gather what it just discarded."""

# The high watermark, kept as an EXACT integer ratio (17/20 = 0.85). The
# overstock decision compares `used / cap >= num / den` by cross-multiplication
# over integers — exact, no float drift at the boundary (mirrored by the proved
# Lean core overstockExcess in formal/Formal/InventoryProfile.lean).
DISCARD_WATERMARK_NUM = 17
DISCARD_WATERMARK_DEN = 20
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
    watermark_num: int = DISCARD_WATERMARK_NUM,
    watermark_den: int = DISCARD_WATERMARK_DEN,
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
) -> int:
    """Return the maximum count of `item_code` worth keeping.

    Anything in inventory beyond this is overstock — safe to sell or delete.
    Considers:
      - Largest recipe-demand for this item across all known recipes
      - Current task demand (`state.task_code == item_code` means keep enough
        for completion)
      - Equipped items (always keep at least 1 of each equipped code)
    """
    # Equipped items: never count below 1
    equipped = {code for code in state.equipment.values() if code}
    return _cap_from_state(item_code, state, game_data, batch_buffer,
                           safety_floor, item_code in equipped)


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
    strictly-higher test goes through the exact int-typed `_equip_value`;
    the per-peer GameData stats reads keep it outside the extracted core)
    and hands the verdict list to the extracted `_is_dominated_pure` fold.
    """
    stats = game_data.item_stats(item_code)
    if stats is None:
        return False
    slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
    if not slots:
        return False
    my_value = _equip_value(stats)
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
        higher = _equip_value(peer) > my_value
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


def _equip_value(stats: ItemStats) -> int:
    """Dominance-gate equip value: attack + resistance + hp_restore + hp_bonus +
    wisdom + prospecting — kept local here to avoid a tiers→inventory_caps import
    cycle. EXACT integer arithmetic (P3c): every summand is an int, so the
    strictly-higher comparison feeding the dominance Bool is exact.

    Includes the flat utility stats (hp_bonus/wisdom/prospecting) so a
    utility-only ARTIFACT (novice_guide: attack/resistance/hp_restore all 0,
    wisdom 25, prospecting 25, hp_bonus 25) is no longer valued 0 → no longer
    trivially dominated → no longer discarded as worthless overstock (the
    Delete(novice_guide×4) bug, trace 2026-06-15). Mirrors the contributors the
    augmented `tiers/equip_value.equip_value` ranks on."""
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    hp = stats.hp_restore
    return (attack + resistance + hp + stats.hp_bonus + stats.wisdom
            + stats.prospecting + stats.inventory_space + stats.haste + stats.lifesteal
            + stats.combat_buff)


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


def _cap_from_state(item_code: str, state: WorldState, game_data: GameData,
                    batch_buffer: int, safety_floor: int, equipped: bool) -> int:
    """Assemble the plain-data inputs of `useful_quantity_cap_pure` from the
    GameData/WorldState accessors (the impure shell of the cap decision)."""
    is_equippable = False
    is_dominated = False
    hp_restore = 0
    stats = game_data.item_stats(item_code)
    if stats is not None:
        if ITEM_TYPE_TO_SLOTS.get(stats.type_):
            is_equippable = True
            is_dominated = _is_equippable_dominated(item_code, state, game_data)
        hp_restore = stats.hp_restore
    return useful_quantity_cap_pure(
        item_code, game_data.max_recipe_demand(item_code), batch_buffer,
        safety_floor, state.task_type or "", state.task_code or "",
        state.task_total, state.task_progress, game_data.crafting_recipes,
        ACTION_CONSUMABLES_CAP.get(item_code, 0),
        is_equippable, is_dominated, hp_restore, equipped)


def useful_quantity_cap_excl_equipped(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
) -> int:
    """useful_quantity_cap without the equipped-floor adjustment."""
    return _cap_from_state(item_code, state, game_data, batch_buffer,
                           safety_floor, False)


def overstocked_items(
    state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
    profile: dict[str, int] | None = None,
    watermark: tuple[int, int] = (DISCARD_WATERMARK_NUM, DISCARD_WATERMARK_DEN),
) -> dict[str, int]:
    """Return {item_code: excess_quantity} for every overstocked item.

    SPACE-DRIVEN + profile-preserving (spec 2026-06-07). An item is overstock
    only when the bag is under real space pressure
    (`inventory_used / inventory_max >= watermark`) AND `held` exceeds the
    protected floor `max(profile_target, useful_quantity_cap)`. Below the
    watermark — with free slots — NOTHING is overstock, so the per-item
    `useful_quantity_cap` is no longer a space-blind dump trigger; it only
    tiebreaks WHICH overstock to shed once the bag is genuinely full. An item
    at or below its profile target is never overstock (the active goal's
    materials are protected).

    `profile` is the active goal's soft target map (item_code -> target_qty);
    `None`/absent means an empty profile (the per-item useful floor still
    applies under pressure).
    """
    profile = profile or {}
    used = state.inventory_used
    cap = state.inventory_max
    watermark_num, watermark_den = watermark
    excess: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        useful_floor = useful_quantity_cap(code, state, game_data, batch_buffer, safety_floor)
        over = overstock_excess(qty, profile.get(code, 0), useful_floor,
                                used, cap, watermark_num, watermark_den)
        if over > 0:
            excess[code] = over
    return excess
