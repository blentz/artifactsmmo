# Roster gap — sprite binning (live API, 2026-07-01)

Totals: monsters 58 total / 30 curated / **28 missing**. npcs 13 / 6 / **7 missing**.

Binning rule: each missing code → a **base** (reuse an existing curated sprite's
shape via `recolor`, or a NEW bespoke 8x8) + a palette intent. Only two NEW base
shapes are needed (`bat`, `dragon`); everything else recolors a curated shape,
keeping the tileset visually coherent. Family label is informational.

## Missing monsters (28)

Format: `code  | family | base (curated shape to recolor, or NEW) | palette intent`

### Recolors of a curated monster shape (26)

- [x] `corrupted_ogre`        | giant    | base=`ogre`            | sickly green→violet corruption tint
- [x] `corrupted_owlbear`     | beast    | base=`owlbear`         | corruption violet over the owlbear browns
- [x] `full_moon_vampire`     | undead   | base=`vampire`         | moon-pale skin, silver accents
- [x] `lich`                  | undead   | base=`skeleton`        | robed: bone + dark-violet robe overpaint
- [x] `demon`                 | humanoid | base=`imp`             | deeper blood-red, larger horns via mark cells
- [x] `goblin_guard`          | humanoid | base=`goblin`          | steel-armored (STEEL over tunic)
- [x] `goblin_priestess`      | humanoid | base=`goblin`          | robe (BREW/violet), pale accent
- [x] `cultist_emperor`       | humanoid | base=`cultist_acolyte` | imperial gold + crimson robe
- [x] `cultist_alchemist`     | humanoid | base=`cultist_acolyte` | green potion palette
- [x] `sea_marauder`          | humanoid | base=`highwayman`      | teal/steel pirate palette
- [x] `sandwhisper_empress`   | humanoid | base=`sandwarden`      | regal sand-gold + violet
- [x] `efreet_sultan`         | giant    | base=`cyclops`         | fire palette (EMBER/AMBER/GOLD)
- [x] `sonnengott`            | giant    | base=`cyclops`         | radiant gold ("sun god")
- [x] `rat`                   | beast    | base=`wolf`            | grey, small (mark trim)
- [x] `fennec`               | beast    | base=`wolf`            | sandy KHAKI (desert fox)
- [x] `grimlet`               | beast    | base=`wolf`            | dark SLATE, ember eyes
- [x] `bandit_lizard`         | beast    | base=`wolf`            | LEAF green reptile
- [x] `duskworm`              | serpent  | base=`sand_snake`      | dusk violet/SLATE
- [x] `dusk_beetle`           | insect   | base=`spider`          | dark carapace (INK/SLATE)
- [x] `solar_desert_scorpion` | insect   | base=`desert_scorpion` | solar gold/ember
- [x] `dryad`                 | plant    | base=`cursed_tree`     | living LEAF green + SKIN face
- [x] `rosenblood`            | plant    | base=`cursed_tree`     | rose BLOOD red + LEAF
- [x] `flameche`              | elemental| base=`green_slime`     | fire palette (EMBER/AMBER) — flame blob
- [x] `pixie`                 | flyer    | base=NEW `bat`         | PINK body, pale wings (small winged)
- [x] `echoless_bat`          | flyer    | base=NEW `bat`         | near-black SLATE, silent variant
- [x] `red_dragon`            | dragon   | base=NEW `dragon`      | BLOOD red, full size
- [x] `baby_red_dragon`       | dragon   | base=NEW `dragon`      | red, lighter/juvenile accent

### New bespoke base shapes (author once, reused above) (2)

- [x] NEW base `_BAT_BASE`    | flyer  | bespoke 8x8 (wings spread, small body) — used by `bat`, `echoless_bat`, `pixie`
- [x] NEW base `_DRAGON_BASE` | dragon | bespoke 8x8 (winged serpent/quadruped) — used by `red_dragon`, `baby_red_dragon`
- [x] `bat`                   | flyer  | base=NEW `bat` | dark BARK/SLATE (the plain bat)

## Missing NPCs (7) — all merchant/trader humanoids

Reuse a curated NPC/humanoid shape via `recolor`; vary palette by trade.

- [x] `beastmaster`        | trader   | base=`archaeologist` (or `tailor`) | earthy BARK/LEAF
- [x] `sorceress`          | trader   | base=`cultist_wizard`              | violet/BREW robe, feminine accent
- [x] `fish_merchant`      | merchant | base=`tailor`                      | WATER blue
- [x] `gemstone_merchant`  | merchant | base=`tailor`                      | GOLD + gem accent
- [x] `herbal_merchant`    | merchant | base=`tailor`                      | LEAF green
- [x] `nomadic_merchant`   | merchant | base=`tailor`                      | KHAKI/AMBER desert robe
- [x] `timber_merchant`    | merchant | base=`tailor`                      | BARK brown

## Notes for the implementer (Tasks 5-6)

- `recolor(base, palette)` (from Task 3) makes a same-shape variant. To recolor,
  read the named curated sprite in `sprites.py`, keep its `rows`, and supply a new
  palette dict mapping the SAME keys to new colors. Add any new color constant to
  `palette.py` and import it into `sprites.py`.
- Where a variant needs more than a recolor (e.g. `demon` bigger horns), overpaint
  a couple of mark cells on the base rows before building the Sprite (see the
  `_player_with_tool` pattern), then it is a bespoke entry rather than a `recolor`.
- Every new entry must pass `validate_sprite` (enforced by the data-driven tests
  in Tasks 5/6).
