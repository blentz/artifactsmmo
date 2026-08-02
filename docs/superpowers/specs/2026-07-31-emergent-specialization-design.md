# Emergent Specialization Design

Date: 2026-07-31
Status: design approved, not yet planned or implemented

Multi-character `play --all` shipped at `c913b4c4..5fc87acd`. This design adds
coordination between those characters: they diverge onto named roles, publish
what they need to a shared board, and produce for each other through the bank.

## 1. Motivating evidence

`docs/PLAN_multi_character_followups.md` closed the multi-character epic with
one open question: whether five independent AIs racing the same bank thrash
badly enough to need coordination, and it recorded that the question could not
be answered without live traces.

The traces now exist. 29 `play-trace-*.jsonl` files from 2026-07-31, four
characters, 2278 recorded cycles.

**Bank contention is not the problem.** Across all 2278 cycles there were 26
`Withdraw` actions, 9 `DepositAll` actions, and exactly four bank errors: two
`HTTP 478: Missing required item(s)` and two `HTTP 404: Item not found`, all on
`Withdraw`, all recovered through the existing `error:*` -> replan path. Every
other non-`ok` outcome was a network fault. The bank is not contended because
the bank is barely used.

**Duplicated labour is the problem.** Three characters ran the same plan:

| gather target | C3P0 | HAL | R2D2 | Robby |
|---|---|---|---|---|
| copper_rocks | 320 | 321 | 258 | 0 |
| ash_tree | 65 | 65 | 90 | 78 |
| iron_rocks | 0 | 0 | 0 | 148 |

| chosen root | C3P0 | HAL | R2D2 | Robby |
|---|---|---|---|---|
| `ObtainItem(copper_boots)` | 172 | 175 | 127 | 0 |
| `ReachCharLevel(10)` | 142 | 141 | 140 | 0 |
| `ObtainItem(wooden_shield)` | 68 | 68 | 69 | 0 |

899 `copper_rocks` gathers produced three copies of the same copper kit.
`Gather` accounted for 1404 of 2278 actions (62%).

This matters because the binding constraint is the per-IP rate budget, not
wall-clock. A duplicated gather is not free parallelism; it spends a request
from a fixed shared pool. Coordination is the only way to buy throughput back.

## 2. Goal and success criteria

Throughput first, breadth second.

**Throughput.** Characters supply each other through the bank so duplicate work
collapses. Measured against the baseline above: on a comparable multi-character
run, duplicate gather count for a shared material drops materially, and at least
one `Withdraw` succeeds against stock a *different* character deposited. Both
are computable from `learning.db` plus the trace files.

**Breadth.** Characters level different skills so the account unlocks every
crafting tier rather than five characters converging on mining. This follows
from the same mechanism and is the longer-term lever against the L50 wall, but
it is not the first increment.

## 3. What already exists

Three pre-existing facts shape the design and remove most of the plumbing.

**The IPC channel exists.** `MultiRun._child_argv` appends `--learn-db <path>`
to every child, identically. `LearningStore.__init__` opens
`sqlite:///{db_path}` with `PRAGMA journal_mode=WAL` and
`PRAGMA synchronous=NORMAL`. All five children already write to one file, and
every row already carries `character`. No new transport is needed.

**Bank-first sourcing exists.** `ai/obtain_sources.py` ranks `WITHDRAW` first:
"a copy is already in the bank. Consumes nothing new", explicitly preferred over
descending into a recipe. The consumer half of producer/consumer is already
built. The missing half is producer-side surplus.

**Hysteresis has precedent.** `GearLatch` is a set-on-trigger /
clear-on-condition / hold-otherwise latch. `progression_tree.focus_aging_order`
is a d'Hondt interleave built for the ring2 arbiter starvation fix.

Two facts constrain it.

**`LearningStore` is single-character by construction.** Every read filters
`character == self._character`, and that invariant is load-bearing: learned
action costs and success rates must not blend across characters at different
levels with different gear. Cross-character reads cannot be added to it.

**`root_category` is too coarse to carry a role.** `tiers/strategy.py`'s
`root_category` returns only `"char_level"` or `"gear"`. A role cannot express
itself by reweighting that axis.

## 4. Decisions

| decision | choice |
|---|---|
| success criterion | both throughput and breadth, throughput first |
| how a producer learns to over-produce | demand board in the learning store |
| what a profile binds to | named role catalog with per-role weights |
| how a role is taken and held | exclusive lease with TTL heartbeat |
| how sibling demand becomes production | new supply goal plus a role ranking factor |

### 4.1 Why a demand board rather than speculative stock

Bank-first consumption alone changes nothing: each character gathers exactly
what its own plan demands, crafts it, and leaves the bank empty. A consumer
preferring `WITHDRAW` still finds nothing. Throughput requires the producer to
make more than it needs, which requires it to know how much more.

Declared demand keeps that signal explicit, queryable from `learning.db` after
the fact, and attributable to a named requester. Speculative stock floors would
produce items nobody asked for and consume shared bank slots on guesses.

### 4.2 Why a named role catalog

A role catalog is a strategy declaration, in the same category as
`LOADOUT_PROFILES` — not a classification derived from API data. The project
rule it might appear to violate ("keep/junk rules generic over API taxonomy,
never hardcoded") governs *item* classification, which this is not.

The guard that does apply: a role's declared skills are validated against the
live API skill set at load and fail loudly on drift, per "use only API data or
fail with an error". A role naming a skill the server does not have is an error
at construction, not a silent no-op.

`ai/tiers/skill_classes.py` already establishes the discipline to follow. It
derives `GATHER_SKILLS`, `COMBAT_CRAFT_SKILLS` and `CONSUMABLE_CRAFT_SKILLS`
from the api-client `CraftSkill` / `GatheringSkill` enums by set algebra over a
single hand-set policy seed, specifically so the sets "cannot drift from the
schema vocabulary". The role catalog draws its skills from those derived sets
and validates by set membership; the only hand-authored content is the pairing
of skills into roles.

### 4.3 Why leases rather than a score-and-dwell latch

Exclusivity is what actually kills duplicate work. A latch without exclusivity
lets two characters independently choose the same role, which is the present
failure. A lease also recovers from a crashed child without supervisor
involvement — the lease simply expires — which matches `RestartPolicy` already
treating children as disposable.

## 5. Architecture

`LearningStore` stays single-character. Cross-character reads live in one new
class, `CoordinationStore`, sharing the same SQLite file and connection
settings. It is the only place in the codebase that queries without a character
filter, which keeps the "reads siblings" surface auditable in one file.

### 5.1 New tables

Added to `ai/learning/models.py` (cohesive SQLModel schemas — the
one-class-per-file exemption for pure data declarations).

`RoleLease`
- `role: str` — UNIQUE
- `character: str`
- `claimed_at: str` — ISO 8601
- `expires_at: str` — ISO 8601

`MaterialDemand`
- `character: str` — indexed
- `item_code: str` — indexed
- `quantity: int`
- `expires_at: str` — ISO 8601
- upsert key: `(character, item_code)`

Both carry `expires_at`, so the system has exactly one liveness rule: a row is
real if unexpired. A crashed child stops renewing, and its lease and its demand
evaporate on the same clock.

### 5.2 New units

| unit | responsibility | depends on |
|---|---|---|
| `ai/learning/coordination_store.py` | claim / renew / release leases; publish own demand; read live siblings | sqlite engine |
| `ai/role_catalog.py` | named roles -> owned skills + weights; validated against API skill names at load | game data |
| `ai/role_selection.py` | pure: (live leases, own lease, demand by role, dwell) -> keep / claim / release | nothing |
| `ai/role_alignment.py` | pure: role x (slot, code) -> `Fraction` multiplier | recipe closure |
| `ai/goals/supply_bank.py` | `SupplyBankGoal` — produce and deposit top unmet sibling demand | coordination store |

### 5.3 Initial role catalog

Derived sets, given the current schema: `GATHER_SKILLS` is
`{mining, woodcutting, fishing}` (alchemy both gathers and brews and is
classified as consumable-craft), `COMBAT_CRAFT_SKILLS` is
`{weaponcrafting, gearcrafting, jewelrycrafting}`, and
`CONSUMABLE_CRAFT_SKILLS` is `{alchemy, cooking}`.

Five roles cover all eight skills with each skill owned exactly once:

| role | gather | craft |
|---|---|---|
| `miner` | mining | weaponcrafting |
| `logger` | woodcutting | gearcrafting |
| `fisher` | fishing | cooking |
| `jeweler` | — | jewelrycrafting |
| `alchemist` | alchemy | alchemy |

`mining` and `woodcutting` appear in *both* API enums — they cover extraction
and the first processing step alike — so `miner` owning `mining` covers ore
through bar, and `logger` owning `woodcutting` covers log through plank.
Verified against the api-client enums on 2026-07-31: `GatheringSkill` is
`{alchemy, fishing, mining, woodcutting}` and `CraftSkill` is
`{alchemy, cooking, gearcrafting, jewelrycrafting, mining, weaponcrafting,
woodcutting}`.

`jeweler` deliberately owns no gather skill: it is a pure consumer of banked
bars, which exercises the supply chain end to end and is the clearest single
signal that collusion is working.

Five roles against a five-character roster means the catalog is saturated in
the common case. Section 7.2 covers both mismatch directions.

### 5.4 Integration points

**Ranking factor.** `_scaled_weights` in `tiers/progression_tree_core.py`
currently computes `gain * falloff(focus) * synergy * achievability`, keyed by
`(slot, code)`, and its two consumers `focus_aging_pick` and
`focus_aging_order` forward the same factor arguments. `role_alignment` becomes
the fifth factor on the same key across all three, with
a `_NO_ROLE` empty-map sentinel that reads as `Fraction(1)` — byte-identical to
the four-factor weight, matching how `_NO_SYNERGY` and `_NO_ACHIEVABILITY`
already land.

This gives the single-character guarantee structurally: no live sibling leases
means identity everywhere, so `play` without `--all` is bit-identical to current
behavior and every existing test stays valid.

**Supply goal.** `SupplyBankGoal` enters as a discretionary goal whose priority
bonus is aggregate unmet sibling demand routed through
`priority_band.clamp_into_band`, the same construction `scalar_priority` uses.
The survival-floor guarantee is then structural rather than tuned: every
discretionary band ceiling sits below the survival floor of 70.

### 5.5 Rejected alternatives

**Fold sibling demand into the existing obtain model.** Sum sibling demand into
own closure demand so existing `GatherMaterials` targets simply grow and
existing deposit logic banks the leftovers. One seam, maximum reuse. Rejected
because it destroys the distinction between "I need this" and "my sibling needs
this": the character will consume the extra bars in its own craft rather than
bank them, and the inflated demand propagates into `task_reservation` and the
inventory keep-caps. That is the shape of the junk-inventory livelock already
fixed at `bf1273c2`.

**Role weighting only, defer the demand board.** Smallest change, but
divergence alone creates no surplus, so throughput does not move — it fails the
criterion chosen in section 2.

## 6. Data flow

One new block in `GamePlayer.run()`, placed immediately beside
`self._gear_latch.update(...)`, which the surrounding comment already
establishes as the pre-selection slot.

Per cycle, five steps, all local SQLite, zero API calls:

1. `renew()` — extend own lease and own demand-row expiry. One UPDATE.
2. `publish_demand()` — upsert own unmet closure demand for the chosen root.
   Reuses `recipe_closure._closure_demand`, the function `task_reservation`
   already calls, minus owned.
3. `live_view()` — one SELECT of unexpired leases plus unexpired demand,
   excluding self.
4. `role_selection.decide(...)` -> keep / claim / release.
5. The resulting role feeds two consumers: the `role_alignment` map passed into
   `decide()`, and `SupplyBankGoal`'s target and clamped priority bonus.

Three statements against a WAL database, inside a cycle already bounded by a
10-30 second cooldown. Coordination costs nothing from the rate budget that is
the actual binding constraint.

## 7. Hysteresis

Three parameters, each defending a different failure.

**Lease TTL — 600s.** Defends against a crashed child holding a role forever.
Renewed every cycle, so it only has to exceed the longest *legitimate* gap
between cycles — not the cooldown, but a capped `Retry-After` backoff or a long
planner search. Ten minutes clears both, and costs at most ten minutes of an
unworked role against sessions that run for hours.

**Min-hold — 100 cycles.** Defends against thrash between two near-equal roles.
Sized from the traces: characters ran 519-587 cycles per session and the copper
phase alone was ~300 gathers. A dwell shorter than a production run means
switching mid-supply-chain and stranding half-made goods in a bag.

**Switch margin — 2x aggregate unmet demand.** Defends against oscillation from
noise on the board. A ratio rather than an absolute delta because demand
magnitudes span orders — `progression_tree_core` documents a live gain ratio of
18100 to 2000, so any fixed threshold is either always or never met.

**Release-on-idle.** A role whose unmet demand stays zero for a full dwell
window is released even with no better alternative. Without this the design has
a hole: a character that finishes its role keeps renewing a lease nobody needs,
and because it renews, the TTL never fires — the role stays locked for the
session.

Two corrections to that sentence, both discovered in review and both shipped.

*It is a run, not a sample.* "Stays zero for a full dwell window" was written as
a window and implemented as one reading, taken on the single cycle where
`held_cycles` crosses the min-hold. That is not the same predicate. Demand is
published from a character's chosen root, `publish_demand` replaces the row
wholesale, and a root that is not an `ObtainItem` (a level root, a task root)
publishes nothing at all — so a requester that is momentarily on such a root
zeroes its own demand row. Across the 39 traced sessions this is 4.8% of 8765
cycles, but the quiet cycles arrive in RUNS, up to 140 long, and correlated
across the roster. A one-sample gate therefore releases roles that are
genuinely needed. `decide_role` now takes `zero_demand_cycles` — how many
CONSECUTIVE cycles the caller has observed zero — and releases only once that
reaches `ROLE_IDLE_DWELL_CYCLES` (100, the same window as min-hold). The
counter is the caller's; `decide_role` stays pure.

*Releasing is not enough on its own.* A release with nothing better to move to
is not a stable outcome but a cycle: the released role is still the only free
one, so the character re-claims it next cycle, holds another min-hold window,
and releases again — forever, without the role ever actually becoming
available to anyone. `decide_role` therefore also takes `idle_released`, the
set of roles this character has voluntarily released. A role in that set is
skipped by the claim search *while its demand is non-positive*, so a real
request re-opens it automatically and the caller never has to clear the set.
Like the counter, the set is owned by the caller (`GamePlayer`), which adds to
it on every `release` the function returns — keeping `decide_role` a pure
function of its arguments, with no clock and no module state.

### 7.1 Claim race and cold start

`RoleLease.role` is UNIQUE. Five children boot within a second, all see an empty
table, and all pick the same top-demand role. One INSERT wins; the others take
`IntegrityError`, re-read, and pick the next best. Repeated, they serialize into
distinct roles within at most N rounds.

So there is no tiebreak rule to design, which is fortunate: the obvious
candidates are alphabetical, and this project has a standing rule against
repr-sorted tiebreaks as decision logic. The race handler *is* the cold-start
allocator.

### 7.2 Degradation

A character holding no role — because every role is leased, or the store is
unreadable — receives the identity multiplier and behaves exactly as today,
while still publishing demand and still preferring `WITHDRAW`. A roster larger
than the catalog strands nobody: the surplus characters simply run present-day
behavior and consume from the bank. A roster smaller than the catalog leaves
roles unleased, which is inert. A single-character `play` run is bit-identical
to current behavior.

## 8. Error handling

Three classes, each handled at exactly one level.

**Claim race.** `IntegrityError` caught only in `CoordinationStore.claim`, which
returns `None`. `role_selection` reads `None` as "no role this cycle" and
retries next cycle. Nothing upstream re-catches it.

**Store unavailable.** Follows `LearningStore`'s existing contract:
`except SQLAlchemyError` -> degrade to default. Here the default is an empty
sibling view: identity weighting, present-day single-character behavior. The
degradation target is a state that is already tested and already shipped.

**Never `except Exception`.** `SQLAlchemyError` and `IntegrityError` only.

### 8.1 Deliberately unhandled

Stale bank contents. A consumer plans against `bank_items`, a sibling withdraws
them first, `Withdraw` returns HTTP 478 or 404, and `error:*` -> replan
recovers. That path already works — all four occurrences in the 2026-07-31
traces recovered cleanly. Specialization will make it more frequent, which is
correct rather than a regression. A second guard on top would be the "multiple
levels of error handling is always a bug" antipattern. It gets measured, not
suppressed.

## 9. Formal gate impact

`MeansKind.SUPPLY_BANK` is a new variant with three lockstep sites, all
compile-time enforced rather than silently driftable:

- `_MEANS_REPR` in `ai/tiers/decide_key.py`, round-tripped by
  `tests/test_ai/test_decide_key.py`
- `goalReprOfMeans` in `formal/Formal/DecideKey.lean` — total match, the
  compiler rejects the build until it is updated
- `formal/Formal/Liveness/ProductionLadder.lean`, whose header describes it as
  a walk over `allInLadderOrder`, which is
  `GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [.objectiveStep] ++
  DISCRETIONARY_ORDER`. It gains one entry, and the ladder proof fails until
  the new rung is discharged.

Sizes, verified 2026-08-01 rather than taken from comments: the Python
`MeansKind` enum has **15** variants and becomes 16. The Lean
`Formal.Liveness.MeansKind` inductive is *not* a mirror of it — it is the
combined guard + collect + objective + discretionary ladder — so the
"17-element MeansKind list" figure in the `ProductionLadder.lean` header
describes neither and is itself stale. That header is corrected as part of the
same change.

This cost is paid deliberately. A previous epic reused a guard slot to avoid it;
here, supplying a sibling is a genuinely distinct decision the strategy commits
to, and folding it into an existing variant would make it invisible in the
traces this project debugs from.

Separately, `role_alignment` entering `_scaled_weights` touches a
mechanically-extracted module, so `_NO_ROLE` must be proven byte-identical to
the current four-factor weight — the same obligation `_NO_ACHIEVABILITY`
already discharges.

## 10. Testing

**Pure cores.** `role_selection.decide`, `role_alignment`, and catalog
validation carry the hysteresis logic and get unit tests at 100% coverage.

**Concurrency.** The claim race needs a real multi-process test, not mocks.
Precedent: `CharacterSupervisor` is tested over a real subprocess. Spawn N
processes against one temp DB; assert exactly one holder per role and at most
one role per character.

**Time.** TTL and dwell tests inject a clock rather than sleeping.

**Runtime activation.** Green tests do not prove active. Three pieces of
evidence are required before this is done:

1. `role_alignment` observably != 1 for some candidate on a live run
2. `SupplyBankGoal` appears as `selected_goal` in a trace
3. a `Withdraw` succeeds against stock a *different* character deposited

The third proves collusion actually happened. Without it the epic is inert
regardless of suite colour.

**Census.** No new census, but obtain-parity must stay clean since
`_scaled_weights` changes.

**Gate.** `bash formal/gate.sh` green before push (~7 minutes), redirected to a
file rather than piped so `${PIPESTATUS[0]}` is not masked by `tail`.

**Pre-commit scope.** The pre-commit hook runs `tests/test_ai/` only. Anything
placed under `tests/test_multi/` is invisible to it and must be caught by the
full suite.

## 11. Open items for the implementation plan

- The numeric weight vector per role. Section 5.3 fixes which skills each role
  owns; the magnitudes that `role_alignment` returns are a tuning decision the
  plan should stage behind the inert-first sequencing below.
- Whether `SupplyBankGoal` needs its own `GuardKind`, or fires purely as a
  discretionary means. Current design assumes means-only.
- Sequencing of the two seams. The `role_alignment` factor can land inert
  first, be proven inert, and be activated separately — the discipline that
  caught the synergy epic running with weighting off.
