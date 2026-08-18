# PLAN: Iron-tier gear acquisition — unwalling the skill-gated craft

Status: proposed, 2026-08-17. No code written yet.

## The observation that started this

No character has ever crafted a single piece of iron gear. Fleet-wide, across
60,395 recorded cycles, the only iron items ever produced are `iron_bar` and one
`iron_ring` (Robby, at character level 21). Every iron armour, shield, helm,
boots, leg armour and ring is absent, and iron weapons were never built either.

The question was specifically about characters in the level 10–20 band. That band
holds 41,249 cycles across C3P0, HAL, Lor and R2D2 and contains zero iron gear
crafts.

## What the probes found

Three separate mechanisms, two of them defects. Everything below is measured,
either from `~/.cache/artifactsmmo/learning.db` or from a live probe that builds
the real `WorldState` through `GamePlayer._initialize` and asks
`acquisition_cost` the same question `J` asks.

### D1 — the gated-craft route is dead in production

`acquisition_cost._gated_craft_option` exists precisely to price a craft whose
skill gate is not yet met: it returns a `RouteOption` carrying
`unlock_actions = skill_grind_cycles(...)`. It declines the route when the
observed grind rate is non-positive:

```python
rate = store.skill_xp_per_cycle_all(skill)
max_xp = state.skill_max_xp.get(skill, 0)
if not rate or rate <= 0 or max_xp <= 0:
    return None
```

`LearningStore.skill_xp_per_cycle_all` averages the skill's XP delta over the
last `WINDOW_RECENT = 100` cycles **of any activity whatsoever**. A character
that has spent its recent cycles fighting — which is what the whole fleet is
doing now — records zero XP for every crafting skill in all 100 rows, so the
estimator returns exactly `0.0`.

Probe result, all four characters, taken live:

```
                 gearcrafting  weaponcrafting  jewelrycrafting  mining
C3P0                      0.0             0.0              0.0     0.0
HAL                       0.0             0.0              0.0     0.0
Lor                       0.0             0.0              0.0     0.0
R2D2                      0.0             0.0              0.0     0.0
```

So `_gated_craft_option` returns `None` for every skill-gated craft, for every
character, all the time. `route_options` then returns `[]`, and
`acquisition_cost` charges `UNOBTAINABLE_PER_UNIT = 10**6` per unit. The feature
is inert in the live regime.

This is an absorbing state, not a transient one:

> rate reads 0 → gated craft route declined → item priced at 10^6 → `J` can never
> rank it → the character never grinds that skill → the rate stays 0.

The only escape is an *incidental* craft on that skill from some other goal,
which briefly lifts the rate for 100 cycles, opens the route, lets `J` commit,
and then closes it again as the window rolls past. That flicker is visible in the
history: 3,658 `LevelSkill(gearcrafting->10)` cycles were spent between
2026-08-03 and 2026-08-15, every one of them under an
`UpgradeEquipment(iron_shield/boots/helm/legs_armor)` goal, and gearcrafting never
reached 10 on any character. The goal was picked up and dropped repeatedly rather
than run to completion.

Counterfactual: substituting a plausible positive rate of 1.6 XP/cycle into the
same live probe turns the price finite and rankable.

| item | current | at rate 1.6 (R2D2) | at rate 1.6 (C3P0) | at rate 1.6 (HAL) | at rate 1.6 (Lor) |
|---|---|---|---|---|---|
| iron_boots | 1,000,000 | 424 | 926 | 1,479 | 1,603 |
| iron_shield | 1,000,000 | 424 | 3,000,926 | 1,499 | 1,584 |
| iron_helm | 1,000,000 | 424 | 3,000,926 | 1,499 | 1,584 |
| iron_armor | 1,000,000 | 3,000,424 | 926 | 3,001,471 | 3,001,584 |
| iron_ring | 1,000,000 | 1,532 | 2,001,991 | 1,706 | 1,576 |

The rows that stay at 3,000,xxx are D2, below.

### D2 — the DROP route is gated on CURRENT hp, so the price swings 7000x

`obtain_sources._drop_sources` admits a monster as a source only when
`is_winnable(state, game_data, monster_code)` holds. `is_winnable` falls through
to `predict_win`, which deliberately uses **current** HP:

> `combat.py:146` — *"Uses CURRENT hp (state.hp), not projected max_hp. Prior
> version used p.max_hp which over-predicted wins when the player was already
> damaged."*

That justification is sound for the question *"should I take this fight right
now"*. It is wrong for the question `obtain_sources` asks, which is *"does a route
to this material exist at all"*. Rest is an action the planner has.

The same probe, on the same characters, at two different moments:

```
C3P0 @ hp 63/315     sheep=False  cow=False  chicken=True   blue_slime=False
C3P0 @ hp 315/315    sheep=True   cow=True   chicken=True   blue_slime=True

R2D2 @ hp 72/350     cow=False
R2D2 @ hp 350/350    cow=True

Lor  @ hp 251/305    cow=False   (at max_hp: True)
```

Consequence: `wool` and `cowhide` price at `10**6` whenever the character happens
to be damaged when `J` runs, which makes `iron_shield`, `iron_helm`, `iron_ring`
(3 wool, 2 wool) and `iron_armor`, `iron_legs_armor` (3 cowhide) swing between
~400 and ~3,000,400 — a factor of about 7,000 — on transient HP alone. `J` uses
this bound as a **ranking key**, not only as a prune, so the ranking is being
modulated by combat noise.

Note the direction of the feedback, which matters for where this is heading: a
character that starts losing fights sits at low HP more often, which turns off the
drop routes for the materials of the gear that would fix the fights. The failure
mode compounds exactly when it is least affordable.

### D3 — the grind itself is real, and it is paid four times

This one is not a defect, it is the tuning question.

Measured over all 3,658 `LevelSkill(gearcrafting->10)` cycles in the history,
classified by what the cycle actually produced:

```
gather / drop   3112   (modal cooldown 30s)
fight            205
nothing          197
actual craft     136   (53-131 gearcrafting xp each)
```

About 23 gathering cycles feed each craft. The effective yield is ~1.6
gearcrafting XP per cycle when averaged over everything, which is why a
100-cycle window that misses a craft reads 0 and why the whole D1 latch exists.

Measured only over cycles the character was actually grinding that skill — the
estimator this plan proposes — the rate is stable and never zero:

```
char   gearcrafting  weaponcrafting  jewelrycrafting
C3P0           3.91            3.41             1.90
HAL            5.08            1.66             3.49
Lor            4.75            1.79             1.26
R2D2           2.93            1.85             0.90
fleet          3.82            1.82             2.49
```

Live remaining distance to gearcrafting 10. `xp short` is what
`skill_grind_cost_core.skill_grind_cycles` computes — `max_xp - xp` for the
current level plus a full `max_xp` for every level in between, so a character two
levels short pays for both. The rate column that matters is the last 100 grinding
cycles, because that is the window the implementation will use.

| char | gc | xp | max_xp | xp short | rate, all grind cycles | rate, last 100 | grind cycles | ≈ wall clock @30s |
|---|---|---|---|---|---|---|---|---|
| C3P0 | 9 | 222 | 1700 | 1478 | 3.91 | 3.58 | 413 | ~3.4 h |
| R2D2 | 9 | 1026 | 1700 | 674 | 2.93 | 1.59 | 424 | ~3.5 h |
| Lor | 7 | 1161 | 1200 | 2439 | 4.75 | 4.92 | 496 | ~4.1 h |
| HAL | 8 | 641 | 1450 | 2259 | 5.08 | 2.28 | 991 | ~8.3 h |

Fleet rate over the last 100 gearcrafting grind cycles, all characters pooled:
2.77.

So the grind is a few hours per character, not a wall — but today it is priced at
infinity, and it is priced *per character*, four times over, for the same five
recipes: ~2,324 cycles fleet-wide to unlock one recipe set.

### Not a defect: iron weapons were correctly skipped

Where the gate was genuinely open, the bot's choice was right. HAL, Lor and R2D2
all reached weaponcrafting 10 and built `greater_wooden_staff` (4,779 committed
cycles) rather than `iron_sword`:

- `greater_wooden_staff` — 24 attack_water, 6 `spruce_plank` + 2 `blue_slimeball`
- `iron_sword` — 24 attack_earth, 6 `iron_bar` (= 60 `iron_ore`) + 2 `feather`

Same tier, roughly a tenth of the material cost. The live probe confirms
`iron_sword` is priced at 2 actions for R2D2 right now (weaponcrafting 10, bars in
stock) and it still loses — correctly. No change proposed here.

## Increments

Each increment lands green and is verified against `learning.db`, never against
`play-trace-*.jsonl` (traces are deleted periodically and are not a durable
record).

### Increment 1 — a grind-rate estimator that does not decay to zero

Add a rate estimator scoped to cycles where the character was actually grinding
the skill in question — rows whose `action_repr` matches
`LevelSkill(<skill>->%)` — and have `_gated_craft_option` consume it.

The distinction from the estimator that caused the 2026-08-08 incident must be
pinned by a test, because it is the whole safety argument. That incident came from
`skill_xp_per_cycle`, the **conditional** mean over cycles with a positive delta,
which read 54.0 against a true 1.3 — a 41x under-pricing that captured R2D2 for
4.5 hours. The estimator proposed here keeps every zero-XP gathering cycle in the
denominator (3,112 of them against 136 crafts) and lands at 1.66–5.08, within a
factor of ~3 of the unconditional truth rather than 41x above it. A test must
assert both bounds on the same fixture, or the fix silently reintroduces the bug
it is standing next to.

Fallback ladder when this character has never grinded the skill:

1. the fleet's rate for the same skill (the `cycles` table holds every character;
   only the store's own queries are name-scoped),
2. decline, as today.

Do **not** fall back to a modelled or constant rate. A made-up rate is the
free-looking grind the existing docstring warns about.

Acceptance: on the live DB, `_gated_craft_option` returns a route for
`gearcrafting` on all four characters, and `acquisition_actions('iron_boots', ...)`
returns a finite number in the low hundreds rather than 1,000,000. Verified by
re-running the probe, not by a unit test alone.

### Increment 2 — route existence asks at restorable HP, not current HP

Four call sites ask a route-existence question while passing the character's
current, possibly-damaged state:

| site | question it is asking |
|---|---|
| `obtain_sources._drop_sources:313` | is there a DROP route to this item |
| `drop_obtainability.fightable_droppers:125` | which droppers may the planner kill |
| `tiers/strategy.py:192` | can this currency be produced |
| `tiers/strategy.py:204` | is this leaf attainable by a fightable drop |

A fifth, `tiers/objective.py:233`, already does the right thing — it builds
`rested = replace(state, hp=state.max_hp)` first. That is the precedent to
follow, and it means no new predicate and no new parameter: the fix is to hand
the existing predicate a rested state at each route-existence site, exactly as
`objective.py` and `tiers/guards.py:217` already do.

`fightable_droppers` must change internally rather than at its callers, because
`drop_obtainability`'s module docstring pins an equivalence its callers rely on:

> `drop_obtainable(...) is False` ⇒ `select_drop_fight(...) is None`, for the
> SAME `item`, `state` and `allow_grey`.

Changing the boolean face without the emission face would break that contract in
the direction that produces a plan step nothing approved.

The safety argument for planning a fight the character cannot currently win:
`FightAction._structurally_applicable` still refuses below
`_MIN_FIGHT_HP_FRACTION = 0.3` at execution time, and `GuardKind.RESTORE_HP`
(`tiers/guards.py:211-217`) exists precisely to rest when the fight is winnable
rested and not winnable now. The planner is allowed to plan through a rest; the
executor is not allowed to walk into a losing fight. Those are different gates
and this change touches only the first.

Runtime target selection stays on current HP, unchanged and still pinned:
`player.py:1047`, `player.py:3742`, `combat_targets.py:88`, `guards.py:215`.

A bonus falls out. `tiers/skill_grind_target.py:167-176` documents a known,
unfixed memo-key defect: the candidate memo omits `state.hp`, while the
`obtainable` field it guards reads it through
`_obtainable → drop_obtainable → fightable_droppers → is_winnable → predict_win`.
Once that chain evaluates at `max_hp`, the field no longer depends on `state.hp`
and the memo key becomes sound as written. The stale docstring must be replaced
in the same commit, or it will read as an open defect that has silently closed.

Acceptance: `acquisition_actions` for `iron_armor` and `iron_shield` returns the
same number for a character at 20% HP and at 100% HP. The 7,000x swing
disappears. Verified by re-running the probe at both HP levels on the same
character, and by the obtain-parity census staying green.

### Increment 3 — verify the grind now completes, then decide whether it needs a latch

The original framing of this increment assumed the abandoned grind needs a
stickiness mechanism. That assumption should not be implemented before it is
tested, for two reasons.

First, increment 1 plausibly fixes the abandonment on its own. The grind was
abandoned when the price flipped from ~400 to 1,000,000, and that flip came from
the rate window emptying. An estimator measured over *the grind's own cycles*
cannot empty while the grind is running — it is being fed by the very cycles it
measures.

Second, the mechanism named in the first draft is the wrong one. `plan_commitment`
is restart-resume persistence, not policy. The focus ledger
(`player._gear_focus`, `_charge_focus`, `focus_aging_order`) is an *anti*-starvation
fall-off — it exists to decay a root that has been pursued too long so siblings can
be heard. Adding stickiness there would fight a mechanism built on purpose, and
the ring2-arbiter-starvation work is what put it there.

So this increment is a measurement with a decision gate, not a code change:

1. Run the fleet with increments 1 and 2 live.
2. Query `learning.db` for whether `gearcrafting` gains a level on any character —
   a change in `cycles.skill_levels_json` — and for whether the selected goal
   stayed on the unlock root across the run.
3. If the level lands, this increment is closed with no code.
4. If the grind is still abandoned, capture *what* displaced it from
   `cycles.selected_goal` around the abandonment, and specify the fix against that
   evidence rather than against this guess.

### Increment 4 (tuning) — amortize the unlock across the fleet

Today each of four characters must pay 160–514 cycles to unlock the same five
gearcrafting recipes. One designated gearcrafter reaching 10 and crafting for
siblings is one grind plus twenty crafts instead of four grinds.

The machinery already exists — `role_leases`, `supply_claims`, `SUPPLY_BANK`, and
`4408211a feat(tiers): serve a sibling's request it cannot fill itself`. What is
missing is that `J` does not price "a sibling can make this" as a route, so a
skill-gated item is unobtainable to a character even when a sibling is one craft
away from making it.

This is deliberately last: it is a genuine design change, and increments 1–3 are
worth having on their own. Open question to settle before starting it: whether the
sibling route belongs in `obtain_sources` as a seventh `SourceKind` (which would
give it to every consumer structurally, per that module's stated contract) or
whether cross-character availability is a different kind of fact that should not
enter a per-character route model. Recommend the former; the module docstring
argues for exactly that.

### Increment 5 (tuning) — start the grind before the wall, not after

Right now `band_adequate` reads true and the fleet is grinding character XP with
every iron root walled at 10^6. The concern that prompted this plan is what
happens when fights start failing at the top of the band. D2 makes that strictly
worse: a losing character sits at low HP, low HP closes the drop routes, and the
materials for the gear that would fix the fights become unobtainable exactly when
they are needed.

After increments 1–3, check whether the fleet begins the gearcrafting unlock
*before* `is_winnable` starts returning false at full HP, and if it does not, the
adequacy verdict is the thing to tune — not the pricing.

Acceptance is behavioural and needs a live window: over a play session, gearcrafting
reaches 10 on at least one character while `is_winnable` at full HP is still true
for the character's current farm target.

## Residuals and things deliberately not fixed

- `iron_bar` prices at 0–13 on every character; smelting is not a bottleneck and
  mining is already at 11–13. No change.
- Iron weapons stay unbuilt and that is correct (see above). If
  `greater_wooden_staff` ever stops winning, this needs re-checking, not
  re-deciding.
- `skill_max_xp` is the XP the *current* level requires, applied to every level in
  between, because the API exposes no curve (`skill_grind_cost_core` documents
  this). The per-character estimates above inherit that approximation. Lor's 514
  cycles is the number most exposed to it, since Lor is three levels short.
- `predict_win` at full HP is still the optimistic stat formula. Making the drop
  route ask it at max HP does not make it *right*, only consistent with the
  question being asked.
- The 100-cycle window is left alone for every other consumer of
  `skill_xp_per_cycle_all`. Increment 1 adds an estimator, it does not
  re-denominate the existing one — re-denomination breaks calibrated call sites,
  which this project has already learned once.
