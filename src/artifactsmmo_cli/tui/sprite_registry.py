"""Resolves entity codes to sprites: curated lookup, else a tinted fallback.

The fallback is a category-colored blob with a deterministic 2-tone marking
derived from a stable checksum of the code (sum of UTF-8 bytes — NOT Python's
salted hash(), which varies across processes). Mirrors glyphs.py's first-letter
fallback in spirit. Curated misses are expected behavior, not errors.
"""

from artifactsmmo_cli.tui.sprites import (
    CATEGORY_FALLBACK_COLOR,
    CURATED_BY_CATEGORY,
    FALLBACK_SILHOUETTE,
    MARK_COLOR,
    MARK_KEY,
    MARK_POSITIONS,
    PLAYER_SPRITE,
    Sprite,
    SpriteCategory,
)


class SpriteRegistry:
    """Maps (code, category) to a Sprite; caches procedural fallbacks."""

    def __init__(self) -> None:
        self._fallback_cache: dict[tuple[SpriteCategory, str], Sprite] = {}

    def sprite_for(self, code: str, category: SpriteCategory) -> Sprite:
        if category is SpriteCategory.PLAYER:
            return PLAYER_SPRITE
        curated = CURATED_BY_CATEGORY[category].get(code)
        if curated is not None:
            return curated
        return self._fallback(code, category)

    def _fallback(self, code: str, category: SpriteCategory) -> Sprite:
        key = (category, code)
        cached = self._fallback_cache.get(key)
        if cached is not None:
            return cached
        sprite = self._build_fallback(code, category)
        self._fallback_cache[key] = sprite
        return sprite

    @staticmethod
    def _build_fallback(code: str, category: SpriteCategory) -> Sprite:
        checksum = sum(code.encode("utf-8"))
        grid = [list(row) for row in FALLBACK_SILHOUETTE]
        for i, (r, c) in enumerate(MARK_POSITIONS):
            if (checksum >> i) & 1:
                grid[r][c] = MARK_KEY
        rows = tuple("".join(row) for row in grid)
        palette = {"#": CATEGORY_FALLBACK_COLOR[category], MARK_KEY: MARK_COLOR}
        return Sprite(rows=rows, palette=palette)
