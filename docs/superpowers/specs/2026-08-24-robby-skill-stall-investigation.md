# Robby's skill grind stalled — root-cause investigation

**Date:** 2026-08-24
**Worktree:** `.worktrees/waves-3-6` (branch `waves-3-6`, identical to the `main` the fleet runs)
**Reported symptom:** "Robby hasn't improved a single skill. He's still just grinding character xp."
**Status:** diagnosis only. No production code was changed.

Every number below comes from `~/.cache/artifactsmmo/learning.db`, from
`~/.cache/artifactsmmo/gamedata-api.artifactsmmo.com.json` (the bot's own live
game-data cache), or from an offline reproduction driven by ONE live sense of
Robby's real character state taken at 2026-08-24T09:20 UTC. No claim rests on a
`play-trace-*.jsonl` file. Where a claim rests on the committed scenario fixture
instead of Robby's real state, it says so — in the event, none does.

---

## 1. The answer in one paragraph

A skill grind exists to **craft** the rung item, because crafting is what pays
skill XP. `next_grind_goal` is supposed to descend past the rung to its deepest
unmet material — a flat gather that plans in a few dozen nodes. That descent is
**switched off** for every gearcrafting and jewelrycrafting rung Robby can
reach, because `obtain_sources` reports a `GE_FILL` source (a standing Grand
Exchange sell order for the rung itself) and `prerequisite_graph._source_leafs`
treats *any* non-CRAFT source as a reason to stop descending. `actionable_step`
therefore returns the rung, `next_grind_goal` falls through to its
"materials are already in hand" branch and emits the full from-scratch
`GatherMaterials(rung, held+1)` goal — the exact search explosion the descent
was built to prevent. That goal costs 45,260 nodes and blows the 15 s planning
budget; `_execute_level_skill` raises, `_mark_grind_failure_doomed` marks
`ReachSkill(gearcrafting->16)` doomed, and the arbiter falls through to
`GrindCharacterXP(spider)` — which is precisely what the user sees.

**Cause A (search explosion) is real and is the proximate failure, but the
report's framing of it was wrong: the descent is not "failing to find a cheap
step", it is never running at all. Cause B (goal/action level mismatch) is
cosmetic and must not be "fixed". The mechanism is a third thing — a
GE-listing-driven leaf in the prerequisite graph.**

---

## 2. Verifying the reported measurements

Window `ts >= '2026-08-24T03:36'`, character Robby (164 cycles, ~3.5 h):

| action_class | outcome | n | avg nodes | empty `delta_skill_xp_json` |
|---|---|---|---|---|
| FightAction | ok | 66 | 6 | 66 |
| RestAction | ok | 47 | 14 | 47 |
| **LevelSkill** | **ok** | **27** | **5 475** | **23** |
| **LevelSkill** | **error:other (timed out)** | **11** | **42 277** | **11** |
| FightAction | error:fight_lost | 4 | 2 | 4 |

All five reported facts reproduce exactly. Two corrections of emphasis:

* Robby did **not** earn zero skill XP in the window. He earned **1 365
  gearcrafting XP** (378 + 378 + 231 + 378), which is in line with the rest of
  the fleet for the same window (C3P0 1 464, HAL 1 230 + 562, R2D2 967 + 61,
  Lor 861). Gearcrafting 15 needs **4 400 XP** to reach 16
  (`skill_xp_observations`), so the level genuinely has not moved — the user's
  observation is correct at level granularity.
* Every one of those four XP-bearing legs happened **before 04:41:12**. From
  `2026-08-24T04:41:35` to the end of the data at `07:11` — 2.5 hours — Robby
  earned **zero** skill XP of any kind. That is the stalled state, and it is
  self-sustaining (see §5).

---

## 3. The root cause, established

### 3.1 The rung the grind picks

Driven from Robby's real live state (character level 30, gearcrafting 15,
jewelrycrafting 15, 14 inventory stacks / 115 units of 158, 43 distinct bank
codes), `build_selectable_grind_candidates('gearcrafting', …)` returns 23
candidates and `skill_grind_target` selects **`iron_legs_armor`**
(`acquire_steps=24`, the cheapest obtainable, XP-positive rung).
`recipe = {iron_bar: 5, cowhide: 3}`. Robby holds `iron_bar: 1` in the bag and
`iron_bar: 1` in the bank, `cowhide: 1` in the bag and none banked — so the
deficit is unambiguously real.

For jewelrycrafting the same walk selects **`water_ring`** (`acquire_steps=10`).

### 3.2 The descent does not descend

`actionable_step(ObtainItem('iron_legs_armor', 1), grind_probe_state(state,
'iron_legs_armor'), …, exclude_recycle_leaf=True)` returns
**`ObtainItem(code='iron_legs_armor', quantity=1)`** — the rung itself, in
0.00 s.

`ai/tiers/strategy.py:86-101` returns the node unchanged when
`prerequisites(...)` yields nothing unmet. Instrumenting that call shows
`prerequisites` returns an **empty list** for every gearcrafting rung tested
(`iron_legs_armor`, `iron_armor`, `leather_legs_armor`, `adventurer_boots`),
even though `node.is_satisfied(...)` is `False` for all four and the probe state
has the rung's own copies stripped.

`ai/tiers/prerequisite_graph.py:138-150` — the `_leafs` predicate — has four
arms. The first three do not fire (not satisfied; `owned_count_pure` is 0 after
`grind_probe_state`; the item has a recipe). The fourth is
`any(_source_leafs(s, …) for s in obtain_sources(node.code, …))`. Enumerating
those sources from Robby's real state:

```
iron_legs_armor
    Source(CRAFT,   'iron_legs_armor',          yield=1, cap=10^9)  leafs=False
    Source(GE_FILL, '6a8b365a0d96d2ebd293f1ef', yield=1, cap=1)     leafs=True
leather_legs_armor
    Source(CRAFT,   …)                                              leafs=False
    Source(GE_FILL, '6a76483abc839d0b67d75c3d', yield=1, cap=15)    leafs=True
adventurer_boots      → GE_FILL '6a8c171b72ef4a884deb1cfe' cap=1     leafs=True
mushmush_wizard_hat   → GE_FILL '6a720d7a1c2680b95bb63d83' cap=6     leafs=True
```

`_source_leafs` (`prerequisite_graph.py:59-71`) leafs on **everything except
CRAFT**, with a single grind-aware exception for RECYCLE. A `GE_FILL` source is
emitted whenever `game_data.ge_best_sell_order(item)` returns a standing order
and the GE tile is known (`obtain_sources.py:348-354`; the GE tile is `(5,1)`,
`forest_grand_exchange1`). Robby's game-data snapshot carries a standing sell
order for **21 of the 23** gearcrafting recipes at level ≤ 15 (only
`adventurer_vest` and `mushmush_jacket` lack one) and for
`water_ring`, `iron_ring`, `copper_ring` and most other low jewelrycrafting
rungs.

So: *a stranger's sell order on the Grand Exchange turns off the skill grind's
descent.* The leaf rule's premise — "a ready non-craft source means this node
is directly actionable, so don't walk its recipe" — is sound for a **material**
and false for the **rung of a skill grind**, because buying the rung yields
zero skill XP. This is the same class of defect as the banked-copy WITHDRAW
leaf that `grind_probe_state` was written to defeat (see the C3P0 2026-08-01
incident recorded in `level_skill_expand.py:100-112`); `grind_probe_state` only
removes *holdings*, and it cannot remove a market listing.

### 3.3 What the emitted goal costs

With the descent inert, `next_grind_goal` reaches its fallthrough
(`level_skill_expand.py:154-157`) and returns
`GatherMaterials(iron_legs_armor, {iron_legs_armor: 1})`. Planned offline
against Robby's real state with the real 1 943-action pool:

```
GatherMaterials(iron_legs_armor, {iron_legs_armor:1})
    15.3s  nodes=45260  depth=27  timed_out=True  plan_len=0
```

That is a byte-for-byte match to the live signature: 11 `error:other` cycles
averaging 42 277 nodes, individually 36 049 – 49 852.

### 3.4 The counterfactual

Patching `_source_leafs` to return `False` for `SourceKind.GE_FILL` and
re-running the *same* state:

```
iron_legs_armor    : actionable_step -> ObtainItem(code='cowhide',  quantity=3)
leather_legs_armor : actionable_step -> ObtainItem(code='cowhide',  quantity=3)
adventurer_boots   : actionable_step -> ObtainItem(code='mushroom', quantity=5)
next_grind_goal('gearcrafting') -> GatherMaterials(cowhide, {cowhide:3})

GatherMaterials(cowhide, {cowhide:3})  0.00s nodes=3  plan=['Fight(cow)', 'Fight(cow)']
GatherMaterials(mushroom,{mushroom:5}) 0.00s nodes=11 plan=['Fight(mushmush)', …]
```

3 nodes instead of 45 260. This is exactly the "FLAT gather that plans in ~70
nodes" the `level_skill_expand` docstring promises, and it is unreachable today.

---

## 4. The 23 `ok`-but-zero-XP legs

`cycles` records only the `LevelSkill(...)` **placeholder** in `action_repr`;
`plan_body_log.body_json` for those cycles is literally `["LevelSkill(gearcrafting->20)"]`.
The executed leg (`GamePlayer._last_grind_leg`) is never persisted anywhere.
The legs below were therefore reconstructed from the tile, the cooldown, the HP
delta and the drop signature, cross-referenced against the map:

| tile | map content | signature | leg |
|---|---|---|---|
| (7,13) | `forest_bank2` | cd ≈ 2.0–2.2 s, Δhp 0, +N of one code | **Withdraw** |
| (5,3), (6,4) | `forest_mushmush1/2` | cd 19.6–23.8 s, Δhp −124…−196, **Δxp 0** | **Fight (grey mushmush)** |
| (3,1) | `forest_gcstation1` | cd 4.9 s, Δinv −7…−14, +1 item, skill XP | **Craft** |

Tally of the 27 `ok` LevelSkill cycles:

* **9 bank Withdrawals** (03:39:32, 03:39:35, 03:50:22, 03:50:26, 03:50:30,
  03:50:34, 03:50:37, 03:53:31, 03:53:34) — moving cowhide / wolf_hair /
  mushroom / spruce_plank out of the bank. Zero XP by construction.
* **13 grey-mob fights against mushmush** (03:41:43 … 03:48:28 and 04:37:01 …
  04:39:41). `delta_xp = 0` on every one: Robby is character level 30 and
  mushmush is level 10, so the fight is inside the server's grey band and pays
  no character XP either. Four of the thirteen dropped anything at all
  (mushroom ×1, mushroom ×2, event_ticket ×1). Cost: ~20 s cooldown plus
  130–200 HP each, which is what drove the 47 interleaved `RestoreHP` cycles.
* **1 Recycle-shaped leg** at the gearcrafting station (03:52:06, cd 2.8 s,
  +1 cowhide +1 spruce_plank, net Δinv +1) five seconds after the grind crafted
  `leather_legs_armor` there. I could **not** determine which item was recycled,
  because nothing in `learning.db` records it — the yield (1+1) does not match
  `leather_legs_armor`'s recycle yield (2 spruce + 1 cowhide) exactly.
* **4 crafts** — the only legs that paid skill XP: `mushmush_wizard_hat` (378),
  `mushmush_wizard_hat` (378), `leather_legs_armor` (231), `adventurer_boots`
  (378).

So the grind was never "executing fine and earning nothing" in a mysterious
way: it was doing the *right shape of work* — withdraw materials, farm the
missing drop, craft — but only ever completing the loop when the bank happened
to hold enough stock. `plan_body_log` shows `RecycleSurplus` executing
`Recycle(mushmush_wizard_hat×1)` at 03:41:00 and 03:41:08, i.e. **the fleet
recycled both wizard hats within seconds of the grind crafting them.** That is
XP-neutral (the XP is already banked) but it is pure churn and worth a separate
look.

### The observability gap

Two things cost me time and should be fixed:

1. **The executed grind leg is not recorded.** `cycles.action_repr` and
   `plan_body_log.body_json` both stop at the `LevelSkill` placeholder.
   `GamePlayer._last_grind_leg` and `_last_grind_expansion` exist (they feed the
   TUI) but are never persisted. Every leg above had to be inferred from map
   tiles and cooldown lengths.
2. **`cycles.planner_nodes` on a LevelSkill cycle measures a different search
   than `plan <char>` reports.** The live `plan Robby --learn` prints
   `ReachSkill(gearcrafting->16): nodes=2 depth=1 plan_len=1`, while the same
   cycle in `cycles` shows 42 277 nodes. Both are correct: the recorded number
   is `planner.last_stats` **after** `_execute_level_skill` ran its sub-plan
   search, overwriting the goal's own stats. Nothing labels which search a row
   describes.

---

## 5. Why the stall is self-sustaining (and why it looks like "grinding character xp")

From 04:41:35 onward every `ReachSkill` cycle is a timeout. The sequence,
straight out of `cycles`:

```
04:41:12  ReachSkill(gearcrafting->16)     LevelSkill(gearcrafting->20)     ok           nodes=3      +378 gearcrafting
04:41:35  ReachSkill(gearcrafting->16)     LevelSkill(gearcrafting->20)     error:other  nodes=49231
04:41:54  ReachSkill(jewelrycrafting->16)  LevelSkill(jewelrycrafting->20)  error:other  nodes=37630
04:42:02  GrindCharacterXP(corrupted_ogre) …
…
05:38:47  ReachSkill(gearcrafting->16)     error:other  nodes=49852
05:39:31  ReachSkill(jewelrycrafting->16)  error:other  nodes=37436
05:40:25  GrindCharacterXP(ogre) → 05:43 … 06:00  GrindCharacterXP(spider) ×8, RestoreHP ×8
06:01:01  ReachSkill(gearcrafting->16)     error:other  nodes=48328
06:01:21  ReachSkill(jewelrycrafting->16)  error:other  nodes=36049
06:01:23  GrindCharacterXP(spider) …
06:20:46 / 06:21:06   same pair, then spider again
06:50:01 / 06:50:20   same pair, then spider again
```

The craft at 04:41:12 consumed the last of the withdrawn stock (inventory 127 →
113). From that instant the emitted goal is genuinely from-scratch, and it never
plans again.

`_execute_level_skill` (`ai/player.py:1470-1490`) raises on the empty sub-plan
and calls `_mark_grind_failure_doomed` (`player.py:1505-1537`), which marks
`ReachSkill(gearcrafting->16)` in the `DoomedMemo`. The memo's key is the
**plannability signature** — character level plus skill levels
(`ai/doomed_memo.py:47-57`) — and its re-probe TTL doubles on each consecutive
failure under the same signature (20 → 40 → 80 → 160 cycles,
`doomed_memo.py:42-45`). Since the only thing that could change gearcrafting is
the grind that cannot run, the signature never changes, so the memo re-arms
forever and the arbiter spends the intervening cycles on
`GrindCharacterXP(spider)` interleaved with `RestoreHP`. The observed re-probe
cadence (04:41 → 05:38 → 06:01 → 06:20 → 06:50) is that escalating window.

That is the user's sentence, mechanically derived: *he's still just grinding
character xp*.

---

## 6. Cause B — the ReachSkill(→16) / LevelSkill(→20) mismatch

Confirmed as real, and confirmed **inert**. Do not "fix" it.

* Wave 3a's `decisions/root.py:415-422` returns
  `ReachSkillLevel(skill, current + 1)` for a skill-blocked gear target, and
  `strategy_driver.py:690-699` maps it to `ReachSkillGoal(skill, 16)`.
* The action pool contains a `LevelSkill(skill, L)` for every L that is some
  recipe's `crafting_level` plus every gather-gate level
  (`ai/actions/factory.py:134-158`) — for gearcrafting that is
  {1, 5, 10, 15, 20, 25, …}. **There is no `LevelSkill(gearcrafting->16)` and
  there never will be.**
* `ReachSkillGoal.relevant_actions` (`ai/goals/reach_skill.py:50-52`) matches on
  skill name only, so `LevelSkill(gearcrafting->20)` is admitted;
  `is_applicable` keeps only targets above 15, and `LevelSkill.cost`
  (`level_skill.py:81-90`) is monotone in the level gap, so A* picks the
  smallest surviving rung, 20. Observed live: `PLAN (1 actions): LevelSkill(gearcrafting->20)`,
  `nodes=2 depth=1`.
* **Tightening `relevant_actions` to a `(skill, level)` match would leave the
  goal with no relevant action at all and kill wave 3a outright.** The loose
  filter is what makes the wave-3a path work.
* The mismatch changes no behaviour downstream: `_execute_level_skill` calls
  `next_grind_goal(action.skill, …)` (`player.py:1458`) and
  `next_grind_goal` takes only the skill (`level_skill_expand.py:21`);
  `target_level` reaches nothing but `LevelSkill.cost`, and `ReachSkillGoal.value`
  is the constant 55.0, so the arbiter's ordering is unaffected too.

The docstring's claim that "a plain skill-name match suffices" is therefore
still true. Its *reason* ("the goal's target and the action pool's target
coincided") is now false and should be rewritten, but that is a comment fix.

---

## 7. What is different about Robby

The GE_FILL leaf is not Robby-specific — it fires for `copper_ring`,
`iron_ring`, `copper_boots`, `copper_armor` and most other low rungs too. What
differs is whether the from-scratch goal it forces is *still* cheap enough to
search. Measured from Robby's own state with his own 1 943-action pool, so the
character is held constant and only the rung varies:

```
copper_ring          0.0s  nodes=    13  plan_len=4   {copper_bar: 6}
copper_boots         0.3s  nodes=  1932  plan_len=7   {copper_bar: 8}
copper_armor         5.5s  nodes= 22169  plan_len=6   {copper_bar: 5, wool: 2}
leather_legs_armor   0.1s  nodes=   380  plan_len=4   {spruce_plank: 5, cowhide: 3}
iron_ring           15.5s  nodes= 47199  TIMEOUT      {iron_bar: 6, wool: 2}
iron_legs_armor     15.4s  nodes= 47320  TIMEOUT      {iron_bar: 5, cowhide: 3}
mushmush_wizard_hat 15.5s  nodes= 51701  TIMEOUT      {cowhide: 4, wolf_hair: 4, mushroom: 6}
```

Three things stack up against Robby specifically:

1. **His crafting skills are the fleet's highest** (gearcrafting 15,
   jewelrycrafting 15; `skill_ledger` has the others at gearcrafting 9/9/10/11
   and jewelrycrafting 3/4/8/8). His in-level rungs are the level-10/15
   recipes, whose materials are
   *monster drops* (`cowhide`, `wolf_hair`, `mushroom`) sitting on top of a
   two-level bar chain — not the single-material ore→bar→ring chains
   (`copper_ring` = 6 copper_bar) that R2D2 and Lor are grinding. Depth plus a
   DROP branch is what explodes the search.
2. **`acquire_steps` is blind to searchability.** It ranked `iron_legs_armor`
   (24) above `leather_legs_armor` (25) — a virtual tie — and picked the one
   that times out over the one that plans in 380 nodes. That is a second,
   independent defect worth its own ticket.
3. **He is character level 30**, so every one of these mobs is grey: 13 grind
   fights, 0 character XP between them, ~20 s and ~150 HP each, feeding the 47
   `RestoreHP` cycles that crowd out the grind. The near-full bag (115/158
   units, 14 of 20 slots) is *not* implicated — the timeouts occur at
   `inventory_used` 111–115 and the successful crafts at 113–128 alike, and
   removing capacity pressure does not change the leafing.

Fleet-wide timeout rates for `action_class='LevelSkill'` in the same window
confirm the gradient: Robby 11/38 (29 %), C3P0 8/38 (21 %), R2D2 7/144 (4.9 %),
Lor 6/168 (3.6 %), HAL 2/426 (0.5 %) — ordered by crafting skill level.

### Why this only surfaced on 2026-08-24

`GE_FILL` landed on 2026-08-20 (`3f427049`, "the Grand Exchange becomes a route
in THE MODEL"). The grind was healthy for the next three days because the fleet
was grinding a **gather** skill: `LevelSkill(woodcutting->20)` accounted for
496/291/849/41 cycles on 08-20…08-23 at 3–7 nodes each and a 96–100 %
skill-XP-per-leg rate. A gather-skill grind takes the
`best_gather_resource_drop` arm (`level_skill_expand.py:150-151`), which never
touches `actionable_step` at all.

Wave 3a (2026-08-23, `11208d75` + the `strategy_driver` arm) made
`ReachSkillLevel` a routine root, and on 08-24 the fleet's grinds moved to
**craft** skills for the first time since GE_FILL shipped. Fleet-wide
`LevelSkill` health, by day:

```
day         n     timeouts  avg nodes  legs paying skill XP
2026-08-20  1768     0          10      1479  (84%)
2026-08-21   438    10        1077       352  (80%)
2026-08-22   905     0          10       869  (96%)
2026-08-23    41     0           3        41  (100%)
2026-08-24   814    34        2579       146  (18%)
```

Wave 3a did not create the bug. It removed the thing that was hiding it.

---

## 8. Recommended fix (one sentence, not implemented here)

Make the skill grind's descent **root** refuse to leaf on any source that
substitutes for the craft — at minimum `GE_FILL` and `BUY`, the two that
`grind_probe_state` cannot neutralise because they do not depend on holdings —
so that `actionable_step` walks into the rung's recipe and returns the flat
material gather (`ObtainItem(cowhide, 3)`, 3 nodes) instead of handing the
planner a from-scratch chain (45 260 nodes, timeout).

Two secondary items, each worth its own change:

* Persist `GamePlayer._last_grind_leg` into `cycles` (a `grind_leg_repr`
  column, or reuse `plan_body_log`) so a grind cycle's real action is legible
  from the DB, and label whose search `cycles.planner_nodes` describes.
* Give `skill_grind_selection` a tiebreak that prefers a rung whose emitted goal
  is actually plannable; today it chose the 47 320-node `iron_legs_armor` over
  the 380-node `leather_legs_armor` on a one-step difference in `acquire_steps`.

---

## 9. Reproduction

One live API call was made (a single `plan_once` sense of Robby at
2026-08-24T09:20 UTC); everything else ran offline from that snapshot plus the
committed game-data cache. The scratch scripts used are throwaway and live in
the session scratchpad; the reproduction is:

1. Sense Robby, keep `player.state`, `player._last_ctx`, `player.game_data`.
2. `build_selectable_grind_candidates('gearcrafting', state, gd, ctx)` → 23 rows;
   `skill_grind_target(...)` → `iron_legs_armor`.
3. `prerequisites(ObtainItem('iron_legs_armor',1), grind_probe_state(state,'iron_legs_armor'), gd, ctx, True)` → `[]`.
4. `obtain_sources('iron_legs_armor', …)` → `[CRAFT, GE_FILL]`;
   `_source_leafs(GE_FILL, gd, True)` → `True`.
5. `next_grind_goal('gearcrafting', …)` → `GatherMaterials(iron_legs_armor, {iron_legs_armor:1})`.
6. `planner.plan(state, that_goal, player._build_actions(), gd)` → 45 260 nodes,
   15.3 s, `timed_out=True`, `plan_len=0`.
7. Patch `_source_leafs` to return `False` for `GE_FILL`; repeat step 5 →
   `GatherMaterials(cowhide, {cowhide:3})`; repeat step 6 → 3 nodes,
   `['Fight(cow)', 'Fight(cow)']`.
