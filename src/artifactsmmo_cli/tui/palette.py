"""Shared hex art-color palette for the sprite tileset.

Single source of art colors. Each material is a `Ramp` of four shades lit from
the top-left: `outline` (the sprite's tinted edge), `dark` (lower-right shadow),
`mid` (the base fill) and `light` (upper-left highlight). The flat constants
below are each ramp's `mid`; they double as UI colors (roster tunic colors) and
stay importable on their own. Distinct from glyphs.py, which holds ANSI
terrain/fallback colors.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Ramp:
    """One material's shades, darkest to lightest."""

    outline: str
    dark: str
    mid: str
    light: str


INK = "#1c1c1c"        # eyes / pupils (outlines are ramp-tinted, not INK)
SHINE = "#f4f8ee"      # specular glint shared by every glossy material
GLOW = "#ff3b2f"       # glowing monster eyes

SKIN_RAMP = Ramp("#5a3020", "#c98a5e", "#f0c090", "#ffe2bc")
HAIR_RAMP = Ramp("#3a200c", "#6a3c1a", "#9a6232", "#c08850")
TUNIC_RAMP = Ramp("#14284a", "#24477e", "#3a6bb4", "#6a9be0")
BLOOD_RAMP = Ramp("#3a0808", "#8a1414", "#cc2a22", "#ff6a50")
LEAF_RAMP = Ramp("#16300e", "#2e5e18", "#4a8a26", "#78b840")
SLIME_RAMP = Ramp("#1a3a10", "#3a7a1e", "#5cae2e", "#8ad64e")
BREW_RAMP = Ramp("#2a1430", "#54305c", "#7a4e86", "#a87cb4")
AMBER_RAMP = Ramp("#4a2408", "#b06010", "#f0952e", "#ffc070")
GOLD_RAMP = Ramp("#4a3a08", "#b89418", "#f0d040", "#fff3a0")
BONE_RAMP = Ramp("#3a3a34", "#9c9a8c", "#d6d4c4", "#f6f5ec")
STONE_RAMP = Ramp("#3a3c3a", "#8a8d88", "#babdb6", "#e2e4de")
SLATE_RAMP = Ramp("#1e201e", "#45484a", "#6b6f6a", "#93968f")
STEEL_RAMP = Ramp("#24262a", "#5a5e66", "#888a85", "#c8ccd4")
BARK_RAMP = Ramp("#2a1808", "#5a3410", "#8a5a24", "#b0804a")
DOORWOOD_RAMP = Ramp("#1e1206", "#3e2608", "#5c3a0a", "#7e5420")
LEATHER_RAMP = Ramp("#2a1a0c", "#4a3018", "#7a5228", "#a07440")
KHAKI_RAMP = Ramp("#2e2a12", "#5e5628", "#8a7f3d", "#b4a862")
PINK_RAMP = Ramp("#5a2a34", "#c87888", "#f5a9b8", "#ffd4dc")
GOBLIN_SKIN_RAMP = Ramp("#203414", "#4f7a28", "#78a83e", "#a8d46a")
ORC_SKIN_RAMP = Ramp("#1e2e12", "#3e5a24", "#5f8436", "#8ab35a")
OGRE_SKIN_RAMP = Ramp("#26301e", "#5e7254", "#8aa37b", "#b4c8a6")
EMBER_RAMP = Ramp("#4a0a04", "#a82010", "#ef4429", "#ffa060")
WATER_RAMP = Ramp("#0c2a40", "#1c5a86", "#2a7fb8", "#6ab4e6")
COPPER_RAMP = Ramp("#3a2006", "#8a5410", "#c17d11", "#e8a848")

SKIN = SKIN_RAMP.mid            # flesh
HAIR = HAIR_RAMP.mid            # brown hair
TUNIC = TUNIC_RAMP.mid          # blue cloth
BLOOD = BLOOD_RAMP.mid          # red
LEAF = LEAF_RAMP.mid            # foliage green
SLIME = SLIME_RAMP.mid          # slime green
BREW = BREW_RAMP.mid            # alchemy / cloth purple
AMBER = AMBER_RAMP.mid          # beak / orange / fish
GOLD = GOLD_RAMP.mid            # treasure / gold roof
BONE = BONE_RAMP.mid            # white / parchment / feathers
STONE = STONE_RAMP.mid          # light stone (walls)
SLATE = SLATE_RAMP.mid          # dark rock
STEEL = STEEL_RAMP.mid          # metal
BARK = BARK_RAMP.mid            # wood / hide brown
DOORWOOD = DOORWOOD_RAMP.mid    # dark door wood
LEATHER = LEATHER_RAMP.mid      # belts, boots, jerkins
KHAKI = KHAKI_RAMP.mid          # explorer cloth
PINK = PINK_RAMP.mid            # snouts / noses (cow, pig)
GOBLIN_SKIN = GOBLIN_SKIN_RAMP.mid
ORC_SKIN = ORC_SKIN_RAMP.mid
OGRE_SKIN = OGRE_SKIN_RAMP.mid
EMBER = EMBER_RAMP.mid          # hellhound fire
WATER = WATER_RAMP.mid          # water surface
COPPER = COPPER_RAMP.mid        # ore veins
