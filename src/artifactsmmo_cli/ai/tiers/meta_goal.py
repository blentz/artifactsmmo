"""Tier-2 meta-goal nodes: concrete progression conditions for the
prerequisite graph. Frozen + hashable so P3 traversal can use visited-sets."""

from dataclasses import dataclass
from typing import Protocol

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.world_state import WorldState


def owned_count(state: WorldState, code: str) -> int:
    """How many of `code` the character has across inventory, bank, and the
    equipped slots (an equipped item counts as one).

    `state.inventory` counts only UNEQUIPPED (spare) copies: the API stores
    equipped items in dedicated equipment slots, separate from the inventory
    list, and `EquipAction.apply` decrements inventory by 1 when equipping. So
    the equipped `+1` counts the worn copy, which is not in the inventory count;
    spare copies of an equipped item may still sit in inventory and are summed
    correctly (1 worn + 1 spare = 2 owned). There is no disjointness-of-codes
    invariant. See `owned_count_pure` and `EquipAction.apply`.
    """
    equipped_codes = [c for c in state.equipment.values() if c is not None]
    return owned_count_pure(state.inventory, state.bank_items, equipped_codes, code)


class MetaGoal(Protocol):
    """A concrete progression condition that is either satisfied or not."""

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool: ...


@dataclass(frozen=True)
class ReachCharLevel:
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.level >= self.level


@dataclass(frozen=True, repr=False)
class ObtainItem:
    code: str
    quantity: int = 1
    slot: str | None = None

    def __repr__(self) -> str:
        if self.slot is not None:
            return (f"ObtainItem(code={self.code!r}, quantity={self.quantity}, "
                    f"slot={self.slot!r})")
        return f"ObtainItem(code={self.code!r}, quantity={self.quantity})"

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        # Per-slot gear root: satisfied iff THIS slot holds the code, so the
        # objective can target the same item in multiple slots (two copper_rings
        # in ring1_slot + ring2_slot). slot=None keeps the legacy semantics below.
        if self.slot is not None:
            return state.equipment.get(self.slot) == self.code
        # Equippable items: owning isn't the end-state — the meta-objective
        # is to WEAR them. Trace 2026-06-05T03:37: Robby crafted wooden_shield
        # but never equipped it; root dropped from candidates because owned >=
        # 1, the UpgradeEquipmentGoal never re-fired, and the shield sat
        # in inventory forever. Require occupancy of an equipment slot.
        # EXCEPT TOOLS (subtype='tool', e.g. copper_pickaxe, copper_axe,
        # fishing_net): owning is the goal because tools ROTATE through
        # weapon_slot per the active gathering task (OptimizeLoadout swaps
        # the right tool in per-fight / per-gather). Recipe-input codes
        # (ash_plank, copper_bar, ash_wood) stay on the owned-count rule —
        # they're consumed by crafts and never enter equipment.
        stats = game_data.item_stats(self.code)
        if stats is not None and ITEM_TYPE_TO_SLOTS.get(stats.type_):
            if stats.subtype == "tool":
                return owned_count(state, self.code) >= self.quantity
            return self.code in state.equipment.values()
        return owned_count(state, self.code) >= self.quantity


@dataclass(frozen=True)
class ReachSkillLevel:
    """The character reaches `level` in `skill`.

    A root-level sibling of `ReachCharLevel`: the tier ladder's answer when a
    gear target is skill-gated is "raise the skill by one", and `chosen_root`
    must be able to name that. Wave 2 could route to `ReachSkillGoal` (a planner
    Goal) but had no MetaGoal for it, so the pane reported the gear root while
    the bot ground a skill.
    """

    skill: str
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.skills.get(self.skill, 1) >= self.level


META_GOAL_KINDS: tuple[type, ...] = (ObtainItem, ReachCharLevel, ReachSkillLevel)
"""The complete set of concrete MetaGoal variants, as a runtime-checkable
isinstance tuple. `MetaGoal` is a Protocol — it cannot be isinstance-tested
directly — so this is the single place a fourth variant must be registered.
Two independent consumers read it and each states its OWN policy for a node
that is NOT one of these kinds: `prerequisite_graph.prerequisites` fails
loudly (planning must not silently misreport a dispatch it doesn't recognise —
see the fix-round-1 finding this closes), while `plan_tree._expand` treats an
unrecognised node as a display leaf stub (a TUI pane degrades gracefully
instead of crashing). Neither policy should be inferred from the other by
leaning on a shared default; META_GOAL_KINDS is what keeps both in sync with
the same list without coupling their behaviour."""


SKILL_FOCUS_SLOT = "<skill>"
"""Focus-ledger slot sentinel for a `ReachSkillLevel` root.

Not an equipment slot, and deliberately unlike one: a skill climb is elected by
`decisions/root.IsThisTargetBlocked` on behalf of whichever gear slot is gated
on it, and TWO slots gated on the same skill are the SAME work, so they share
one ledger entry. Angle brackets because no API slot name can collide with
them."""

ITEM_FOCUS_SLOT = "<item>"
"""Focus-ledger slot sentinel for a slot-less `ObtainItem` — the material-gated
head (`ObtainItem(code=blocker, quantity=n)`, no slot) and the recipe-input
steps. Sibling of `SKILL_FOCUS_SLOT`."""


def focus_key(node: "MetaGoal | None") -> tuple[str, str] | None:
    """The anti-starvation ledger's key for a committed root, or None for a
    root that does not compete for attention.

    ONE key function for BOTH halves of the ledger: `GamePlayer._charge_focus`
    writes with it and `decisions/root.WhichSlotIsFurthestBehind._aged_head`
    reads with it. They used to disagree, and that is the whole reason this
    function exists.

    THE DEFECT IT CLOSES (wave 3a fix-round 2). `_gear_root_key` read
    `getattr(root, "slot")` and `getattr(root, "code")` and returned None
    unless BOTH were `str`. That was true for every root the RANKING could
    produce — `_candidate_root` always built `ObtainItem(code, slot=slot)` —
    and false for two of the three the WALK produces:

      * `ReachSkillLevel` (skill-gated head) has neither attribute;
      * `ObtainItem(code=blocker, quantity=n)` (material-gated head) has
        `slot=None`.

    Both keyed to None, `_charge_focus` returned early, and the ledger stayed
    permanently EMPTY — so the aged arm never engaged and the same root won
    every cycle. Measured over 130 charged cycles on `l10_weapon_upgrade` and
    `l12_taskgated_bag`: one distinct root, `ledger: {}`. The skill-climb root
    this epic exists to produce was exactly the root that could not rotate.

    `ReachCharLevel` returns None ON PURPOSE and is an explicit arm, not a
    fall-through: the xp trunk is not a slot contender, it is the last-resort
    alternative every board carries, and ageing it would let the ledger decay
    the one root that must always stay reachable. An UNREGISTERED kind fails
    loudly instead — the silent None is what produced the defect above, and
    `prerequisite_graph.prerequisites` already establishes the pattern.
    """
    if node is None:
        return None                       # the wall: nothing was committed
    if isinstance(node, ObtainItem):
        return (node.slot or ITEM_FOCUS_SLOT, node.code)
    if isinstance(node, ReachSkillLevel):
        return (SKILL_FOCUS_SLOT, node.skill)
    if isinstance(node, ReachCharLevel):
        return None
    assert not isinstance(node, META_GOAL_KINDS), (
        f"{node!r} is registered in META_GOAL_KINDS but focus_key() has no "
        f"arm for it")
    raise AssertionError(f"unhandled MetaGoal kind: {node!r}")


def focus_key_str(key: tuple[str, str]) -> str:
    """`focus_key`'s tuple as ONE string.

    Two consumers need a scalar: `CycleSnapshot.gear_focus` / `.interleave_seats`
    are JSON objects, whose keys must be strings, and `dhondt_step` apportions
    over a `Mapping[str, Fraction]`. The seat ledger is keyed by this FULL key
    rather than by the slot alone — two slots can resolve to different roots
    that share a sentinel slot (`<skill>` for `gearcrafting` and for
    `jewelrycrafting`), and a slot-only seat key would collapse them into one
    apportionment entry."""
    slot, code = key
    return f"{slot}|{code}"
