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

### The committed scenarios cannot see either defect

Zero walled candidates in every scenario against 6–9 of 9–13 live, and 6–24 ms per
walk against 479–2,828 ms live. The fixtures are systematically unrepresentative on
exactly the two axes this epic is about — the pricing wall and the cost of the
walk — because a cold `:memory:` store never consults the 48 MB learning DB per
monster per rung, and the fixture bundle prices nothing at 10^6.

That widens Tool 3 beyond band-edge coverage: a scenario carrying a **skill-gated,
walled** candidate set is needed, or the suite will keep reporting green on a model
the live fleet cannot use.

## Order of work

1. ~~Tool 1 without `--target`~~ — **DONE 2026-08-18**, E1 recorded above.
2. Increment 1 — the parameterisation refactor — then `--target`, then E2.
3. Tool 3 scenarios: band edges (`l19_band_edge`, `l11_band_floor`) **and** a
   skill-gated/walled candidate set, per E1's finding that no committed fixture
   carries one.
4. Tool 2, then E3.
5. E4, re-framed by E1: measure the `acquisition_actions` term against the ~300 ms
   per-rung term, and decide whether C is cheaper or dearer than what ships.
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
