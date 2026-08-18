"""Liveness census: has every Goal and Action this bot defines ever actually RUN?

THE CENSUS THIS REPO DID NOT HAVE. Six censuses gate on whether the planner CAN
do a thing. None asks whether it ever DID. Measured 2026-08-18 over 63,310 live
cycles, that gap was hiding a lot:

  * 18 of 34 `Goal` classes and 17 of 36 `Action` classes had never fired once,
    and none of the 18 appeared in a `plan_body_log` body either.
  * No character had EVER held a task (`task_code` non-null in 0 of 63,310
    cycles, over 16 days and five characters), which silently killed six goals in
    a chain and the whole `tasks_coin` funding epic built on them.
  * The unified objective `J` had never executed (`docs/PLAN_bounded_horizon_objective.md`).
  * `MeansKind.CURRENCY_TURNIN`, shipped 2026-08-16, has never been selected —
    and the reason turned out to be two reasons, one of them a scope limit
    nobody had stated (see `CurrencyTurnInGoal` below).

Every one of those was found by hand, late, after the code had been green for
weeks. A green test suite says the code is CORRECT; it says nothing about whether
it is REACHED.

WHY DORMANCY MUST BE DECLARED, NOT INFERRED. "Never fired" is not automatically a
defect. `ParticipateRaidGoal` needs a live raid; code merged this morning has not
run yet. So the census does not fail on dormancy — it fails on UNDECLARED
dormancy. Every class must be either observed live or carry a written reason in
`DORMANT`, and adding a new Goal or Action without either is what turns the gate
red. That makes the question unavoidable at the moment the code is written, which
is the only moment the answer is cheap.

IT ALSO FAILS ON A STALE DECLARATION. A class declared dormant that the store
shows running means the reason is no longer true, and a reason nobody rechecks is
worse than none — it is a green light with an out-of-date argument behind it.

TWO MODES, AND THE OFFLINE ONE IS THE GATE. With no learning DB (CI, a fresh
clone) the census still runs and still fails on an undeclared class: the roster
comes from the SOURCE, so completeness of the declaration is checkable without any
observations at all. A DB, when present, adds the live counts and the
stale-declaration arm. That is deliberate — a census that could only run where the
bot had already played would be exactly the kind of thing that never runs.
"""

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1] / "ai"

#: Classes with no observed run and a REASON. The key is the class name; the
#: value says why dormancy is expected and what would end it. A reason of the
#: form "unreachable: ..." is a DEFECT that is being tracked, not an excuse —
#: the census reports those separately so they cannot hide among the benign.
DORMANT: dict[str, str] = {
    # --- Structurally unreachable, tracked. See
    # `docs/PLAN_priority_ladder_unification.md`: the discretionary means band
    # sits below the objective step, and a step is present in 14,064 of 14,064
    # traced cycles, so nothing in that band can be selected.
    "AcceptTaskGoal": "unreachable: MeansKind.ACCEPT_TASK is in DISCRETIONARY_ORDER, "
                      "below the objective step, present in 14064 of 14064 cycles",
    "AcceptTaskAction": "unreachable: emitted only by AcceptTaskGoal",
    "PursueTaskGoal": "unreachable: requires a held task, and AcceptTask can never be selected",
    "CompleteTaskGoal": "unreachable: requires a held task; task_code non-null in 0 of 63,310 cycles",
    "CompleteTaskAction": "unreachable: emitted only by CompleteTaskGoal",
    "TaskCancelGoal": "unreachable: requires a held task",
    "TaskCancelAction": "unreachable: emitted only by TaskCancelGoal",
    "LowYieldCancelGoal": "unreachable: requires a held task to judge",
    "TaskExchangeGoal": "unreachable: requires tasks_coin, earned only by "
                        "completing tasks",
    "TaskExchangeAction": "unreachable: emitted only by TaskExchangeGoal",
    "TaskTradeAction": "unreachable: items-task delivery, requires a held task",
    "MaintainConsumablesGoal": "unreachable: MeansKind.MAINTAIN_CONSUMABLES is in the discretionary band",
    "ExpandBankGoal": "unreachable: MeansKind.BANK_EXPAND is in the discretionary band",
    "BuyBankExpansionAction": "unreachable: emitted only by ExpandBankGoal",
    "PostBuyBidGoal": "unreachable: MeansKind.GE_BID is in the discretionary band",
    "GePostBuyOrderAction": "unreachable: emitted only by PostBuyBidGoal",
    "WaitGoal": "unreachable: MeansKind.WAIT is last in the discretionary band",
    "WaitAction": "unreachable: emitted only by WaitGoal",
    # --- Genuinely conditional on world state the fleet has not met.
    "ParticipateRaidGoal": "conditional: needs a live raid; none has been open while the fleet ran",
    "MapTransitionAction": "conditional: needs a layer transition (raid/underground areas)",
    "TeleportAction": "conditional: needs an unlocked teleport destination",
    # --- Conditional on a character state the fleet has not reached.
    "UnlockBankGoal": "conditional: the bank is already unlocked for every live character",
    "ReachUnlockLevelGoal": "conditional: fires only below the bank-unlock level",
    "DepositGoldAction": "conditional: gold is banked by DepositAll, not as a separate step",
    "WithdrawGoldAction": "conditional: no goal has needed banked gold yet",
    "UseGoldBagAction": "conditional: no gold bag has dropped",
    # --- Subsumed: a live sibling does the same work, so these are candidates
    # for DELETION rather than activation. Flagged so the choice is deliberate.
    "MoveAction": "subsumed: travel is folded into each action's own venue hop",
    "MoveTo": "subsumed: superseded by the venue model in obtain_sources",
    "UnequipAction": "subsumed: OptimizeLoadoutAction performs swaps atomically",
    "GeFillSellOrderAction": "subsumed: the fleet posts sell orders and fills buys",
    # --- Two more downstream of the dead task subsystem, established 2026-08-18.
    "ReachCurrencyGoal": "unreachable: routed only from a currency-blocked leaf, "
                         "and it mints only tasks_coin, which requires tasks",
    "ReachSkillGoal": "unreachable: constructed only under MeansKind.PURSUE_TASK, "
                      "which requires a held task",
    # --- Currency turn-in. Investigated 2026-08-18 with the fleet stopped; the
    # answer is TWO independent reasons, and only one of them is conditional.
    #
    # Measured fleet holdings against every sink's price:
    #   cowhide      33 >= hard_leather@3   READY
    #   snake_hide    4 >= snakeskin@4      READY
    #   wool          3 >= cloth@3          READY
    #   lich_race_medal 4 <  trophy@10      short 6
    #   event_ticket   34 <  medal@100      short 66
    #
    # The three READY ones are blocked by RULE 3 of `_resolve_turn_in` — the
    # buyer's `pick_loadout_cached` must place the bought item in a SLOT. All
    # three are `type=resource` (cloth, hard_leather, snakeskin), so no loadout
    # can ever hold one and rule 3 can never pass. The mechanism is named
    # "currency turn-in" but can only ever buy EQUIPMENT.
    #
    # The one equippable sink IS correctly gated: R2D2 at L20 passes rules 3 and
    # 4 for `lich_race_trophy` (wears it, level-qualified) and waits only on
    # stock. So this rung is genuinely conditional AND carries a scope limit.
    "CurrencyTurnInGoal": "conditional: the only sink whose item a loadout can "
                          "wear (lich_race_trophy) needs 10 medals and the fleet "
                          "holds 4; every READY sink buys a resource, which "
                          "_resolve_turn_in rule 3 can never accept",
    "SurrenderCurrencyGoal": "conditional: the holder side of the same election, "
                             "so it waits on the same turn-in being resolved",
    # --- Provision-marginal-fight. Its gate needs a utility-slot heal already in
    # the bag; measured live, `best_held_heal` is None and both utility slots are
    # empty on all five characters. `UseConsumableAction` fires 1,621 times, so
    # the fleet does eat — just never a utility-slot heal it is holding for a
    # fight. Adjacent to the objective never ranking a utility candidate.
    "ProvisionMarginalFightGoal": "conditional: needs a held utility-slot heal; "
                                  "best_held_heal is None on every character",
}


#: Goal reprs whose leading identifier is not the class name with `Goal` stripped.
#: EXPLICIT, not a prefix heuristic: a heuristic that credited `EquipOwnedGear` to
#: `EquipOwnedGoal` by common prefix would also credit unrelated near-neighbours,
#: and an over-credit here reads a dead class as live — the one direction this
#: gate must never fail in. One entry today; the gate checks it is still earned.
REPR_ALIASES: dict[str, str] = {
    "EquipOwnedGear": "EquipOwnedGoal",
}


@dataclass(frozen=True)
class LivenessRow:
    """One Goal or Action class and what the store has seen of it."""

    name: str
    kind: str            # "goal" | "action"
    observed: int        # cycles selecting/executing it; -1 when no store was read
    declared: str | None  # its DORMANT reason, or None

    @property
    def live(self) -> bool:
        return self.observed > 0

    @property
    def undeclared_dormant(self) -> bool:
        """The must-be-zero residual: never ran and nobody said why."""
        return self.observed == 0 and self.declared is None

    @property
    def stale_declaration(self) -> bool:
        """Declared dormant, but the store shows it running."""
        return self.observed > 0 and self.declared is not None


def defined_classes() -> dict[str, str]:
    """`{class_name: "goal"|"action"}` for every Goal/Action subclass under `ai/`.

    Read from the SOURCE, not from an import graph: the roster must be complete
    even for a class nothing imports yet, which is exactly the class most likely
    to be dead on arrival."""
    out: dict[str, str] = {}
    pattern = re.compile(r"^class (\w+)\((?:\w+, )*(Goal|Action)\b", re.M)
    for path in sorted(AI_ROOT.rglob("*.py")):
        for match in pattern.finditer(path.read_text()):
            name, base = match.group(1), match.group(2)
            out[name] = "goal" if (base == "Goal" or name.endswith("Goal")) else "action"
    return out


def observed_counts(db_path: str) -> dict[str, int]:
    """`{class_name: cycles}` from a learning DB, or `{}` when there is none.

    Goals are counted by the LEADING identifier of `selected_goal` — the repr's
    class name before any `(`. Actions are counted by `action_class`, which the
    store already records as the bare class name.
    """
    if not Path(db_path).exists():
        return {}
    counts: dict[str, int] = {}
    # `closing`, not a bare `with`: sqlite3's own context manager commits the
    # transaction and leaves the CONNECTION open, so a bare `with` leaks it and
    # the suite (which runs `-W error`) turns the ResourceWarning into a failure.
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
        for goal, n in conn.execute(
                "select selected_goal, count(*) from cycles "
                "where selected_goal is not null group by 1"):
            stem = re.split(r"[(\[]", goal)[0].strip()
            counts[stem] = counts.get(stem, 0) + n
            # `UpgradeEquipment` is the repr of `UpgradeEquipmentGoal`; the store
            # records reprs, the roster records class names. Credit both spellings
            # rather than maintaining a hand-written repr->class map that would be
            # one more thing to keep in step.
            counts[stem + "Goal"] = counts.get(stem + "Goal", 0) + n
            alias = REPR_ALIASES.get(stem)
            if alias is not None:
                counts[alias] = counts.get(alias, 0) + n
        for action, n in conn.execute(
                "select action_class, count(*) from cycles "
                "where action_class is not null group by 1"):
            counts[action] = counts.get(action, 0) + n
            counts[action + "Action"] = counts.get(action + "Action", 0) + n
    return counts


def run_census(db_path: str) -> list[LivenessRow]:
    """One row per defined class, in name order."""
    counts = observed_counts(db_path)
    has_store = bool(counts)
    return [
        LivenessRow(name=name, kind=kind,
                    observed=counts.get(name, 0) if has_store else -1,
                    declared=DORMANT.get(name))
        for name, kind in sorted(defined_classes().items())
    ]


def undeclared(rows: list[LivenessRow]) -> list[LivenessRow]:
    """The gate's must-be-zero residual."""
    return [r for r in rows if r.undeclared_dormant]


def stale(rows: list[LivenessRow]) -> list[LivenessRow]:
    """Declarations the store contradicts. Empty when no store was read."""
    return [r for r in rows if r.stale_declaration]


def orphan_declarations(rows: list[LivenessRow]) -> list[str]:
    """Entries that name something the source no longer has.

    Covers `DORMANT` — a reason kept for a deleted or renamed class, which would
    silently excuse the wrong thing if the name were reused — and `REPR_ALIASES`,
    whose targets must stay real for the same reason. An alias pointing at a
    class that no longer exists would quietly stop crediting anything, turning a
    live class into a false UNDECLARED."""
    known = {r.name for r in rows}
    return sorted({name for name in DORMANT if name not in known}
                  | {target for target in REPR_ALIASES.values()
                     if target not in known})


def summary_line(rows: list[LivenessRow]) -> str:
    live = sum(1 for r in rows if r.live)
    unknown = sum(1 for r in rows if r.observed < 0)
    tracked = sum(1 for r in rows
                  if r.declared and r.declared.startswith("unreachable:"))
    unclassified = sum(1 for r in rows
                       if r.declared and r.declared.startswith("UNCLASSIFIED:"))
    return (f"{len(rows)} classes; LIVE {live}; declared-dormant "
            f"{sum(1 for r in rows if r.declared)} (of which unreachable {tracked}, "
            f"unclassified {unclassified}); undeclared {len(undeclared(rows))}; "
            f"stale {len(stale(rows))}"
            + (f"; no store read ({unknown} unknown)" if unknown else ""))


def render_matrix(rows: list[LivenessRow]) -> str:
    """The generated report. Ordered dead-first: the rows that need a decision
    are the ones worth seeing at the top of a diff."""
    out = [
        "# Liveness census — has every Goal and Action ever actually run?",
        "",
        "GENERATED by `scripts/gen_liveness.py`. Do not edit by hand.",
        "",
        "A green suite says the code is CORRECT. This says whether it is REACHED.",
        "Dormancy is allowed; UNDECLARED dormancy is not — every class must be",
        "observed live or carry a reason in",
        "`audit/liveness_completeness.DORMANT`. See",
        "`docs/PLAN_priority_ladder_unification.md` for why the `unreachable:`",
        "rows are a defect being tracked rather than a design.",
        "",
        summary_line(rows),
        "",
        "| class | kind | observed | status | reason |",
        "|---|---|---|---|---|",
    ]
    def sort_key(r: LivenessRow) -> tuple[int, str]:
        if r.undeclared_dormant:
            return (0, r.name)
        if r.stale_declaration:
            return (1, r.name)
        if r.declared and r.declared.startswith("UNCLASSIFIED:"):
            return (2, r.name)
        if r.declared and r.declared.startswith("unreachable:"):
            return (3, r.name)
        if r.declared:
            return (4, r.name)
        return (5, r.name)
    for r in sorted(rows, key=sort_key):
        if r.undeclared_dormant:
            status = "**UNDECLARED**"
        elif r.stale_declaration:
            status = "**STALE**"
        elif r.declared:
            status = "dormant"
        else:
            status = "live"
        seen = "unknown" if r.observed < 0 else str(r.observed)
        out.append(f"| `{r.name}` | {r.kind} | {seen} | {status} | {r.declared or ''} |")
    return "\n".join(out) + "\n"
