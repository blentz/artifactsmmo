# PLAN: gem / skill-gated-material inventory strategy (QUEUED)

**Status:** designed 2026-06-18, QUEUED behind the level-50 formal work (#2-6)
AND behind resolving the pending `inventory_caps.py` git stash. Side-quest from
a live-inventory check.

## Problem (live data, Robby level 10)

The bot held **48 units (~66% of a 73/118 bag) of level-20 gemstones** —
`topaz_stone ×15, ruby_stone ×16, emerald_stone ×15, sapphire_stone ×2`
(`type=resource, subtype=mining, level=20`) — during a level-10 copper grind.

Why they accumulate AND clog:
- Gemstones drop as byproducts from EVERY mining node, including `copper_rocks`
  / `iron_rocks` (the low-level nodes the bot grinds). Unavoidable at low level.
- Cutting a stone into a usable gem is `mining@20` (topaz/ruby/emerald/sapphire;
  diamond `mining@35`); 24 stones → 1 cut gem. The bot (mining ≪ 20) CANNOT cut
  them, and the cut gems feed only level-20+ gear. So they are not near-term
  usable.
- `useful_quantity_cap(topaz_stone)` is recipe-driven and SKILL-BLIND: it sees
  the `topaz` recipe consumes 24/batch → cap = `BATCH_BUFFER(5) × 24 = 120` →
  held 15 ≪ 120 → NEVER flagged overstock. So gems are neither discarded
  (correct — 6000g cut value) nor deposited (deposit fires only ≥85% full and
  the cap says they aren't bankable surplus). They pile up.

Root: the cap counts FAR-FUTURE skill-gated recipe demand as NEAR-TERM useful.
A strategy gap, not a correctness bug — the bot still progresses, just with a
bag clogged by stones reserved for a recipe ~10 levels out of reach.

## Strategy

**A high-value resource whose only use is a recipe gated far above the current
skill → bank it proactively (preserve value, free the bag); never discard;
resume use once the gating skill is reached.** Gems are the salient instance;
the rule generalizes to any skill-gated-material clog.

## Mechanism (recommended)

Make `useful_quantity_cap`'s recipe-demand contribution **conditional on the
consuming recipe being reachable**: a material's recipe-demand only counts toward
its useful cap if the consuming recipe's `crafting_skill` level is within a
near-term horizon of the current skill level (reuse the `+2` horizon idiom from
the progression-reserve work, or "≤ current skill level"). When the only
consumers are far-gated, the near-term cap falls to the `safety_floor` → the
material becomes deposit-eligible surplus → **banked** (not deleted: discard
still protects high value; deposit fires first and the bank preserves).

- Active-goal materials stay protected (keep-set / `profile_codes`).
- Generalizes beyond gems (any future-skill-gated material).
- Forward-looking GOLD lever: banked gems become a windfall once mining@20 — cut
  → 6000g each via `gemstone_merchant`, feeding the progression reserve. A later
  follow-on could add an explicit "cut + sell accumulated gems" economy goal once
  mining@20 is reached.

### Alternatives (rejected)
- Special-case `precious_stone` / way-above-level resources to bank eagerly —
  narrower, less principled than the skill-reachability rule.
- Lower the deposit watermark globally — would bank everything eagerly, hurting
  the working set; the issue is the CAP misclassifying gems, not the watermark.

## Cost / blockers (read before starting)

1. **Formal lockstep.** `inventory_caps` is a PROVEN extracted core
   (`useful_quantity_cap_pure` ↔ `Formal/Extracted/InventoryCaps.lean` +
   `Formal/InventoryCaps.lean`). Changing the cap's recipe-demand term =
   re-extract + re-prove + differential + mutation + full `formal/gate.sh`. The
   pure core gains a skill-reachability input (current skill level + the
   consuming recipe's gate), threaded by the impure `_cap_from_state` shell.
2. **Pending stash.** The `inventory_caps.py` git stash (the historical `>`→`<`
   edit + un-regenerated extracted Lean — the drift that blocked the gate
   earlier) MUST be resolved/cleared before touching this file, or it collides.
   Resolve that first.
3. Differential/mutation anchors on `useful_quantity_cap_pure` will move — refresh
   `mutate.py` anchors after the refactor.

## Acceptance
- A level-10 bot with mining < 20 banks its gemstones (frees the bag); gems are
  never discarded; a high-level bot (mining ≥ 20) keeps enough to cut/use.
- Test: live-data-shaped fixture — topaz_stone with only a `mining@20` consumer,
  current mining 10 → cap = safety_floor (deposit-eligible); current mining 20 →
  cap = batch cap (keep).
- Full unit suite 100% cov + full formal gate green.

## Status log
- 2026-06-18: diagnosed from live inventory; strategy + mechanism designed;
  queued behind level-50 #2-6 and the inventory_caps stash resolution.
