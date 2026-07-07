"""Tier-3 strategy engine: rank Tier-1 roots and descend to the nearest
actionable subgoal. Pure; P3a runs it in shadow (traced, not enacted)."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import expected_yield_per_cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers import progression_tree
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE, strategic_value
from artifactsmmo_cli.ai.tiers.strategic_weights import strategic_weights
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from artifactsmmo_cli.ai.tiers.objective import GOLD, CharacterObjective, _permanent_vendor_purchases
from artifactsmmo_cli.ai.tiers.personality import Personality
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    balancing as _balancing_pure,
)
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    blend_weight,
)
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    learned_blend as _learned_blend_pure,
)
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.potion_supply import bootstrap_potion_target
from artifactsmmo_cli.ai.thresholds import (
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState

# P4a: all score constants are exact Fractions — the ranking pipeline
# (_base_prior * _marginal * _balancing, the learned blend, the sticky
# dominance test and the decide sort key) computes over exact rationals, no float
# rounding. Near-ties that float arithmetic happened to (un)equalize now
# resolve exactly; exact is the spec.
PRIOR_CHAR_LEVEL = Fraction(1)
PRIOR_COMBAT_GEAR = Fraction(1)
PRIOR_UTILITY_GEAR = Fraction(2, 5)
PRIOR_COMBAT_CRAFT_SKILL = Fraction(3, 5)
PRIOR_GATHER_SKILL = Fraction(2, 5)
PRIOR_CONSUMABLE_SKILL = Fraction(3, 10)
SKILL_MARGINAL = Fraction(1, 5)
SKILL_GAP_PER_LEVEL = Fraction(1)
"""Per-level catch-up boost on a NEAR-TERM (below-endgame) skill root's
marginal. With PRIOR_COMBAT_CRAFT_SKILL=3/5 and balancing 1: gap 1 → marginal 1.2,
gap ≥ 1.5 → marginal 1.7 (capped by SKILL_GAP_CAP). General skill-XP grinding is
deliberately a low-priority backstop: at typical balancing (~1) a near-term skill
root scores ~0.6×1.7×1 ≈ 1.0, below combat gear and the level+2 char bootstrap
(1.48). A specific gear's skill requirement is still driven by that gear's
ObtainItem closure (the prereq-chain), and a badly-lagging skill is still lifted
by the balancing multiplier — this only stops general grinding from out-ranking
the real objectives."""
SKILL_GAP_CAP = Fraction(3, 2)
"""Cap on the boosted gap so general near-term skill roots can't dominate gear /
char. Lowered from 3 to 1.5 on 2026-06-14: skill-leveling was over-weighting to
the recipe-curve target (e.g. ranking ReachSkillLevel(...,5) above committed
gear). 1.5 is a starting calibration."""
CHAR_MARGINAL = Fraction(1)
"""Base char-level marginal (multiplier on PRIOR_CHAR_LEVEL=1.0). The
DYNAMIC marginal applied at `_marginal` scales upward with the gap
between current state.level and the root's target — see `_marginal`."""

CHAR_REACHABLE_HORIZON = 10
"""Char-level horizon for the urgency boost — gaps within this window
are scored as "actionable now". The bootstrap root
(`ReachCharLevel(state.level + 2)`, gap=2) sits at the steep end; the
long-haul `ReachCharLevel(50)` at L3 (gap 47) is outside the horizon
and gets no bonus. This makes the SHORT-horizon root rank above tool
roots (matching the user's request to grind monsters when the bot is
behind) while the long-haul root yields to the bootstrap so the
e27779e stand-down doesn't trigger on the LONG step.level."""

CHAR_GAP_PER_LEVEL = Fraction(3, 50)
"""Per-level urgency for char-level roots WITHIN the reachable horizon,
used WHILE a combat armor slot is still empty (gear-first). For a bootstrap
gap of 2: bonus = (10 - 2) × 0.06 = 0.48 → marginal = 1.48 → value = 1.48,
beating PRIOR_RELEVANT_TOOL (1.1) so GrindCharacterXP fires when the bot is
under-leveled — but staying below the empty-slot armor urgency (2.5 / sticky
×3/2 = 2.22) so filling an empty combat slot still wins. For gaps outside the
horizon: bonus = 0, marginal stays at CHAR_MARGINAL (1.0)."""

CHAR_GAP_PER_LEVEL_GEARED = Fraction(5, 32)
"""Per-level char-level urgency once every fillable combat ARMOR slot is
equipped (`_has_empty_armor_slot` is False). For a bootstrap gap of 2:
bonus = (10 - 2) × 5/32 = 1.25 → marginal = 2.25 → value = 2.25, so
character leveling out-ranks general skill-XP grinding (≈2.04) once the bot
is geared. While an armor slot is still empty the lower CHAR_GAP_PER_LEVEL
applies, preserving the empty-slot-armor-dominates invariant without touching
EMPTY_SLOT_URGENCY (2026-06-14, surgical: bump only after slots are filled)."""

CHAR_CAPSTONE_SCALE = Fraction(2, 5)
"""Weak long-range attractor for the L50 capstone (ReachCharLevel(target)) when
its gap exceeds CHAR_REACHABLE_HORIZON. Scales with progress (level/target) from
~1.08 (L10) to ~1.32 (L40), staying strictly below the +2 bootstrap (1.48) so it
never triggers the e27779e items-task stand-down and below EMPTY_SLOT_URGENCY so
gear-first holds — but non-flat, so the capstone can win flat windows and the bot
is pulled toward 50 instead of only local +2 hops."""

GEAR_EQUIP_SCALE = Fraction(20) * STRATEGIC_SCALE
"""Normalizes gear strategic-value gain to ~[0,1]; tune so a first-tier upgrade
~0.7-0.9. Scaled by STRATEGIC_SCALE (1000) because `_equip_gain` now measures the
gain in strategic_value's fixed-point units (combat stats × SCALE) rather than raw
equip_value, so combat-gear marginals keep the same ~[0,1] gradation as before."""
STICKY_DOMINANCE_RATIO = Fraction(3, 2)
"""Tier-2 sticky-commitment threshold. The previous cycle's chosen_root is
kept unless a new top candidate's score strictly exceeds
`STICKY_DOMINANCE_RATIO * sticky_score`. Matches Tier-3 means-tier
commitment: only switch when the new winner dominates by 50%+. Prevents
single-cycle objective flap from transient predicate flips (e.g.
combat_capable=False momentarily because pick_loadout's inventory
projection changes when inventory composition shifts)."""
PRIOR_RELEVANT_TOOL = Fraction(11, 10)
"""Active-task tool boost: a target_tools item whose skill_effects match
the bot's currently-active gathering skill (state.task_code resolved via
`game_data.active_gathering_skills`) gets this prior, BEATING
PRIOR_CHAR_LEVEL=1.0 so the bot crafts the tool before continuing the
grind. Without this boost, target_tools items scored at static
PRIOR_UTILITY_GEAR=0.4 * marginal=0=0 (or PRIOR_UTILITY_GEAR*0.25
fallback=0.1) and the bot never crafted any tool despite hours of
gathering. Fix shipped after trace cycle 760 evidence of static
0.1 tool scoring."""
COMBAT_READINESS_URGENCY = Fraction(2)
"""Multiplier applied to the combat-enabling weapon root's marginal while the
character is not combat-capable (combat_monster is None). Sized to lift the weapon
root above competing gear/tool/skill/char roots so it becomes chosen_root — the
binding objective that unblocks combat. Switches off once a weapon makes the bot
combat-capable (no permanent override of the long-term objective)."""
EMPTY_SLOT_URGENCY = Fraction(5, 2)
"""Multiplier on the marginal of a combat-gear root that would fill an EMPTY
slot with an item usable at the current character level. Runtime bridge for
the kernel-proved `Formal.GearPolicy.armor_strictly_dominates_empty_slot` —
the proof needs a live armor candidate to dominate, and before near_term_gear
none existed. Sized to beat the char-level bootstrap THROUGH the sticky
commitment: bootstrap scores 1.48 and sticky holds unless the challenger
exceeds STICKY_DOMINANCE_RATIO (3/2) x 1.48 = 2.22; 5/2 = 2.5 > 2.22.
Switches off the moment the slot is filled (root satisfied → removed)."""
OCCUPIED_SLOT_UPGRADE_URGENCY = Fraction(5, 2)
"""Urgency for replacing an OCCUPIED combat armor slot when the candidate beats
the equipped item by at least GEAR_EQUIP_SCALE (a ~2x strategic-value jump).
Ties EMPTY_SLOT_URGENCY so a large upgrade interrupts grinding/leveling and the
bot re-gears (copper->iron). Self-limits: per-tier gains shrink below the gate as
gear improves, so char-leveling resumes once well-geared. Gate at
gain >= GEAR_EQUIP_SCALE keeps minor upgrades from winning."""
BAG_SLOT_URGENCY = Fraction(1)
"""Empty-bag-slot marginal floor (2026-07-03). Strictly below
COMBAT_READINESS_URGENCY (2) and EMPTY_SLOT_URGENCY (5/2) so a weapon / empty
combat armor slot always outranks the bag, but non-zero so the bag is pursued
when no combat/gear upgrade is servable. A bag's strategic_value is 0 when the
learned inventory_weight is cold, so this floors the marginal directly. The
funding route (ReachCurrencyGoal) + sticky commitment then acquire the satchel.
See docs/superpowers/specs/2026-07-03-satchel-bag-acquisition-priority-design.md."""
POTION_SUPPLY_URGENCY = EMPTY_SLOT_URGENCY * PRIOR_COMBAT_GEAR / PRIOR_UTILITY_GEAR
"""Urgency multiplier on an under-stocked health-potion utility root's marginal.
Derived so PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == PRIOR_COMBAT_GEAR *
EMPTY_SLOT_URGENCY = 2.5 — an under-baseline heal potion ties an empty combat
slot at the top of the bootstrap band. Expressed as the ratio (not a literal
25/4) so it stays pinned to combat-gear-equivalent urgency if the priors are
retuned. Fires only while equipped heal-potion qty < potion_baseline (level-
scaled); breaks the alchemy-1→5 deadlock so the CraftPotions guard can then
maintain the stack. See docs/superpowers/specs/2026-07-01-bootstrap-potion-
supply-weighting-design.md."""
LEARN_W_MAX = Fraction(1, 2)
LEARN_SAMPLE_FULL = 20
XP_RATE_REFERENCE = Fraction(10)
"""Observed char-XP/cycle that normalizes to 1.0; tune to a strong grind rate."""


def root_category(node: MetaGoal) -> str:
    if isinstance(node, ReachCharLevel):
        return "char_level"
    if isinstance(node, ReachSkillLevel):
        return "skills"
    return "gear"  # ObtainItem


def desired_state_of(node: MetaGoal | None) -> dict[str, object]:
    if isinstance(node, ObtainItem):
        return {"have": {node.code: node.quantity}}
    if isinstance(node, ReachSkillLevel):
        return {"skill": {node.skill: node.level}}
    if isinstance(node, ReachCharLevel):
        return {"level": node.level}
    return {}


def actionable_step(root: MetaGoal, state: WorldState, game_data: GameData) -> MetaGoal | None:
    """Deepest unmet node reachable from root whose DIRECT prerequisites are all
    satisfied (the 'singular loop' step). None when cyclically blocked.

    Per-path cycle tracking mirrors is_reachable + matches the proved Lean model
    `Formal.StrategyTraversal.actStep` — bridge between Python and Lean is now
    byte-equivalent at the algorithm level. A node on the CURRENT DFS path is
    rejected (cycle guard); a node reached via a sibling branch is NOT pruned
    (the path frozenset backtracks on return)."""
    def _step(node: MetaGoal, path: frozenset[MetaGoal]) -> MetaGoal | None:
        if node in path:
            return None
        unmet = [p for p in prerequisites(node, state, game_data)
                 if not p.is_satisfied(state, game_data)]
        if not unmet:
            if isinstance(node, ObtainItem) and not _producible(node.code, state, game_data):
                return None
            return node
        sub_path = path | {node}
        for prereq in sorted(unmet, key=repr):
            step = _step(prereq, sub_path)
            if step is not None:
                return step
        return None

    return _step(root, frozenset())


def unmet_closure_size(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
    """Structural cost proxy: count of unmet nodes in root's prereq closure (min 1)."""
    seen: set[MetaGoal] = set()
    stack: list[MetaGoal] = [root]
    count = 0
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if not node.is_satisfied(state, game_data):
            count += 1
            stack.extend(prerequisites(node, state, game_data))
    return max(count, 1)


def root_cost(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
    """Effort proxy in 'steps remaining': levels for leaf progression goals,
    craft/gather chain size for gear. Floored at 1."""
    if isinstance(root, ReachCharLevel):
        return max(1, root.level - state.level)
    if isinstance(root, ReachSkillLevel):
        return max(1, root.level - state.skills.get(root.skill, 1))
    return unmet_closure_size(root, state, game_data)


def _producible(code: str, state: WorldState, game_data: GameData) -> bool:
    """True when the item can be made by known means: craftable (has a recipe),
    gatherable (some resource drops it), task-earnable (awarded by the task loop),
    currency-buyable from a permanent vendor for gold or a directly task-earnable
    currency, or obtainable by FIGHTING — some monster that drops it is WINNABLE
    with the best on-hand loadout.

    The winnability gate is load-bearing: a drop from an unwinnable monster must
    NOT read as producible, else the planner would emit an unreachable FightAction
    plan. The SPAWN-LOCATION gate is equally load-bearing: a winnable dropper with
    no known `monster_locations` entry yields NO FightAction (the fight-is-None
    guard in GatherMaterialsGoal.relevant_actions), so the item would read
    producible yet generate an empty/stuck plan. Requiring a non-empty spawn list
    makes producible ⇒ a FightAction can actually be emitted (genuinely obtainable).

    The currency-buy check here is FLAT (non-recursive): currency is gold or is
    directly task-earnable. This is sufficient because tasks_coin (the real
    use-case) is directly task-earnable. Cross-prerequisite recursion lives in
    is_reachable, not here. The `known_spawn_drop` flag uses the WINNABLE+spawned
    drop (state-aware), preserving the winnability gate.

    Routes the leaf decision through leaf_attainable_pure so the Lean proof
    governs the live behavior (Finding B fix). Craftable short-circuits before
    the core call to avoid instantiating the four flags when unneeded."""
    if game_data.crafting_recipe(code) is not None:
        return True
    # Already IN HAND (inventory or bank): nothing left to produce — the
    # obtain step is served by withdraw/equip. Without this arm a HELD
    # recipe-less vendor item (sandwhisper_bag bought a cycle ago) still
    # read not-producible and actionable_step went dead (2026-07-06).
    bank = state.bank_items or {}
    if state.inventory.get(code, 0) > 0 or bank.get(code, 0) > 0:
        return True
    # Currency-buy, one level deep: gold, task-earnable (tasks_coin), or a
    # currency the character can PRODUCE now — gatherable (hides come from
    # fights but wool/dusts also gather-adjacent items count via the full
    # drop tables) or dropped by a currently-winnable spawned monster
    # (P3, docs/PLAN_engagement_expansion.md: tailor leathers @ hides,
    # archaeologist @ shards, cultist @ corrupted_gem). Currencies are base
    # items, so one level suffices; is_reachable recurses for the rest.
    def _currency_producible(currency: str) -> bool:
        if currency == GOLD or game_data.is_task_earnable(currency):
            return True
        if currency in game_data.gatherable_drop_items():
            return True
        return any(
            is_winnable(state, game_data, monster_code)
            and game_data.monster_spawn_known(monster_code)
            for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(currency))
    # A purchase is producible when the currency can be PRODUCED — or is
    # ALREADY EARNED: currency on hand (inventory + bank) covering the price
    # counts even when its droppers are currently unwinnable (the incremental
    # accumulation route banks coins across cycles; 2026-07-06).
    buyable = any(
        state.inventory.get(currency, 0) + bank.get(currency, 0) >= price
        or _currency_producible(currency)
        for price, currency in _permanent_vendor_purchases(code, game_data))
    # Winnable drop: state-aware (preserves the winnability gate).
    winnable_drop = any(
        is_winnable(state, game_data, monster_code)
        and game_data.monster_spawn_known(monster_code)
        for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))
    return leaf_attainable_pure(
        code in game_data.gatherable_drop_items(),
        winnable_drop,
        game_data.is_task_earnable(code),
        buyable)


def is_reachable(root: MetaGoal, state: WorldState, game_data: GameData,
                 path: frozenset[MetaGoal] = frozenset()) -> bool:
    """True when `root`'s entire prerequisite chain bottoms out in obtainable
    leaves. Cycle-safe (a node on the current path can't bottom out)."""
    if root.is_satisfied(state, game_data):
        return True
    if root in path:
        return False
    if isinstance(root, ReachSkillLevel):
        return True  # grinding the skill is always an available action
    prereqs = prerequisites(root, state, game_data)
    if isinstance(root, ObtainItem) and not prereqs:
        return _producible(root.code, state, game_data)
    sub_path = path | {root}
    return all(is_reachable(p, state, game_data, sub_path) for p in prereqs)


@dataclass(frozen=True)
class RootScore:
    root_repr: str
    category: str
    contribution: Fraction
    cost: int
    score: Fraction
    step_repr: str
    instrumental: bool = False

    def to_dict(self) -> dict[str, object]:
        # P4a float boundary: scores are exact Fractions internally; the trace
        # record stays JSON-numeric by converting ONCE here (trace-only seam,
        # never read back into decisions).
        d = asdict(self)
        d["contribution"] = float(self.contribution)
        d["score"] = float(self.score)
        return d


@dataclass(frozen=True)
class StrategyDecision:
    interrupt: str | None
    chosen_root: MetaGoal | None
    chosen_step: MetaGoal | None
    desired_state: dict[str, object]
    ranking: list[RootScore] = field(default_factory=list)
    # Ranked alternative steps below the chosen one. Used by the arbiter
    # to fall back when the top step's goal is None (e.g. ReachCharLevel
    # with no winnable monster) instead of dropping straight into
    # discretionary. Closes the 2026-06-06 09:59 gap where 50+ cycles of
    # PursueTask ran because bootstrap step yielded None and the gear
    # roots (copper_boots, copper_helmet) at score 1.0 were never tried.
    fallback_steps: list[MetaGoal] = field(default_factory=list)
    # The ROOT paired with each fallback step (same index). The arbiter
    # uses this to map an intermediate ObtainItem step back to its
    # equippable root: a step like ObtainItem(copper_bar, 8) emerged from
    # ObtainItem(copper_boots) → UpgradeEquipmentGoal(copper_boots) should
    # be used (planner crafts bars + boots in one chain) rather than
    # GatherMaterials(copper_bar) which only crafts bars and stops.
    fallback_roots: list[MetaGoal] = field(default_factory=list)

    def to_trace(self) -> dict[str, object]:
        return {
            "interrupt": self.interrupt,
            "chosen_root": repr(self.chosen_root) if self.chosen_root is not None else None,
            "chosen_step": repr(self.chosen_step) if self.chosen_step is not None else None,
            "desired_state": self.desired_state,
            "ranking": [rs.to_dict() for rs in self.ranking],
            "fallback_steps": [repr(s) for s in self.fallback_steps],
            "fallback_roots": [repr(r) for r in self.fallback_roots],
        }


@dataclass(frozen=True)
class StrategyEngine:
    objective: CharacterObjective
    personality: Personality

    def _gear_slot(self, code: str, state: WorldState,
                   game_data: GameData) -> str | None:
        """The equipment slot an ObtainItem root targets. target_gear keeps
        its explicit slot mapping; target_tools stay slot-less (the dedicated
        tool-value axis, never slot-scored); anything else — the near-term
        gear roots — resolves by item type to the WEAKEST currently-equipped
        candidate slot (the slot the upgrade would actually fill)."""
        slot = next((s for s, c in self.objective.target_gear.items() if c == code), None)
        if slot is not None:
            return slot
        if code in self.objective.target_tools.values():
            return None
        stats = game_data.item_stats(code)
        if stats is None:
            return None
        slots = [s for s in ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
                 if s in EQUIPMENT_SLOTS]
        if not slots:
            return None

        def _current_value(s: str) -> int:
            current = state.equipment.get(s)
            current_stats = game_data.item_stats(current) if current else None
            return equip_value(current_stats) if current_stats is not None else 0

        return min(slots, key=lambda s: (_current_value(s), slots.index(s)))

    def _root_slot(self, root: MetaGoal, state: WorldState,
                   game_data: GameData) -> str | None:
        """The slot a gear root scores against: the root's explicit slot when it
        carries one (per-slot gear roots), else the code's target_gear slot."""
        if isinstance(root, ObtainItem) and root.slot is not None:
            return root.slot
        code = root.code if isinstance(root, ObtainItem) else ""
        return self._gear_slot(code, state, game_data)

    def _combat_gear_slots(self, game_data: GameData) -> frozenset[str]:
        """Slot names for all effect-derived combat gear types.
        Derived from game_data.combat_gear_types (which includes rune/artifact after
        the approved gear reclassification) via ITEM_TYPE_TO_SLOTS — a new slot for
        a combat type (e.g. a 3rd ring) is included without editing any slot list.
        Spec: docs/superpowers/plans/2026-06-28-gear-taxonomy.md
        """
        return frozenset(
            slot
            for t in game_data.combat_gear_types
            for slot in ITEM_TYPE_TO_SLOTS.get(t, [])
        )

    def _base_prior(self, root: MetaGoal, state: WorldState,
                    game_data: GameData) -> Fraction:
        category = root_category(root)
        weight = self.personality.category_weight(category)
        if isinstance(root, ReachCharLevel):
            tier = PRIOR_CHAR_LEVEL
        elif isinstance(root, ReachSkillLevel):
            if root.skill in COMBAT_CRAFT_SKILLS:
                tier = PRIOR_COMBAT_CRAFT_SKILL
            elif root.skill in GATHER_SKILLS:
                tier = PRIOR_GATHER_SKILL
            elif root.skill in CONSUMABLE_CRAFT_SKILLS:
                tier = PRIOR_CONSUMABLE_SKILL
            else:
                tier = Fraction(0)   # unknown skill — no prior, scores zero
        elif isinstance(root, ObtainItem):
            slot = self._root_slot(root, state, game_data)
            tier = PRIOR_COMBAT_GEAR if slot in self._combat_gear_slots(game_data) else PRIOR_UTILITY_GEAR
        else:
            tier = Fraction(0)
        return tier * weight

    def _has_empty_armor_slot(self, state: WorldState, game_data: GameData) -> bool:
        """True when a combat ARMOR slot targeted by near_term_gear is empty.
        Excludes weapon_slot — an empty/unusable weapon is covered by the
        combat-capability gate (combat_monster is None). Gates the char-level
        boost: while such a slot remains, leveling stays at the lower rate so
        empty-slot armor wins; once equipped, char leveling rises above general
        skill grinding.

        Iterates near_term_gear (usable-now targets) instead of target_gear
        (endgame BiS). The old target_gear iteration silently skipped empty
        slots when the BiS item was too high level, falsely reporting geared.
        near_term_gear already filters to stats.level <= state.level, so the
        inner level check is not needed here."""
        combat_slots = self._combat_gear_slots(game_data)
        for slot, _code in self.objective.near_term_gear(state).items():
            if slot == "weapon_slot" or slot not in combat_slots:
                continue
            if state.equipment.get(slot) is None:
                return True
        return False

    def _equip_gain(self, root: MetaGoal, state: WorldState,
                    game_data: GameData,
                    history: LearningStore | None = None) -> int:
        """Exact-int gain of equipping a gear root over what the target slot
        already holds: `max(0, strategic_value(item) - strategic_value(current))`.
        Empty slot ⇒ current is 0, so the gain is the item's full strategic value.
        Returns 0 for non-gear or stats-unknown roots.

        Uses `strategic_value` (NOT `equip_value`) so CROSS-SLOT gear priority is
        efficiency-weighted (#16): combat stats carry the dominant SCALE weight so
        combat-slot ordering is unchanged, while non-combat efficiency stats
        (wisdom/prospecting down-weighted; inventory/haste held at parity pending
        their derived rates) get their own weight — a bag/rune slot's gain reflects
        its non-combat value instead of a 1:1-with-attack sum. WITHIN-slot best-item
        SELECTION (target_gear / near_term_gear) stays on the proved equip_value.

        Single source for both the `_marginal` score and the `decide` sort key's
        protection tiebreak (`decide_key`'s third field), so the two never diverge
        on what "better gear" means. The gain is in strategic_value fixed-point
        units (combat × STRATEGIC_SCALE); GEAR_EQUIP_SCALE is scaled to match."""
        if not isinstance(root, ObtainItem):
            return 0
        stats = game_data.item_stats(root.code)
        if stats is None:
            return 0
        slot = self._root_slot(root, state, game_data)
        current_code = state.equipment.get(slot) if slot is not None else None
        current_stats = game_data.item_stats(current_code) if current_code else None
        # Weights + efficiency budget LEARNED from gameplay (#16 Phase 3b): combat
        # dominant, efficiency stats by cooldown-seconds-saved × action-mix, capped
        # below combat. history=None (cold / unit tests) → efficiency weights 0, so
        # gain is combat-only (efficiency gear uncredited until learned).
        weights, budget = strategic_weights(state, history)
        # #14 horizon: scale efficiency by the leveling still ahead,
        # (max_level − level)/max_level — efficiency gear is worth most early,
        # ~0 near max level. Clamp the numerator at 0 for level >= max.
        max_level = game_data.max_character_level
        horizon = (max(0, max_level - state.level), max_level) if max_level > 0 else None
        current_value = (strategic_value(current_stats, weights, budget, horizon)
                         if current_stats is not None else 0)
        return max(0, strategic_value(stats, weights, budget, horizon) - current_value)

    def _marginal(self, root: MetaGoal, state: WorldState, game_data: GameData,
                  combat_monster: str | None = None,
                  history: LearningStore | None = None) -> Fraction:
        if isinstance(root, ReachCharLevel):
            # Inverse-gap char-level urgency: smaller gaps (the bootstrap
            # root `ReachCharLevel(state.level + 2)`) score HIGHER than the
            # long-haul `ReachCharLevel(target_char_level)` root. This
            # is the load-bearing rank ordering so the bootstrap (whose
            # step.level is 2 away from current) bypasses the e27779e
            # items-task stand-down, while the long-haul root (whose
            # step.level is far from current) doesn't trigger the
            # stand-down by winning the rank. User request 2026-06-06:
            # "PursueTask can be deprioritized when we need ...
            # GrindMonstersForXP." Implemented at the ranking layer —
            # when the SHORT-horizon char-level root beats
            # PRIOR_RELEVANT_TOOL (1.1), its step (GrindCharacterXP)
            # takes the step slot ahead of PursueTask in the arbiter
            # walk.
            gap = max(0, root.level - state.level)
            if gap >= CHAR_REACHABLE_HORIZON:
                return CHAR_MARGINAL + Fraction(state.level, root.level) * CHAR_CAPSTONE_SCALE
            reach = max(0, CHAR_REACHABLE_HORIZON - gap)
            # Gear-first: the char-leveling boost (out-ranking skill grind)
            # applies only once the bot is combat-ready AND every fillable
            # combat armor slot is equipped. While not combat-capable
            # (combat_monster is None — weapon-readiness path) or any armor slot
            # is still empty, the lower rate keeps leveling below weapon /
            # empty-slot-armor urgency so those get filled first.
            geared = (combat_monster is not None
                      and not self._has_empty_armor_slot(state, game_data))
            per_level = CHAR_GAP_PER_LEVEL_GEARED if geared else CHAR_GAP_PER_LEVEL
            bonus = reach * per_level
            return CHAR_MARGINAL + bonus
        if isinstance(root, ReachSkillLevel):
            # Endgame skill-50 roots stay flat/long-horizon; only NEAR-TERM
            # recipe-curve roots (target below max) get the catch-up boost,
            # scaled by how far the skill trails its curve target and capped so
            # it cannot swamp every other category (run-7 just-in-time skilling).
            if root.level >= game_data.max_skill_level:
                return SKILL_MARGINAL
            current = state.skills.get(root.skill, 1)
            gap = max(0, root.level - current)
            progress = Fraction(current, max(1, root.level))
            boost = (1 - progress) * min(Fraction(gap), SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL
            return SKILL_MARGINAL + boost
        if isinstance(root, ObtainItem):
            stats = game_data.item_stats(root.code)
            if stats is None:
                return Fraction(0)
            slot = self._root_slot(root, state, game_data)
            current_code = state.equipment.get(slot) if slot is not None else None
            # P4a: equip_value is an exact int — the gain is exact integer
            # arithmetic; the normalisation divides into an exact Fraction.
            gain = self._equip_gain(root, state, game_data, history)
            marginal = min(Fraction(1), gain / GEAR_EQUIP_SCALE)
            # Combat-readiness urgency: a weapon-slot upgrade is the binding
            # objective while the character cannot fight at all.
            if combat_monster is None and slot == "weapon_slot":
                marginal = max(marginal, Fraction(1)) * COMBAT_READINESS_URGENCY
            # Empty-slot urgency: filling an empty combat slot with a
            # usable-at-level item dominates grinding (GearPolicy bridge —
            # see EMPTY_SLOT_URGENCY). Excludes weapon_slot: the weapon has
            # its own combat-readiness path above, and tools (type
            # "weapon") must not ride this boost into the slot.
            elif (slot in self._combat_gear_slots(game_data) and slot != "weapon_slot"
                    and current_code is None
                    and stats.level <= state.level and gain > 0):
                marginal = max(marginal, Fraction(1)) * EMPTY_SLOT_URGENCY
            # Occupied-slot upgrade urgency: replacing a FILLED combat armor slot
            # with a large upgrade (gain >= GEAR_EQUIP_SCALE, roughly a 2x
            # strategic-value jump) interrupts grinding so the bot re-gears
            # (copper_boots → iron_boots). Self-limits: once the tier gap closes
            # the gain falls below the gate and char-leveling resumes.
            elif (slot in self._combat_gear_slots(game_data) and slot != "weapon_slot"
                    and current_code is not None
                    and stats.level <= state.level
                    and gain >= GEAR_EQUIP_SCALE):
                marginal = max(marginal, Fraction(1)) * OCCUPIED_SLOT_UPGRADE_URGENCY
            # Potion-supply urgency: an under-stocked health potion is as urgent
            # as an empty combat slot during bootstrap. Unlike the empty-slot
            # branch this is NOT gated on gain > 0 — a heal potion must stock
            # even when the strategic-value model scores its equip-gain at 0
            # (max(marginal, 1) forces the multiplier). `stats.type_ ==
            # "utility"` mirrors target_potion_pure's slot-family predicate;
            # equipped_potion_qty sums both utility slots. Breaks the alchemy
            # deadlock (see POTION_SUPPLY_URGENCY); the CraftPotions guard
            # maintains the baseline once alchemy unlocks crafting.
            # Fires only for the effect-based bootstrap_potion_target — never an aspirational high-tier potion (would drive a multi-level skill grind).
            elif (stats.type_ == "utility"
                    and stats.hp_restore > 0
                    and root.code == bootstrap_potion_target(state, game_data)
                    and equipped_potion_qty(state, root.code) < potion_baseline_pure(
                        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                        POTION_HIGH_LEVEL, POTION_HIGH_QTY)):
                marginal = max(marginal, Fraction(1)) * POTION_SUPPLY_URGENCY
            # Bag-slot floor (2026-07-03): an empty bag slot whose bag is
            # craftable NOW (gearcrafting >= its crafting_level) is worth a
            # non-zero, BELOW-combat pursuit so the arbiter fills it in windows
            # with no combat/gear upgrade. BAG_SLOT_URGENCY < COMBAT_READINESS
            # (2) and < EMPTY_SLOT (5/2), so a weapon / empty combat slot always
            # wins. Floors marginal directly (bag strategic_value is 0 cold).
            elif (slot == "bag_slot" and current_code is None
                    and stats.level <= state.level
                    and stats.crafting_skill is not None
                    and state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level):
                marginal = max(marginal, BAG_SLOT_URGENCY)
            return marginal
        return Fraction(0)

    def _balancing(self, root: MetaGoal, state: WorldState) -> Fraction:
        if not isinstance(root, ReachSkillLevel):
            return Fraction(1)
        levels = list(state.skills.values())
        leader = max(levels) if levels else 0
        current = state.skills.get(root.skill, 0)
        return _balancing_pure(leader, current)

    def _relevant_tool_value(self, root: MetaGoal, state: WorldState,
                             game_data: GameData) -> Fraction:
        """Active-task tool boost. Returns PRIOR_RELEVANT_TOOL when the
        root is a target_tools item whose skill matches the current
        task's active gathering skill; else 0. Combined with `_value`
        via max so the boost can't accidentally suppress a higher-scored
        baseline."""
        if not isinstance(root, ObtainItem):
            return Fraction(0)
        # Find the gathering skill this tool would boost (the target_tools
        # entry maps skill → code; reverse the lookup).
        skill_for_tool = next(
            (s for s, c in self.objective.target_tools.items() if c == root.code),
            None,
        )
        if skill_for_tool is None:
            return Fraction(0)
        active = game_data.active_gathering_skills(
            state.task_code, state.crafting_target,
        )
        if skill_for_tool not in active:
            return Fraction(0)
        category = root_category(root)
        weight = self.personality.category_weight(category)
        return PRIOR_RELEVANT_TOOL * weight

    def _value(self, root: MetaGoal, state: WorldState, game_data: GameData,
               combat_monster: str | None = None,
               history: LearningStore | None = None) -> Fraction:
        base = (self._base_prior(root, state, game_data)
                * self._marginal(root, state, game_data, combat_monster, history)
                * self._balancing(root, state))
        return max(base, self._relevant_tool_value(root, state, game_data))

    def _learned_blend(self, root: MetaGoal, value: Fraction,
                       history: LearningStore | None, combat_monster: str | None) -> Fraction:
        if not (isinstance(root, ReachCharLevel) and history is not None and combat_monster):
            return value
        y = expected_yield_per_cycle(f"FarmMonster({combat_monster})", history)
        if y.sample_count <= 0:
            return value
        # P4a: lift the observed float yield EXACTLY (Fraction(float) is the
        # exact binary expansion — the P3c boundary idiom); everything after
        # the lift is exact rational arithmetic.
        normalized = min(Fraction(1), max(Fraction(0), Fraction(y.char_xp) / XP_RATE_REFERENCE))
        w = blend_weight(y.sample_count)
        return _learned_blend_pure(value, normalized, w)

    def decide(self, state: WorldState, game_data: GameData,
               history: LearningStore | None = None,
               combat_monster: str | None = None,
               last_chosen_root: str | None = None,
               step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
               band_adequate: bool = False,
               ) -> StrategyDecision:
        """THE FLIP (Phase 4b Task 1): thin delegate to the progression tree —
        the flat scalar ranking is bypassed (its pipeline is deleted in Task 2).

        `history`/`combat_monster`/`last_chosen_root` are accepted for
        callsite stability this task and deliberately unused: the tree is
        deterministic (326 consecutive identical picks in shadow), so
        decide-level sticky SCORING and the learned blend die with the
        ranking. Arbiter-level commitment (`_update_sticky_anchor`,
        objective-committed arbitration, zombie release) survives untouched.
        Task 2 prunes whichever parameters end up unused after callers
        adjust.

        `band_adequate` is the caller's progression-band verdict (see
        `GamePlayer._tree_band_adequate`); `step_servable` keeps the
        plannability demotion alive across the cutover (see
        `progression_tree._servable_promotion`)."""
        del history, combat_monster, last_chosen_root  # legacy-ranking inputs; tree ignores them
        return progression_tree.decide_tree(
            state, game_data, self.objective,
            band_adequate=band_adequate, step_servable=step_servable)
