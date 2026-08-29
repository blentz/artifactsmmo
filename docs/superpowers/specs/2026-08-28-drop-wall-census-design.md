# The unwinnable-dropper wall has a name — and it lives on the ALTERNATIVES

`[DESIGN 2026-08-28]`

## 1. The silence

`obtain_sources._drop_sources` (`obtain_sources.py:455`) withholds a DROP route
when `is_winnable(rested, game_data, monster)` is False. The item then has no
drop route; if it has no other, the pricer charges `UNOBTAINABLE_PER_UNIT` and
every recipe consuming it inherits infinity. Nothing anywhere says *"you cannot
beat the thing that drops this."*

The 2026-08-09 exclusion audit ranked this the **biggest unfixed wall** of its
twenty sites and recorded why it stayed unfixed: *"cost to become able to beat
monster X has no simple measure and is circular."* That was true then.
`combat_deficit` — which returns a gear chain, a per-step `acquire_cost` and a
`closes` verdict — did not yet exist in the form it has now.

This design does NOT price the route. It gives the wall a name, measures how
often it binds, and leaves production behaviour alone. That is the same stopping
point §13 took for gold, taken for the same reason: a census is what tells us
whether the behaviour change is worth making, and it is cheaper to be wrong
about a name than about a price.

## 2. Why every previous audit was blind to it

Every census in this repo prices **the resolved root** — the argmax of the tier
walk. Measured on the committed bundle, across all 44 scenarios in their own
declared worlds:

| | |
|---|---|
| roots resolved | 42 |
| roots priced UNOBTAINABLE | 27 |
| of those, walled on an INGREDIENT (cross when every non-root item is granted) | 4 |
| of those 4, walled on an unwinnable dropper | **0** |

Read no further and the wall names nothing — which is exactly the verdict §12
gave the funding widening, and it would have been wrong. **An infinite price is
a veto.** A candidate walled at infinity never becomes the argmax, so a
differential that only asks about the winner cannot see the thing the wall is
doing. It is the same shape as the gold row's blindness one layer up: the name
was fine, the grid could not see its subject.

Priced over **root + every alternative** (`RootResolution.alternatives`, the set
`_servable_promotion` walks):

| | |
|---|---|
| candidates priced | **448** |
| priced UNOBTAINABLE | 371 |
| **crossing when the unwinnable-dropper items are granted** | **9** |

The nine, with the monster that walls each and `combat_deficit`'s verdict:

| scenario | candidate root | dropper | margin | closes | chain |
|---|---|---|---|---|---|
| `l10_copper_adequate` | `ObtainItem(cowhide, 5)` | `cow` | −23 | yes | `iron_sword` |
| `l12_deep_chain_grind` | `ObtainItem(cowhide, 5)` | `cow` | −10 | yes | `iron_sword` |
| `l10_weapon_upgrade` | `ObtainItem(blue_slimeball, 2)` | `blue_slime` | −7 | yes | `iron_sword` |
| `l35_artifact_fill` | `ObtainItem(king_slimeball, 2)` | `king_slime` | −5 | yes | `cursed_sceptre` |
| `l35_boots_drop_farm` | `ObtainItem(king_slimeball, 2)` | `king_slime` | −2 | yes | `cursed_sceptre` |
| `l30_rune_fill` | `ObtainItem(king_slimeball, 6)` | `king_slime` | −9 | yes | `death_knight_sword` |
| `l20_bag_critical_empty_bank` | `ObtainItem(mushroom, 4)` | `mushmush` | 0 | yes | `forest_whip` |
| `l22_rest_for_combat` | `ObtainItem(mushroom, 4)` | `mushmush` | 0 | yes | `forest_whip` |
| `l20_boost_stock` | `ObtainItem(mushroom, 4)` | `mushmush` | 0 | yes | `forest_whip` |

**9 of 9 close, and every chain is ONE item.** The mid-game chicken-and-egg the
2026-08-09 audit described is in the corpus, in its simplest possible form: the
sword that opens the cow is one acquisition away, and the pricer says infinity.

## 3. What the census measures

**Grid.** One row per `(scenario, candidate root)` that prices
`>= UNOBTAINABLE_PER_UNIT`, over `ai/scenario.SCENARIOS` × `root +
RootResolution.alternatives`. Candidates, not the winner — §2 is the whole
reason.

**Each cell in the world its scenario declares.** `declared_world` keyed on
`(ge_market, unlocked_achievements)`, identical to `currency_wall_census`. A
single shared `GameData` measures a world no scenario asked for; that failure
has been shipped once already.

**Detection is a crossing differential, not a second closure walk.** The pricer
does not report what it walled on, and re-deriving the demand closure here would
be the second cost model obligation O6 forbids. So the census asks production's
own pricer twice: price the candidate as it stands, then price it again with the
unwinnable-dropper items granted into the bag. A price that FALLS was paying an
unobtainable charge for one of them. One pricer, no rival walk.

**The grant set is structural, and it is the negation of `_drop_sources`' own
conjuncts** — `monsters_dropping(item)` is non-empty, at least one dropper has
live tiles in `all_monster_locations`, and none of those is `is_winnable` at
restorable HP. Reading the same three facts production reads is what keeps the
census and the pricer from disagreeing about why a route is absent. 109 items in
the catalogue carry a dropper; the structural filter selects up to 68 per
scenario, 2,221 `(scenario, item)` cells in total.

**Two names, split by `combat_deficit(monster).closes`:**

* `WALL_DROPPER_UNWINNABLE_CLOSES` — a gear chain exists that flips the fight.
  This is the priceable one, and the one a future `_gated_drop_option` would
  open. **9 witnesses.**
* `WALL_DROPPER_OUT_OF_REACH` — no chain in the catalogue closes the margin.
  An honest terminal wall. **0 witnesses**, and the census asserts that zero, so
  the first fixture that exercises it FAILS rather than letting the arm rot. That
  guard is the one that paid off in §13.

**Positive controls, because a differential that never fires proves nothing.**
Three, each pinning a way the detector could be silently dead: a candidate that
is obtainable is never walled; granting every non-root catalogue item crosses 4
roots (so the pricer does respond to grants); and the drop grant crosses exactly
the nine above and no others.

## 4. What this does NOT do

**Production behaviour is unchanged.** No `Decision` moves, no route is added,
no price changes. Those nine candidates still price at infinity and the
promotion walk still skips them silently. The census makes the wall visible and
gate-enforced; acting on it is a separate change.

**And the evidence for that follow-up is now concrete,** which is the point of
building this first: the arm to price is `CLOSES`, it has nine witnesses, and
every one of them is a ONE-STEP chain — so a `_gated_drop_option` mirroring
`_gated_craft_option` would need one level of chain pricing, not an unbounded
recursion. The circularity the 2026-08-09 audit feared is not what the corpus
contains. That remains unbuilt here, deliberately.

## 5. Files

* `src/artifactsmmo_cli/audit/drop_wall_census.py` — new.
* `tests/test_audit/test_drop_wall_census.py` — new.
* `docs/superpowers/specs/CURRENCY_WALL_MATRIX.md` sibling row, or its own
  matrix if the shape does not fit.
* No production file changes.

Audit modules carry no mutation anchors by convention — they are verification
tooling, not production logic — and are held to 100% statement coverage.

---

## 6. `[SHIPPED 2026-08-28]` What the census measured

`src/artifactsmmo_cli/audit/drop_wall_census.py`, wired into `formal/gate.sh` and
`census-gate.yml` beside its currency sibling.

```
438 candidate cells over 44 scenarios; obtainable 77; not_drop_walled 350;
walled 9 (9 on ALTERNATIVES); closes 9; out_of_reach 0;
drop_wall_unattributed 0; root_unresolved 2
argmax blindness: 0 of 9 walls sit on a RESOLVED root.
```

The design's §2 prediction held exactly: **every** wall in the committed set sits
on an alternative, so the argmax-only reading every other census takes sees zero
of them. That line is computed from the grid by `argmax_blindness`, not
transcribed, so it cannot rot into a claim about a fixture set that has moved.

**Departure from §3: `ROOT_UNRESOLVED` is not a residual.** Two of the 44
scenarios resolve no root. Failing the gate on that would make this census the
enforcer of a property it does not measure — the currency census takes the same
reading of the same class. The class still exists so those scenarios contribute a
VISIBLE row rather than silently contributing zero cells, and the blind-sweep
case is covered by `MIN_CELLS` and `witness_residual` instead.

**The `OUT_OF_REACH` arm has no witness and the suite asserts that zero**, so the
first fixture to exercise it fails rather than letting the arm rot — the guard
that paid off for the gold row within two days of being written. The arm is kept
honest meanwhile by a positive control rather than by the grid.

**Production behaviour is unchanged, as designed.** Those nine candidates still
price at infinity and the promotion walk still skips them.
