"""Shared hex art-color palette for the outline-only sprite tileset.

Single source of art colors. Sprites in sprites.py reference these constants
as palette values so the tileset stays cohesive. Distinct from glyphs.py,
which holds ANSI terrain/fallback colors.
"""

INK = "#1c1c1c"        # universal silhouette outline + default eye
LEAF = "#4e9a06"       # foliage / slime green
STONE = "#babdb6"      # light stone (walls)
SLATE = "#6b6f6a"      # dark rock
STEEL = "#888a85"      # metal
GOLD = "#fce94f"       # treasure / gold roof
AMBER = "#fcaf3e"      # beak / orange / fish
COPPER = "#c17d11"     # ore veins
BARK = "#8f5902"       # wood / hide brown
DOORWOOD = "#5c3a0a"   # dark door wood
KHAKI = "#8a7f3d"      # explorer cloth
BLOOD = "#cc0000"      # comb / red
BONE = "#eeeeec"       # white / parchment / feathers
SKIN = "#fce0b0"       # flesh
TUNIC = "#3465a4"      # blue cloth
WATER = "#2a7fb8"      # water surface
BREW = "#75507b"       # alchemy / cloth purple
PINK = "#f5a9b8"       # snouts / noses (cow, pig)
