# Roster gap — sprite binning (live API, 2026-07-01)

Totals: monsters 58 total / 30 curated / **28 missing**. npcs 13 / 6 / **7 missing**.

Binning rule: each missing code → a **base** (reuse an existing curated sprite's
shape via `recolor`, or a NEW bespoke 8x8) + a palette intent. Only two NEW base
shapes are needed (`bat`, `dragon`); everything else recolors a curated shape,
keeping the tileset visually coherent. Family label is informational.

## Missing monsters (28)

Format: `code  | family | base (curated shape to recolor, or NEW) | palette intent`

### Recolors of a curated monster shape (26)

- [ ] `corrupted_ogre`        | giant    | base=`ogre`            | sickly green→violet corruption tint
- [ ] `corrupted_owlbear`     | beast    | base=`owlbear`         | corruption violet over the owlbear browns
- [ ] `full_moon_vampire`     | undead   | base=`vampire`         | moon-pale skin, silver accents
- [ ] `lich`                  | undead   | base=`skeleton`        | robed: bone + dark-violet robe overpaint
- [ ] `demon`                 | humanoid | base=`imp`             | deeper blood-red, larger horns via mark cells
- [ ] `goblin_guard`          | humanoid | base=`goblin`          | steel-armored (STEEL over tunic)
- [ ] `goblin_priestess`      | humanoid | base=`goblin`          | robe (BREW/violet), pale accent
- [ ] `cultist_emperor`       | humanoid | base=`cultist_acolyte` | imperial gold + crimson robe
- [ ] `cultist_alchemist`     | humanoid | base=`cultist_acolyte` | green potion palette
- [ ] `sea_marauder`          | humanoid | base=`highwayman`      | teal/steel pirate palette
- [ ] `sandwhisper_empress`   | humanoid | base=`sandwarden`      | regal sand-gold + violet
- [ ] `efreet_sultan`         | giant    | base=`cyclops`         | fire palette (EMBER/AMBER/GOLD)
- [ ] `sonnengott`            | giant    | base=`cyclops`         | radiant gold ("sun god")
- [ ] `rat`                   | beast    | base=`wolf`            | grey, small (mark trim)
- [ ] `fennec`               | beast    | base=`wolf`            | sandy KHAKI (desert fox)
- [ ] `grimlet`               | beast    | base=`wolf`            | dark SLATE, ember eyes
- [ ] `bandit_lizard`         | beast    | base=`wolf`            | LEAF green reptile
- [ ] `duskworm`              | serpent  | base=`sand_snake`      | dusk violet/SLATE
- [ ] `dusk_beetle`           | insect   | base=`spider`          | dark carapace (INK/SLATE)
- [ ] `solar_desert_scorpion` | insect   | base=`desert_scorpion` | solar gold/ember
- [ ] `dryad`                 | plant    | base=`cursed_tree`     | living LEAF green + SKIN face
- [ ] `rosenblood`            | plant    | base=`cursed_tree`     | rose BLOOD red + LEAF
- [ ] `flameche`              | elemental| base=`green_slime`     | fire palette (EMBER/AMBER) — flame blob
- [ ] `pixie`                 | flyer    | base=NEW `bat`         | PINK body, pale wings (small winged)
- [ ] `echoless_bat`          | flyer    | base=NEW `bat`         | near-black SLATE, silent variant
- [ ] `red_dragon`            | dragon   | base=NEW `dragon`      | BLOOD red, full size
- [ ] `baby_red_dragon`       | dragon   | base=NEW `dragon`      | red, lighter/juvenile accent

### New bespoke base shapes (author once, reused above) (2)

- [ ] NEW base `_BAT_BASE`    | flyer  | bespoke 8x8 (wings spread, small body) — used by `bat`, `echoless_bat`, `pixie`
- [ ] NEW base `_DRAGON_BASE` | dragon | bespoke 8x8 (winged serpent/quadruped) — used by `red_dragon`, `baby_red_dragon`
- [ ] `bat`                   | flyer  | base=NEW `bat` | dark BARK/SLATE (the plain bat)

## Missing NPCs (7) — all merchant/trader humanoids

Reuse a curated NPC/humanoid shape via `recolor`; vary palette by trade.

- [ ] `beastmaster`        | trader   | base=`archaeologist` (or `tailor`) | earthy BARK/LEAF
- [ ] `sorceress`          | trader   | base=`cultist_wizard`              | violet/BREW robe, feminine accent
- [ ] `fish_merchant`      | merchant | base=`tailor`                      | WATER blue
- [ ] `gemstone_merchant`  | merchant | base=`tailor`                      | GOLD + gem accent
- [ ] `herbal_merchant`    | merchant | base=`tailor`                      | LEAF green
- [ ] `nomadic_merchant`   | merchant | base=`tailor`                      | KHAKI/AMBER desert robe
- [ ] `timber_merchant`    | merchant | base=`tailor`                      | BARK brown

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
