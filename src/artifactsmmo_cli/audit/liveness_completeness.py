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

THE STALL REPORT. The census used to raise a gate alarm whenever the lifetime
count of `Wait` cycles grew past a hand-bumped baseline. A lifetime tally cannot
tell a ten-second spin from a four-hour deadlock, and it never fell, so every
incident meant editing a number. It is replaced by a REPORT of stalls: each
character's stretch of consecutive `Wait` cycles lasting `STALL_MIN_SPAN` or
longer, with the goal the character was on before it stuck. The report never
fails `--check`; it is there to be read.
"""

import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1] / "ai"

#: The shortest run of consecutive `Wait` cycles, first to last, that the report
#: lists as a stall. The user's ruling (2026-10-19): Waiting is not itself a
#: defect, so this is "report only, 10 minutes is fine". It replaces a gate on
#: the lifetime Wait tally against a hand-bumped baseline, which the user ruled
#: not a useful test.
STALL_MIN_SPAN = timedelta(minutes=10)

#: The store's `selected_goal` repr of `WaitGoal`.
WAIT_GOAL_REPR = "Wait"

#: Classes with no observed run and a REASON. The key is the class name; the
#: value says why dormancy is expected and what would end it. A reason of the
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
    # CompleteTask{Goal,Action} and TaskCancel{Goal,Action} LEFT THIS TABLE on
    # 2026-08-27, for the same reason and by the same rule as the accept pair
    # above: the store shows each of them running. The task lifecycle now closes
    # end to end — a task is accepted, worked, and either completed or cancelled
    # — so "requires a task worked to completion" is no longer a reason nobody
    # has met. It is a thing the fleet has done.
    #
    # 2026-10-08: `LowYieldCancelGoal` LEFT this list — the class was deleted
    # with the retired low-yield cancel chain (Phase 5-2c-iii cleanup).
    # 2026-10-08: `PursueTaskGoal` and `TaskTradeAction` LEFT this list — the
    # task objective's held items task ran live (Robby `PursueTask(coal)`, HAL
    # `PursueTask(spruce_plank)`: 242 cycles, 16 `TaskTrade` deliveries).
    # 2026-10-06: `TaskExchangeGoal`/`TaskExchangeAction` LEFT this list — the
    # task objective's exchange (c-2 #2) ran 5 cycles live, Lor's paying out.
    # 2026-09-13: ExpandBankGoal and BuyBankExpansionAction were removed from
    # this table entirely. They carried `unreachable: MeansKind.BANK_EXPAND is
    # in the discretionary band` for as long as that band sat below the
    # objective step; the promotion into COLLECT_REWARD_ORDER retired the
    # reason, and Robby bought an expansion at 09:11:47 the same day (bank
    # 50 -> 70 slots, -3500 gold). They are LIVE, and the census says so.
    # 2026-10-11: `JoinPartyGoal` / `HoldForPartyAction` (group fights increment
    # 4b) were declared conditional and ran live within the hour of the push —
    # they never belonged in this table past the first fleet cycle.
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
    # --- Raids. RECLASSIFIED 2026-08-18 to `unreachable:` — every raid goal was
    # appended at BAND_DISCRETIONARY, below even the FALLBACK steps, so "a timed
    # bonus that yields to a step present in 14,064 of 14,064 cycles is one that
    # expires unused, so the rationale defeats itself".
    #
    # BAND FIXED 2026-08-23 (wave 3a fix-round 1): raids sit at their own
    # `BAND_RAID`, above the fallback steps and below the committed objective
    # step — the priority `_raid_candidates`' docstring always claimed.
    #
    # STILL `unreachable:` (fix-round 2). The band was only ONE of TWO blockers,
    # and correcting it moved the wall rather than removing it. The other is the
    # SURVIVABILITY gate: `expected_damage_per_fight` has no turn cap and no
    # shared-raid model, so it prices a SOLO kill of a raid boss.
    # Measured 2026-08-23 against `pixie` (600,000 hp): monster_per_turn 629.35,
    # player_kill_step 204.58, 2,933 rounds -> 1,844,857 expected damage, so
    # `raid_survivable_pure(1570, 1570, 1844857)` is False and
    # `_raid_candidates` builds nothing. That holds for ANY raid boss a real
    # loadout could meet, so the goal still cannot fire live.
    #
    # The offline pair passes its gate only because those two scenarios run
    # `derive_combat_stats=False`: with no attack, `player_kill_step <= 0`,
    # expected damage is 0, and the gate waves it through. A shared-raid damage
    # model is a wave-4 change, not a cutover fix.
    "ParticipateRaidGoal": "unreachable: expected_damage_per_fight prices a SOLO "
                           "raid-boss kill (pixie: 1,844,857 vs 1,570 hp), so "
                           "raid_survivable_pure refuses every real loadout",
    # --- Genuinely conditional on world state the fleet has not met.
    "TeleportAction": "conditional: needs an unlocked teleport destination",
    # --- Conditional on a character state the fleet has not reached.
    "UnlockBankGoal": "conditional: the bank is already unlocked for every live character",
    "ReachUnlockLevelGoal": "conditional: fires only below the bank-unlock level",
    # TRUE SINCE 2026-09-14, AND IT WAS NOT BEFORE. This reason shipped while
    # `DepositAllAction.execute` called `deposit_item` and nothing else, so it
    # excused the action with a mechanism that did not exist and no character
    # banked a coin in 184,010 cycles. `DepositAllAction._gold_deposit` now
    # issues the gold request on the same trip, which is why the action itself
    # stays dormant: the planner has no separate gold step to pick.
    "DepositGoldAction": "conditional: gold is banked inside DepositAllAction.execute, not as a separate planner step",
    "UseGoldBagAction": "conditional: no gold bag has dropped",
    # --- Subsumed: a live sibling does the same work, so these are candidates
    # for DELETION rather than activation. Flagged so the choice is deliberate.
    "MoveAction": "subsumed: travel is folded into each action's own venue hop",
    "MoveTo": "subsumed: superseded by the venue model in obtain_sources",
    # GeFillSellOrderAction WAS here as "subsumed: the fleet posts sell orders and
    # fills buys". It went LIVE on 2026-08-19: `UpgradeEquipmentGoal` now
    # synthesizes the GE fill for its own target, so a standing sell order is a
    # route the planner can take. C3P0 bought `adventurer_pants` for 1,498 gold
    # with it — the purchase that ended an 84-cycle Wait deadlock. The census
    # flagged the declaration stale on the first six executed cycles, which is
    # what the stale check is for.
    # --- Two more downstream of the dead task subsystem, established 2026-08-18.
    "ReachCurrencyGoal": "unreachable: routed only from a currency-blocked leaf, "
                         "and it mints only tasks_coin, which requires tasks",
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
    # CurrencyTurnInGoal LEFT THIS TABLE on 2026-09-21, one restart after
    # SurrenderCurrencyGoal did, and the note there predicted it. Lor was the
    # elected buyer: `Unequip(artifact1_slot)` ->
    # `Withdraw(lich_race_medal x9)` -> `NpcBuy(lich_race_trophy x1
    # @archaeologist)` at 01:50-01:51 UTC, 14 minutes after the restart, then
    # `Equip(lich_race_trophy->artifact1_slot)`. The whole fleet-currency
    # mechanism is now live end to end: 10 medals pooled from five characters'
    # worn artifacts, one trophy bought.
    # --- Provision-marginal-fight. Its gate needs a utility-slot heal already in
    # the bag; measured live, `best_held_heal` is None and both utility slots are
    # empty on all five characters. `UseConsumableAction` fires 1,621 times, so
    # the fleet does eat — just never a utility-slot heal it is holding for a
    # fight. Adjacent to the objective never ranking a utility candidate.
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
        and "remove the declaration" is the wrong remedy. How long the bot sat
        in Wait is the stall report's question (`find_stalls`).
        """
        return (self.observed > 0 and self.declared is not None
                and not self.declared.startswith("witness:"))


@dataclass(frozen=True)
class Stall:
    """One character's run of consecutive `Wait` cycles spanning `STALL_MIN_SPAN`
    or longer."""

    character: str
    start: datetime           # the run's first Wait cycle
    end: datetime             # the run's last Wait cycle
    waits: int                # Wait cycles in the run
    preceding_goal: str | None  # the last non-Wait cycle's goal; None when there is none


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


def _goal_stem(goal: str) -> str:
    """The repr's class name before any `(` or `[`."""
    return re.split(r"[(\[]", goal)[0].strip()


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
            stem = _goal_stem(goal)
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


def stall_runs(cycles: Iterable[tuple[str, str, str | None]]) -> list[Stall]:
    """Stalls in `(character, ts, selected_goal)` cycles given in timestamp order,
    newest first.

    Each character keeps its own run: another character's cycle neither extends
    nor ends it. Any non-Wait cycle by the same character — including one that
    selected nothing — ends the run and becomes the next run's preceding goal."""
    previous: dict[str, str | None] = {}
    open_runs: dict[str, tuple[str | None, list[datetime]]] = {}
    found: list[Stall] = []
    for character, ts, goal in cycles:
        key = character
        if goal is not None and _goal_stem(goal) == WAIT_GOAL_REPR:
            open_runs.setdefault(key, (previous.get(key), []))[1].append(
                datetime.fromisoformat(ts))
            continue
        _close_run(key, open_runs, found)
        previous[key] = goal
    for key in list(open_runs):
        _close_run(key, open_runs, found)
    return sorted(found, key=lambda s: s.start, reverse=True)


def _close_run(key: str, open_runs: dict[str, tuple[str | None, list[datetime]]],
               found: list[Stall]) -> None:
    """End `key`'s open run, keeping it when it spans `STALL_MIN_SPAN`."""
    if key not in open_runs:
        return
    preceding, stamps = open_runs.pop(key)
    if stamps[-1] - stamps[0] >= STALL_MIN_SPAN:
        found.append(Stall(character=key, start=stamps[0], end=stamps[-1],
                           waits=len(stamps), preceding_goal=preceding))


def find_stalls(db_path: str) -> list[Stall] | None:
    """Stalls in a learning DB, newest first, or None when there is no DB —
    nothing read is not the same as nothing stalled. Read-only, like
    `observed_counts`."""
    if not Path(db_path).exists():
        return None
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
        cycles = conn.execute(
            "select character, ts, selected_goal from cycles order by ts, id").fetchall()
    return stall_runs(cycles)


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


def render_matrix(rows: list[LivenessRow], stalls: list[Stall] | None) -> str:
    """The generated report. Ordered dead-first: the rows that need a decision
    are the ones worth seeing at the top of a diff. The stall section follows;
    `stalls` is None when no store was read."""
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
    out += [
        "",
        "## Stalls",
        "",
        "A stall is one character's run of consecutive `Wait` cycles whose first and",
        f"last cycle are at least {STALL_MIN_SPAN.total_seconds() / 60:g} minutes "
        "apart; any other cycle by that",
        "character ends the run. Report only: a stall never fails `--check`.",
        "Newest first; `preceding goal` is the character's last non-Wait goal before",
        "the run.",
        "",
    ]
    if stalls is None:
        out.append("No store was read, so no stalls can be reported.")
        return "\n".join(out) + "\n"
    out += [
        f"{len(stalls)} stalls.",
        "",
        "| character | start | end | Wait cycles | preceding goal |",
        "|---|---|---|---|---|",
    ]
    for st in stalls:
        goal = "none" if st.preceding_goal is None else f"`{st.preceding_goal}`"
        out.append(f"| {st.character} | {st.start.isoformat(timespec='seconds')} "
                   f"| {st.end.isoformat(timespec='seconds')} | {st.waits} | {goal} |")
    return "\n".join(out) + "\n"
