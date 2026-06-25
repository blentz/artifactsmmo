# PLAN: value/need-scaled junk keep cap + sell/discard excess

**Bug:** [[project_junk_inventory_livelock]] — Robby L5 wedged in
Withdraw(ash_plank)↔DepositAll. Bag 108/108 = 62 sap + 25 apple (ash_tree
byproducts) + working materials. sap is profile-protected (input to L20-40
potions, soft-target 1) but `select_bank_deposits` keeps ALL 62 (binary keep
ignores the target). At free==0 the last-resort banks the active craft input
(ash_plank) instead of the junk → re-withdraw loop. All actions succeed → no
stuck signal.

**User policy:** total keep (inv+bank) scaled by VALUE and NEED-horizon. sap =
low value, needed ~15 levels out → keep a small cap (≈ soft-target). Excess →
SELL (if a buyer) else DISCARD. Do NOT hoard 60+ in the bank. Never bank an
active craft input as last-resort while junk excess exists.

## Investigation gate (do FIRST)
The overstock-discard (`InventoryProfile.overstockExcess`) ALREADY computes
target-aware excess (sap 62 − target 1 = 61). Why doesn't it fire here? Find the
relief-ladder order / firing predicates (guards.py): is DEPOSIT (last-resort)
preempting DISCARD? Is the discard watermark not tripping at free==0? The
smallest correct fix is likely "junk-overstock discard/sell fires before
last-resort banking a craft input."

## Design (staged)
- **Stage 1 — break the livelock (core):** make the deposit/relief respect the
  soft-target QUANTITY, not binary keep. Keep `soft_target(code)` units of a
  profile material; the excess is releasable. Route excess: SELL if
  `npcs_buying_item` has a buyer at price>0, else DISCARD. Never deposit junk
  to bank beyond the cap. Fix `_last_resort_deposit` to never pick an active
  crafting_target recipe material while any releasable junk excess exists.
- **Stage 2 — value scaling:** keep cap = max(soft_target, value floor). A
  high-value low-need item may keep more than soft-target; low-value far-need
  (sap) keeps soft-target. (soft_target already = need; value is the add-on.)

**Disposal order (user-confirmed 2026-06-24): deposit-buffer-then-sell/discard.**
Keep `cap(code)` units in INVENTORY; deposit up to one more `cap` as a BANK
buffer (so a few stay retrievable, bank bounded ≈ cap); beyond inv-cap + bank-cap
the excess is SOLD (NPC buyer at price>0) else DISCARDED. Junk discard/sell must
fire INDEPENDENT of bank room (today DISCARD_*/SELL_RELIEF gate on
`not bank_has_room`, so junk never clears while the bank has slots — the core
design gap). cap(sap) is small (low value + ~15-level need) → inv≈cap, bank≈cap,
the other ~60 sold/discarded.

## Lockstep (gated)
- `bank_selection.py` (Formal/BankSelection.lean): keep becomes quantity-aware
  (keep `min(held, cap)`; deposits/excess = `held − cap`). Update keepList/
  deposits_exact/freeze_invariant/task_inputs_protected; oracle now drives a
  non-empty profile with quantities; differential + mutation.
- `inventory_profile.py` (Formal/InventoryProfile.lean): the cap (need×value).
- relief ladder (guards.py): discard/sell junk-overstock ordered before
  last-resort input-banking.
- 100% cov; differential + mutation green; axioms safety-3.

## Also fold in
The uncommitted `wanted`-satisfied filter (strategy_driver) — caps the wanted
grind to slot demand, curbing the wooden_shield over-production that helped fill
the bag. Verify + include.
