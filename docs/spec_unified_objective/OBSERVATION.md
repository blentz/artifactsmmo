# Σ — Observation alphabet

**Artifact under test:** a pure decision core that ranks progression candidates
(gear roots and the XP trunk) by a unified objective `J` and returns the chosen
one. Python 3.13, extracted mechanically to Lean 4 and pinned by a
differential + mutation gate.

**Application class:** offline pure decision/ranking core inside an autonomous
game-playing planner. Not a service, not a UI, no network in front of it.

**Agent class `A`:** Claude Opus 5 adversaries/judges (spec-forge defaults).

**Toolchain `T`:** Python 3.13 (`uv`), `mypy --strict`, `ruff`, Lean 4 +
mathlib with mechanical extraction (`scripts/extract_lean.py`), Hypothesis
differential harness against a Lean oracle, mutation gate (`formal/diff/mutate.py`),
pytest at 100% line coverage. Fractions (`fractions.Fraction`) available for exact
rational arithmetic; no dependent types, no refinement types.

---

## Dimension verdicts

| # | Dimension | Verdict | Boundary / justification |
|---|---|---|---|
| 1 | Value semantics | IN | The chosen candidate, and the total order over candidates, are the entire product. |
| 2 | Error taxonomy | IN | The core is total: it must define behaviour for an empty candidate set, an unreachable objective, and a non-finite projection. Which of these are distinguishable to the caller is in Sigma. |
| 3 | Persisted state | OUT | The core is pure and writes nothing. The learning store is a read-only INPUT to the cycle oracle, never an output of this core, so no later read can observe anything it did. |
| 4 | Side effects | OUT | Pure function: no API calls, no writes, no notifications. Any implementation performing one is already out of spec by S-001, so granting this freedom costs nothing. |
| 5 | Idempotence | IN | Determinism: identical inputs must produce the identical choice and order on every call, with no dependence on call order or hidden state. A planner re-deciding mid-plan must not oscillate between equal-scoring candidates. |
| 6 | Ordering | IN | The candidate list is an ordered input and the ranking is an ordered output, consumed in order as the fallback chain. Tie-break behaviour is therefore observable. |
| 7 | Concurrency | OUT | Single-threaded per character; the core is called from one planner loop and multi-character runs share no state through it. No two callers can race on it. |
| 8 | Timing | PARTIAL | Boundary: wall-clock latency is OUT (a faster implementation is not a different one). In-model GAME CYCLE counts are IN — they are the objective's unit, not a performance property. |
| 9 | Resource bounds | PARTIAL | Boundary: memory and allocations are OUT. The NUMBER OF CALLS into the cycle oracle is IN — the oracle walks a level ladder and dominates cost, so per-level-per-candidate versus once-per-candidate is observable against the planning budget. |
| 10 | Interface shape | OUT | Internal module with no published contract: names, argument order and file layout are free, and no consumer outside this repo binds to them. |
| 11 | Presentation | OUT | No UI surface of its own. The TUI renders the ranking, but layout and copy are the TUI's concern and we will not complain about any choice made here. |
| 12 | Observability | PARTIAL | Boundary: log and trace WORDING is OUT. The ranking list is genuinely parsed downstream (trace audit reads category and score; the status pane reads the projection), so its CONTENT is IN while its formatting is OUT. |

**No dimension is undeclared.**

---

## Notes on the two PARTIAL boundaries that will matter

**Timing (8).** Two different clocks appear in this spec and must never be
conflated: *wall-clock milliseconds* (OUT — a faster implementation is not a
different implementation) and *game cycles* (IN — the unit `J` is denominated in).
A witness about "the projection is slow" is out of Σ; a witness about "the
projection returns a different number of cycles" is in.

**Observability (12).** The `ranking` output is a genuine contract because
downstream code parses it: the trace audit reads `category` and `score`, and the
status pane reads the projection. So "the ranking omits candidates that scored
`inf`" is a real, in-Σ divergence. "The ranking is a list of dicts vs a list of
dataclasses" is not.

## Explicitly OUT — freedoms granted

- Names of functions, parameters, locals, and the module file.
- Whether the core memoises internally, provided S-01x's determinism and the
  oracle-call-count bound hold.
- Log/trace *wording*.
- Numeric representation (`int` vs `Fraction`) **except** where exactness is
  required by an explicit clause — a float that changes a comparison outcome is
  in Σ via dimension 1.
