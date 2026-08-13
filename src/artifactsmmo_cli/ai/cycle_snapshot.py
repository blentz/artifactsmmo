"""CycleSnapshot: frozen per-cycle state + decision context for TUI consumers."""

from pydantic import BaseModel, ConfigDict, Field

from artifactsmmo_cli.ai.fight_record import FightRecord


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


class ObjectiveUnplannable(BaseModel):
    """The FIRST candidate the arbiter attempted this cycle, which produced no
    plan — while a LOWER-ranked candidate was executed instead.

    "First attempted", not "rank-1": `select_pure` short-circuits to the
    sticky-committed goal before walking the ranked list, so under a live
    commitment this is the committed objective. Either way it is the objective
    the arbiter was pursuing and abandoned. A satisfied or suppressed candidate
    is never attempted, so it never lands here.

    Absent on every other cycle. The fall-through is intended; its silence was
    not — live traces 2026-08-12 show UpgradeEquipment(greater_wooden_staff)
    attempted first and abandoned on 955 consecutive cycles with nothing
    recorded, so 31 hours of runtime read as a deliberate choice to grind XP."""

    goal: str
    nodes: int = 0
    depth: int = 0
    timed_out: bool = False


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


class RoleChange(BaseModel):
    """The specialization role this character gave up or took THIS cycle.

    Carried on the snapshot rather than diffed by the widget that renders it.
    `build_log_lines` is pure over ONE snapshot, and the alternative — a widget
    holding the previous snapshot — cannot survive `LogPane.replace_history`:
    the store's per-character buffer is a bounded `deque`, so a replay starts at
    whatever cycle is still retained and its predecessor is simply gone. The
    same history would then render one way live and another way after a focus
    switch. Detecting the transition where it HAPPENS (the player's coordination
    block) makes both renderings the same function of the same data.

    A release and the following claim are SEPARATE cycles by construction —
    `_update_coordination` sets `_role = None` on a release and only claims on a
    later cycle — so `previous` and `current` are never both non-None. Both
    being None cannot occur: the field is only set when the role actually
    changed.

    `reason` comes from `role_selection.RoleDecision.reason`, i.e. from the rule
    that fired. Empty when the decision named none; renderers omit the clause
    rather than inventing one."""

    model_config = ConfigDict(frozen=True)

    previous: str | None = None
    current: str | None = None
    reason: str = ""


class CycleSnapshot(BaseModel):
    """Everything a watcher needs about one bot cycle. Frozen at end-of-cycle."""

    cycle_index: int
    timestamp: str  # ISO-8601 UTC
    character: str

    # State
    x: int
    y: int
    layer: str = "overworld"
    """Map layer the character stands on (`WorldState.layer`).

    Coordinates alone do NOT identify a tile: (0,0) exists on the overworld,
    underground and interior layers alike. Without this the map pane drew
    overworld content under a character standing in an interior, and the two
    tiles printed identically in the HUD. Defaults to overworld so snapshots
    built before this field existed still validate."""
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
    objective_unplannable: ObjectiveUnplannable | None = None
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

    # The transcript of the fight executed this cycle, when the action was a
    # FightAction that reached the server. None on every other cycle. Drives the
    # log pane's summary line and the fight modal.
    fight: FightRecord | None = None

    # Cross-character coordination (emergent-specialization spec, Task 11).
    role: str | None = None
    """The specialization role this character held this cycle, or None when it
    holds none (every cycle of a single-character run)."""

    supply_target: str | None = None
    """`repr` of the sibling demand being served this cycle, or None. This is
    the trace field that proves collusion actually fired.

    Shape: `repr((item_code, target banked quantity, unmet demand))`, the triple
    `GamePlayer._pick_supply_target` returns. `tui.plan_format
    .parse_supply_target` is the one reader that takes it apart."""

    role_change: RoleChange | None = None
    """The role transition that happened on THIS cycle, or None on the
    overwhelming majority of cycles where the role did not change (and on every
    single-character run). See `RoleChange` for why the transition is detected
    at the source instead of being diffed by the log widget."""
