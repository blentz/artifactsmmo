# Season 8 (API v8.0.0) Readiness Plan

**Created:** 2026-06-26 · **Status:** roadmap (multi-session) · **Trigger:** the live
server went down to roll out **v8.0.0** (new season). Our vendored client is **v7.0.4**.
Source: https://docs.artifactsmmo.com/changelog/

This is a cross-session roadmap. Each formal-gated phase (P2, parts of P3) gets its own
brainstorm → spec → plan → subagent-driven cycle when executed; the mechanical phases
(P0, P1, P4) are executed directly. Phases are ordered by priority and by what blocks what.

## Status (updated 2026-06-27 — server live at v8.0.0)

- **P0 DONE** (branch `feat/season8-client-regen`, commit 3b04dec8). Surprise: the
  vendored *client code* was already v8-generated; only `openapi.json` was stale at 7.0.4.
  Regen left the client tree byte-identical and refreshed the spec → lockstep restored.
  Both generator spec-patches still apply.
- **P1 DONE** (same commit). The actual breakage was NOT the predicted GE/pending-items
  module renames (those already matched the v8 client). Real breaks surfaced by
  `import` + `mypy --strict`: (a) model renames `NPCItem→NPCItemSchema`,
  `GEOrderCreationrSchema→GEOrderCreationSchema` (v8 fixed the typo),
  `DataPageGeOrderHistorySchema→DataPageGEOrderHistorySchema`; (b) equip/unequip bodies
  now **arrays** — wrapped at all 4 call sites; (c) `EventSchema.content` nullable —
  guarded `_build_events`; (d) `CharacterSkin` enum removed (skins now dynamic `/skins`
  data) — dropped enum, added `APIWrapper.get_all_skins` + live-catalog
  `validate_skin_code(skin, api)`. Suite green: 4054 passed, 100% cov, mypy clean.
  *Lesson:* an import smoke test misses array/nullable/Any-typed mismatches — `mypy
  --strict` is the real P1 enumerator.
- **P3.3 SCOPED (not done)** — live v8 load raises `GameDataCoverageError`. Exactly **3**
  new monster ability codes, mechanics confirmed from `/effects`:
  - `enchanted_mirror` (pixie): monster reflects {value}% of damage taken, once per 3 turns.
  - `greed` (baby_red_dragon, red_dragon): each time monster loses 10% max HP it gains
    {value}% damage for the rest of the fight.
  - `sun_shield` (sonnengott): the first hit the monster takes each turn is reduced by {value}%.
  Each needs the proven-core `predict_win` restructure + Lean lockstep (see P3.3 below).
  ~~**The bot hard-fails on live data until all 3 are modeled** — this is the live-boot blocker.~~
  **P3.3 DONE 2026-06-27** (branch `feat/season8-p33-monster-abilities`, commit 7ecb7ec7):
  all 3 modeled in predict_win, full formal gate green, live boot verified. See
  docs/PLAN_p33_monster_abilities.md. **Live-boot blocker cleared.**
- P2 (batch-craft), P3.1/P3.2 (genericity/item-effect guard), P4 (cooldown cost): unchanged.

## What changed in v8.0.0 (relevant to our reach-50 leveling bot)

**Breaking API changes** (will break our generated client on contact):
- `GET /my/pending-items` → `GET /my/pending_items`
- Grand Exchange endpoints renamed (hyphen→underscore in paths; the generated module
  names encode the URL, so every GE import path changes)
- Equip/unequip now take an **array** of equipment objects (was a single object); utilities
  can specify quantities; equip/unequip **cooldown is multiplied by item count**
- `POST /simulation/fight_simulation` → `POST /simulation/fight` — **we don't use it**
- `POST /events/spawn` removed → `/gems_shop/spawn_event` — **we don't use it** (we read
  `/events/active`)

**Balance / data-model changes:**
- Some recipes now yield **multiple items per craft** (potions ×2, food ×2–3) — the
  `CraftSchema.quantity` output field (already in the spec, value 1 until now) becomes >1
- Monster HP / elemental-attack increases; consumable heal values reduced; 79 crafts
  rebalanced; recycling yields +30% — all **API-data-driven, auto-handled**
- Bank expansion pricing changed (3,500 → doubling → cap 448,000) — **auto-handled**
  (we read `BankSchema.next_expansion_cost`)
- 10 new monsters, 45+ new items, new resources, new maps — **mostly auto-handled** (generic
  loaders), with two silent-gap exceptions (see P3)

**New mechanics (new endpoints we do NOT consume):** Raids, Gems & Subscriptions, Gems Shop,
Game Assistant, Season Rewards, Character Statistics. None are required to reach level 50.
**Out of scope** for readiness — see "Future / out of scope".

## Impact audit summary

| Area | Verdict | Evidence |
|---|---|---|
| Client regen mechanism | Regenerable via `generate_openapi_client.sh` (curls live spec, patches, generates, post-processes 499 code) | `generate_openapi_client.sh` |
| `/simulation/fight` rename | No impact — not imported anywhere | (audit) |
| `/events/spawn` removal | No impact — we use `/events/active` | `world_state.py:108` |
| pending-items rename | Import path changes | `ai/actions/claim.py:8` |
| GE renames | Many import paths change | `commands/trade.py` (9), `game_data.py:17`, `ai/actions/ge_fill.py`, `ge_fill_sell.py` |
| Equip/unequip array | Request schema changes; AI layer omits `quantity` (CLI includes it) — pre-existing seam | `ai/actions/equip.py:127`, `unequip.py:61`, `commands/action.py:314,347`, `api_wrapper.py:129-145` |
| Bank expansion cost | AUTO-HANDLED (reads `next_expansion_cost`) | `game_data.py:1019` |
| Combat ability coverage | AUTO-HANDLED — **hard-fails** on unknown effect code (`GameDataCoverageError`) | `game_data.py:1461-1493`, `_MONSTER_EFFECT_CARVEOUTS` empty |
| Batch craft output qty | **WILL MISBEHAVE** — `CraftSchema.quantity` never read; planner assumes 1 output/craft | `game_data.py:1209-1220`, `actions/crafting.py:27,59`, `min_crafts.py`, `recipe_closure.py` |
| New-content genericity | Mostly generic; 2 hardcoded armor/gear type sets + no item-effect coverage guard | `inventory_caps.py:46`, `tiers/strategy.py:152`, item-effect loader `game_data.py:1126-1207` |
| Equip/unequip cooldown cost | Planner cost hardcoded `1.0`; runtime unaffected (waits on server cooldown) | `actions/equip.py:122`, `unequip.py:56` |

---

## P0 — Regenerate the client from the v8.0.0 spec  ⟂ BLOCKED on server up

**Goal:** vendored client matches v8.0.0. Nothing in P1 can be verified until this lands.

1. When the server is back up, run `./generate_openapi_client.sh`. It `curl`s
   `https://api.artifactsmmo.com/openapi.json` (overwriting the committed `openapi.json`),
   applies its two in-place spec patches, regenerates into `artifactsmmo-api-client/`, and
   `sed`s the 499/`GameHTTPStatus` post-process.
2. **Verify the two spec-patches still apply** to the v8.0.0 schema:
   - Patch 1 collapses an `allOf+$ref+default` on `/my/{name}/action/fight`'s request body.
   - Patch 2 rewrites `{$ref, nullable:true}` siblings to `anyOf`.
   If v8.0.0 restructured those, update the patch logic (the script must not silently no-op).
3. Confirm `openapi.json` now reports `"version": "8.0.0"`. Commit the new `openapi.json`
   **and** the regenerated `artifactsmmo-api-client/` together (they must move in lockstep).
4. Run `uv run python -c "import artifactsmmo_cli.main"` — a bare import smoke test surfaces
   the renamed-module `ImportError`s that P1 fixes.

**Offline prep (do before the server returns):** obtain the v8.0.0 `openapi.json` from the
docs if it is published there, so P1's exact new module names and the equip/unequip array
schema can be confirmed without waiting. If unavailable, P1 is fully gated on P0.

**Done when:** client regenerated at v8.0.0, committed in lockstep with the spec; import
smoke test enumerates the breakage for P1.

---

## P1 — Fix the breaking call sites  ⟂ BLOCKED on P0

Mechanical migration driven by the regenerated client's compile/import failures. Execute
directly (no formal gate — these are I/O glue). One commit per concern; run the unit suite.

1. **GE import paths.** Update every generated-client import to the new module names the
   regen produced (discover by `ls artifactsmmo-api-client/.../api/grand_exchange/` and by
   `mypy`/import errors). Sites: `commands/trade.py` (9 fn imports + `GEBuyOrderSchema`,
   `GECancelOrderSchema`, `GEOrderCreationrSchema`), `game_data.py:17` (`get_ge_orders`,
   `GEOrderType`), `ai/actions/ge_fill.py`, `ai/actions/ge_fill_sell.py`. The `game_data`
   GE facade (`ge_best_buy_order`, `grand_exchange_location`, …) and its AI consumers
   (`liquidation_venue.py`, `discard_overstock.py`, `gathering.py`, `progression_reserve.py`)
   are insulated — they need no change once `game_data`'s import is fixed.
2. **pending-items.** Update `ai/actions/claim.py:8` to the new `get_pending_items_my_pending_items_get`
   module name. (`state.pending_items` is local state — untouched.)
3. **Equip/unequip array schema.** The endpoints now take an array. Update, in lockstep with
   the new generated model:
   - `ai/actions/equip.py:127` and `unequip.py:61` — wrap the request in the new array shape;
     **resolve the pre-existing seam** where the AI layer omits `quantity` while
     `commands/action.py:314,347` includes it. Decide one canonical body builder.
   - `api_wrapper.py:129-145` `body: Any` boundary still forwards; confirm the new generated
     signature (array param) is satisfied.
   - `commands/action.py` equip/unequip CLI paths.
   Cover with unit tests asserting the array body shape.
4. Full unit suite green (100% coverage). No formal gate (no decision logic changed).

**Done when:** `uv run python -c "import artifactsmmo_cli.main"` succeeds, `uv run artifactsmmo
--help` exits 0, equip/unequip/GE/claim actions construct valid v8.0.0 request bodies, suite green.

---

## P2 — Batch-craft output quantity  ◇ OFFLINE-STARTABLE (formal-gated)

`CraftSchema.quantity` ("Quantity of items crafted", the output yield) is **already in the
v7.0.4 spec** and every recipe is `1` today, so this fix is forward-compatible: a no-op now,
correct under v8.0.0. It is a genuine latent bug — when a recipe yields 2, the planner
over-crafts 2×, and task-progress / skill-XP credit are off by the yield. **Can begin before
the server returns.**

This touches proved decision cores (`recipe_closure`, `min_crafts`, the craft apply model),
so it follows the full formal-development lockstep (Lean def + role theorems + differential +
mutation). Its own brainstorm → spec → plan cycle.

Scope:
1. Read `craft.quantity` into the recipe model — `game_data._build_items()` (`game_data.py:1209-1220`)
   stores an output-yield alongside the ingredient map (default 1 when UNSET).
2. Propagate the yield through the planner:
   - "crafts needed for N items" divides by yield (ceil) — `min_crafts.py`, `recipe_closure.py`.
   - `CraftAction.apply` credits `runs × yield` items, and `task_progress` / XP use the same
     (`actions/crafting.py:59,62,79`).
3. Lean lockstep: update the `MinCrafts` / `RecipeClosure` cores + role theorems + Contracts +
   differential + mutation anchors. Regenerate `Formal/Extracted/*` if extraction sources change.
4. Full `formal/gate.sh` green + unit suite 100%.

**Done when:** a recipe with yield 2 schedules ⌈need/2⌉ crafts, apply/XP/task-progress credit
the true yield, all gates green. Verifiable offline against synthetic yield-2 fixtures.

> **P2 DONE 2026-06-28** (branch `feat/batch-craft-yield`, atop the season8 chain, commits
> e97ee871..c77aae69; NOT merged). Learned>prior(`CraftSchema.quantity`)>1 yield resolution;
> ceil-batch ⌈need/Y⌉ threaded through the proved RecipeClosure/closureDemand cores (Lean
> re-proved, extraction regenerated, Y>1 differential + 4 yield/ceil mutants). Wrappers default
> to the prior map so the fix is live for all callers under v8. Full suite 4092 pass/100% cov;
> full formal gate green. See docs/superpowers/plans/2026-06-26-batch-craft-yield.md.

---

## P3 — Silent-gap hardening (genericity + new abilities)

Two silent misclassifications + one missing guard the audits found; plus new monster abilities
that only become knowable after P0 loads v8.0.0 data.

1. **Generic combat-gear typing** (offline-startable). `_ARMOR_TYPES`
   (`inventory_caps.py:46`) and `_COMBAT_GEAR_TYPES` (`tiers/strategy.py:152`) are hardcoded
   frozensets; a new armor/gear item type (e.g. "gloves") is silently mis-scored. Derive these
   from the API item taxonomy (type / equip-slot), per the established generic-categorization
   principle. Formal-gated where it touches gear scoring/decide_key.
2. **Item-effect coverage guard** (offline-startable). Unlike the monster-effect dispatch
   (which hard-fails on unknown codes), item-effect loading (`game_data.py:1126-1207`) silently
   drops unrecognized effect codes → new v8.0.0 consumable/equipment effects undervalue gear.
   Add a hard-fail coverage guard mirroring `_MONSTER_EFFECT_CARVEOUTS`, so new effects must be
   modeled (or explicitly carved out) — not silently ignored.
3. **New monster ability codes** (BLOCKED on P0). The monster-effect guard
   (`game_data.py:1461-1493`) will **refuse to start** if a v8.0.0 monster carries an unmodeled
   ability code — the correct failure mode. After regen + loading live data, enumerate any new
   codes and model each via the proven-core restructure (the established lifesteal/poison/…
   pattern). Unknown until v8.0.0 data is in hand.

**Done when:** combat-gear typing is taxonomy-driven, item effects fail loudly on unknowns,
and every v8.0.0 monster ability is modeled (bot starts clean against live data). Gates green.

---

## P4 — Equip/unequip cooldown cost (planning accuracy)  ⟂ low priority

Equip/unequip planner cost is hardcoded `1.0` (`actions/equip.py:122`, `unequip.py:56`); with
v8.0.0's per-item-count cooldown multiplier, multi-item swaps are under-costed in GOAP search.
**Runtime is unaffected** (the bot waits on the server-returned cooldown), so this is
planning-optimality only — schedule after P1–P3. Model the cost as item-count-scaled (or read
the action's modeled cooldown). Formal implications only if it enters a proved cost core.

---

## Future / out of scope (new mechanics — not needed to reach level 50)

These are new subsystems behind new endpoints we don't consume. Document as opportunities; do
not build for readiness:
- **Raids** (`/raids`, leaderboards, `raid_started`/`raid_ended` WS) — cooperative bosses.
- **Season Rewards** (`/season_rewards`) — badges/skins/gems by achievement points.
- **Character Statistics** (`/characters/{name}/stats`, members-only) — could feed learning.
- **Gems / Subscriptions / Gems Shop / Game Assistant** — monetization + members-only; no
  bearing on the autonomous leveling loop.

A later roadmap can evaluate Raids (new high-level XP source) and Character Statistics (richer
learning signal) on their own merits.

---

## Execution order

1. **Now (offline, server down):** P2 (batch craft) and P3.1/P3.2 (genericity + item-effect
   guard) — all forward-compatible against v7.0.4, real latent bugs, verifiable on synthetic
   fixtures. Pursue P0 offline-prep (grab the v8.0.0 spec from docs if published).
2. **When the server returns:** P0 (regen) → P1 (fix breakage) → P3.3 (model new abilities
   surfaced by live data) → P4.
3. New mechanics: separate future roadmap, only if a leveling/learning benefit is identified.
