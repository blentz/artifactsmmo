"""Map (x,y) tile content → glyph + color for the TUI map pane.

Each content category has its own color so glyphs that share a letter across
categories (tailor 'T' cyan vs woodcutting-resource 'T' green) stay distinct.
NPCs are uppercase letters, monsters lowercase, structures box-drawing glyphs,
doors '+'. Unknown NPC/monster codes fall back to their first letter.
"""

PLAYER_GLYPH = "@"
PLAYER_COLOR = "bright_yellow"

NPC_COLOR = "cyan"
MONSTER_COLOR = "red"
STRUCTURE_COLOR = "white"
DOOR_COLOR = "magenta"

DOOR_GLYPH = "+"
GENERIC_STRUCTURE_GLYPH = "▢"

NPC_GLYPHS: dict[str, str] = {
    "archaeologist": "A",
    "cultist_wizard": "C",
    "rune_vendor": "R",
    "sandwhisper_trader": "S",
    "tailor": "T",
    "tasks_trader": "K",
}

MONSTER_GLYPHS: dict[str, str] = {
    "blue_slime": "s", "green_slime": "s", "red_slime": "s",
    "yellow_slime": "s", "king_slime": "s",
    "chicken": "c", "cow": "o", "cyclops": "y", "cultist_acolyte": "u",
    "cursed_tree": "t", "death_knight": "d", "desert_scorpion": "x",
    "flying_snake": "f", "goblin": "g", "goblin_wolfrider": "g",
    "hellhound": "h", "highwayman": "j", "imp": "i", "mushmush": "m",
    "ogre": "r", "orc": "q", "owlbear": "b", "pig": "p", "sand_snake": "n",
    "sandwarden": "l", "sheep": "e", "skeleton": "k", "spider": "a",
    "vampire": "v", "wolf": "w",
}

STRUCTURE_GLYPHS: dict[str, str] = {
    "bank": "╣",
    "grand_exchange": "╠",
    "workshop": "╬",
    "tasks_master": "╤",
}

RESOURCE_GLYPHS: dict[str, tuple[str, str]] = {
    "resource_woodcutting": ("T", "green"),
    "resource_mining": ("*", "yellow"),
    "resource_fishing": ("~", "blue"),
    "resource_alchemy": ("%", "magenta"),
}

UNMAPPED_GLYPH = " "
WALKABLE_GLYPH = "·"
WALKABLE_COLOR = "grey50"


def npc_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for an NPC code: curated, else uppercased first letter."""
    return (NPC_GLYPHS.get(code) or code[:1].upper(), NPC_COLOR)


def monster_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for a monster code: curated, else lowercased first letter."""
    return (MONSTER_GLYPHS.get(code) or code[:1].lower(), MONSTER_COLOR)


def structure_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for a structure code: curated, else a generic box."""
    return (STRUCTURE_GLYPHS.get(code, GENERIC_STRUCTURE_GLYPH), STRUCTURE_COLOR)
