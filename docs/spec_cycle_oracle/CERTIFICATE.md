# Certificate of behavioral completeness — <project>

**This is a certificate, not a proof.** Deciding whether a specification is complete
is undecidable in general (Rice). What follows is the result of an adversarial
search that failed to find a gap. Read the RESIDUALS section before relying on it.

## Scope — what this certificate is relative to

| field | value |
|---|---|
| `agent_class` | claude-opus-4-8 |
| `toolchain` | Python 3.13 |
| `sigma` | value semantics, persisted state, error taxonomy |
| `spec_hash` | sha256:0000000000000000 |
| `dry_rounds` | 2 |
| `blind_rounds` | 3 (every round verified blind) |
| `blindness_failures` | 0 |
| `k_required` | 2 |

**A weaker agent or a weaker toolchain voids this certificate.** Completeness is
relative to `(agent class, toolchain)`: the type system carries spec bits, so a
spec complete for one toolchain is routinely incomplete for the same behavior in
another. And an adversary weaker than `agent_class` will find gaps this one could
not.

`spec_hash` covers `SPEC.md`, `OBSERVATION.md`, and `ONTOLOGY.md`. **Change any of
them and this certificate is void** — a single clause added after certification is
a clause no adversary ever probed.

## Evidence

| | |
|---|---|
| grid | 3 subjects × 7 stimuli = 21 cells, 0 blank |
| cells probed | 17 (4 `IGNORE`, carved out) |
| adversaries spent | 11 |
| witnesses raised | 14 |
| root causes after clustering | 7 |
| resolved into clauses | 7 |
| consecutive non-void dry rounds | 2 |
| adversary canary | passed every round |
| judge decoys | killed every round |
| clauses | 12 |
| load-bearing | 12 |
| zero-bit | 0 (2 found and deleted) |
| mutation canary | passed |

## RESIDUALS — what this certificate does NOT establish

*Mandatory. A certificate without this section is marketing.*

**0. Adversary blindness.** Every round was checked with `blindness_lint` against its own
transcripts: no agent read source, an oracle, or a reference implementation. This matters
because an adversary that consults the code is not testing the spec — it is diffing
spec-against-code, and **the code cannot tell you what the spec should have said.** Where
the implementation is itself wrong, such an adversary confirms the bug and reports the spec
as fine. A certificate from a round that was not verified blind is worthless.

**1. Correlated priors.** This certificate establishes that adversaries of class
`claude-opus-4-8` could not find a divergence. It does **not** establish that no
divergence exists. Those adversaries share a prior, and they will silently agree on
"obvious defaults" this spec never states. Adversarial framing and model diversity
reduce this; they do not eliminate it.

**2. Σ is itself a specification.** Everything outside Σ is undetermined *by
design* and was never probed. If Σ is wrong, this certificate is confidently wrong.
The dimensions declared OUT are listed in `OBSERVATION.md`, each with the reason we
are content to let the implementer choose freely.

**3. Carve-outs.** These grid cells were deliberately not specified:

| cell | justification |
|---|---|
| Order / add-item | Orders are immutable once created; line edits act on the Cart. |
| … | … |

**4. Prose-only clauses.** These clauses landed on the bottom rung of the discharge
table. Nothing enforces them. **They are the bug budget.**

| clause | why it could not be discharged |
|---|---|
| … | … |

**5. Auto-resolved gaps.** Gaps the build loop resolved without human ratification,
if the run was unattended. Each one is behavior an agent chose, not a human.

| gap | default chosen | ratified? |
|---|---|---|
| … | … | … |

**6. Mutual redundancy.** The mutation gate deletes one clause at a time, so it
cannot see two clauses that forbid exactly the same thing — both read as zero-bit.
Any group flagged `mutual_redundancy` had all but one member deleted, never the
whole group.

**7. Contradiction, as distinct from silence.** This certificate establishes that
adversaries could not find behavior the spec fails to determine. It does **not**
establish that the spec determines that behavior *consistently*. The loop hunts
silences; it does not hunt two clauses that both apply and disagree. Where a formal
clause and a narrative clause conflict, a judge — and your implementer — will follow
the formal one, and the certificate will read green either way.

**8. Named assumptions.** Things this spec depends on but cannot state, and cannot
check.

| assumption | why it is unprovable here | how it is monitored |
|---|---|---|
| … | … | … |
