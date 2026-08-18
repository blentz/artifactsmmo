# Observation alphabet (Σ) — the cycle economy

**Class:** pure decision core. Given a world state, choose what the bot does next and
what that choice costs, in cycles. No I/O, no rendering, no network.

**Toolchain:** Python 3.13; `mypy --strict`; `ruff`; `pytest` with a 100%-coverage
gate and `-W error`; Hypothesis; a Lean 4 differential harness with a mutation gate
(`formal/`). The type rung is nearly empty (see
`references/toolchain-profiles/python.md`), so the specification bar here is the
HIGH one — a clause that Rust would discharge in a type must be stated, validated,
property-tested and mutation-checked.

**Agent class:** the models configured for this run's adversaries, judges and
verifiers; recorded in CERTIFICATE.md at issue time.

**Artifact under test:** the decision logic named in SPEC.md — the objective's walk
and its cost (`J`), the means comparison, and the acquisition route set.

**Explicitly NOT under test**, and therefore never a clause: the A* planner's search;
the loadout picker; the combat model (`predict_win`, `expected_damage_per_fight`);
the coordination protocol (claims, elections, holdings); the executor that performs
the chosen action; the server's own rules. These supply INPUTS to the comparison. A
witness about their internals is out of scope and belongs in RESIDUALS.

---

| # | Dimension | Verdict | Boundary / why you are content to let the implementer choose |
|---|---|---|---|
| 1 | Value semantics | IN | Which option is chosen for a given state, and the cycle figure attached to it. This is the entire spec. |
| 2 | Error taxonomy | IN | The decision core is TOTAL — `NoDeadlockV2.productionLadder_total` proves it always returns something. So "failure" here is a distinguishable *output*: no route to an item, a walk that cannot complete, an unpriceable route. A caller must be able to tell "costs a lot" from "cannot be done", and S-005 turns the second into the first. Conflating them is the `10^6` sentinel defect this spec exists to remove. |
| 3 | Persisted state | PARTIAL | READS are IN: the learning DB's observed rates, craft yields and task rewards change the chosen option, so two implementations reading different columns diverge observably. WRITES are OUT — no clause here decides what the store records, and the recording path is the executor's. |
| 4 | Side effects | OUT | The core returns a CHOICE; it performs no game action. Executing the choice — and therefore every consequence of accepting a task or spending a coin — belongs to the executor, which is not under test. |
| 5 | Idempotence | IN | The decision runs once per cycle and is re-run after every failure and replan. The same state must yield the same choice; a core that drifted between two evaluations of one unchanged state would make the sticky-commitment machinery incoherent. |
| 6 | Ordering | IN | Not just the winner. The full ranking is consumed downstream — `justifying_identities` filters the candidate set to those that beat the trunk, and ties are broken by input position. Two implementations agreeing on the winner and disagreeing on second place diverge observably. |
| 7 | Concurrency | IN | Five characters decide concurrently against one shared store. A means whose value depends on a sibling's holdings or claim (supply, turn-in) can be chosen by two characters in the same tick, and whether that is legal is a Σ question. |
| 8 | Timing | IN | Bounded, and the bound is a contract: the decision must complete inside the planning window, which is the remaining cooldown floored at 15 s. Measured today at 6–34 s, i.e. already violating it. Acceptance criterion A9. |
| 9 | Resource bounds | PARTIAL | IN for the per-decision compute that feeds dimension 8 — the count of projection walks and route pricings, which is what makes or breaks A9. OUT for memory and for the planner's own node budget, which is not under test. |
| 10 | Interface shape | OUT | Every name here is internal. No published contract, no external consumer. Naming witnesses are noise and would drown the loop. |
| 11 | Presentation | OUT | TUI panes and CLI formatting render the decision; they do not make it. |
| 12 | Observability | PARTIAL | IN for the `learning.db` columns downstream tooling PARSES — `cycles.selected_goal`, `cycles.action_class`, `cycles.delta_skill_xp_json`, `cycles.action_repr` — because the liveness census and the grind-rate estimator read them as an API, and a change to their shape breaks a gate. OUT for free-text diagnostics, trace prose and log wording. |
