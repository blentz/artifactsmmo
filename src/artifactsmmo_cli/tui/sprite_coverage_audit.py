"""Warn-level audit: report entity codes present in-game but with no curated
sprite. Non-fatal — the procedural fallback still renders uncurated tiles.
Mirrors GameData._audit_effect_coverage in spirit (print, never raise)."""

from collections.abc import Iterable

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, NPC_SPRITES


class SpriteCoverageAudit:
    """Compares live monster/NPC codes against curated sprite dict keys."""

    def run(self, game_data: GameData) -> None:
        self._report("monsters", game_data.all_monster_locations.keys(), MONSTER_SPRITES.keys())
        self._report("npcs", game_data.npc_locations.keys(), NPC_SPRITES.keys())

    @staticmethod
    def _report(label: str, live_codes: Iterable[str], curated_codes: Iterable[str]) -> None:
        uncurated = sorted(set(live_codes) - set(curated_codes))
        if uncurated:
            print(f"[sprites] uncurated {label}: {uncurated}")
