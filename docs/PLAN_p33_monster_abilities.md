# P3.3 — Model 3 new Season-8 monster abilities in predict_win (formal lockstep)

**Created:** 2026-06-27 · **Parent:** docs/PLAN_season8_readiness.md (P3.3) · **Branch:** `feat/season8-p33-monster-abilities` (off `feat/season8-client-regen`)

## Context

Season 8 (API v8.0.0) added 3 monster ability codes the parser does not model.
`game_data._build_monsters` HARD-FAILS (`GameDataCoverageError`) on any unmodeled
monster effect code (the combat-veto coverage guard), so **the bot refuses to
start against live v8 data** until all 3 are modeled. Each feeds the
kernel-proven `predict_win` (the combat veto the whole bot trusts), so each
follows the full formal-development lockstep: extend the Lean `def`, re-prove the
3 role theorems, thread the oracle/differential/mutation, keep ×10000
exact-integer arithmetic.

`predict_win` is **closed-form** (per-round net "kill step" / "die step" rates,
no turn counter). Per-turn effects are modeled as a constant per-round delta that
is **conservative for the player** (over-estimate monster strength) so the verdict
stays a SAFE veto — being too pessimistic only makes the bot skip a fight, which
is fine for reach-50 (bosses are not level-50 blockers).

## The 3 abilities (mechanics from live `/effects`, values from live monsters)

| code | monster(s) | value | API meaning |
|---|---|---|---|
| `sun_shield` | sonnengott (L55, 1.5M hp) | 50 | first hit the monster takes each turn reduced by value% |
| `greed` | baby_red_dragon (L50,10), red_dragon (L51,20) | 10/20 | each time the monster loses 10% max HP it gains value% damage, rest of fight |
| `enchanted_mirror` | pixie (L40, 600k hp) | 50 | when the monster takes damage it reflects value% back, once per 3 turns |

Note pixie & sonnengott have boss HP (verdict already `false` on rounds>100), so
enchanted_mirror/sun_shield rarely swing a verdict; greed on the red dragons is
the one affecting near-cap winnability. All 3 must still be modeled (guard + gate).

## Modeling decisions (all conservative-for-player; ×10000 integer space)

Base per-round damage in the ×10000 space is `50*raw*(200+crit)`; value% of it is
`value*raw*(200+crit) // 2` (since 50/100 = 1/2) — the existing
bubble/berserker/frenzy term shape.

1. **sun_shield** — monster DEFENSIVE, reduces player→monster damage. Subtract from
   `killStepNet`, identical shape to `protective_bubble`, always-on (first-hit/turn
   → every round, conservative):
   `- monsterSunShield * rawPlayer * (200 + pCrit) / 2`
2. **enchanted_mirror** — monster REFLECT to player. Add to `dieStep`; reflect =
   value% of damage the monster TOOK = value% of player output. "once per 3 turns"
   relaxed to every turn (conservative, mirrors the `healing` per-3-turn→every-turn
   convention). Note: this is the FIRST `dieStep` term that depends on `rawPlayer`/`pCrit`:
   `+ monsterEnchantedMirror * rawPlayer * (200 + pCrit) / 2`
3. **greed** — monster OFFENSIVE ramp. Add to `dieStep`, same shape as
   berserker/frenzy but ×`GREED_MAX_STACKS`. Stack count = **9** (monster triggers
   at 10..90% HP lost = 9 times while still alive and dealing damage; tightest true
   upper bound). Always-on at max stacks (conservative):
   `+ 9 * monsterGreed * rawMonster * (200 + mCrit) / 2`

## Theorem-role impact (the proof risk)

Three role theorems thread EVERY `predictWin` parameter, so all gain the 3 new
params. Statement/proof changes:

- **`predict_win_eq_sim`** (closed-form = operational sim): LOW. The sim
  (`simRoundsNet`) takes the step *values* as args, so extending the
  `killStepNet`/`dieStep` definitions only threads params; proof body unchanged.
- **`predict_win_mono_monsterhp`** (↓monster HP never flips win→loss): LOW. None of
  the 3 new terms depend on `monsterHp`; threads cleanly.
- **`predict_win_mono_player`** (↑player raw never flips win→loss): the real work.
  - sun_shield is a raw_player-proportional subtraction from kill_step (like bubble).
    Two such terms (bubble + sun_shield) can over-subtract, so the existing
    `monsterBubble ≤ 100` hypothesis becomes the **joint** `monsterBubble +
    monsterSunShield ≤ 100` (+ `0 ≤ monsterSunShield`). Documented: no real monster
    carries both; the cap keeps the player's net kill rate monotone in raw damage.
    Extend the kill_step-monotonicity sub-proof with the same factoring used for bubble.
  - enchanted_mirror puts `rawPlayer` into `dieStep`, so the proof's "die_step is
    independent of rawPlayer" endgame is FALSE in general → mono_player is genuinely
    NOT true ∀ inputs with reflect. Honest fix: add hypothesis
    **`monsterEnchantedMirror = 0`**. Documented: reflect couples player output to
    player damage taken, defeating raw-damage monotonicity; the sole mirror monster
    (pixie) is HP-unwinnable and never a reach-50 grind target, so no decision relies
    on mono_player for it. (greed depends on rawMonster, not rawPlayer → no impact.)

`Contracts.lean` pins the EXACT new statements (incl. the new hypotheses) — this is
the mechanized statement review; the new hyps are deliberate and reviewed, not gaming.

## Touchpoints (lockstep — all move together)

1. `src/artifactsmmo_cli/ai/monster_catalog.py`: 3 dataclass fields (`sun_shield`,
   `greed`, `enchanted_mirror`) + 3 `monster_<x>(code)` methods (`.get(code,0)`).
2. `src/artifactsmmo_cli/ai/game_data.py`: 3 property/setter pairs, 3 public
   accessors, 3 default-`0` inits in `_build_monsters`, 3 `elif code == "<x>"`
   ingestion branches (removes them from the unmodeled set → guard passes).
3. `src/artifactsmmo_cli/ai/combat.py`: `GREED_MAX_STACKS = 9` const; read the 3
   accessors; sun_shield term in `kill_step`; enchanted_mirror + greed terms in
   `die_step`. Keep ×10000 exact-integer and `// 2`.
4. `formal/Formal/PredictWin.lean`: add params to `killStepNet`/`dieStep`/`predictWin`
   + the 3 terms; update the 3 role theorems (signatures + mono_player hyps + proofs).
5. `formal/Formal/Contracts.lean`: update the 3 PredictWin role-contract `example`s to
   the new exact statements.
6. `formal/Formal/Manifest.lean`: unchanged (role names unchanged) — verify still compiles.
7. `formal/Oracle.lean` `runPredictWin`: decode `g 43/44/45` (sun_shield, greed,
   enchanted_mirror) and pass to `predictWin`.
8. `formal/diff/test_predict_win_diff.py`: 3 new `m_*` params in `_run` + the flat
   `args` list (extend to index 45), 3 Hypothesis strategy lines, 3 deterministic
   `test_<x>_flips_*_against_lean` pins.
9. `formal/diff/mutate.py` `PREDICT_WIN_LIFESTEAL_MUTATIONS`: 1 "drop term" mutant per
   new ability (killed by the new flip tests).

## Verification (done-when)

- `formal/gate.sh` fully green: `lake build`, no-sorry, axiom-lint (only
  `propext/Classical.choice/Quot.sound` on all 3 role theorems), Manifest, Contracts,
  differential (Python ≡ oracle over random + the new flip pins), mutation (every new
  drop-term mutant killed).
- `uv run mypy src` clean; unit suite 100% coverage (update monster_catalog/game_data
  tests; the `GameDataCoverageError` carve-out test no longer sees these 3 codes).
- Live boot check: `GameData.load(client, force_refresh=True)` no longer raises (run
  the same script that surfaced the 3 codes).

## Phase 4 adversarial review (mandatory)

After green: read each new term against reachable states. Confirm (a) the conservative
always-on framing is an UPPER bound on monster damage / LOWER bound on player damage
(safe veto), (b) the mono_player hypotheses are honest necessities not convenience
dodges, (c) the flip tests actually exercise a verdict change driven by each term (not
vacuous), (d) the mutation drop-term mutants are killed by those flip tests.
