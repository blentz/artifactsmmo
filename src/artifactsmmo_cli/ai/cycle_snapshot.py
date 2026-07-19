"""CycleSnapshot: frozen per-cycle state + decision context for TUI consumers."""

from pydantic import BaseModel, ConfigDict, Field


class RootScoreView(BaseModel):
    """Compact view of a ranked strategy root for the TUI plan screen."""

    root_repr: str
    category: str
    score: float
    step_repr: str = ""


class GoalRankEntry(BaseModel):
    """One row in the per-cycle goal-priority ladder."""

    goal: str
    priority: float


class GoalAttempt(BaseModel):
    """One planner attempt recorded in the trace: the goal that was planned and
    the planner stats that attempt produced."""

    goal: str
    nodes: int = 0
    depth: int = 0
    timed_out: bool = False
    plan_len: int = 0


class PlanTreeNode(BaseModel):
    """One node in the chosen objective's prerequisite tree (TUI plan screen).

    Frozen recursive value object. `kind` drives the glyph; `status` drives the
    style. `root_stub` nodes are the non-chosen ranked roots (no children).
    """

    model_config = ConfigDict(frozen=True)

    key: str                    # stable id for expansion memory (usually repr(node))
    label: str
    kind: str                   # obtain | skill | charlevel | step | root_stub
    status: str                 # met | unmet | current
    detail: str = ""
    children: tuple["PlanTreeNode", ...] = ()


class CycleSnapshot(BaseModel):
    """Everything a watcher needs about one bot cycle. Frozen at end-of-cycle."""

    cycle_index: int
    timestamp: str  # ISO-8601 UTC
    character: str

    # State
    x: int
    y: int
    level: int
    xp: int
    max_xp: int
    hp: int
    max_hp: int
    gold: int
    inventory: dict[str, int] = Field(default_factory=dict)
    inventory_max: int = 0
    equipment: dict[str, str | None] = Field(default_factory=dict)
    skills: dict[str, int] = Field(default_factory=dict)
    skill_xp: dict[str, int] = Field(default_factory=dict)
    task_code: str | None = None
    task_type: str | None = None
    task_progress: int = 0
    task_total: int = 0

    # Cooldown (seconds remaining at snapshot time; 0 when free)
    cooldown_remaining: float = 0.0

    # Decision
    selected_goal: str
    action: str
    action_kind: str = "other"          # move|gather|fight|rest|other (TUI animation)
    action_target: str | None = None    # gather resource / fight monster / "x,y"
    outcome: str
    goal_rank: list[GoalRankEntry] = Field(default_factory=list)
    path_next_action: str | None = None
    projected_cycles_to_max: float | None = None
    max_level: int = 0
    remaining_levels: int = 0

    # Planner trace internals (the deep per-cycle detail also written to
    # traces.jsonl) — surfaced for the full-screen log modal.
    planner_nodes: int = 0
    planner_depth: int = 0
    planner_timed_out: bool = False
    plan_len: int = 0
    goals_tried: list[GoalAttempt] = Field(default_factory=list)
    suppressed_goals: list[str] = Field(default_factory=list)
    path_blocked: bool = False

    # Committed strategy root + ranking + bank, for the TUI plan screen.
    chosen_root: str | None = None
    strategy_ranking: list[RootScoreView] = Field(default_factory=list)
    bank_items: dict[str, int] | None = None
    plan_tree: tuple[PlanTreeNode, ...] = ()

    # The runtime skill-grind legs captured this cycle when the executed action
    # was a LevelSkill (the concrete gather/craft chain the planner re-derives
    # per cycle and discards). Empty on non-grind cycles. Rendered under the
    # current step in the plan tree and flattened into the log.
    grind_expansion: tuple[PlanTreeNode, ...] = ()

    # Arbiter anti-starvation epic follow-up: the runtime gear-focus aging
    # ledger, so a trace can verify the fall-off climbs and SUSTAINS across
    # level-ups instead of resetting. `GamePlayer._gear_focus` is keyed by
    # the `(slot, code)` tuple; JSON object keys must be strings, so each key
    # is encoded as `f"{slot}|{code}"` (see `GamePlayer._focus_key_str`).
    gear_focus: dict[str, int] = Field(default_factory=dict)
    # Whether THIS cycle's committed gear pick went through the focus-aging
    # interleave (`StrategyDecision.aged_pick`) rather than the plain argmax.
    aged_pick: bool = False
    # The d'Hondt seat accumulator (`GamePlayer._interleave_seats`), keyed by
    # equipment slot.
    interleave_seats: dict[str, int] = Field(default_factory=dict)
