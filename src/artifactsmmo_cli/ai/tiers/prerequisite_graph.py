"""Pure prerequisite edges over Tier-2 meta-goals — the P3 search substrate.

`prerequisites(node, state, game_data)` returns a node's DIRECT prerequisites,
derived only from game data. Gathering and unknown-source items are leaves so
chains terminate; cycles (if any) are left for P3's visited-set traversal."""

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind, obtain_sources
from artifactsmmo_cli.ai.requirement_projections import requirement_edges
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    META_GOAL_KINDS,
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_SUBSTITUTE_KINDS = frozenset({SourceKind.BUY, SourceKind.GE_FILL})
"""Sources that hand over the finished item INSTEAD of crafting it, and that
`grind_probe_state` cannot take away.

Under a `grind_descent` these must not leaf (see `_source_leafs`). A skill grind
earns its XP from the CRAFT — the item is the byproduct, not the goal — so a
route that substitutes for the craft serves the grind's target and not the
grind. RECYCLE is a craft-substitute too and has its own value-aware arm below.

WHY THESE TWO AND NOT `GATHER`/`DROP`/`WITHDRAW`: `grind_probe_state` strips the
rung from inventory, bank AND equipment, which neutralises the WITHDRAW and
owned/worn leaf arms outright. It cannot neutralise these two — an NPC vendor is
permanent and a stranger's standing GE order is not ours to remove — so they are
exactly the substitutes that survive the probe. GATHER and DROP are not on the
list because a rung is a crafted item and generally has neither; widening to
them would be unmotivated (a `_leafs` arm above already leafs anything with no
recipe at all).

LIVE 2026-08-24, Robby: `obtain_sources` emits a GE_FILL for any item with a
standing Grand Exchange sell order, and the snapshot carried one for 21 of the
23 gearcrafting rungs at level <= 15. So the descent leafed AT the rung,
`prerequisites` returned [], `actionable_step` handed the rung back unchanged
and `next_grind_goal` fell through to the from-scratch `GatherMaterials(rung,
held+1)` the descent exists to prevent — 63k nodes and a timeout offline,
matching the live 42,277-node error:other signature. `ReachSkill(gearcrafting
->16)` was selected 32 times over 3.5h and the skill never moved."""

RECYCLE_LEAF_VALUE_FLOOR = 256_000_000
"""pursuit_value below which a recyclable item is JUNK (obsolete gear) a skill
grind may recover cheaply, vs CURRENT-TIER gear it must not churn. Only consulted
under a `grind_descent` (see `prerequisites`): a RECYCLE source leafs a material
iff the recycled item's pursuit_value is below this floor.

THE ONE absolute pursuit_value threshold in the codebase, so it is re-derived
whenever that ruler's scale moves. Calibrated exactly as before, against the
same four live witnesses, at the current scale: obsolete fishing_net / copper_axe
score 200_000_000 and must recover; current-tier wooden_staff (328_001_000) and
fire_staff (656_001_000) must be skipped so the grind gathers fresh. The floor is
the geometric mean of the two adjacent witnesses (√(200.0M × 328.0M) = 256.1M),
the same midpoint rule the retired 10000 satisfied on the retired scale
(√(8000 × 13000) = 10198). `tests/test_ai/test_pursuit_value.py` pins all four
witnesses against the catalog bundle, so a scale change fails the suite instead
of silently reclassifying every recyclable.

RE-DERIVED AND UNCHANGED when `equipment/scoring.RULER_SCALE` moved onto the
armor terms. This threshold reads `pursuit_value`, whose COMBAT term is
`gear_components(stats, Rank)[0]`, and all four calibration witnesses are
WEAPONS — whose combat term that change left bit-identical (the factor was
already on the weapon side; what moved was the ARMOR side, up to meet it). So
the geometric mean is the same number it was: √(200.0M × 328.0M) = 256.1M.

What DID move is armor, by design: 55 armor items (level-35/40 shields, books
and amulets among them) now sit above the floor where they used to sit below it,
because they were being measured on a ruler that priced them at HALF a weapon's
magnitude for the same real swing. Classifying a level-40 shield as junk
relative to a level-6 staff was the asymmetry, not the floor.

Tunable — a proxy for 'current-tier', not load-bearing for correctness; the
null-cycle guard (GatherMaterialsGoal.exclude_recycle) protects the rung
independently."""


def _source_leafs(source: Source, game_data: GameData,
                  grind_descent: bool) -> bool:
    """Whether `source` makes its material a descent LEAF. CRAFT never leafs (the
    descent walks the recipe). Every other kind leafs — EXCEPT under a
    `grind_descent`, where THE CRAFT IS THE GOAL and a source that SUBSTITUTES
    for it therefore must not end the descent:

      * `CRAFT_SUBSTITUTE_KINDS` (BUY / GE_FILL) never leaf. Buying the rung
        pays zero skill XP.
      * a RECYCLE leafs only when the recycled item is JUNK (pursuit_value <
        RECYCLE_LEAF_VALUE_FLOOR — cheap recovery). A CURRENT-TIER item does not
        leaf: the grind descends to gather rather than churn it.

    The one rule, two arms: RECYCLE is the value-aware substitute, BUY/GE_FILL
    the unconditional ones. The predicate previously carved out only RECYCLE —
    the special case, not the rule — which is the 2026-08-24 Robby stall
    documented on `CRAFT_SUBSTITUTE_KINDS`."""
    if source.kind is SourceKind.CRAFT:
        return False
    if grind_descent:
        if source.kind is SourceKind.RECYCLE:
            stats = game_data.item_stats(source.code)
            return stats is not None and pursuit_value(stats) < RECYCLE_LEAF_VALUE_FLOOR
        if source.kind in CRAFT_SUBSTITUTE_KINDS:
            return False
    return True


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
                  ctx: SelectionContext = NO_PROFILE_CONTEXT,
                  grind_descent: bool = False) -> list[MetaGoal]:
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
        # Axis-2 (spec §4.2): state-truncation is a PREDICATE fed to the graph's
        # one-ply `requirement_edges`, not logic baked into the walk. `_leafs`
        # returns True when `node` is directly actionable — so the descent does
        # NOT fall into its recipe — for exactly the reasons the old branch did:
        #   * already satisfied, or already OWNED (equippable held-not-equipped:
        #     the only remaining step is the equip, so re-descending the recipe
        #     would re-gather mats to build a second copy — UpgradeEquipmentGoal
        #     plans the EquipAction via this empty prereq path);
        #   * a READY non-craft source exists (withdraw / licensed recycle / live
        #     gather / located vendor / winnable drop) per the shared
        #     `obtain_sources` model.
        # `grind_descent` (set by a SKILL GRIND) suspends the leaf for every
        # source that SUBSTITUTES for the craft, because under a grind the CRAFT
        # is the goal and the item only its byproduct: BUY and GE_FILL never
        # leaf, and RECYCLE leafing becomes VALUE-AWARE — a grind gathers
        # materials fresh rather than churning CURRENT-TIER gear (pursuit_value
        # >= RECYCLE_LEAF_VALUE_FLOOR) but still recovers surplus JUNK cheaply.
        # See `_source_leafs` / `CRAFT_SUBSTITUTE_KINDS`. The rung itself is
        # forbidden separately by GatherMaterialsGoal.exclude_recycle (null cycle).
        # `requirement_edges` only ever queries `node.code` (one ply), so `_leafs`
        # is called with that item alone; the skill-gate is NOT emitted as a prereq
        # (under-skill gear grinds planner-natively via LevelSkill, epic P3).
        def _leafs(item: str) -> bool:
            if node.is_satisfied(state, game_data):
                return True
            equipped_codes = [c for c in state.equipment.values() if c is not None]
            if owned_count_pure(
                state.inventory, state.bank_items, equipped_codes, node.code,
            ) >= node.quantity:
                return True
            if game_data.crafting_recipe(node.code) is None:
                return True  # buyable / drop / gatherable / unknown → leaf
            sources = obtain_sources(node.code, state, game_data, ctx)
            return any(_source_leafs(s, game_data, grind_descent)
                       for s in sources)

        graph = game_data.requirement_graph.graph()
        edges = requirement_edges(graph, node.code, _leafs)
        return [ObtainItem(mat, qty) for mat, qty in edges.items()]
    if isinstance(node, ReachCharLevel):
        if combat_capable(state, game_data):
            return []
        weapon = best_attainable_weapon(game_data)
        return [ObtainItem(weapon)] if weapon is not None else []
    if isinstance(node, ReachSkillLevel):
        # A skill climb has no MetaGoal prerequisites — LevelSkill /
        # ReachSkillGoal owns the sub-plan (§5.1).
        return []
    # Fail loudly rather than silently reporting "no prerequisites" for a kind
    # this dispatch does not know (fix-round-1, task 2 review): the trailing
    # `assert not isinstance(...)` distinguishes a truly foreign node from the
    # DRIFT case — a variant registered in META_GOAL_KINDS but never given its
    # own arm above — so the message tells a future maintainer which mistake
    # they made.
    assert not isinstance(node, META_GOAL_KINDS), (
        f"{node!r} is registered in META_GOAL_KINDS but prerequisites() has "
        f"no arm for it")
    raise AssertionError(f"unhandled MetaGoal kind: {node!r}")


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
