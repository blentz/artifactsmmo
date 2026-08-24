# Wave 3c — gated investigation: `_committed_repr` and `DoomedMemo`

Branch `waves-3-6`, worktree `.worktrees/waves-3-6`, at `750a2fe0`. This plan
writes no production code. Its deliverable is a per-site KEEP/DELETE verdict
with, for every DELETE, the measurement that justifies it.

Context: the parent spec
(`2026-08-22-goal-decision-graph-design.md`, committed 2026-08-22 23:46) put two
items on the wave-3 deletion list that are not ranking machinery. §6.4 of
`2026-08-23-wave3-resolution-design.md` ruled them "investigate, do not delete"
and deferred them here. The precedent is task 5.3, which investigated three
"obviously dead" sites and found all three live.

## 0. Headline

| subject | verdict |
|---|---|
| `StrategyArbiter._committed_repr` | **KEEP the mechanism.** Measured: of 183 possible commitments across the 30-scenario set, **17 change the walk's answer and all 17 are band 5 (`BAND_DISCRETIONARY`)** — the one band `select_pure` exempts from band preemption, and the one the resolution graph never produces. At bands 1–4, including the objective step the graph does produce, a commitment changed the answer **zero** times out of 155. Three of the four proven roles are now redundant *in the sense that the walk reproduces them*; the fourth is not, and the mechanism cannot be split without deleting the theorem that makes the fourth safe. |
| `DoomedMemo` | **KEEP, unconditionally, and the CPU argument is not the reason.** The class has a **second production consumer the deletion list does not mention**: `player._rejected_actions` (`player.py:270`), a categorical-server-refusal memo wired straight into the planner via `planner.set_refusal_filter` (`player.py:228`). It was added at `5b1a2512` on **2026-08-23 08:37**, ten hours *after* the parent spec that proposed the deletion. Deleting `DoomedMemo` breaks the planner's action filter, which has nothing to do with the arbiter, the ranking, or the graph. |

The CPU regression was measured anyway, because the plan asked for a number
rather than an argument. It is **0.34 ms per cycle on the scenario set** — three
orders of magnitude below the "15s" the docstring quotes — and the reason is
that the scenario set contains **zero planner timeouts**, so it cannot exhibit
the case the memo exists for. See §2.4 for the full spread and §4 for what that
does and does not license.

---

## 1. Subject A — `StrategyArbiter._committed_repr`

### 1.1 Every site

The spec's "19 refs across `arbiter_select.py`, `strategy_driver.py`,
`player.py`" is exactly right as a count. It resolves to **15 code lines and 4
comment/docstring lines**. The count also *omits the entire CLI surface*, which
is production and is listed below the rule.

| file:line | kind | what it is | verdict |
|---|---|---|---|
| `ai/arbiter_select.py:16,23,96,98` | comment/docstring | describes sticky-commitment and the "there is no guard candidate at all" consequence | KEEP |
| `ai/arbiter_select.py:91` | production | `committed_repr` parameter of `select_pure` | KEEP |
| `ai/arbiter_select.py:108,110` | production | `is not None` gate + `find` of the committed means candidate | KEEP |
| `ai/arbiter_select.py:118` | production | `guard_precedes` | KEEP (§1.4) |
| `ai/arbiter_select.py:135` | production | `lower_band_precedes` | KEEP (§1.3) |
| `ai/arbiter_select.py:140,142` | production | sticky attempt + early return | KEEP |
| `ai/strategy_driver.py:716` | production | `self._committed_repr: str \| None = None` | KEEP |
| `ai/strategy_driver.py:1041` | comment | "captured BEFORE `_committed_repr` is overwritten" | KEEP |
| `ai/strategy_driver.py:1043` | production | `prev_committed = self._committed_repr` | KEEP (§1.5 — **second consumer**) |
| `ai/strategy_driver.py:1047` | production | `self._committed_repr = new_committed` | KEEP |
| `ai/strategy_driver.py:1549,1557` | production | the two `select_pure` calls (walk, worth-gate-bypass re-walk) | KEEP |
| `ai/strategy_driver.py:1572` | production | Wait fallback carries the commitment forward unchanged | KEEP |
| `ai/player.py:1058` | production | `plan --committed` diagnostic seam | KEEP |

Sites the §6.4 ref count misses, all production:

| file:line | kind | what it is | verdict |
|---|---|---|---|
| `ai/strategy_driver.py:1083` | production | `collect_reprs = {… if c.band == BAND_COLLECT and c.repr_ != prev_committed}` — a *derived* read of `_committed_repr` outside `select_pure` | KEEP (§1.5) |
| `ai/plan_report.py:32` | production | `PlanReport.simulated_committed` | KEEP |
| `ai/player.py:996-997,1089` | production | `plan_from_state(committed=…)` signature and report field | KEEP |
| `commands/plan.py:99-101,121,133,148` | production | the `--committed` CLI option and both call sites | KEEP |
| `commands/plan.py:34,38,39` | production | prints the injected commitment back | KEEP |
| `scripts/measure_means_suppression.py:307,311` | tooling | wraps `select_pure`, forwards `committed_repr` | KEEP (update only if the signature changes) |

Tests: `tests/test_ai/test_arbiter_sticky_band.py` (4 refs, lines 86/107/129/149)
and `tests/test_ai/test_strategy_driver.py` (lines 1548, 1563-1587, 2248, 2319,
2844). Formal: `Formal/ArbiterSelect.lean`,
`Formal/Extracted/ArbiterSelect.lean:58-77`, `Formal/Extracted/Bridges2.lean:25,73`,
`formal/diff/test_arbiter_select_diff.py:98,101`, and 8 mutation entries in
`formal/diff/mutate.py:2228-2290`, six of which mutate the sticky logic directly.

### 1.2 The measurement

`select_pure` is pure with respect to its three closures, and calls `try_plan`
at most once per distinct goal. That makes an exhaustive counterfactual cheap:
intercept the call, wrap the closures in caches, then re-run the *same*
`select_pure` against the *same* cached closures once per candidate, with that
candidate's repr as the commitment. Nothing is re-planned that the real walk
already probed, and the comparison is exact rather than sampled.

For each scenario cycle the probe recorded:

* the real result;
* the result with `committed_repr=None` — the **no-sticky baseline**;
* for every means candidate `C`: whether a commitment to `C` is structurally
  blocked (`guard_precedes` / `lower_band_precedes`), and if not, the result of
  committing to it.

Harness: `sticky_probe.py` (scratch, not committed), driving
`GamePlayer.seed_offline` + `plan_from_state` over all 30 entries of
`ai/scenario.SCENARIOS` against `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`.
30 cycles, 183 means candidates enumerated.

### 1.3 Result: only band 5 is load-bearing

```
band 1 COLLECT         1 candidate    1 same-as-walk    0 flips
band 2 STEP           28 candidates  22 same-as-walk    6 blocked    0 flips
band 3 RAID            1 candidate    1 same-as-walk    0 flips
band 4 FALLBACK_STEP 129 candidates   1 same-as-walk  128 blocked    0 flips
band 5 DISCRETIONARY  24 candidates   3 same-as-walk    4 blocked   17 FLIPS
```

Totals: 183 means candidates; 138 structurally blocked (106 by
`lower_band_precedes`, 32 by `guard_precedes`); 45 where the sticky
short-circuit could fire; **17 where it changes the answer, every one of them at
band 5**, spread over 14 of the 30 scenarios. The flipping commitments are
`MaintainConsumables` (14) and `DrainBankJunk` (3), each preempting an objective
step or skill-climb the walk would otherwise have taken.

This is precisely the case `arbiter_select.py:135` exempts by hand — `band < 5`
in the `lower_band_precedes` conjunct, whose comment says "committed income
tasks stay governed by the semantic worth gate, not this structural rule". The
measurement says that exemption is not a corner: **it is the only thing sticky
commitment still does.**

What this means for the parent spec's redundancy argument, stated as an
enumeration rather than a verdict:

1. **Commit to the objective step (band 2).** Redundant *given* a walk that
   returns the same step. 22 of 28 band-2 commitments returned exactly the
   no-sticky answer, 6 were structurally blocked, none flipped.
2. **Commit to a fallback step (band 4).** Effectively dead already, and not
   because of the graph: 128 of 129 were blocked by `lower_band_precedes`, which
   is the anti-freeze rule added for the copper_ring char-XP freeze. Sticky has
   not been able to defend a fallback step since that rule landed.
3. **Commit to a collect-band or raid goal (bands 1, 3).** Two candidates in the
   whole set, both same-as-walk. Not exercised; see §3.
4. **Commit to a discretionary goal (band 5).** **Not redundant.** The graph
   emits roots and steps; it never emits `MaintainConsumables`, `PursueTask`,
   `DrainBankJunk`, or any other `DISCRETIONARY_ORDER` means, so nothing in the
   resolution walk makes a discretionary commitment stable.

So "three of four roles are now redundant, the fourth is not" is the honest
shape of the answer — with the caveat that role 2 was already dead for an
unrelated reason, and that roles 1–3 are redundant only in the sense that the
walk *reproduces* them, not that removing the code would be a no-op if the walk
ever disagreed with itself between cycles (§3).

### 1.4 An exact structural fact, checked exhaustively

`select_pure` blocks the sticky short-circuit if any *guard* candidate precedes
the committed one. Guards are prepended by `_build_candidates`
(`strategy_driver.py:1209-1211`, `is_means=False`, `band=BAND_GUARD`), so any
guard precedes any means. The docstring at `arbiter_select.py:16-20` already
says this — "i.e. there is no guard candidate at all" — and the probe confirms
it with no exceptions: in the 5 scenarios that had at least one guard candidate,
**all 32 means candidates were blocked by `guard_precedes`, 32 of 32.**

Consequence worth carrying into any future edit: sticky commitment is inert on
every cycle where any guard fires. Pre-flip live data gives a lower bound on how
often that is — `cycles.selected_goal` is a guard-only goal (`RestoreHP`,
`DiscardOverstock`, `CraftRelief`, `DepositInventory`) on **20,857 of 78,552
cycles (26.6%)**, and a guard that fires without winning is invisible to that
query, so the true figure is higher.

### 1.5 The second consumer

`strategy_driver.py:1043` captures `prev_committed` *before* the write at
`:1047`, and `:1083` uses it:

```python
collect_reprs = {c.repr_ for c in candidates
                 if c.band == BAND_COLLECT and c.repr_ != prev_committed}
first = next((g for g in self.goals_tried if g["goal"] not in collect_reprs), None)
```

This is not `select_pure`. It is the derivation of `objective_unplannable`, the
field added so that "UpgradeEquipment ranked first and abandoned on 955
consecutive cycles" stops reading as a deliberate choice. `_committed_repr` is
what lets a *committed collect goal* count as the abandoned objective rather
than being filtered out as ordinary collect-band noise. The field flows out
through `player.py:1195,1372` into `CycleSnapshot.objective_unplannable`
(`cycle_snapshot.py:158`) and the observer, and is pinned by
`tests/test_ai/test_strategy_driver.py:2811-2823` and
`tests/test_ai/test_cycle_observer.py:129-136`.

This is the 5.3 pattern exactly: a live consumer reached through a path the
deletion list did not trace. It is small, but it means "delete `_committed_repr`"
is not a `select_pure`-local edit.

### 1.6 Verdict

**KEEP, whole.** No site in the table earns a DELETE.

The narrower proposal — "keep the band-5 exemption, delete the rest" — is not
available either, and the reason is structural rather than aesthetic: the four
Lean roles in `Formal/Manifest.lean:293-299`
(`select_pure_guard_wins`, `select_pure_sticky_idempotent`,
`select_pure_no_sticky_preempt_lower_band`, `select_pure_no_commitment_is_walk`,
plus `walk_returns_head` and `guardPrecedes_of_head_guard`) are what make the
band-5 exemption *safe*. `no_sticky_preempt_lower_band` is the theorem that says
a stale commitment cannot freeze the bot, and it is stated over the same
`committed_repr` the other three use. Keeping only the exemption keeps the one
arm that has no anti-freeze proof.

---

## 2. Subject B — `DoomedMemo`

### 2.1 Every site

§6.4 says "27 refs across `doomed_memo.py`, `planner.py`, `player.py`,
`strategy_driver.py`, `goals/progression.py`" and "4 test files". Both are
undercounts, and the miss is not cosmetic.

| file:line | kind | role | verdict |
|---|---|---|---|
| `ai/doomed_memo.py` (whole file) | production | the class | **KEEP** |
| `ai/planner.py:36` | comment | the "15s once per re-probe window" claim | KEEP (see §2.4 — the claim is arithmetically intact but its live magnitude is unmeasured) |
| `ai/planner.py:161,183-208` | production | `_is_refused` / `set_refusal_filter` — the seam the **action** memo is wired into | **KEEP** |
| `ai/strategy_driver.py:33,728` | production | import + `self._memo = DoomedMemo()` (role 1, planner-cost) | KEEP |
| `ai/strategy_driver.py:935,937` | production | `_record_attempt`: clear on plan, mark on no-plan (timeout included) | KEEP |
| `ai/strategy_driver.py:1525,1530` | production | `memo_bypass` set + `_skip` | KEEP |
| `ai/strategy_driver.py:930,1522,1580` | comment | memo-bypass rationale | KEEP |
| `ai/player.py:67` | production | import | KEEP |
| `ai/player.py:270` | production | **`self._rejected_actions = DoomedMemo()` — role 2, action rejection** | **KEEP (the decisive site)** |
| `ai/player.py:228` | production | `self.planner.set_refusal_filter(self._is_categorically_refused)` | **KEEP** |
| `ai/player.py:1723` | production | mark on a categorical HTTP refusal | **KEEP** |
| `ai/player.py:2587-2598` | production | `_is_categorically_refused` → `_rejected_actions.is_doomed` | **KEEP** |
| `ai/player.py:1536` | production | role 3 — `_mark_plan_fault` marks the plan-cache goal into the arbiter memo | KEEP |
| `ai/player.py:1056` | production | `plan --doom` diagnostic seed | KEEP |
| `ai/goals/base.py:20` | production | `memo_exempt: bool = False` — the escape | KEEP |
| `ai/goals/supply_bank.py:72`, `ai/goals/grind_character_xp.py:45` | production | the two goals that take the escape | KEEP |
| `ai/goals/supply_bank.py:48,61,232`, `ai/goals/grind_character_xp.py:44`, `ai/player.py:3232`, `ai/goals/progression.py:869`, `ai/tiers/skill_grind_target.py:172` | comment | rationale/cross-references | KEEP |

Tests: **six** files, not four — `tests/test_ai/test_doomed_memo.py` (27 refs),
`tests/test_ai/test_action_rejection.py` (14), `tests/test_ai/test_strategy_driver_tiered.py`
(6), `tests/test_ai/test_strategy_driver.py` (3), `tests/test_ai/test_player_level_skill_hook.py`
(2), `tests/test_ai/test_plan_command.py` (1).

Formal: `Formal/DoomedMemo.lean` (8 manifest roles at `Manifest.lean:1204-1211`),
`Formal/Contracts.lean:2998-3021` (5 anti-weakening pins), `Formal/Audit.lean:952-959`
(8 axiom prints), `Oracle.lean:2361-2372`, `Formal/PlanModel.lean:3403`,
`formal/diff/test_doomed_memo_diff.py`, and 4 mutation entries at
`formal/diff/mutate.py:2771-2782`.

### 2.2 The consumer the deletion list missed

`player.py:270` constructs a **second, independent `DoomedMemo`**, keyed by
`rejection_key(action)` rather than by goal repr, and used at the *execution*
layer:

* `player.py:1723` marks an action whose server response was a categorical
  refusal (`is_categorical_rejection`);
* `player.py:2598` asks the memo, through `_is_categorically_refused`;
* `player.py:228` wires that predicate into the planner as its refusal filter,
  which `planner.py:206-208` applies to **every** action a goal's
  `relevant_actions` returns — including actions goals *synthesise* rather than
  select (`goals/recycle_surplus.py`, `ai/disposal_route.py`).

Its own docstring records why it exists: "C3P0 sent `Recycle(water_boost_potion×1)`
37 times over eight hours, every one answered 473, because nothing carried the
refusal back into the model." The escalating re-probe window is what makes a
misclassified item code self-heal instead of being disabled forever — i.e. this
role needs the *specific* `DoomedMemo` semantics (signature invalidation +
geometric backoff), not just any dictionary.

Timeline, which is the point:

| when | what |
|---|---|
| 2026-08-22 23:46 | `aac8e2d0` — parent spec written, puts `DoomedMemo` on the deletion list |
| 2026-08-23 08:37 | `5b1a2512` — "fix(actions): a categorical server refusal poisons the action" creates the second consumer |
| 2026-08-23 12:18 | `34ddde13` — wave-3 resolution design defers `DoomedMemo` to this investigation, still describing it as purely a planner-cost memo |

The deletion list was not wrong when it was written. It is wrong now, and grep
alone would have shown it — `DoomedMemo` appears twice in `player.py`
constructors, and only one of them is the arbiter's.

### 2.3 CPU measurement — method

Because a scenario cycle starts with a cold memo, a single `plan_from_state` can
never exercise it. The A/B therefore re-plans the **same frozen scenario state
for 6 consecutive cycles**, bumping `player._cycle_counter` each time so the
re-probe window advances honestly, and discards cycle 0 from both arms so that
`GameData`'s recipe/requirement memos are equally warm on each side. The only
difference between arms is whether `DoomedMemo.is_doomed` may return `True`
(patched to a constant `False` in the OFF arm). Harness: `memo_bench.py`
(scratch). 30 scenarios × 5 measured cycles = 150 cycles per arm.

### 2.4 CPU measurement — numbers

```
                                   memo ON      memo OFF     delta
wall clock, 150 cycles             4973.9 ms    5024.8 ms    50.9 ms
per cycle                            33.2 ms      33.5 ms     0.34 ms
goal attempts recorded                  150          235      85 skipped (36%)
planner time inside those attempts     87.4 ms     153.3 ms    65.9 ms
planner TIMEOUTS                          0            0
```

* The memo **is** hitting post-flip: it skipped **85 of 235** candidate attempts
  (36%). The "the walk may plan different goals than the ranking did, so the hit
  rate may have changed" worry is answered — the memo still finds work to do
  against the resolution walk.
* The saving is nonetheless **0.34 ms/cycle**, because the 95 no-plan attempts in
  the OFF arm cost **67.0 ms in total, 0.71 ms each, maximum 2.4 ms** — they are
  `nodes=1` dead ends, not searches. The most expensive was
  `GatherMaterials(king_slimeball, {king_slimeball:2})` at 2.40 ms.
* **Zero timeouts in either arm, across all 30 scenarios.** The scenario set
  cannot exhibit the case the docstring's "15s" describes. This is the single
  most important qualifier on the number above.
* Planner time is 87–153 ms of a 4974 ms total: on this fixture, ~2–3% of a
  cycle. The other 97% is `decide_tree` and state construction, which the memo
  does not touch. Any argument about the memo's CPU value that starts from
  "planning dominates the cycle" is false on the scenario set.

### 2.5 Is "15s once per re-probe window" still true?

Arithmetically, yes, and it is checkable from two constants rather than
measured: `planner._SEARCH_BUDGET_SECONDS = 15.0` (`planner.py:15`), floored
against the cooldown window by `strategy_driver._cycle_budget_seconds`
(`:769`); and `DoomedMemo(retry_after_cycles=20, max_retry_after_cycles=160)`
with `_ttl = min(base << (failures-1), max)`. So the memo converts a per-cycle
cost into one occurrence per 20 cycles at the first failure, doubling to one per
160 at the cap — a 20× to 160× reduction on any goal that keeps failing under an
unchanged plannability signature.

What the live database (pre-flip; see §3) says about how often the 15s branch is
taken, over 78,552 cycles from 2026-08-02 to 2026-08-23:

| quantity | value |
|---|---|
| cycles whose **last** planner invocation timed out (`planner_timed_out=1`) | **265 (0.34%)** |
| mean `planner_nodes` on those cycles | 14,669 |
| mean `actual_cooldown_seconds` on those cycles | **3.51 s** |
| median `actual_cooldown_seconds`, all cycles | 29.6 s |
| fraction of all cycles with cooldown ≥ 15 s | **70.8%** |

The last two rows are the non-obvious part. Cooldown *is* the planning window,
so on the 70.8% of cycles with ≥15 s of cooldown a 15 s search is spent on time
the bot would have idled through and costs no throughput at all. Timeouts do not
land there: they concentrate on cycles whose cooldown averages **3.51 s**, an
order of magnitude below the median — exactly the cycles where the 15 s floor is
latency the bot pays out of pocket. The memo's value is therefore concentrated
where it is worth the most, and a per-cycle *average* is the wrong summary
statistic for it.

`cycles` records only the last invocation of each cycle, so 265 is a **lower
bound** on timed-out searches; candidates that timed out before a later one
succeeded leave no row.

### 2.6 Live spot check

Two live planning cycles were run (the budget allowed by this plan), read-only,
through the same `plan_once` seam the `plan --learn` command uses:

| character | wall | candidates attempted | result |
|---|---|---|---|
| C3P0 | 23.57 s (of which 44.0 ms planner) | 1 | `CraftPotionsGoal`, nodes=125, plan_len=4, no timeout |
| Robby | 7.71 s (of which 38.1 ms planner) | 1 | `GatherMaterials(lifesteal_rune…)`, nodes=4, plan_len=2, no timeout |

Both cycles found a plan on the first candidate, so both measured the memo's
saving at exactly zero — and had nothing for it to save. The wall clock is game
data load plus the character fetch, not search. Two cycles generalise to
nothing; they are recorded so the next reader does not re-spend the budget
expecting a different shape.

### 2.7 Verdict

**KEEP, whole.** No site earns a DELETE. The `memo_exempt` escape
(`goals/base.py:20`) stays with it: it is taken by `SupplyBankGoal` and
`GrindCharacterXPGoal`, and `SupplyBank` was the selected goal on 3,773 live
cycles.

Had the second consumer not existed, the CPU evidence alone would *not* have
supported a deletion either — it would have supported "unmeasured", because the
only body of evidence that can exhibit the memo's purpose (a timing-out search)
is absent from the scenario set and only partially visible in the database.

---

## 3. What I could not determine

* **No post-flip live data exists.** Wave 3a is on this branch only; `origin/main`
  is 51 commits behind and the fleet runs main. Every number drawn from
  `~/.cache/artifactsmmo/learning.db` in this report describes the **pre-flip**
  ranking bot. The scenario set is the only post-flip evidence, and it is a
  fixture.
* **No before/after of the memo's hit rate.** Measuring the pre-flip hit rate
  would mean running the same A/B on a commit before wave 3a, which needs a
  second worktree — outside this plan's "work only here, change no production
  code" boundary. The post-flip rate (36% of attempts skipped) is measured; the
  delta is not.
* **No multi-cycle offline simulator exists.** There is no harness that advances
  world state across scenario cycles, so I could not measure how often
  `_committed_repr` is *actually non-None at the start of a cycle*, nor how
  often the walk returns the same node on two genuinely different consecutive
  states. §1.3 measures the complete space of *possible* commitments per cycle
  instead, which is a stronger statement per cycle and a weaker one across a run.
  For pre-flip context only: consecutive live cycles selected the same goal on
  34,190 of 78,142 pairs (43.8%).
* **No live per-candidate planner cost.** `cycles` stores one row per cycle with
  the last invocation's stats; the cost of candidates that failed before the
  winner is not recorded anywhere durable. The distribution of no-plan attempt
  costs is therefore known only from the fixture (0.71 ms mean) and bounded
  above by the budget (≥15 s), a spread of four orders of magnitude that I
  could not narrow.
* **Bands 1 and 3 are barely exercised.** One collect-band and one raid-band
  candidate in the whole scenario set. Their "same-as-walk" results are true but
  carry almost no weight; nothing here would catch a regression in sticky
  behaviour for a collect-band commitment.

## 4. Recommendation for wave 3b

**Do not touch, at all:**

* `ai/doomed_memo.py` and every site in §2.1. The class has two independent
  production consumers, one of which post-dates the deletion list and is wired
  into the planner. Its 8 Lean roles, 5 contract pins and 4 mutation entries stay.
* `ai/arbiter_select.py` and every site in §1.1, including
  `strategy_driver.py:1043` and `:1083`. `Formal/ArbiterSelect.lean`,
  `Formal/Extracted/ArbiterSelect.lean`, the `Bridges2` rows and the 8 mutation
  entries stay with them.

**Safe to say out loud in 3b's commit messages, because it is now measured:** at
bands 1–4 the sticky short-circuit reproduces the resolution walk's own answer
(0 flips in 155 candidates), so the parent spec's stability intuition was
*correct about the root* — it was only wrong about the scope. Nothing follows
from that for the code, because band 5 is in the same function and the same
theorems.

**If a later wave wants to revisit Subject A**, the thing to build first is the
missing multi-cycle offline driver. Without it, no one can measure how often a
commitment exists to be defended, and every argument about stickiness stays an
argument about a single frozen cycle.
