"""Pure builder: the chosen strategy root's prerequisite tree for the TUI plan
screen. Recurses prerequisites() (material ObtainItem edges down to raw gathers;
skill grinds are planner-native LevelSkill legs, not prerequisite nodes, since
epic P3); non-chosen ranked roots are leaf stubs; the current step gets a
synthetic serve child sourced from the running goal + action. No planning or
I/O."""

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import (
    META_GOAL_KINDS,
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.tui.plan_format import short_root, supply_detail

# Matches UpgradeEquipmentGoal.max_depth — a chain longer than this is treated as
# a leaf rather than recursed (defence against a pathological recipe/gate graph).
_DEPTH_CAP = 32


def rank_detail(row: RootScore) -> str:
    """`RootScore.score` rendered as a string, and nothing else.

    THE FLIP (wave 3a) replaced the scored ranking with a resolution walk;
    `RootScore.j` and `.reachable_level` are no longer set by anything (the
    walk has no objective to price them against) so the two arms that used to
    read them are gone, not merely unreachable — see `_resolution_rows` below
    for what carries the walk's real content now. `score` itself stays: it is
    a required field on `RootScoreView`, a Pydantic model with no default that
    the TUI log pane and two test modules pin (spec §1.4), so `RootScore.score`
    is not deleted here — that is wave 3b's schema change, in one commit with
    the rest of it. `decide_tree` now writes the constant `Fraction(1)` to it
    on every row, so this no longer differentiates one row from another; it
    exists to keep `RootScoreView.score` constructible, not to be read for
    meaning."""
    return f"{float(row.score):.2f}"


def _resolution_rows(row: RootScore) -> str:
    """The row's reason: what the plan pane and the CLI print in place of the
    number `rank_detail` used to supply.

    THE FLIP moved the walk's real content into `category` (spec §5.2,
    `progression_tree._resolution_rows`, which builds these rows): the
    resolution trail for the chosen root, `"alternative · <kind>"` for every
    other row. Same name as that function on purpose — this is its
    display-side counterpart, reading the field it writes — but a different
    module: `progression_tree` builds the `RootScore` list from a
    `RootResolution`; this one formats a single already-built row for a
    reader, which is all a pure display module needs and keeps this module
    free of a dependency on `decisions.root`/`resolve_root` it has never had.

    Both `build_plan_tree` and `commands/plan.py` call this instead of
    `rank_detail` now, so the plan pane and the CLI keep showing the SAME
    reason for a cycle — the "single funnel" `rank_detail` used to be, before
    its own content went constant."""
    return row.category


def _label(node: MetaGoal) -> tuple[str, str]:
    """(label, kind) for a meta-goal node."""
    if isinstance(node, ObtainItem):
        qty = "" if node.quantity == 1 else f" ×{node.quantity}"
        return f"{node.code}{qty}", "obtain"
    if isinstance(node, ReachCharLevel):
        return f"character → {node.level}", "charlevel"
    if isinstance(node, ReachSkillLevel):
        # "skill" matches tiers.strategy.root_category's naming for this
        # category, so the plan pane and the resolved root's own category
        # agree on what kind of root this is.
        return f"{node.skill} → {node.level}", "skill"
    return short_root(repr(node)), "obtain"


def _expand(node: MetaGoal, decision: StrategyDecision, state: WorldState,
            game_data: GameData, serve_step: str | None,
            visited: frozenset[MetaGoal], depth: int,
            ctx: SelectionContext = NO_PROFILE_CONTEXT,
            grind_children: tuple[PlanTreeNode, ...] = ()) -> PlanTreeNode:
    label, kind = _label(node)
    is_current = node == decision.chosen_step
    status = "current" if is_current else (
        "met" if node.is_satisfied(state, game_data) else "unmet")
    children: list[PlanTreeNode] = []
    # Display's own policy for a MetaGoal kind this module doesn't recognise:
    # render it as a leaf stub rather than descend. `prerequisites()` fails
    # loudly on an unhandled kind (fix-round-1, task 2 review) — that is
    # planning's policy, not display's, so this guard keeps the TUI from
    # inheriting a crash it never asked for.
    if (isinstance(node, META_GOAL_KINDS) and node not in visited
            and depth < _DEPTH_CAP):
        nxt = visited | {node}
        for prereq in prerequisites(node, state, game_data, ctx):
            children.append(
                _expand(prereq, decision, state, game_data, serve_step, nxt,
                       depth + 1, ctx, grind_children))
    if is_current and serve_step:
        children.append(PlanTreeNode(
            key=f"step:{node!r}", label=serve_step, kind="step", status="current",
            children=grind_children))
    return PlanTreeNode(key=repr(node), label=label, kind=kind, status=status,
                        children=tuple(children))


def _supply_node(supply_target: tuple[str, int, int] | None,
                 ) -> tuple[PlanTreeNode, ...]:
    """The chosen root's supply child — the sibling demand this character is
    producing for — or an empty tuple when it is producing for nobody.

    A CHILD of the chosen root rather than a second root, because it is work
    this character is doing right now and the plan pane's top level is the
    resolved-root list (chosen root plus `RootResolution.alternatives`); and
    `kind="step"` rather than `obtain`, because it is
    NOT a prerequisite of the objective above it — it is the other thing the
    arbiter is spending cycles on. The `step` kind is what already carries that
    meaning for the synthetic serve node, and it takes the same dim-cyan style
    and `•` glyph, so it cannot be misread as a material the root is waiting
    on."""
    if supply_target is None:
        return ()
    item_code, quantity, demand = supply_target
    return (PlanTreeNode(key=f"supply:{item_code}", label=f"supplying {item_code}",
                         kind="step", status="current",
                         detail=supply_detail(quantity, demand)),)


def build_plan_tree(decision: StrategyDecision, state: WorldState,
                    game_data: GameData, serve_step: str | None,
                    ctx: SelectionContext = NO_PROFILE_CONTEXT,
                    grind_children: tuple[PlanTreeNode, ...] = (),
                    role: str | None = None,
                    supply_target: tuple[str, int, int] | None = None,
                    ) -> tuple[PlanTreeNode, ...]:
    """Chosen root expands its prerequisite subtree; other ranked roots become
    leaf stubs. The current step gains a synthetic serve child. Bounded by a
    visited-set (frozen MetaGoals are hashable) + a depth cap.

    `ctx` (the player's per-cycle `SelectionContext`) is forwarded to
    `prerequisites` so the TUI tree shows the SAME descent the planner
    actually takes (one-obtain-model epic, Task 5) rather than a stale
    from-scratch recipe descent.

    `grind_children` are the runtime skill-grind legs the player captured this
    cycle (empty unless the executed action was a LevelSkill); they graft onto
    the current step's synthetic serve child so the tree shows the whole action
    chain below a LevelSkill step instead of stopping at it.

    `role` and `supply_target` are this character's cross-character
    specialization state (`GamePlayer._role` / `._supply_target`, the same two
    fields `CycleSnapshot.role` / `.supply_target` carry). The role annotates
    the chosen root; the supply target becomes a child of it. Both default to
    the single-character shape — no role, nothing to supply — under which the
    tree is byte-identical to the one built before they existed. They are
    passed explicitly rather than read off `ctx.supply_target` so the plan pane
    and the log pane are rendering the same cycle's fields: `ctx` is the
    SELECTION context, and a cycle whose selection was preempted still carries
    the previous one."""
    if decision.chosen_root is None:
        return ()
    chosen_node = _expand(decision.chosen_root, decision, state, game_data,
                          serve_step, frozenset(), 0, ctx, grind_children)
    chosen_repr = repr(decision.chosen_root)
    # Show the chosen root's OWN resolution reason — alternatives already show
    # theirs, so without this the chosen root is the only node with no
    # explanation, and a user cannot see WHY the walk resolved here.
    chosen_score = next((r for r in decision.ranking if r.root_repr == chosen_repr), None)
    # Details accumulate rather than compete: a supplying character's root has to
    # show BOTH why the walk resolved here and which role it is holding while it
    # works. An empty list joins to "", which is the same detail a root absent
    # from `decision.ranking` has always had, so the unannotated case is
    # unchanged.
    details: list[str] = []
    if chosen_score is not None:
        details.append(_resolution_rows(chosen_score))
    if role is not None:
        details.append(f"[{role}]")
    chosen_node = chosen_node.model_copy(update={
        "detail": "   ".join(details),
        "children": chosen_node.children + _supply_node(supply_target),
    })
    roots: list[PlanTreeNode] = [chosen_node]
    for i, r in enumerate(decision.ranking):
        if r.root_repr == chosen_repr:
            continue
        roots.append(PlanTreeNode(
            key=r.root_repr, label=short_root(r.root_repr), kind="root_stub",
            status="unmet",
            detail=f"root {i + 1} · {_resolution_rows(r)}"))
    return tuple(roots)
