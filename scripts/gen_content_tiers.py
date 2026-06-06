"""Generate docs/behavioral_completeness/content_tiers.md from live game data.
Run: uv run python scripts/gen_content_tiers.py  (needs TOKEN / API access)."""

from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.content_tiers import derive_content_tiers, render_markdown
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def main() -> None:
    ClientManager().initialize(Config.from_token_file(None))
    gd = GameData.load(ClientManager().client)
    items = {c: s.level for c, s in gd._item_stats.items()}
    monsters = dict(gd._monster_level)
    resources = {c: lvl for c, (_skill, lvl) in gd._resource_skill.items()}
    tiers = derive_content_tiers(items, monsters, resources, band=10)
    out = Path("docs/behavioral_completeness/content_tiers.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(tiers))
    print(f"wrote {out} ({len(tiers)} tiers)")


if __name__ == "__main__":
    main()
