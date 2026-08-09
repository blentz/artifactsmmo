# Σ — Observation alphabet

**Artifact under test:** the **cycle oracle** — a pure function that, given one
character state, a target character level, a body of learned observations, and the
game's static catalogue, answers two questions: *how far up the level ladder can
this character get*, and *how many executed planner actions does that cost*.

It is the producer whose results `docs/spec_unified_objective/SPEC.md` consumes as
opaque inputs. That spec says so in as many words — *"no clause here constrains its
accuracy"* — and this spec exists to constrain it.

**Application class:** offline pure projection/simulation core inside an autonomous
game-playing planner. Not a service, not a UI, no network in front of it. It is
called once per candidate per decision, several times a cycle.

**Agent class `A`:** Claude Opus 5 adversaries/judges (spec-forge defaults).

**Toolchain `T`:** Python 3.13 (`uv`), `mypy --strict`, `ruff`, Lean 4 + mathlib
with mechanical extraction (`scripts/extract_lean.py`), Hypothesis differential
harness against a Lean oracle, mutation gate (`formal/diff/mutate.py`), pytest at
100% line coverage. `fractions.Fraction` available for exact rational arithmetic;
no dependent types, no refinement types.

---

## Dimension verdicts

| # | Dimension | Verdict | Boundary / justification |
|---|---|---|---|
| 1 | Value semantics | IN | The reachable level and the cycle count ARE the product. Both are read by a ranking core that decides what the character does next, so any difference in either is a different implementation. |
| 2 | Error taxonomy | IN | The oracle must define behaviour when the ladder cannot be climbed, when no monster is beatable, when the target is already met, and when the learned observations are empty. Whether the caller can tell these apart is in Σ — the consuming spec bands on exactly that distinction. |
| 3 | Persisted state | OUT | The oracle is pure and writes nothing. The learning store is a read-only INPUT; no later read can observe anything the oracle did. |
| 4 | Side effects | OUT | No API calls, no writes, no notifications. An implementation performing one is already out of spec, so granting the freedom costs nothing. |
| 5 | Idempotence | IN | Determinism: identical inputs must produce identical results on every call, with no dependence on call order or hidden state. Two calls within one decision must agree, or the ranking they feed is incoherent. |
| 6 | Ordering | IN | The per-level path is an ordered output: which monster is chosen at each rung, and in what order the rungs are crossed, are both consumed (the planner reads the first segment to pick its next fight). |
| 7 | Concurrency | OUT | Single-threaded per character; called from one planner loop. Multi-character runs share no state through it. |
| 8 | Timing | PARTIAL | **Boundary:** wall-clock latency is OUT — a faster oracle is not a different oracle. **Game cycles are IN**: they are the output's unit. This boundary is load-bearing; the predecessor of this function was denominated in seconds while named cycles and ran ~80× high. |
| 9 | Resource bounds | PARTIAL | **Boundary:** memory and allocations are OUT. The **number of distinct beatability verdicts computed** is IN — it is quadratic in ladder length × catalogue size, it dominates the cost, and the planning budget is real (an earlier walk shipped that was exponential in a different parameter and doubled live cycle time). |
| 10 | Interface shape | OUT | Internal module with no published contract: names, argument order, and file layout are free. No consumer outside this repo binds to them. |
| 11 | Presentation | OUT | No UI surface of its own. The TUI renders the projection; layout and copy are the TUI's concern. |
| 12 | Observability | PARTIAL | **Boundary:** log and trace WORDING is OUT. The per-rung path CONTENT is IN — the trace audit and the status pane both parse it, and the planner acts on its first segment. |

**No dimension is undeclared.**

---

## Notes on the three PARTIAL boundaries

**Timing (8).** Two clocks appear here and must never be conflated: *wall-clock
seconds* (OUT) and *game cycles*, one per executed planner action (IN — the output's
unit). "The oracle is slow" is out of Σ. "The oracle returns a different number of
cycles" is in. The whole reason this artifact is being specified separately is that
a unit error in it is invisible to the spec that consumes it.

**Resource bounds (9).** Beatability is the expensive predicate and the ladder is
long (up to 49 rungs against a catalogue of every monster in the game). An
implementation that hoists the verdict out of the rung loop and one that recomputes
it per rung are **not** interchangeable — and, note, they are not even necessarily
computing the same thing, which is a value question (dimension 1), not only a cost
one. Both readings are in Σ.

**Observability (12).** The path is a genuine contract: the planner reads the first
segment's monster to decide what to fight next, and the TUI renders the chain. "The
path omits rungs it crossed" is a real, in-Σ divergence. "A rung is a dataclass vs a
tuple" is not.

## Explicitly OUT — freedoms granted

- Names of functions, parameters, locals, and the module file.
- Whether the oracle memoises internally, provided determinism (5) and the
  verdict-count bound (9) hold.
- Log/trace *wording*.
- Numeric representation (`int`, `float`, `Fraction`) **except** where a clause
  requires exactness, or where the choice changes a reported value — a rounding
  that changes which rung is reported reachable is in Σ via dimension 1.
- The order in which candidate monsters at one rung are examined, provided the
  selection among them is deterministic and the reported choice is the same.
