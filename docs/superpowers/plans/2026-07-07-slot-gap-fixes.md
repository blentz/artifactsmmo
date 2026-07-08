# Slot-Coverage Gap Fixes (post-flip planner gaps 1-3, 5-6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the five real planner gaps pinned by the slot-coverage net (`tests/test_ai/scenarios/test_slot_coverage.py`); each gap's tripwire test is DESIGNED to fail when its gap is fixed — every task flips its tripwire into a positive assertion of the new behavior. Gap 4 (XP branch outranks empty utility slots) is the approved adequacy design and is NOT fixed.

**Architecture:** Gaps 1-2 are attainability leaves (`objective.py`); gap 5 is the utility-target emitter (`objective.py` + candidate skip in `progression_tree.py`); gap 3 is the vendor-routing gold arm (`strategy_driver.py`); gap 6 is targeted drop-acquisition in `UpgradeEquipmentGoal` (`goals/progression.py` + grey-farm policy). Each fix is small and testable in isolation; the scenario net is the acceptance harness.

**Tech Stack:** Python 3.13 (`uv`), pytest. Lean/mutation impact per task noted (several files carry mutate.py anchors — static-sweep after every edit).

## Global Constraints

- The tripwire tests in `test_slot_coverage.py` carry LIMITATION comments naming their gap — when your fix lands, the tripwire FAILS: rewrite it as a positive test of the fixed behavior (same scenario, new expectation, derivation comment). Never delete coverage; never leave a stale LIMITATION comment.
- Repo rules: only API data, no defaulting; never catch Exception; no inline imports; exact arithmetic; multiple error-handling levels = bug; 100% coverage; mypy strict; TDD (the failing test often ALREADY EXISTS as the tripwire — flipping it first IS the red phase).
- The bot may be LIVE: no gate.sh/mutate.py execution. After ANY edit to an anchored file (objective.py, strategy_driver.py, goals/*, progression_tree.py), run the static anchor sweep (python: import mutate, stub _execute, run main — print stale count; the pattern exists in prior session reports) and include the output in your report. Full gate owed at next bot downtime (final task notes it).
- `plan --scenario <name>` is the fastest empirical probe; the scenario net is the acceptance harness: `uv run pytest tests/test_ai/scenarios/ -q --no-cov`.
- Sequencing: tasks are independent; land in order 1→5 anyway (later tasks' scenarios can shift when earlier attainability fixes land — re-derive pins honestly and document every ripple).

---

### Task 1: GAP-1 — held/banked stock credits attainability

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/objective.py` (`is_attainable_now` leaf arms, ~:131); Test `tests/test_ai/scenarios/test_slot_coverage.py` (`test_bag_slot_banked_stock_not_credited` flips), `tests/test_ai/test_tiers_objective.py` (unit).

The `_attainable_closure` leaf gains a FIRST arm: `state.inventory.get(leaf, 0) + (state.bank_items or {}).get(leaf, 0) > 0` → attainable (mirror `_producible`'s held-stock arm from b6328a3a — same semantics, same None-bank handling). Recipe nodes: held stock of the CRAFTED item itself also counts (a banked satchel makes satchel attainable-now). Unit tests: leaf-in-bank, leaf-in-inventory, crafted-item-in-bank, bank-None (unknown ≠ zero — NOT attainable via stock when bank unknown), partial stock does not over-credit quantity semantics (attainability is boolean — quantity handling stays the planner's job).

- [ ] Flip the tripwire (red) → implement → scenario net green → anchor sweep → commit `fix(objective): held/banked stock credits is_attainable_now`.

### Task 2: GAP-2 — rare gather drops are gatherable

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/objective.py` (`_gatherable` ~:76); Test: tripwire in test_slot_coverage.py (small_pearls/perfect_pearl vendor-route test) flips + unit tests.

`_gatherable` switches from the primary `resource_drops` map to the FULL drop set (`game_data.gatherable_drop_items()` — verify the exact accessor; `resource_drops_full` exists in the snapshot). Filter-at-use-time rule: attainability counts any real drop; rate-based planning judgment stays downstream (GatherAction cost already models rates? — verify; if a 1-in-2000 drop would produce an absurd plan, note it in the report as follow-up, do NOT pre-filter here).

- [ ] Flip tripwire → implement → net green (WATCH: this may ripple l35/l30 pins — artifacts/runes with rare-drop paths may become attainable; re-derive honestly) → anchor sweep → commit `fix(objective): full gather-drop set feeds _gatherable`.

### Task 3: GAP-5 — utility2 fillable; per-slot stock check

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/objective.py` (`utility_potion_targets` ~:302 — emit BOTH utility slots), `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`_utility_candidates` — skip per SLOT: `state.utility1_slot_quantity`/`utility2_...` via the slot being targeted, not `equipped_potion_qty`'s any-slot sum); Test: both l20_dual_utility tripwires flip (empty+empty targets utility1; one-stocked targets utility2) + unit tests.

Churn guard stays: a stocked slot is NEVER a candidate; both stocked → zero utility candidates. Same potion code in both slots is the expected steady state (duplicate-slot rules permit it — verify DUPLICATE_SLOT_TYPES covers utility, else use the catalog's second-best potion for slot 2 and document).

- [ ] Flip tripwires → implement → net green → anchor sweep → commit `fix(tree): both utility slots fillable — per-slot stock check`.

### Task 4: GAP-3 — gold-priced vendor purchases plannable

**Files:** Modify `src/artifactsmmo_cli/ai/strategy_driver.py` (`_equippable_goal` currency arm ~:558-570: the `currency != "gold"` filter); AUDIT `src/artifactsmmo_cli/ai/tiers/strategy.py` `_producible`/`_currency_producible` gold handling + action factory NpcBuy applicability for gold prices. Test: l30_rune_fill tripwire flips (25,000 gold, 10-30k rune → must produce a buy plan) + unit tests.

Semantics: gold price + `state.gold + bank_gold >= price` → route to the direct acquisition goal (`GatherMaterialsGoal(target_item=code, needed={code: 1})` — verify NpcBuy actions fire for gold purchases in the GOAP layer: the l30 tripwire showed GatherMaterials(lifesteal_rune) at 0 nodes, so SOMETHING blocks the buy edge — diagnose whether it's the goal's relevant_actions, NpcBuy applicability (event-NPC gating? gold check?), or factory enumeration, and fix at the ROOT). Unaffordable gold prices: defer honestly (no gold-grinding root this task — note as follow-up if the tree should fund gold like task-coins; that is a design extension, not this gap).

- [ ] Flip tripwire (expect a diagnosis step first — the 0-node dead end has an unidentified root cause) → implement at root → net green → anchor sweep → commit `fix(driver): gold-priced vendor equippables plannable when affordable`.

### Task 5: GAP-6 — targeted drop acquisition for equip targets

**Files:** Modify `src/artifactsmmo_cli/ai/goals/progression.py` (`UpgradeEquipmentGoal.relevant_actions` ~:251 — the Fight-drop exclusion for uncommitted targets); possibly `src/artifactsmmo_cli/ai/grey_farm.py` (policy covers recipe-consumers; an equip TARGET is its own consumer — extend `grey_farm_allowed` or bypass for the goal's own target item). Test: l35 tripwire flips (old_boots: winnable dropper spider → plan must Fight toward the boots) + unit tests incl. xp-positive vs xp-zero dropper (drop_farm flag wiring per the gathering.py precedent).

CAUTION: this is the goal/GOAP layer with combat semantics — is_winnable gating must hold (never plan fights the loadout loses; the l35 scenario's spider IS winnable at realistic stats). Respect the Lean dropFarm scope theorems (ActionApplicability.lean) — the drop_farm arm exists and is proven; you are WIRING it into UpgradeEquipment's action set, not changing its semantics. If the Lean model constrains the goal's shape, mirror the gathering.py wiring exactly.

- [ ] Flip tripwire → implement → net green → anchor sweep → commit `fix(goals): equip targets acquire via targeted monster drops`.

### Task 6: Wrap-up

- [ ] Re-run the WHOLE scenario net + full suite; reconcile every pin that shifted across tasks 1-5 (list them in the spec addendum).
- [ ] Spec addendum (progression-tree design doc): "Slot-gap fix wave SHIPPED" — per-gap one-liner, gap-4 explicitly retained as designed, follow-ups (gold-funding root design, rare-drop rate modeling, equip_value utility-inflation).
- [ ] Static anchor sweep final output in the ledger; note the owed full gate (bot-live constraint) for next downtime.
- [ ] Memory updates.
