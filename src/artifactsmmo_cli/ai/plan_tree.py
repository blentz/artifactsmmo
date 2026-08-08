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
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.tui.plan_format import short_root, supply_detail

# Matches UpgradeEquipmentGoal.max_depth — a chain longer than this is treated as
# a leaf rather than recursed (defence against a pathological recipe/gate graph).
_DEPTH_CAP = 32


def _rank_detail(row: RootScore) -> str:
    """How a root's standing reads in the plan pane: its `J` when the objective
    decided, otherwise its per-category score.

    `J` leads because `J` is what chose. `score` is NOT a comparable ranking — it
    is `pursuit_value` for gear and a constant 1.0 for the xp trunk — so showing
    it alone made gear look like a landslide (2.6e8 against 1.0) on cycles where
    `J` had the trunk winning by 0.006%, which is what sent a reader hunting for a
    bug in the pivot on 2026-08-08. Lower `J` wins, hence the explicit label:
    an unlabelled number next to a higher-is-better one invites the wrong reading
    twice over."""
    if row.j is not None:
        return f"J {row.j}"
    return f"{float(row.score):.2f}"


def _label(node: MetaGoal) -> tuple[str, str]:
    """(label, kind) for a meta-goal node."""
    if isinstance(node, ObtainItem):
        qty = "" if node.quantity == 1 else f" ×{node.quantity}"
        return f"{node.code}{qty}", "obtain"
    if isinstance(node, ReachCharLevel):
        return f"character → {node.level}", "charlevel"
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
    if node not in visited and depth < _DEPTH_CAP:
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
    ranked-root ladder; and `kind="step"` rather than `obtain`, because it is
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
    # Show the chosen root's OWN score/category — alternatives already show theirs,
    # so without this the winner is the only node with no value, and a user cannot
    # see WHY it beat the rest (or how dominant it is).
    chosen_score = next((r for r in decision.ranking if r.root_repr == chosen_repr), None)
    # Details accumulate rather than compete: a supplying character's root has to
    # show BOTH why it won the ranking and which role it is holding while it
    # works. An empty list joins to "", which is the same detail a root absent
    # from the ranking has always had, so the unannotated case is unchanged.
    details: list[str] = []
    if chosen_score is not None:
        details.append(f"{chosen_score.category} · {_rank_detail(chosen_score)}")
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
            detail=f"root {i + 1} · {r.category} · {_rank_detail(r)}"))
    return tuple(roots)
