# SPIKE: measure option C before speccing it

Increment 0 of `docs/PLAN_bounded_horizon_objective.md`. Read-only. **No change to
any decision path.** The deliverable is two answers and a recorded baseline; the
by-product is the objective diagnostics this repo has never had.

## The two questions

**Q1 — would C change the ranking?** If the walk buying its own upgrades produces
the same order the shipped objective produces, the epic is inert and must not be
built.

**Q2 — what does the walk cost?** Today: ~30ms per `cheapest_path_to_level` × 9
candidates ≈ 300ms per decision, against a ~30s cycle. C is one walk but evaluates
upgrades per rung. This seam has already produced one exponential blow-up
(`adventurer_vest`, 10.1M recursive calls in 20s, four of five characters ~2x
slower per cycle) so the number must be measured, not reasoned about.

## Why this needs new tooling first

The objective's own terms are **not observable by any shipped tool**:

* `plan` prints `d.ranking` — the progression *tree*'s `RootScore` rows. The
  objective's inputs (`acquire_cost`, `reachable_level`, `cycles_to_fifty`, band,
  finite `J`) are not in it.
* `rank_detail` has been printing `->L26` for every row for months — the string
  that means "unreachable band, J never ran". Correct, honest, and unreadable as
  the diagnosis it was.
* `j_ranking` exists only in `play-trace-*.jsonl`, which is deleted periodically
  and is explicitly not a durable record.
* Nothing prints per-decision timing.

Every measurement in `PLAN_bounded_horizon_objective.md` came from throwaway
scratchpad scripts that monkey-patched `TARGET_LEVEL`. That is the tooling gap this
spike closes, and the tools stay useful whether or not C is built.

## Tool 1 — `artifactsmmo objective` (new command)

`src/artifactsmmo_cli/commands/objective.py`, registered in `main.py` beside
`plan`/`macro-research`/`combat-loadout-report`. Read-only, no actions, offline
under `--scenario`.

```
uv run artifactsmmo objective --scenario l15_midband
uv run artifactsmmo objective R2D2 --learn
```

Prints one row per `ProgressionCandidate` — every term the objective ranked on,
plus which key actually decided:

```
=== l15_midband  level=15  milestone=20  target=50  candidates=9
identity                          acquire_cost  reach  cycles  J        band
xp_trunk                                     0     26       -  -        UNREACHABLE
artifact2_slot:lich_race_medal              96     26       -  -        UNREACHABLE
boots_slot:iron_boots                  1000001     26       -  -        UNREACHABLE
...
DECIDED BY: S-006 key 2 (acquisition cost) — key 1 tied at reach=26 for 9/9
WINNER: xp_trunk
timing: 9 walks, 284ms total, 31.6ms mean
```

The `DECIDED BY` line is the point. It states which clause settled the ranking, so
"J never ran" is a printed fact rather than something to be inferred from a `->L`
prefix. It is also the assertion the spike's experiments read.

**Flags:**

- `--scenario NAME` / `--bundle PATH` — same offline harness `plan` already uses.
- `--target N` — override the objective's target level. Requires increment 1 (the
  parameterisation refactor); until that lands the flag is rejected rather than
  faked. This is what replaces monkey-patching `TARGET_LEVEL`.
- `--json` — machine-readable, so the experiments below are scripted rather than
  eyeballed.

## Tool 2 — bundle pricing (`objective --bundle-price`)

The decisive C measurement, and it needs **no** change to the walk.

C's amortisation claim is that a shared prerequisite is paid once. That delta is
computable today: `acquisition_cost_core._accumulate` already threads one
`paid`/`owned` pair through a walk, so pricing a *set* of roots through one shared
pair gives exactly the number C would see, while pricing them individually gives
what A and B see.

```
uv run artifactsmmo objective --scenario l15_midband \
  --bundle-price iron_boots,iron_helm,iron_shield,iron_armor,iron_legs_armor
```

```
individually:  iron_boots 556  iron_helm 556  iron_shield 556  ...   sum 2780
as a bundle:   916            (shared: skill:gearcrafting:10 = 496)
amortised:     1864 cycles (67%)
```

Implementation is a read-only analysis helper next to the existing pricer — a loop
over roots sharing one `paid`/`owned`, not a new cost model, and not wired into any
decision. If it needs a seam inside `acquisition_cost_core`, that seam is
`_accumulate`'s existing parameters; do not add a second walk.

## Tool 3 — band-edge scenarios

The committed set has band *entries* (`l20_band_entry`, `l30_band_entry`,
`l40_band_entry`) and one midband (`l15_midband`). It has **no character near the
top of a band**, which is exactly R2D2's degenerate case — level 19, milestone 20,
one level of headroom, every candidate's benefit flat at 212. The whole scenario
suite is blind to it.

Add to `ai/scenario.py`:

- `l19_band_edge` — level 19, milestone one level away. The flat-benefit case.
- `l11_band_floor` — level 11, milestone nine levels away. The long-walk case,
  where a horizon change bites hardest and the walk is most expensive.

Both modelled on `l15_midband`'s gear/skill shape so the three differ only in band
position. They belong in the committed suite regardless of C: a horizon of any kind
must state what it does at a band edge, and today nothing tests that.

## Tool 4 — persist `j_ranking`

Add the objective's per-candidate terms to `learning.db` (a table beside
`plan_body_log`, one row per candidate per decision). Currently they exist only in
play-traces, so the "0 finite J in 10,716 cycles" figure cannot be checked over the
full history and cannot be re-checked after the epic lands.

This is the durability fix for the residual already recorded in
`PLAN_bounded_horizon_objective.md` §8, and it is what makes increment 4's
before/after diff possible at all.

## The experiments

Each names its kill criterion. A spike that cannot fail is not a spike.

### E1 — confirm the baseline offline

Run `objective` across `l11_band_floor`, `l15_midband`, `l19_band_edge`,
`l20_band_entry`, `l30_band_entry` at the shipped `--target 50`.

*Expected:* `DECIDED BY: S-006 key 2` on every scenario; no finite `J` anywhere.

*Kills the epic if:* the scenarios show finite `J` and a real trade-off. That would
mean the live 0/10,716 is a property of the live fleet's state, not of the model,
and the diagnosis is wrong.

### E2 — horizon sweep

Same scenarios, `--target` swept over `{milestone, milestone+10, level+3, 50}`.

*Expected:* J becomes finite below 50; `l19_band_edge` shows a flat benefit column
(the degenerate near end); `l11_band_floor` shows the widest spread.

*Records:* the per-scenario benefit spread — `max(cycles) - min(cycles)` across
candidates. This is the quantity C needs to be non-zero. Live figures to reproduce:
Lor L16→20 spread 229; R2D2 L19→20 spread 0.

*Kills the epic if:* the spread is ~0 at every horizon and every band position.
That would mean the projection cannot see gear at all, and C's benefit term is
unimplementable without first fixing `cheapest_path_to_level` — a different epic.

### E3 — bundle amortisation

`--bundle-price` the iron set on `l11_band_floor` and `l15_midband`, and the L20
set on `l20_band_entry`.

*Expected:* bundle cost materially below the sum, with `skill:<craft>:<n>` as the
shared key.

*Kills C's main advantage if:* bundle ≈ sum. Then the shared-prerequisite argument
is wrong, C's edge over B collapses, and B becomes the recommendation.

### E4 — cost of the walk

Time `objective` per scenario with `--target` at the widest horizon, and count
`acquisition_actions` calls. Then estimate C's per-decision cost as
`rungs × candidates × per-call`, using E1's measured per-call time.

*Expected:* same order as today's ~300ms, worst at `l11_band_floor` (9 rungs).

*Kills C if:* the estimate exceeds ~5s per decision, or is superlinear in rungs.
Fall back to B, which walks once per candidate exactly as today.

## E1 RESULT — 2026-08-18: baseline confirmed, epic not killed, one new defect

Tool 1 built and run. `objective` is live as
`uv run artifactsmmo objective [CHARACTER|--scenario NAME] [--learn] [--json]`.

| subject | L | cands | walled | total | per walk | decided by |
|---|---|---|---|---|---|---|
| `l15_midband` (offline) | 15 | 4 | 0 | 97ms | 24ms | S-006 key 1 — `iron_sword` reaches L19 alone |
| `l20_band_entry` (offline) | 20 | 7 | 0 | 44ms | 6ms | S-006 key 2 — 7/7 tied at L20 |
| `l30_band_entry` (offline) | 30 | 7 | 0 | 60ms | 9ms | S-006 key 2 — 7/7 tied at L30 |
| C3P0 (live) | 18 | 13 | 8 | 6,224ms | 479ms | S-006 key 2 — 13/13 tied at L19 |
| R2D2 (live) | 19 | 9 | 6 | 21,931ms | 2,437ms | S-006 key 2 — 9/9 tied at L26 |
| Lor (live) | 16 | 12 | 9 | 33,934ms | 2,828ms | S-006 key 2 — 12/12 tied at L26 |

*"walled" = candidates priced at `UNOBTAINABLE_PER_UNIT` or above.*

**E1 passes; the diagnosis stands.** No finite `J` anywhere, live or offline. The
kill criterion (scenarios showing a real trade-off) did not fire. `l15_midband` is
the one non-degenerate case and it is decided by key 1, not by `J` — the
weapon-raises-the-ceiling channel that accounts for the 18% of live weapon wins.

### New defect the tool found on first use: the ranking blows the cooldown budget

`branch_objective`'s docstring claims *"~30ms each measured inside a search cache
(~300ms for a 9-candidate decision, against a ~30s cycle)."* Measured live inside
the same search cache: **479–2,828 ms per walk, 16–94x that figure**, and Lor's
full ranking takes **33.9 s** — longer than the ~30 s cooldown it is supposed to
fit inside, against a planning budget that is the remaining cooldown floored at
15 s.

Cost is per-rung, and the two figures agree on that: Lor walks 10 rungs at
~283 ms/rung, C3P0 walks 1 at ~479 ms. So today's cost is
**candidates × rungs × ~300 ms**.

This is a live defect independent of the horizon epic and it should be filed
separately. It also **reframes E4**: C restructures the same work from
`candidates × rungs × rung_cost` to `rungs × (rung_cost + candidates × acq_cost)`,
paying the expensive per-rung term once instead of once per candidate. If
`acquisition_actions` is cheap relative to a rung, C is *faster* than what ships —
Lor would be ~10 × (283 ms + 12 × acq) against today's 34 s. E4 must measure the
`acq` term rather than assuming C is the expensive option.

### The scenarios are far cheaper than live

6–24 ms per walk offline against 479–2,828 ms live. A cold `:memory:` store never
consults the 48 MB learning DB per monster per rung, so no scenario can carry the
timing measurement E4 needs. That gap is real and holds regardless of how a
scenario is built.

> **CORRECTED 2026-08-18.** This section first also claimed "zero walled candidates
> in every scenario". That was measured over six scenarios that all happen to be in
> the half of the suite with `derive_combat_stats=False`. Re-measured over the
> deriving half, walled candidates are common: `l12_deep_chain_grind` prices 7 of 8
> at `UNOBTAINABLE_PER_UNIT`, `l10_gearcrafting_gap` 2 of 3. The pricing-wall axis
> is covered by the existing suite after all; only the timing axis is not. See the
> E2 correction below for the same sampling error and its consequences.

## E2 RESULT — 2026-08-18: kill criterion does NOT fire; the epic survives

`--target` shipped as increment 1a (see below). Live sweep, `--learn`, production's
own candidate set:

| char | L | headroom | target | reachers | **spread** | max reach | ms |
|---|---|---|---|---|---|---|---|
| HAL | 17 | 3 | **20** | 11/11 | **1128** | 20 | 9,686 |
| Lor | 16 | 4 | **20** | 12/12 | **1086** | 20 | 13,264 |
| R2D2 | 19 | 1 | **20** | 9/9 | **0** | 20 | 3,421 |
| C3P0 | 18 | 2 | **20** | 0/13 | — | 19 | 7,782 |
| HAL | 17 | — | 30 | 0/11 | — | 26 | 34,857 |
| Lor | 16 | — | 30 | 0/12 | — | 26 | 41,096 |
| Lor | 16 | — | 50 | 0/12 | — | 26 | 43,550 |
| R2D2 | 19 | — | 30 | 0/9 | — | 26 | 26,314 |
| R2D2 | 19 | — | 50 | 0/9 | — | 26 | 28,050 |
| C3P0 | 18 | — | 30/50 | 0/13 | — | 19 | ~7,400 |

*`spread` = max−min cycles among candidates that reached the target. Candidates
whose walk stopped short are excluded rather than counted as zero.*

**The benefit term discriminates, strongly, at the milestone horizon.** 1,086 and
1,128 cycles of spread on HAL and Lor across 11–12 candidates each. E2's kill
criterion — spread ~0 at every horizon and every band position — did not fire.

**The near-degenerate end is confirmed and quantified.** R2D2, one level from its
milestone: 9/9 reach, spread exactly **0**. A horizon measured in levels really
does go flat at a band edge, and the number is 0, not "small".

**New: the far end is not the only unreachable one.** C3P0 is blocked at L19
against its *own* milestone of 20 — 0/13 reach even the nearest horizon. So a
banded design cannot assume the milestone is reachable; it inherits the same
unreachable case it was meant to remove, just less often.

**A shorter horizon is also 3–4x cheaper.** Target 20 costs 3.4–13.3 s against
26–44 s at target 30/50, because cost is per-rung and a nearer target walks fewer
rungs. That is an independent argument for banding and it strengthens C's
performance story: C's rung loop pays the expensive per-rung term once per rung
rather than once per rung per candidate, on a walk that is already shorter.

### Correction to an earlier figure

`PLAN_bounded_horizon_objective.md` §4 records Lor's spread at target 20 as **229**
cycles, from the pre-tool scratchpad probe. The measured figure through production's
candidate set is **1,086**. The probe assembled its candidates by hand from
`_structural_candidates` alone and dropped `_utility_candidates` — the second
producer this spike's `objective_candidates` extraction exists to prevent, caught
by its own tooling. Live state has also moved since. The 1,086 supersedes; the
qualitative reading (the benefit term discriminates at four levels of headroom)
was right for the wrong arithmetic.

### The scenarios CAN carry this measurement — but only half of them, and thinly

A first sweep over six scenarios returned `spread = None` in all 24 cells, with the
maximum reachable level equal to the character's own level. That was a **sampling
error, corrected here**: all six were in the half of the suite with
`derive_combat_stats=False`, whose characters carry zero attack by design.
`scenario.py` documents it exactly — *"the pre-existing scenarios were all
empirically pinned … under the harness's original zero-stat states, where
`is_winnable` is False against EVERY monster (predict_win sees 0 attack)"*. A
blocked walk there is the correct consequence of a deliberate fixture choice, not
a defect, and 14 of the 28 scenarios opt in to real combat stats.

Re-measured over the deriving half:

| scenario | L | target | reachers | spread | ms |
|---|---|---|---|---|---|
| `l10_gearcrafting_gap` | 10 | 20 | 3/3 | 7 | 162 |
| `l12_gearcrafting_gap` | 12 | 20 | 3/3 | 7 | 151 |
| `l21_grey_material_grind` | 21 | 30 | 11/11 | 16 | 830 |
| `l20_dual_utility` | 20 | 30 | 3/3 | 0 | 290 |
| `l12_deep_chain_grind` | 12 | 20 | 0/8 | — | 276 |
| `l30_rune_fill` | 30 | 40 | 0/2 | — | 154 |
| any of the above | | 50 | 0 | — | |

So a scenario CAN reach a banded target and CAN produce a spread. What it cannot
do is produce a representative one: spreads of 0–16 against 1,086–1,128 live, over
1–11 candidates against 9–13. Scenario measurements in this epic will be
qualitatively right and quantitatively unrepresentative, and any acceptance
threshold written against a scenario number will be meaningless.

**Tool 3's remaining gap is therefore narrower than first stated.** Walled
candidates and non-blocked projections both exist in the suite already. What is
missing is a character at a band EDGE — the nearest deriving scenarios are
`l21_grey_material_grind` (9 levels of headroom) and `l20_dual_utility` (10) —
which is the one position where the horizon goes provably flat.

## TOOL 3 RESULT — 2026-08-18: the band edges are covered, and the flat pole reproduces

`l19_band_edge` (L19, one level from the L20 milestone) and `l11_band_floor`
(L11, nine levels) added to `ai/scenario.py`. Same gear, skills and bank as
`l21_grey_material_grind`; they differ from it and from each other in LEVEL
alone, so band position is the only variable. Both set
`derive_combat_stats=True`, which is load-bearing rather than decorative — the
flag's own docstring records that without it `is_winnable` is False against every
monster, and the walk would then block at rung one and report a flat benefit
column for a reason unrelated to the band position the fixture exists to isolate.

| scenario | L | headroom | target | reachers | spread | ms |
|---|---|---|---|---|---|---|
| `l19_band_edge` | 19 | 1 | 20 | 7/7 | **1** | 61 |
| `l19_band_edge` | 19 | 11 | 30 | 7/7 | 13 | 688 |
| `l11_band_floor` | 11 | 9 | 20 | 7/7 | 6 | 357 |
| `l11_band_floor` | 11 | 19 | 30 | 7/7 | 19 | 933 |
| either | | — | 50 | 0/7 | — | ~1,000 |

Discrimination is monotone in how far the walk runs, and it collapses to ~0 at
one level of headroom — the same shape as live (R2D2 spread 0 at L19, Lor 1,086
at L16), at a fraction of the magnitude, which is what a cold `:memory:` store
falling back to the documented XP formula produces.

`tests/test_ai/scenarios/test_band_edge_horizon.py` pins the property as an ORDER
over three horizons, never as a magnitude: a threshold copied from a cold-store
scenario would be meaningless against the live fleet. It also pins the design
invariant (same milestone, same gear, levels 1 and 9 out) and carries an explicit
non-vacuity guard on `state.attack`. Verified by mutation: removing
`derive_combat_stats=True` from `l19_band_edge` fails three of the six tests,
including the guard.

## E3 RESULT — 2026-08-18: bundle ≈ sum does NOT hold; C's advantage is real

Tool 2 shipped as `objective --bundle-price a,b,c` plus
`acquisition_cost_core.bundle_acquisition_cost` and its impure wrapper. It is
`acquisition_cost`'s own walk with one shared ledger instead of a fresh one per
call — same `_accumulate`, same fuel bound, same route memo — and a parity test
pins a bundle of one against `acquisition_cost` pointwise so it cannot drift into
a second cost model.

**The decisive measurement**, on `l21_grey_material_grind` with gearcrafting
dropped to 5 so the five iron pieces sit behind one five-level grind, and a store
carrying a 5 xp/cycle observed rate:

```
  individually iron_boots            537
  individually iron_helm             546
  individually iron_shield           546
  individually iron_armor            546
  individually iron_legs_armor       546
  sum of the parts                  2721
  as ONE plan                        711
  amortised                         2010   (74%)
  pay-once keys: bank 1, chicken 1, cow 1, sheep 1,
                 skill:gearcrafting:10 500, workshop:gearcrafting 1
```

E3's kill criterion — bundle ≈ sum, collapsing C's edge and making B the
recommendation — **does not fire**. It is the opposite, decisively: **74%** of the
cost of the five priced apart is the same grind charged five times.

Read against E2: Lor's live benefit spread at the milestone is 1,086 cycles. A
five-piece set at 711 total is inside that; five pieces at 546 each are not. This
is the first time those two numbers have been comparable at all, and the trade is
the one C exists to evaluate.

### Two dependencies the measurement exposed

**The wall hides the amortisation.** Priced on `l12_deep_chain_grind` the same
bundle returns 6,000,709 against 6,001,522 — a 0.01% saving, because five
`UNOBTAINABLE_PER_UNIT` sentinels for unroutable cowhide and wool swamp the term
under test. Not a fixture artefact: it is the live interaction this scope already
records, where the pricing wall and the objective each hide the other's defects.
The test fixture removes the wall deliberately, and says so.

**The unlock key only exists where the grind rate does.** `_gated_craft_option`
declines the route on a non-positive rate, so with a cold `:memory:` store — every
scenario — the gate produces no route and therefore no shared key. Measured live
the rate is 0.0 for every character and every crafting skill (D1 of
`PLAN_iron_gear_acquisition.md`), so the largest shared cost in the model is
currently unreachable in production. **E3's number is therefore a counterfactual
until increment 2 lands**, and the amortisation C depends on cannot be observed
live before it.

What IS measurable today is venue sharing: on the same scenario with the gates
MET, bundling the iron set saves 10 actions of 221 (5%) across five shared venues.
Real, and two orders of magnitude smaller than the unlock.

## E4 RESULT — 2026-08-18: C is ~4x CHEAPER than what ships, not dearer

Per-call timing added to `--bundle-price`, because that is the only place the
pricer runs in isolation. Live, two characters:

| char | candidates C | rungs R | per-rung | `acquisition_actions` |
|---|---|---|---|---|
| Lor L17 | 12 | 9 | 366 ms | 47.1 ms (routable) / 0.3–0.6 ms (walled) |
| R2D2 L20 | 10 | 6 | 451 ms | 67.6 ms (routable) / 0.4–0.7 ms (walled) |

**The walled figure is not the one to use.** A candidate with no route
short-circuits before walking anything, which is why eight of Lor's nine priced in
under a millisecond while the single routable one took 47 ms. Once the pricing
wall is fixed most candidates become routable, so the honest term is the routable
one and every estimate below uses it.

### The two shapes, and the arithmetic

Today, `branch_ranking` pays one `acquisition_actions` per candidate and one full
R-rung walk per candidate:

    today  =  C·acq + C·R·rung

Option C walks once and evaluates C upgrades at each rung:

    C      =  R·rung + R·C·acq

| char | today, modelled | today, measured | option C, modelled | speedup |
|---|---|---|---|---|
| Lor | 40,092 ms | **39,566 ms** | **8,370 ms** | 4.7x |
| R2D2 | 27,740 ms | **27,031 ms** | **6,786 ms** | 4.0x |

The model reproduces the measurement to within 2%, which is what makes the
estimate worth anything.

**Break-even is `acq` against `rung`.** For any non-trivial C and R the dominant
terms are `R·C·acq` against `C·R·rung`, so C is cheaper exactly when
`acq < rung`. Measured: 47 ms against 366 ms, and 68 ms against 451 ms — a margin
of **6.6x to 7.8x**. `acq` would have to grow nearly an order of magnitude before
C became the expensive option.

**With banding as well** (Lor at target 20, three rungs): today 13,264 ms
measured; C modelled at 3·366 + 3·12·47 = **2,790 ms**. Against a ~30 s cooldown
and a 15 s planning floor, that is the difference between an objective that fits
in its budget and one that does not.

### Verdict on the kill criterion

E4 killed C if the estimate exceeded ~5 s per decision or grew superlinearly in
rungs. It is linear in rungs by construction, and at the banded target it is
~2.8 s. At the shipped target of 50 it is 6.8–8.4 s, which does exceed 5 s — but
target 50 is precisely what the epic removes. **Not killed.**

### Residual, and it is the one with history

`adventurer_vest` — the candidate whose recipe fan-out once ran 10.1M recursive
calls in 20 s at this exact seam — is currently WALLED, so it priced in 0.5 ms
here and this measurement says nothing about it. Every figure above must be
re-taken after the pricing wall is fixed, when the deep-closure candidates start
walking for real. The memo that fixed that blow-up is still in place and the walk
is linear in the closure, so the expectation is that `acq` rises toward the 47–68 ms
band rather than exploding — but expectation is not measurement, and this seam has
surprised the project once already.

---

## SPIKE VERDICT — 2026-08-18: **build C**

All four kill criteria cleared:

| | criterion | result |
|---|---|---|
| E1 | scenarios show a real trade-off ⇒ diagnosis wrong | 0 finite `J` live and offline; **not killed** |
| E2 | spread ~0 at every horizon ⇒ benefit unimplementable | 1,086–1,128 cycles at the milestone; **not killed** |
| E3 | bundle ≈ sum ⇒ fall back to B | 74% amortised, `skill:gearcrafting:10` the shared key; **not killed** |
| E4 | >5 s per decision or superlinear ⇒ fall back to B | ~2.8 s banded, linear in rungs, 4x cheaper than today; **not killed** |

C is recommended, and the ordering constraint E3 exposed is now a hard
dependency rather than a preference: **increment 2 (the pricing wall) must land
before increment 3 (the acquisition edge)**, because the largest shared cost in
the model — the skill unlock — exists only where a grind rate does, and every
candidate carrying one is currently walled. Building C first would produce a walk
that can buy nothing worth buying, and it would look inert for a reason that has
nothing to do with C.

## Order of work

1. ~~Tool 1 without `--target`~~ — **DONE 2026-08-18**, E1 recorded above.
2. ~~Increment 1 — the parameterisation refactor — then `--target`, then E2.~~
   **DONE 2026-08-18** as increment **1a** only: `branch_objective._outcome`,
   `trunk_candidate`, `gear_candidate` and `branch_ranking` take a `target`
   keyword defaulting to `TARGET_LEVEL`, so every production caller is unchanged.
   The proved core is deliberately NOT parameterised — `progression_choice`'s
   `TARGET_LEVEL` is mirrored in `Formal.ProgressionChoice` and pinned pointwise
   by `formal/diff/test_progression_choice_diff.py`, so threading a target
   through it means five theorems and the oracle's wire format. Under option C
   that banding apparatus is DELETED rather than parameterised, so the proof cost
   would be paid only to remove it. Increment **1b** (parameterise the core) is
   therefore deferred and happens only if A or B wins. Under a swept `--target`
   the command's band and `DECIDED BY` columns abstain rather than re-deriving a
   second banding.
3. ~~Tool 3 scenarios~~ — **DONE 2026-08-18**, see the result above. Walled candidates and
   non-blocked projections already exist in the `derive_combat_stats=True` half
   of the suite, so E3 has fixtures. What is missing is a character at a band
   EDGE: `l19_band_edge` (one level of headroom, the provably flat case) and
   `l11_band_floor` (nine levels, the long-walk case). Both must set
   `derive_combat_stats=True` or they inherit the zero-attack state and block.
   E4 still cannot be measured offline at all — scenarios run 6–37x faster than
   live because a cold store never touches the 48 MB learning DB.
4. ~~Tool 2, then E3.~~ **DONE 2026-08-18**, see the result above. Note the
   dependency it exposed: the unlock key — the large shared cost — exists only
   where a grind rate does, so E3's live confirmation waits on increment 2.
5. ~~E4~~ **DONE 2026-08-18**: `acq` 47–68 ms against a 366–451 ms per-rung term,
   so C is ~4x cheaper than what ships. See the result above and the spike
   verdict.
6. Tool 4, independent of the rest, any time.
7. File the 33.9 s ranking as its own defect — it is not contingent on the epic.

## Deliverable

A short findings section appended to
`docs/PLAN_bounded_horizon_objective.md`: the four experiment results, the recorded
baseline for increment 4 to diff against, and one of three verdicts — **build C**,
**fall back to B**, or **diagnosis wrong, stop**.

## Constraints

- Read-only throughout. No command added here may execute a game action, and none
  may alter a decision the bot would make.
- New commands live under `src/artifactsmmo_cli/commands/`, one module, registered
  in `main.py`. `scripts/` is coverage-omitted; `src/` is not, so these need tests
  and the 100% gate applies.
- The pre-commit hook runs `pytest tests/test_ai/` only. A new command under
  `commands/` is invisible to it — run the full suite (`bash formal/gate.sh`)
  before pushing.
- Delete `scratchpad/probe_acq.py`, `probe_drop.py` and `probe_band.py` once Tools
  1 and 2 subsume them. Two ways to ask the same question is how this whole
  situation started.
