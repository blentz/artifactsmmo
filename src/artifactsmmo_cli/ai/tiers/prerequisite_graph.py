"""Pure prerequisite edges over Tier-2 meta-goals — the P3 search substrate.

`prerequisites(node, state, game_data)` returns a node's DIRECT prerequisites,
derived only from game data. Gathering and unknown-source items are leaves so
chains terminate; cycles (if any) are left for P3's visited-set traversal."""

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.world_state import WorldState


def combat_capable(state: WorldState, game_data: GameData) -> bool:
    """True when some monster is stat-beatable with the best on-hand loadout,
    using the shared `predict_win` verdict (gear + damage formula). Replaces the
    old `monster_level <= char_level + 1` proxy so the prerequisite graph agrees
    with FightAction / runtime target selection on what 'beatable' means."""
    return any(predict_win(state, game_data, code) for code in game_data.monster_levels)


def best_attainable_weapon(game_data: GameData) -> str | None:
    """Highest equip_value weapon in the item table (ties broken by code), or
    None when there are no weapons."""
    best: tuple[int, str] | None = None  # P4a: equip_value is exact int
    for code, stats in game_data.all_item_stats.items():
        if stats.type_ != "weapon":
            continue
        value = equip_value(stats)
        if best is None or value > best[0] or (value == best[0] and code < best[1]):
            best = (value, code)
    return best[1] if best else None


def prerequisites(node: MetaGoal, state: WorldState, game_data: GameData) -> list[MetaGoal]:
    """Direct prerequisites of `node`, derived from game data."""
    if isinstance(node, ObtainItem):
        if node.is_satisfied(state, game_data):
            return []
        # For equippables: if the item is already OWNED (in inventory or
        # bank) but not yet equipped, no recipe descent is needed — the
        # only remaining step is the equip itself. Without this guard,
        # the prereq tree falls into the recipe (which consumed its
        # inputs during the original craft) and the bot would re-gather
        # mats to build a second copy. The arbiter's UpgradeEquipmentGoal
        # plans the EquipAction for the existing copy via the empty
        # prereq path.
        equipped_codes = [c for c in state.equipment.values() if c is not None]
        if owned_count_pure(
            state.inventory, state.bank_items, equipped_codes, node.code,
        ) >= node.quantity:
            return []
        recipe = game_data.crafting_recipe(node.code)
        if recipe is not None:
            prereqs: list[MetaGoal] = []
            stats = game_data.item_stats(node.code)
            if stats is not None and stats.crafting_skill:
                prereqs.append(ReachSkillLevel(stats.crafting_skill, stats.crafting_level))
            prereqs.extend(ObtainItem(mat, qty) for mat, qty in recipe.items())
            return prereqs
        for res_code, drop in game_data.resource_drops.items():
            if drop == node.code:
                skill_level = game_data.resource_skill_level(res_code)
                if skill_level is not None:
                    return [ReachSkillLevel(skill_level[0], skill_level[1])]
        return []  # buyable / monster-drop / unknown → leaf
    if isinstance(node, ReachCharLevel):
        if combat_capable(state, game_data):
            return []
        weapon = best_attainable_weapon(game_data)
        return [ObtainItem(weapon)] if weapon is not None else []
    return []  # ReachSkillLevel → leaf (materials enter via ObtainItem chains)


_CHAR_LEVEL_BOOTSTRAP_HORIZON = 2
"""Look-ahead for the character-level bootstrap root. When `state.level <
target_char_level`, prepend a `ReachCharLevel(current + _HORIZON)` root so
GrindCharacterXP gets a low-effort competitor that ranks above
gear-chain ObtainItems.

Trace 2026-06-03/05 (3 days): Robby was last seen in combat 2026-06-03
01:45 when he dinged level 3. After that NO fights at all across ~3300
cycles — bot stuck at level 3, xp 6/350, every fight-XP-gain event
attributed to L1 or L2. Root cause: `ReachCharLevel(50)` has effort=47
and consistently loses Tier-1 ranking to small-effort gear/tool roots
(unmet_closure_size ~6-30). The bot funded gear progress via tasks
forever and never bothered combat. A bootstrap root with effort=2
restores combat parity without overriding the long-term goal —
GrindCharacterXP fires until level rises +2, then a new bootstrap
auto-emits at the next horizon. Removed once current_level + horizon >=
target_char_level (we're already in the home stretch)."""


def objective_roots(
    objective: CharacterObjective,
    state: WorldState | None = None,
) -> list[MetaGoal]:
    """The Tier-1 objective expressed as root meta-goals for P3's search.

    Tools (target_tools) are emitted alongside combat gear (target_gear).
    Both compete for the weapon_slot in the equipment layer; the planner
    pursues whichever currently scores higher in the Tier-2 ranking,
    and OptimizeLoadout swaps the active item per the current task's
    gathering-skill needs.

    Standalone `ReachSkillLevel` ROOTS are no longer emitted (progression-tree
    Phase 4b Task 2): skills are pure prerequisites — a skill enters the search
    only as a prereq/step inside a gear/char chain (`prerequisites`,
    `skill_target_curve`-derived steps), never as its own top-level objective."""
    roots: list[MetaGoal] = [ReachCharLevel(objective.target_char_level)]
    if state is not None:
        # Char-level bootstrap: gap-2 root competing with gear chains so
        # GrindCharacterXP actually fires. See _CHAR_LEVEL_BOOTSTRAP_HORIZON.
        char_horizon = state.level + _CHAR_LEVEL_BOOTSTRAP_HORIZON
        if char_horizon < objective.target_char_level:
            roots.append(ReachCharLevel(char_horizon))
        # Near-term gear: best usable-at-level upgrade per slot. The BiS
        # target_gear roots below are unreachable at low level (filtered by
        # is_reachable), which left the gear category with no live candidate —
        # the 2026-06-11 gear-starvation treadmill. See
        # CharacterObjective.near_term_gear.
        roots.extend(ObtainItem(code, slot=slot)
                     for slot, code in objective.near_term_gear(state).items())
        # Utility potions are judged by EFFECT, not level (see
        # utility_potion_targets / bootstrap_potion_target): the single
        # effect-based heal root is emitted at every level — including
        # bootstrap, where the level-gated near_term_gear emits nothing.
        roots.extend(ObtainItem(code, slot=slot)
                     for slot, code in objective.utility_potion_targets(state).items())
    roots.extend(ObtainItem(code, slot=slot) for slot, code in objective.target_gear.items())
    roots.extend(ObtainItem(code) for code in objective.target_tools.values())
    # A near-term target can coincide with a BiS/tool target; one root each.
    seen: set[MetaGoal] = set()
    deduped: list[MetaGoal] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            deduped.append(root)
    return deduped
