# The learned-rate branch launders the grey-mob penalty across 38 levels

**Measured 2026-08-09 against the live account and the live learning store.**
Deliberately kept OUT of `docs/spec_cycle_oracle/`: that directory is read by
blind spec-forge agents, and implementation evidence in it would contaminate a
round.

## What the game says

`https://docs.artifactsmmo.com/concepts/stats_and_fights/`:

> XP = Round(((monster_level / player_level) × 20 + monster_hp × 0.04) ×
> **level_penalty** × monster_multiplier × wisdom_bonus)

with `level_penalty` a step function of the gap: at-or-below the monster's level
**100%**, five or more levels above **70%**, **ten or more levels above 0%** —
the kill awards nothing at all.

> **Correction, 2026-08-15.** The published prose is loose at that last edge. A
> gap of exactly ten pays, at the 70% rate; the zero band starts at **eleven**.
> Measured over the learning store's 10 857 ok-fights: 372 at gap 10, every one
> paying, and 107 zero-xp fights, none below gap 11. The finding below is
> unaffected in substance — a rate measured at one level was reused at every
> rung regardless — only the level at which `green_slime` stops paying moves
> from 14 to 15.

## What the projection does

`cheapest_path_to_level` picks a per-rung XP rate from one of two branches:

- the **formula** branch, `game_data.xp_per_kill(code, sim_level, ...)`, which
  takes the simulated rung level and therefore *does* apply the penalty; and
- the **learned** branch, `expected_yield_per_cycle(grind_xp_repr(code), store)`,
  taken whenever the store has any sample with `char_xp > 0`, which returns a rate
  measured at the character's level **at the time of measurement** and is reused
  unchanged at every rung of the walk.

The learned branch wins whenever it is available. It carries no level with it, so
the penalty simply is not applied on that path.

## The measurement

Two level-12 characters, same catalogue, same code, same moment:

| character | branch taken | rung rates | projected reach |
|---|---|---|---|
| **C3P0** | learned (`green_slime`, 100 samples, 7.0/cycle) | **7.0 flat, rungs 12 → 49** | **50, not blocked** |
| **R2D2** | formula (`red_slime` learned rate is **−11.1**, so declined) | 6.0, 5.5, 5.0, 5.0, 4.5 … decaying | **17, blocked** |

`green_slime` is a **level-4** monster. Asked directly, the formula agrees with the
published rule:

```
green_slime is level 4; formula xp at char level 12/30/49: 7/0/0
red_slime   is level 7; formula xp at char level 12/30/49: 12/0/0
```

So C3P0's projection reaches level 50 by killing a level-4 slime at a flat 7 XP per
cycle from level 12 to level 49 — a rate the game's own published rule fixes at
**zero** from level 14 onward.

## Why it matters

This is not a rounding error, it is the sign of the whole objective.

`J` = `acquire_cost + cycles_to_fifty`, banded finite < unreachable. A trunk that
projects **reach 50 at acquisition cost 0** is unbeatable: no gear candidate can
compete with a free path to the terminal objective. Four of five live characters
sat on `xp_trunk` at cost 0 in the last trace audit, and that is why.

R2D2 was the outlier — the only character whose store had no usable positive
observation, so the only one that got the honest formula, so the only one that
correctly concluded it needs gear to pass level 17.

**The character that looked broken was the only one that was right.** The four that
looked healthy were riding a projection that promises unlimited XP from a monster
that will award none.

Note the shape: this is the fifth instance in this epic of *a quantity that is not
what its name says*. `expected_yield_per_cycle(...).char_xp` reads as "XP per cycle
for this monster". It is really "XP per cycle for this monster **at the level the
samples were taken**" — and the walk uses it as though the qualifier were not there.

## Related, found in the same pass

- **R2D2's learned rate is negative** (`char_xp = −11.1` over 100 samples). A
  negative XP rate should not be representable; it is presumably deaths or a level
  reset inside the window. The `> 0` guard hides it rather than reporting it.
- **HP growth is NOT the cause.** The published rule grants +5 max HP per level and
  the walk freezes the body at the current level, so I expected the wall to move
  once the body grew. Measured: it does not. With +5/level applied the wall stays
  at rung 17 for both characters — the binding constraint is attack, which comes
  from gear, not from levelling. The frozen-loadout limit is real but it is not
  what produces this wall.

## What the spec forge did with it, blind

`docs/spec_cycle_oracle/SPEC.md` was clausified with this hole deliberately left
open — S-008 says a measured rate "may supersede" a predicted one and constrains
only that they share a unit. The Phase 1 extractor, which read the spec and no
source, listed among the entities absent from the spec entirely:

> **THE OBSERVATION RECORD ITSELF.** S-008 says observations "contain a measured
> rate for a monster" — a rate of what, per what, keyed how, with what sample count
> or confidence, is never given a shape. It is the one input the spec both leans on
> and refuses to describe.

and, on the staleness axis:

> TIME/EXPIRY is NOT waived anywhere … a measured rate recorded 400 levels ago …

The instrument found the gap from the spec alone.
