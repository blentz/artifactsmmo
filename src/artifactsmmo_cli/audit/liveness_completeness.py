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
#: Witness firings already investigated, per class. The alarm fires only ABOVE
#: this count.
#:
#: An alarm nothing can clear is an alarm everyone learns to ignore, and these
#: cycles are in the store permanently. Raising a number here is not a way to
#: silence it: it requires writing down what was found, exactly as `DORMANT`
#: requires a reason. If the count grows, something deadlocked AGAIN.
WITNESS_BASELINE: dict[str, int] = {
    # 2026-08-20 23:22-23:51, 24 cycles out of 66,250 ever, all within 40 minutes
    # of the tier-1 winnability gate (e4df6bef) shipping. Two causes:
    #   C3P0 x12 — the gear latch armed only on a LOSS, and the gate stopped the
    #              bot taking the fight it was losing, so the cure lost its
    #              trigger. FIXED: the latch now arms on the deficit FACT.
    #   HAL  x12 — `GrindCharacterXP(sheep)` ranked at 30.0 but planned to
    #              plan_len 0 in 3 nodes, at hp 258/310 and inventory 109/132
    #              (83%): too full to fight, below the 85% deposit guard. A dead
    #              band between two thresholds. OPEN.
    "WaitGoal": 24,
    "WaitAction": 24,
}

#: form "unreachable: ..." is a DEFECT that is being tracked, not an excuse —
#: the census reports those separately so they cannot hide among the benign.
DORMANT: dict[str, str] = {
    # --- Structurally unreachable, tracked. See
    # `docs/PLAN_priority_ladder_unification.md`: the discretionary means band
    # sits below the objective step, and a step is present in 14,064 of 14,064
    # traced cycles, so nothing in that band can be selected.
    #
    # AcceptTaskGoal / AcceptTaskAction LEFT THIS TABLE on 2026-08-19: ACCEPT_TASK
    # was promoted into COLLECT_REWARD_ORDER (S-051, gated on an owed draw), and
    # the store recorded its first selection — after 0 of 63,310 cycles. The
    # entries below are RECLASSIFIED with it: they were declared unreachable
    # because no task could ever be held, and that premise is gone. They are
    # CONDITIONAL now — waiting on a draw the fleet has not yet made in anger,
    # not on a structure that forbids one.
    "PursueTaskGoal": "conditional: requires a held items-task the projection says to pursue",
    "CompleteTaskGoal": "conditional: requires a task worked to completion",
    "CompleteTaskAction": "conditional: emitted only by CompleteTaskGoal",
    "TaskCancelGoal": "conditional: requires a held task AND a pocket tasks_coin "
                      "to spend on the cancel (S-052 works one it cannot discard)",
    "TaskCancelAction": "conditional: emitted only by TaskCancelGoal",
    "LowYieldCancelGoal": "conditional: requires a held task and enough samples to judge it",
    "TaskExchangeGoal": "conditional: requires tasks_coin, earned only by "
                        "completing tasks",
    "TaskExchangeAction": "conditional: emitted only by TaskExchangeGoal",
    "TaskTradeAction": "conditional: items-task delivery, requires a held items-task",
    "ExpandBankGoal": "unreachable: MeansKind.BANK_EXPAND is in the discretionary band",
    "BuyBankExpansionAction": "unreachable: emitted only by ExpandBankGoal",
    "PostBuyBidGoal": "unreachable: MeansKind.GE_BID is in the discretionary band",
    "GePostBuyOrderAction": "unreachable: emitted only by PostBuyBidGoal",
    # --- PROOF WITNESS. Never firing is this rung WORKING, not this rung dead.
    # `Formal.Liveness.NoDeadlockV2.productionLadder_total` — the headline
    # no-deadlock theorem, that the bot always has something to do — is proved
    # VIA `wait_mem_ladder` and `waitFires s = true`, i.e. `wait` is the ladder's
    # totality witness. It is last in DISCRETIONARY_ORDER and fires
    # unconditionally, so anything above it firing instead is the guarantee
    # being redundant, which is the point. Deleting it breaks the proof.
    "WaitGoal": "witness: MeansKind.WAIT is the unconditional last resort that "
                "proves the ladder total (Liveness.NoDeadlockV2)",
    "WaitAction": "witness: the action WaitGoal emits; same proof obligation",
    # --- Raids. RECLASSIFIED 2026-08-18: `conditional:` was wrong. No raid has
    # been open while the fleet ran, but that is not what stops it — every raid
    # goal is appended at BAND_DISCRETIONARY (`_raid_candidates`' call site), and
    # its own docstring calls that "the right priority for a timed bonus". A
    # timed bonus that yields to a step present in 14,064 of 14,064 cycles is one
    # that expires unused, so the rationale defeats itself. Even with an open
    # window, a known tile and a survivable boss it could not be selected.
    "ParticipateRaidGoal": "unreachable: appended at BAND_DISCRETIONARY, below "
                           "the objective step, so a raid window closes unused",
    # --- Genuinely conditional on world state the fleet has not met.
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
        """Declared dormant, but the store shows it running.

        A `witness:` row is deliberately EXCLUDED. Its declaration is not a claim
        that the rung is unused — it is a claim that the rung firing means
        something is WRONG — so observing it does not make the declaration stale
        and "remove the declaration" is the wrong remedy. See
        `liveness_alarm`.
        """
        return (self.observed > 0 and self.declared is not None
                and not self.declared.startswith("witness:"))

    @property
    def liveness_alarm(self) -> bool:
        """A PROOF WITNESS fired — the bot did the thing that means it was stuck.

        The census had exactly one signal for "the bot deadlocked" and it was
        `WaitGoal`'s declaration going stale. That framing gave the wrong advice:
        STALE says "remove the declaration", and removing this one invites
        deleting the witness that proves the ladder total — which
        `test_a_proof_witness_is_never_reclassified_as_deletable` exists to stop,
        after it nearly happened on 2026-08-18.

        Same detection, opposite remedy. The declaration STAYS; what needs
        attention is why everything above the witness had nothing to offer.

        Live 2026-08-20: `Wait` fired 24 times out of 66,250 cycles ever, all of
        them in the 40 minutes after the tier-1 winnability gate shipped — C3P0
        x12 (its gear latch armed only on a LOSS, and the gate stopped it taking
        the fight it was losing, so the cure lost its trigger) and HAL x12
        (`GrindCharacterXP(sheep)` ranked but planned to plan_len 0 at inventory
        109/132, a dead band below the 85% deposit guard).
        """
        return (self.declared is not None
                and self.declared.startswith("witness:")
                and self.observed > WITNESS_BASELINE.get(self.name, 0))


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


def liveness_alarms(rows: list[LivenessRow]) -> list[LivenessRow]:
    """Proof witnesses the store shows FIRING — the bot was stuck. See
    `LivenessRow.liveness_alarm`."""
    return [r for r in rows if r.liveness_alarm]


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
            f"stale {len(stale(rows))}; liveness alarms {len(liveness_alarms(rows))}"
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
        if r.liveness_alarm:
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
        elif r.liveness_alarm:
            status = "**LIVENESS ALARM**"
        elif r.stale_declaration:
            status = "**STALE**"
        elif r.declared:
            status = "dormant"
        else:
            status = "live"
        seen = "unknown" if r.observed < 0 else str(r.observed)
        out.append(f"| `{r.name}` | {r.kind} | {seen} | {status} | {r.declared or ''} |")
    return "\n".join(out) + "\n"
