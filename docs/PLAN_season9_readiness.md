# Season 9 (Altar of Sacrifice) Readiness and Leaderboard Plan

**Created:** 2026-09-21 · **Status:** design spec (multi-session roadmap) · **Trigger:**
season 9 announcement. Source: https://www.artifactsmmo.com/news/season-9

Live server at announcement time: API `8.2.4`, season 8 ("God of the Sun"), started
2026-06-27.

Precedent for the mechanical phases: `docs/PLAN_season8_readiness.md`.

This is a roadmap across four tracks, not a single implementation plan. Each track gets its
own implementation plan when it is executed; the mechanical parts of T3 are executed
directly. T1 is first in line.

## Key dates

| Date | Event |
|---|---|
| 2026-10-24 | Test server opens — **members only, we have no access** |
| 2026-10-31 16:00 UTC (12:00 ET) | Season 9 launches; full reset |

Full reset means characters, inventories, and all progression are wiped. Leaderboards and
the Grand Exchange are cleared.

## What season 9 adds

### The Altar of Sacrifice

A seasonal event on a specific map tile, available only for the duration of season 9. A
character travels to the altar and accepts one of its offerings.

The altar's demands rotate every day at 00:00 UTC. Each daily rotation contains:

- Combat offerings, based on resources obtained from monsters.
- Offerings for two different skills, selected fresh each day.
- Separate offerings for the 10–20, 21–30, 31–40, and 41–50 level ranges.

The two selected skills rotate so that all eight eligible skills — mining, woodcutting,
fishing, alchemy, weaponcrafting, gearcrafting, jewelrycrafting, cooking — appear once in
every four-day cycle. Depending on the skill, the altar asks either for gathered resources
or for crafted items. Each requirement is sized at roughly 15 minutes of activity, varying
with character, equipment, route, and luck.

Each character may accept one offering per available category per day. Once accepted, that
category and level range are locked for that character until the next daily reset.

Accepting an offering immediately grants favors that last until 00:00 UTC:

- **+50% XP** for the exact activity the offering names.
- **+50% drop rate** on that specific monster or resource node, for offerings tied to one.

Crafting offerings apply their XP bonus to a specific recipe rather than to a node.

Completing the sacrifice at the altar pays an immediate XP reward equal to 25% of the XP
required for the character's current level in that offering's category. The favors do not
end on completion — they run until 00:00 UTC regardless.

### Crafting tools

A new family of tools reduces crafting duration, working the same way gathering tools
already do: equip the matching tool, get a percentage reduction on that crafting activity.
Cooking tools arrive first; alchemist gloves gain a crafting bonus. More skills follow in
later updates.

### Crafting XP

Overall crafting XP is increased by approximately 20%. This is a server-side data change.

## Objective for season 9

The season's target is **leaderboard placement on both boards, with the character board
primary**.

The two boards rank different things:

- `GET /leaderboard/characters` ranks each character independently by `total_xp`, which
  sums character XP and every skill's XP. At the time of writing the top character holds
  12,861,767 total XP, of which alchemy alone contributes 11,285,664.
- `GET /leaderboard/accounts` ranks accounts by `achievements_points`, breaking ties by
  the earliest `completed_at`. The top accounts hold 210 points.

Because the character board ranks characters individually, the fleet runs as **five
parallel cooperating runners**. Every character maximizes its own `total_xp`. In addition,
every character:

1. answers sibling requests for material assistance, and
2. plans against the fleet-wide capability matrix, so a character can commit to a recipe
   whose inputs require a skill only a sibling holds.

Achievement points are a secondary tiebreak term in ranking, not a driver.

This replaces the current objective, which targets character level 50 and then skills.
Under `total_xp`, level 50 stops being a terminus and all XP becomes commensurable.

## Constraint: no test-server access

The test server is members-only and we do not have member access. The altar's endpoints,
schemas, and error codes are therefore unknown until the v9 `openapi.json` publishes at
launch.

Consequence for the design: every altar decision is built and tested blind against our own
domain types, and every API detail is confined to a single adapter module that fails loudly
until it is filled in on launch day. Nothing about the altar defaults, guesses, or falls
back — consistent with the project rule that the player uses only API data or fails with an
error.

## What already exists

Audited before designing, to avoid rebuilding shipped machinery.

**The fleet-wide capability matrix is built and wired.** `CoordinationStore.publish_skills`
and `sibling_skill_levels` (`src/artifactsmmo_cli/ai/learning/coordination_store.py:628`
and `:660`) maintain the TTL'd `skill_ledger` table. `src/artifactsmmo_cli/ai/player.py`
publishes and reads it once per cycle (lines 3496 and 3528). `SelectionContext.sibling_skills`
(`src/artifactsmmo_cli/ai/selection_context.py:176`) threads it to the ranking walk as data,
and `acquisition_cost._sibling_craft_option`
(`src/artifactsmmo_cli/ai/acquisition_cost.py:375`, called at `:544`) already prices a route
through a sibling's skill: it waives the skill gate and still charges the recipe inputs plus
the measured request cost.

What is *not* established is whether that route fires on live data, whether it covers
gathering skills as well as crafting skills, and whether it handles multi-hop cases where
one sibling crafts an input for another sibling's craft. That is an audit, not a build.

**Window arithmetic is built.** `event_availability.event_window_sufficient_pure` answers
"does this window stay open long enough to travel there and finish the plan", denominated
in seconds against planner cost. The altar's 00:00 UTC deadline is the same question.

**Commitment storage is built.** The `plan_commitment` table already records a character's
standing commitment with an expiry.

## Tracks

Four tracks. T1, T2 and T3 are verifiable on the live season-8 fleet during the 40 days
before launch; T4 cannot be verified until launch day.

Ordering constraint: T4's favor multiplier only means something once XP is commensurable,
so T1 lands first. T2 and T3 are independent of both.

### T1 — Objective: maximize `total_xp`

Move the objective's target from "character level 50, then skills" to "maximize this
character's `total_xp`", with achievement points as a secondary tiebreak.

Affected modules: `ai/tiers/progression_tree.py`, `ai/tiers/strategic_value.py`,
`ai/tiers/strategic_weights.py`, `ai/learning/scalarizer.py`. The planner itself does not
change — this is a change to what ranking maximizes, not to how plans are found.

Specific decisions:

- Character XP and skill XP enter the objective on the same ruler. `scalarizer` already
  carries `CHARACTER_XP_LEVEL_SCALAR` and `SKILL_XP_BASELINE_WEIGHT`; under a `total_xp`
  objective those weights are no longer free parameters — one point of skill XP and one
  point of character XP are worth the same on the board.
- The existing level-50 terminus must not silently cap ranking. Any term that goes flat or
  undefined above level 50 is a defect under this objective.
- Achievement points are added as a strictly lower-priority tiebreak, so they can never
  outrank an XP-bearing root.

Verification: the `objective` CLI diagnostic must show the new terms and name what decided
the ranking, on a live character, before this track is called done.

### T2 — Fleet capability audit and extension

Establish whether the sibling-craft route actually fires, then extend it where it does not.

1. Census over live data: for each character, how many candidate roots are priced through
   `_sibling_craft_option`, and how many of those become the chosen root. A census, not a
   test — a green test proves nothing about whether the route fires in production.
2. If the route is dormant, find the gate that suppresses it before changing anything.
3. Extend to gathering skills if the audit shows gathering-gated routes are walled while a
   sibling holds the level.
4. Extend to multi-hop only if the census shows real instances.

No new coordination table. `skill_ledger` already carries the data.

Note for the census: the coordination tables are live TTL'd state, not history. An empty
`skill_ledger` means "nothing published recently", never "this never ran". Only `cycles`
is history.

### T3 — v9 readiness

Mechanical, following season 8's P0/P1 shape.

1. **Client regen.** Regenerate the vendored client from the v9 `openapi.json` once it
   publishes. Confirm the generator spec-patches still apply.
2. **Breakage enumeration with `uv run mypy --strict`.** Season 8's lesson: an import smoke
   test misses array-shaped bodies, nullable fields, and `Any`-typed mismatches. `mypy
   --strict` is the real enumerator.
3. **New content codes.** New monster abilities and item effects raise
   `GameDataCoverageError` on live load. Each new ability needs modelling in the proven
   `predict_win` core with its Lean lockstep, exactly as season 8's three abilities did.
4. **Craft-duration tool effect.** The new crafting tools carry an effect that reduces
   craft duration. Gathering tools already have this shape; the craft cost model must read
   the equipped tool's effect rather than assuming a fixed craft duration. Until this lands,
   every craft is mispriced for any character holding one.
5. **+20% crafting XP.** API data. No code change, but the observed craft-XP numerator is
   learned per recipe, so season-8 rows must not price season-9 crafts — which T3's season
   column handles.
6. **learning.db season partition.** Add a season column to the observation and cycle
   tables, stamp existing rows as season 8 in the migration, and scope every learned-rate
   read to the current season. History stays queryable for cross-season comparison; season-8
   numbers can never price a season-9 decision. This is one migration shared with T4's
   favor column.

### T4 — Altar

Built blind. Everything except the adapter is unit-testable before launch.

**Domain types** — new package `src/artifactsmmo_cli/ai/altar/`, pure, no API imports:

- `Offering` — category (combat or skill), the skill or monster code, level band, the
  required item and quantity, and the target the favor attaches to.
- `Favor` — target activity, XP multiplier, drop multiplier, and `expires_at` set to the
  next 00:00 UTC.
- `DailyRotation` — the day's offerings grouped by category and band, plus which categories
  this character has already locked.

Per the one-class-per-file rule, behavioural classes get their own module; this set is
cohesive value objects and may share one.

**Adapter** — `src/artifactsmmo_cli/ai/altar/api.py`, the only module where altar endpoint
names, request bodies, or response schemas appear. Until filled from the v9 spec it raises
`AltarSchemaUnknownError`, a sibling of the existing `game_data_error.GameDataCoverageError`.
No defaulting and no fallback: unknown altar data stops the character with an error.

**Goal and actions** — `ai/goals/altar_offering.py` emits two actions, accept and sacrifice.
The gathering or crafting between them is not altar-specific: it is the existing obtain
machinery pointed at the offering's required item. The goal must declare every action it
needs as a relevant edge, including the obtain route, the travel edge to the altar tile, and
any Withdraw synthesized for banked inputs — a fired rung that names no edge produces no plan.

**State seam** — the rotation and the character's own favors are read once per cycle in
`player.py`'s coordination block and threaded into `SelectionContext` as data, on the same
seam `sibling_skills`, `supply_target` and `asymmetric_demand` use. No new plumbing.

**Commitment, not latch** — an accepted category and band are locked until reset, recorded
in `plan_commitment` with a 00:00 UTC expiry. It is deliberately not a sticky latch: a latch
armed on a standing condition previously froze a character's XP for 981 cycles.

**Favor and the rate model.** A favor is a multiplier on exactly the quantity the rate model
measures, so an unstamped observation would launder the bonus into the learned base rate.
Two treatments were considered:

- *De-multiply* — divide the observation by 1.5 and keep it. This assumes the server applies
  exactly 1.5 and that it composes cleanly with every other modifier. Neither assumption is
  checkable.
- *Exclude* — stamp each observation with the favor state active when it was taken, and let
  base-rate learning read only unfavored rows. **Chosen.**

The favor is then applied at ranking time as an explicit multiplier on the base rate, so it
appears in the `objective` diagnostic's terms instead of being baked into history. This is
the same shape as the level-scoping fix: the learned rate carries the dimension it depends
on. Schema: a favor column on `skill_xp_observations` and `cycles`, in the same migration as
T3's season column.

**Accept and complete are asymmetric.** Accepting is cheap and starts the favor clock
immediately. Completing pays the 25% instant XP. So the window check applies only to
completion: a late accept still earns a full evening of favor, while a sacrifice that cannot
be finished before 00:00 UTC is wasted gathering.
`event_availability.event_window_sufficient_pure` answers this with the offering deadline as
its `remaining_seconds`.

**Offering selection.** Where more than one offering is available in a category, rank by the
value the favor is expected to return over the remaining day, plus the completion XP, minus
the seconds-denominated cost of obtaining the required items. All three terms are already
denominated in the existing cost model. The candidate set must be measured, not only the
argmax: an unpriceable candidate is a veto, so it never becomes the argmax and an
argmax-only audit reports no wall where the candidate set has several.

## Reset-day runbook

Season 9 starts every character at level 1, and the altar's lowest band is 10–20. So the
altar contributes nothing until a character reaches level 10, and the first hours are
ordinary early-game progression under the new objective.

Order of operations at launch:

1. Stop the fleet before 16:00 UTC. Archive nothing — the season column keeps season-8 rows
   in place.
2. Pull the v9 `openapi.json`, regenerate the client, run `uv run mypy --strict`, and work
   the breakage list (T3.1, T3.2).
3. Boot one character against live v9 data and collect every `GameDataCoverageError` — the
   full list of new ability and effect codes (T3.3).
4. Fill the altar adapter from the v9 spec and confirm the domain types match the real
   schema (T4).
5. Start the fleet under the `total_xp` objective; confirm via the `objective` diagnostic
   that ranking is live, not merely green in tests.
6. Once any character passes level 10, confirm the altar rung fires and that a full
   accept → obtain → sacrifice cycle completes.

Step 3 gates live play, exactly as it did in season 8: unmodelled abilities hard-fail the
bot on contact.

## Error handling

The project rule is that multiple levels of error handling are a bug, and that the player
uses only API data or fails with an error. Applied here:

- Unknown altar schema, unknown offering category, or an offering naming an item the
  catalogue does not hold: raise. No default offering, no skip-and-continue.
- A rejected accept because the category is already locked is **not** an error — it is state
  we failed to read, and the fix is to re-read the rotation, not to catch and retry. The
  generated client returns an error schema rather than raising on a non-200, so an altar
  response must be checked by type, never by `hasattr(result, "data")`.
- The 00:00 UTC rollover invalidates rotation and favors. Treat a stale rotation the same way
  a drained Grand Exchange offer is treated: stale data to re-read, not a dead end.
- `except Exception` is never used.

## Testing and verification

Success criteria stay the project's: 0 errors, 0 warnings, 0 skipped, 100% coverage. All
tests live in `tests/`.

Per track:

- **T1** — the `objective` CLI diagnostic on a live character, showing the new terms and what
  decided the ranking. Green tests are not sufficient: a ranking change must be observed to
  fire on a live `plan <char>`.
- **T2** — a census over live data, reported as counts of candidate roots and chosen roots,
  not as a passing test.
- **T3** — `uv run mypy --strict` clean, the full formal gate (`bash formal/gate.sh`, roughly
  five minutes) green, and a live boot that raises no `GameDataCoverageError`.
- **T4** — unit coverage of the domain types, selection ranking, window arithmetic and favor
  stamping, all against our own types. The adapter is exercised only after launch. Mutation
  anchors are refreshed in the same commit as the edit that moves them.

Note that the pre-commit hook runs `pytest tests/test_ai/` only; the formal and differential
suites are not in the default `tests/` run and must be invoked through the gate.

Every scenario must declare its own world. Sharing one `GameData` across altar scenarios
would make the daily rotation identical in every case and the measurements vacuous.

## Residuals and open questions

1. **Band selection.** Whether a character may accept an offering from a band other than its
   own level's is unknown. The design ranks whatever categories the adapter reports, so this
   resolves itself at launch.
2. **Favor stacking.** Whether the +50% XP favor composes additively or multiplicatively with
   other bonuses is unknown, and is the reason observations are excluded rather than
   de-multiplied.
3. **Altar tile discovery.** The altar's map coordinates are unknown. Presumably discoverable
   through the maps endpoint by content type, as raid and event tiles are.
4. **Achievement tiebreak weight.** The secondary term's weight is unset until we see how
   many points are cheaply reachable in season 9.
5. **Per-IP rate budget.** Five characters already run at roughly 52 cycles per hour each,
   with 29–49% of wall clock blocked on the shared request budget. Daily altar trips add
   travel and two actions per character per category. If the rate budget binds, the altar's
   value per request is what decides whether the trip is worth it — that ratio is not yet
   modelled.
6. **Two live-API audit tests fail with HTTP 429 whenever the fleet is running.** They pass
   standalone. This predates season 9 and will confuse the launch-day gate run if not
   remembered.
