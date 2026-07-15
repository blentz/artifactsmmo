"""Pure prerequisite edges over Tier-2 meta-goals — the P3 search substrate.

`prerequisites(node, state, game_data)` returns a node's DIRECT prerequisites,
derived only from game data. Gathering and unknown-source items are leaves so
chains terminate; cycles (if any) are left for P3's visited-set traversal."""

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import SourceKind, obtain_sources
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
)
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


def prerequisites(node: MetaGoal, state: WorldState, game_data: GameData,
                  ctx: SelectionContext = NO_PROFILE_CONTEXT) -> list[MetaGoal]:
    """Direct prerequisites of `node`, derived from game data.

    A craftable material with ANY READY non-craft source — a bank withdraw, a
    recyclable licensed surplus, a live gather, a located permanent vendor, or a
    winnable drop, per the shared `ai/obtain_sources` model — is a LEAF: directly
    actionable, so the descent does NOT fall into its recipe. Only when the
    SOLE source is CRAFT (or there is no source at all) does the descent
    continue into the recipe's ingredients.

    Without this, the descent re-derives from raw resources what the bag already
    holds in crafted form: live 2026-07-13, ObtainItem(ash_plank) descended to
    ObtainItem(ash_wood, 10) and the bot chopped 50 ash_wood at 1/cycle (~56 cycles
    of WOODCUTTING xp while the weaponcrafting grind it was serving stayed frozen)
    — while holding 7 fishing_net, whose recipe IS 6 ash_plank each (originally
    fixed by a bespoke `recoverable: Mapping[str, int]` RECYCLE-only map; the
    one-obtain-model epic generalizes the same leaf rule to every ready source).

    The leaf rule is "a source EXISTS", not "fully covers the need": GOAP mixes
    the ready source with gather/craft to make up any shortfall, finding the true
    optimum rather than an all-or-nothing cliff."""
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
            sources = obtain_sources(node.code, state, game_data, ctx)
            if any(s.kind is not SourceKind.CRAFT for s in sources):
                return []  # a ready non-craft source exists → LEAF
            # An ObtainItem's prereqs are just its material ObtainItems. The
            # crafting-skill gate is no longer emitted as a prerequisite node:
            # under-skill gear is grinded planner-natively by UpgradeEquipmentGoal
            # via the LevelSkill action (epic P3), not by a tree-level skill root.
            return [ObtainItem(mat, qty) for mat, qty in recipe.items()]
        return []  # buyable / monster-drop / gatherable / unknown → leaf
    if isinstance(node, ReachCharLevel):
        if combat_capable(state, game_data):
            return []
        weapon = best_attainable_weapon(game_data)
        return [ObtainItem(weapon)] if weapon is not None else []
    return []


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


# NOTE: `objective_roots` (the Tier-1 objective expressed as P3 search roots)
# was retired in progression-tree Phase 4b Task 5 — the flat-ranking search it
# fed was deleted in Task-1's THE FLIP, leaving zero callers (tiers/__init__
# re-export only). `_CHAR_LEVEL_BOOTSTRAP_HORIZON` above stays: it is a live
# formal/diff anchor (test_objective_step_is_fight_diff.py,
# ObjectiveStepFight.lean) independent of the deleted function.
