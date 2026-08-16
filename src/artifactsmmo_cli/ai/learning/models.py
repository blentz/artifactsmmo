"""SQLModel definitions for the GOAP learning store.

The two-model pattern: `CycleBase` is a non-table SQLModel (full Pydantic
validation at construction). `Cycle(CycleBase, table=True)` adds persistence.

Construct as `Cycle.model_validate(data)` or `Cycle(**CycleBase(...).model_dump())`
to get validation; construct as `Cycle(...)` directly to skip validation (SQLModel's
default for table models, optimised for ORM round-trips).
"""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CycleBase(SQLModel):
    """Non-table base: Pydantic validates all fields at construction."""

    ts: str = Field(index=True)
    session_id: str = Field(index=True)
    cycle_index: int
    character: str = Field(index=True)

    # State snapshot
    x: int | None = None
    y: int | None = None
    hp: int | None = None
    max_hp: int | None = None
    gold: int | None = None
    level: int | None = None
    xp: int | None = None
    inventory_used: int | None = None
    inventory_max: int | None = None
    bank_accessible: bool = True
    task_code: str | None = None
    task_type: str | None = None
    task_progress: int | None = None
    task_total: int | None = None

    # Goal + action
    selected_goal: str | None = Field(default=None, index=True)
    action_repr: str | None = Field(default=None, index=True)
    action_class: str | None = None
    outcome: str

    # Cost & planner
    predicted_cost: float | None = None
    actual_cooldown_seconds: float | None = None
    planner_nodes: int | None = None
    planner_depth: int | None = None
    planner_timed_out: bool | None = None
    plan_len: int | None = None

    # Effects (state delta from previous cycle)
    delta_gold: int | None = None
    delta_xp: int | None = None
    delta_hp: int | None = None
    delta_inv_used: int | None = None
    drops_json: str | None = None
    # Per-skill XP delta as JSON {skill_name: int}. Sparse — only skills
    # whose XP actually changed appear. Default "{}" so old rows are valid.
    # Read by Phase G-B projections to attribute skill-XP yield per cycle.
    delta_skill_xp_json: str = Field(default="{}")

    skill_levels_json: str | None = Field(default=None)
    """The character's skill levels BEFORE this cycle's action, as a JSON
    object, or None for a row written before this column existed (2026-08-15).

    PRE-ACTION, and that is load-bearing: the server's `level_penalty` applies
    at the level held when the xp is paid, so a replay reading the level after
    the action misattributes every action that levels the skill.

    `cycles` has always carried the character LEVEL (`level`) and skill
    DELTAS (`delta_skill_xp_json`), but never SKILL levels, which is why
    measurements needing `skill_level - content_level` had to read
    play-trace files instead — a dependency this column removes. See
    `docs/superpowers/specs/2026-08-15-harnesses-read-the-learning-store-design.md`.

    NULLABLE, NOT BACK-FILLED. The rows already in the wild were written
    without levels and cannot acquire them; inventing one would hand a
    measurement a fabricated observation."""

    # Items consumed this cycle as JSON {item_code: qty}. Sparse — non-empty
    # only on fights that consumed equipped utility consumables. Generalizes
    # to any utility effect (Phase 2 resolves each code's effect).
    consumables_expended_json: str = Field(default="{}")

    # Goal completion tracking
    cycles_to_satisfy: int | None = None


class Cycle(CycleBase, table=True):
    """ORM-persisted Cycle. Inherits all fields from CycleBase."""

    __tablename__ = "cycles"

    id: int | None = Field(default=None, primary_key=True)


class SessionBase(SQLModel):
    """Non-table base: Pydantic validates all fields at construction."""

    started_at: str
    character: str = Field(index=True)
    ended_at: str | None = None
    cycle_count: int = 0
    exit_reason: str | None = None


class Session(SessionBase, table=True):
    """ORM-persisted Session row, one per GamePlayer.run() invocation."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)


class BlockerBase(SQLModel):
    """A learned dependency: doing X requires reaching some prerequisite first.

    First instance: HTTP 496 on bank deposit — the bank's achievement gate
    requires killing a monster the player cannot yet beat. We remember the
    monster + required character level so that future sessions skip
    bank-dependent goals until the prerequisite is met.
    """

    blocker_code: str = Field(primary_key=True)
    character: str = Field(index=True)
    unlock_monster: str | None = None
    required_level: int = 0
    discovered_at: str  # ISO-8601 UTC timestamp


class Blocker(BlockerBase, table=True):
    """ORM-persisted blocker."""

    __tablename__ = "blockers"


class SkillXpObservation(SQLModel, table=True):
    """Observed `<skill>_max_xp` (XP to reach the next level) at a given level,
    per character. One row per (character, skill, level); last write wins."""

    __tablename__ = "skill_xp_observations"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    skill: str = Field(index=True)
    level: int
    max_xp: int


class TaskRewardObservation(SQLModel, table=True):
    """Gold-equivalent value of a completed task's reward, per character."""

    __tablename__ = "task_reward_observations"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    value: float


class LearnedSetting(SQLModel, table=True):
    """Generic per-character key/int store for facts the bot learns from
    API responses and that should survive session restarts. First use:
    `task_exchange_min_coins` — the taskmaster's per-exchange coin cost,
    discovered by climbing past HTTP 478 ("missing items") rejections.
    Without persistence each new session re-pays ~3-5 HTTP 478 rejections
    to re-learn the same minimum (trace: 42 HTTP_478 across ~10 sessions =
    ~4 per restart, exactly the discovery climb)."""

    __tablename__ = "learned_settings"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    key: str = Field(index=True)
    value: int


class RoleLease(SQLModel, table=True):
    """One character's claim on a specialization role. NOT exclusive: any
    number of characters may hold the same role at once.

    `role` was UNIQUE, which made a role a scarce resource and forced a fixed
    five-way partition of the roster. Live 2026-08-03 showed what that costs:
    `mining` was the strongest skill for FOUR of five characters, one `miner`
    slot existed, and the three losers of the startup race cascaded into roles
    they had no levels in (the account's best miner, mining 21, served alchemy
    16). Allocation has to follow demand — zero alchemists when nothing needs
    alchemy, three loggers when woodcutting demand warrants it — so the
    scarcity had to go.

    The key is now UNIQUE `(role, character)`, which is the row's actual
    identity: "this character holds this role". It is load-bearing, not
    decorative. `CoordinationStore.live_leases` returns holders per role and
    `role_selection` DIVIDES a role's demand by its holder count, so a
    duplicated row would silently halve the demand a role advertises. The
    constraint makes that unrepresentable rather than merely unlikely.

    `expires_at` is the single liveness rule in the coordination system: a row
    is real if unexpired. A crashed child stops renewing and its lease
    evaporates without supervisor involvement."""

    __tablename__ = "role_leases"
    __table_args__ = (UniqueConstraint("role", "character", name="uq_role_lease_holder"),)

    id: int | None = Field(default=None, primary_key=True)
    role: str = Field(index=True)
    character: str = Field(index=True)
    claimed_at: str
    expires_at: str


class MaterialDemand(SQLModel, table=True):
    """One character's declared unmet need for one item. Upsert key is
    (character, item_code). Carries the same `expires_at` liveness rule as
    RoleLease so a dead character's demand stops being served on the same
    clock that frees its role."""

    __tablename__ = "material_demand"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    item_code: str = Field(index=True)
    quantity: int
    expires_at: str


class HoldingLedger(SQLModel, table=True):
    """One character's holding of one DUAL-ROLE item — worn plus carried.

    Upsert key is (character, item_code), replaced wholesale like
    `MaterialDemand`, because holdings are a snapshot of right now and a spent
    unit must stop counting toward a fleet threshold at once.

    Only dual-role codes are published (`ai/dual_role_currency`), so this table
    stays a handful of rows per character rather than a mirror of five
    inventories. The bank is NOT published: it is account-shared, so every
    child would publish the same units and the fleet total would multiply by
    the number of children.

    Carries the same `expires_at` liveness rule as `RoleLease`,
    `MaterialDemand`, `BankStockClaim` and `GeOrderClaim` — a row is real if
    unexpired — so the coordination system still has exactly ONE liveness
    rule."""

    __tablename__ = "holding_ledger"
    __table_args__ = (
        UniqueConstraint("character", "item_code", name="uq_holding_ledger_holder"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    item_code: str = Field(index=True)
    quantity: int
    expires_at: str


class BankStockClaim(SQLModel, table=True):
    """One character's claim on BANK stock it is withdrawing. Upsert key is
    (character, item_code), the same shape as `MaterialDemand`.

    The bank is ACCOUNT-shared, so every `play --all` child holds the same
    `bank_items` snapshot and `bank_drain.bank_drain_excess` derives the same
    shed licence from it — five characters independently concluding they may
    take the same 17 eggs. The losers of that race spend an action-bucket
    request on HTTP 478 "Missing required item(s)"; the 2026-08-05 validation
    run wasted 7 of 72 cycles that way. This table is where a character says
    "these units are spoken for" so siblings subtract them before deriving
    their own licence.

    Carries the same `expires_at` liveness rule as `RoleLease` and
    `MaterialDemand` — a row is real if unexpired — so the coordination system
    still has exactly ONE liveness rule. `claimed_at` is diagnostic only:
    nothing orders claims by it, because an ordering would be a decision
    tiebreak and the loser of a simultaneous claim is already covered by the
    HTTP 478 -> replan backstop.

    NOT a lock. Nothing blocks on it and nothing consults it for correctness:
    the withdraw itself is authoritative, and a claim that is missed simply
    reproduces today's behaviour."""

    __tablename__ = "bank_stock_claims"
    __table_args__ = (
        UniqueConstraint("character", "item_code", name="uq_bank_stock_claim_holder"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    item_code: str = Field(index=True)
    quantity: int
    claimed_at: str
    expires_at: str


class GeOrderClaim(SQLModel, table=True):
    """One character's claim on a GRAND EXCHANGE order it is cancelling. Upsert
    key is (character, order_id).

    Grand Exchange orders are ACCOUNT-scoped: `/my/grandexchange/orders` returns
    the same list to every `play --all` child, so all five age the same order
    past `ge_order_config.TTL_CYCLES` and all five independently decide to
    cancel it. The losers of that race spend an action-bucket request on
    HTTP 404 "Order not found". Measured on the 2026-08-10 five-character run:
    6 of 20 distinct order ids were attacked by two or more characters, costing
    8 wasted requests out of a budget that pays out only ~52 actions per
    character per hour — see `docs/PLAN_ge_cancel_race.md`.

    Per-ORDER rows that ACCUMULATE, unlike `BankStockClaim`'s replace-wholesale.
    A bank claim describes the one withdraw a character has in flight, so a new
    one makes the old stale. Cancels are different: `cancel_targets` can report
    several ids at once and the planner works through them one action per cycle,
    so an earlier claim is still live when the next is written. Replacing would
    un-hide an order this character is still working toward.

    Carries the same `expires_at` liveness rule as `RoleLease`,
    `MaterialDemand` and `BankStockClaim` — a row is real if unexpired — so the
    coordination system still has exactly ONE liveness rule. `claimed_at` is
    diagnostic only; nothing orders claims by it, because an ordering would be
    a decision tiebreak.

    NOT a lock, exactly like `BankStockClaim`. Nothing blocks on it: the cancel
    request itself is authoritative and the HTTP 404 -> replan path still
    exists unchanged, so a claim that is missed simply reproduces today's
    behaviour rather than breaking anything."""

    __tablename__ = "ge_order_claims"
    __table_args__ = (
        UniqueConstraint("character", "order_id", name="uq_ge_order_claim_holder"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    order_id: str = Field(index=True)
    claimed_at: str
    expires_at: str


class TurnInClaim(SQLModel, table=True):
    """The election of exactly ONE character to spend a fleet-shared currency
    on one turn-in item.

    `HoldingLedger` lets every character SEE the fleet's total holding of a
    dual-role item, but seeing the same total is exactly what makes it
    dangerous: once the total crosses a turn-in threshold, all five children
    read the same fact on the same cycle and each would recall the same
    units unless exactly one of them acts. This table is that one-of-five
    lock.

    Modelled on `RoleLease.claim`'s ORIGINAL pre-2026-08-03 shape (see
    `coordination_store.py` git history at `fd71410c`), not on its current
    non-exclusive one: `role_leases` stopped contending when its key widened
    to `(role, character)`, but a turn-in has the opposite requirement — it
    MUST contend, so exactly one winner exists. The key here is UNIQUE on
    `item_code` ALONE, not `(character, item_code)`, and that is the entire
    mechanism: two characters claiming the same item write to the SAME row,
    so the second write either loses to a live incumbent or, if the
    incumbent already expired, takes the row over. Keying on `(character,
    item_code)` instead — the shape every OTHER claim table in this module
    uses — would let every character hold its own row for the same item and
    all five would "win" silently.

    Carries the same `expires_at` liveness rule as `RoleLease`,
    `MaterialDemand`, `HoldingLedger`, `BankStockClaim` and `GeOrderClaim` —
    a row is real if unexpired — so a character that crashes mid-turn-in does
    not hold the trophy hostage for longer than one liveness window."""

    __tablename__ = "turn_in_claims"
    __table_args__ = (UniqueConstraint("item_code", name="uq_turn_in_claim_item"),)

    id: int | None = Field(default=None, primary_key=True)
    item_code: str = Field(index=True)
    character: str = Field(index=True)
    claimed_at: str
    expires_at: str


class PlanBodyLogBase(SQLModel):
    """One computed plan body, logged at re-plan time. Counted by the Phase-2
    macro detector."""

    character: str = Field(index=True)
    session_id: str = Field(index=True)
    ts: str
    goal_repr: str = Field(index=True)
    head_action_repr: str = Field(index=True)
    body_json: str  # JSON list[str] of action reprs


class PlanBodyLog(PlanBodyLogBase, table=True):
    __tablename__ = "plan_body_log"

    id: int | None = Field(default=None, primary_key=True)


class PlanCommitmentBase(SQLModel):
    """The bot's live plan commitment — one row per character, upserted on each
    re-plan, for restart-resume."""

    character: str = Field(primary_key=True)
    goal_repr: str
    goal_json: str  # JSON serialization of the goal (see goal_serialization, Task 5)
    plan_json: str  # JSON list[str] of action reprs
    cursor: int
    crafting_target: str | None = None
    latch_active: bool = False
    replanned_ts: str


class PlanCommitment(PlanCommitmentBase, table=True):
    __tablename__ = "plan_commitment"


class CraftYieldObservation(SQLModel, table=True):
    """Observed output quantity and XP per craft run, per character + item.

    One row per (character, item_code); last write wins. The bot records this
    from real craft responses so the planner can ground-truth CraftSchema.quantity.
    """

    __tablename__ = "craft_yield"

    character: str = Field(primary_key=True)
    item_code: str = Field(primary_key=True)
    quantity: int
    xp: int
    skill_level: int | None = Field(default=None)
    """The crafting skill's level when `xp` was observed, or None for a row
    recorded before this column existed (2026-08-15) or by a caller that could
    not resolve the skill.

    XP FALLS AS THE SKILL RISES — the server's `level_penalty` term — so `xp`
    alone is "N at some level" and goes stale silently as the character levels
    past it. This column is what makes a row usable as an input to a per-skill
    XP fit rather than merely as corroboration; without it the fit's own
    `skill_level` term has nothing to regress against. See
    `docs/superpowers/specs/2026-08-15-observed-craft-xp-numerator-design.md`.

    NULLABLE ON PURPOSE. The rows already in the wild cannot acquire a level
    retroactively, and inventing one — 0, or the character's level today —
    would feed the fit a fabricated observation. A consumer must exclude
    None rather than default it."""


class LoadoutProfileObservation(SQLModel, table=True):
    """The loadout the bot uses for a recurring task. One row per (character,
    task_key); last write wins. task_key is 'combat:<monster>' / 'gather:<skill>'.
    `loadout` is JSON {slot: code}. Source for sub-project C's keep economy + D's
    learned loadout."""

    __tablename__ = "loadout_profile"

    character: str = Field(primary_key=True)
    task_key: str = Field(primary_key=True)
    loadout: str  # JSON-encoded dict[slot, code]


class CombatLoadoutOutcome(SQLModel, table=True):
    """One row per resolved fight: the worn loadout, predict_win's verdict, and the
    actual result. APPEND (calibration history; NOT last-write). task_key is
    'combat:<monster>'. `loadout` is JSON {slot: code}. Read-only diagnostics
    (sub-project D); drives no bot behavior."""

    __tablename__ = "combat_loadout_outcome"

    id: int | None = Field(default=None, primary_key=True)  # autoincrement
    character: str = Field(index=True)
    task_key: str
    loadout: str  # JSON {slot: code}
    predicted_win: bool
    actual_win: bool
