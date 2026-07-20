# PLAN: fall-off for low-yield currency grinds (event tickets)

Status: **DESIGNED, not implemented.** 2026-07-20.
Cannot be built right now: the bot is running, so `pytest` cannot run concurrently
and this touches the arbiter focus ledger, which has a Lean mirror.

## Trigger

Robby is live-selecting `GatherMaterials(event_ticket, {event_ticket:2})`.

## The economics (upstream changelog 8.2.0, 07/19/26)

| Source | Drop rate | Expected cost |
|---|---|---|
| Monsters | 1% | **100 kills per ticket** |
| Resources | 0.5% | **200 gathers per ticket** |
| Raids | guaranteed | **1 per 20,000 damage dealt** |

Sinks: *Lich Race Medal* = 100 tickets. *Lich Race Trophy* = 10 Medals = 1,000
tickets.

So the current 2-ticket goal is ~400 gather actions. A single Medal is ~10,000
kills or ~20,000 gathers. A Trophy is ~100,000 kills. No cap on accumulation is
documented.

## Why the existing fall-off does not cover it

`player.py:268-277` `_gear_root_key` returns `None` unless the root has BOTH a
`slot` and a `code`, and says so deliberately:

> "Non-gear roots (ReachCharLevel, task roots, and slot-less ObtainItem
> recipe-input steps) do not age — only a root that targets a specific equipment
> slot competes with siblings for that slot."

A currency root has no slot, so it never enters `_gear_focus`, never decays, and
never yields a d'Hondt seat to a sibling. It can hold the arbiter indefinitely —
the same failure `project_ring2_arbiter_starvation` fixed for gear, in a root
shape that fix cannot see.

## The reframing this forces

The gear fall-off was justified by SLOT CONTENTION ("siblings compete for that
slot"). That is the wrong general principle. The real one is:

> A root that makes negligible progress per cycle must not monopolize the
> arbiter, regardless of what it targets.

Slot contention was a proxy for that, adequate while gear was the only long root.
A 0.5%-per-action currency grind is statistically indistinguishable from the STUCK
wolf_ears root that motivated the original fix — 199 of every 200 cycles produce
nothing observable.

## Design sketch (needs review before building)

1. **Generalise the ledger key.** `_gear_focus` becomes a root-focus ledger keyed
   by a semantic root identity, not `(slot, code)`. Gear roots keep their existing
   key so their proven behaviour is unchanged; currency/material roots get
   `(kind, code)`. Do NOT key on `repr` — see `feedback_no_alphabetical_tiebreak`;
   a decision key must be semantic.

2. **Keep one curve.** Reuse `focus_aging_pick` / the d'Hondt interleave exactly as
   proven. This is a change to WHICH roots enter the ledger, not to the curve or
   the scheduler — that keeps `ProgressionTree.lean` and the interleave
   no-starvation proof intact. Verify that claim before writing code.

3. **Reset semantics.** Gear focus resets on level-up (pruned to live candidates)
   and on equippable craft. The currency analogue is: reset when the currency is
   SPENT, or when the target quantity is reached. An unreset currency ledger would
   decay to the floor and stay there forever, which is wrong — the bot should
   return to ticket farming periodically, not abandon it.

4. **Yield target.** With no fall-off the bot burns ~400 actions on 2 tickets. With
   one, it interleaves gear/XP/task progress and still accumulates tickets in the
   background. The floor (currently `1/9`) already guarantees the root is never
   fully starved.

## The raid connection — this is the important part

Raids drop tickets at a **guaranteed** 1 per 20,000 damage, versus 1% per kill.
For any character that can contribute damage to a raid boss, raids are the
efficient ticket source by a wide margin — and unlike the 1% roll, the yield is
deterministic and therefore PLANNABLE.

That makes `ParticipateRaid` (epic P4, `docs/PLAN_events_raids_epic.md`) not merely
the fix for the L48 wall but the correct answer to ticket demand. Recall from the
raid mechanics that a raid fight is won by SURVIVING 100 TURNS or killing the boss,
so a character too weak to kill can still farm damage-thresholded rewards.

Sequencing implication: build the fall-off first (it is the safety net that stops
the bot sinking 20,000 gathers into a currency), then P4 gives it a far better
source to hand off to.

## Open questions

1. Should the fall-off be **yield-aware** — i.e. keyed on observed drops per action
   from the learning store — rather than a flat curve? The store already tracks
   per-action outcomes. A yield-aware curve would decay a 0.5% grind fast and a 50%
   grind slowly, which is more honest than treating all long roots alike.
2. Does the currency's SINK matter? Farming 2 tickets is very different from
   farming 1,000 for a Trophy. A goal that can never realistically complete
   (100,000 kills) arguably should not be pursued at all rather than merely aged.
3. Does generalising the ledger key disturb the Lean mirror or the d'Hondt
   no-starvation proof? Must be answered BEFORE code — the proof is over the
   scheduler, which should be untouched, but the claim needs checking.
