"""Snapshot live game_data to JSON for the Lean GameDataFixture (Phase 24-fix).

Runs against the production ArtifactsMMO API using the local TOKEN file.
Dumps recipes, item_stats, monster stats, resource_skill mappings to a
JSON snapshot pinned by capture date.

The Lean fixture (Formal/Liveness/GameDataFixture.lean) is regenerated
from this snapshot. A differential test verifies the snapshot matches
the live API at fixture-check time (or skips if server unreachable).

Usage:
  uv run python formal/sim/snapshot_game_data.py [output_path]

Default output: formal/sim/game_data_snapshot.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent / "game_data_snapshot.json"
    )

    cfg = Config.from_token_file()
    mgr = ClientManager()
    mgr.initialize(cfg)
    gd = GameData.load(mgr.client)

    snapshot: dict[str, object] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": cfg.api_base_url,
        "monster_level": dict(gd._monster_level),
        "monster_hp": dict(gd._monster_hp),
        "monster_attack": {k: dict(v) for k, v in gd._monster_attack.items()},
        "monster_resistance": {k: dict(v) for k, v in gd._monster_resistance.items()},
        "monster_initiative": dict(gd._monster_initiative),
        "monster_critical_strike": dict(gd._monster_critical_strike),
        "crafting_recipes": {k: dict(v) for k, v in gd._crafting_recipes.items()},
        "resource_skill": {k: list(v) for k, v in gd._resource_skill.items()},
        "resource_drops": dict(gd._resource_drops),
        "item_stats": {
            code: {
                "level": stats.level,
                "type": stats.type_,
                "crafting_skill": stats.crafting_skill,
                "crafting_level": stats.crafting_level,
            }
            for code, stats in gd._item_stats.items()
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    print(
        f"Snapshot written to {output_path}: "
        f"{len(snapshot['monster_level'])} monsters, "
        f"{len(snapshot['item_stats'])} items, "
        f"{len(snapshot['crafting_recipes'])} recipes, "
        f"{len(snapshot['resource_skill'])} resources"
    )


if __name__ == "__main__":
    main()
