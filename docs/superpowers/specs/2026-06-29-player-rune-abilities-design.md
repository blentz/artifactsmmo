# Follow-on — Player Rune Abilities: carve solidification — Design

**Status:** approved (brainstorm 2026-06-29) · **Follows:** gear epic (A→ruler→B→C→D, all merged).
**Branch:** `feat/player-rune-abilities` (off main `1da32687`).

## Why

The gear epic deferred 9 player-side rune-ability effect codes (`burn`, `enchanted_mirror`,
`frenzy`, `greed`, `guard`, `healing`, `healing_aura`, `shell`, `vampiric_strike`) under
`_DEFERRED_RUNE_ABILITIES` (game_data.py), `pass`'d through the equippable-effect coverage guard
with the comment "modeling deferred to the Player rune abilities sub-project." This brainstorm
investigated the live `/effects` mechanics + the `predict_win` model and reached two conclusions
that **collapse the deferred work to a documentation/reclassification task**:

1. **`predict_win` must stay conservative — do NOT model these (approved).** `predict_win` is a
   conservative combat veto (over-estimate the monster, under-estimate the player → safe). The
   P3.3 pattern modeled *monster* abilities, which makes the veto *more* conservative. These are
   *player* abilities — crediting player buffs makes the veto *optimistic*, which is **unsafe**
   (risks losses the veto exists to prevent). The safety direction is inverted, so the P3.3
   pattern does not transfer.
2. **Rune gear-value modeling is deferred to a data-driven future (approved).** Flat-valuing
   combat-DYNAMIC abilities (greed ramps with HP loss, burn is a multi-turn DoT, healing is
   periodic) is a crude proxy; runes are endgame-only; and it would re-open the proven
   gear_value/combat_raw cores. Better: let sub-project D's combat-loadout diagnostics accumulate
   real win data, then value runes from ground truth later.

The 9 never reach `predict_win` today anyway (no `ItemStats` field → the loadout projection never
sees them → they are *already* conservatively uncredited). So the genuine work is to make the
carve **intentional and documented** rather than a "deferred TODO."

## Solo-bot classification of the 9 (from live `/effects`)

- **Solo-inert** — no effect for a single-character bot, carved like `threat`:
  - `guard` — redirect damage to protect a low-HP **ally** (no allies).
  - `healing_aura` — heal **allies**, explicitly NOT the caster.
  - `vampiric_strike` — on crit, heal lowest-HP **ally**, NOT the caster.
  - `shell` — +resistance below 40% HP, **boss/raid fights only** (inert in normal grind).
- **Player buffs, conservatively uncredited** — crediting in the veto is unsafe optimism:
  - `burn` — player applies a decaying DoT to the monster (offense).
  - `greed` — player gains damage% per 10% max-HP lost (offense ramp).
  - `enchanted_mirror` — reflect % of damage taken (offense; also breaks player-monotonicity, cf.
    the existing PredictWin `enchantedMirror = 0` hypothesis).
  - `healing` — self-heal % HP every 3 turns (survival).
- **Player self-harm** — a downside:
  - `frenzy` — on a crit, deal damage to **self** (and allies). Uncredited in `predict_win`; and
    since rune *value* is not modeled, a self-harm rune is not preferred for equipping anyway.

## Scope (the whole change)

1. Rename `_DEFERRED_RUNE_ABILITIES` → `_RUNE_ABILITY_CARVEOUTS` (game_data.py) and rewrite its
   comment to an intentional carve documenting the three groups above (per-code rationale), in
   the spirit of the `threat` carve. Update the `else`-branch raise message
   (game_data.py:1335) + the elif comment (1320-1322) to reference the classification, not "the
   sub-project."
2. A regression test locking that all 9 codes ingest without tripping `GameDataCoverageError`
   (extend `tests/ai/test_game_data_item_effect_guard.py`, which already covers `burn`).
3. **No** `predict_win`/`PredictWin.lean` change, **no** new `ItemStats` fields, **no**
   `gear_value` change, **no** new Lean. Full unit suite stays 100%; `formal/gate.sh` unaffected.
4. Update the epic memory + a one-line docs note recording the data-driven-rune-valuation
   deferral (D's diagnostics → a future valuation sub-project).

## Out of scope / non-goals

- Modeling any of the 9 in `predict_win` (unsafe — conservative carve, approved).
- Adding rune-ability gear value / new `ItemStats` fields (deferred to a data-driven sub-project
  after D's diagnostics accumulate real combat-loadout outcomes).
- The separate "prefer learned loadout" behavior follow-on (consumes D's data; independent).

## Testing

- The 9-code ingest regression test (no `GameDataCoverageError`); the renamed constant still
  carves them. Full suite 100%; `lake build` clean (no formal change). No live-network test.
