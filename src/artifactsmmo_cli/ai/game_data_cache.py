"""Disk cache for GameData's static API pages: configurable-TTL, versioned,
atomic. Holds NO game logic — only persistence + freshness."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CACHE_VERSION = 4  # v4: all-layer map fetch + access/transition facts (P5b data)
"""Bump when the raw-page schema changes; an old version reads as a miss."""

RawPages = dict[str, Any]
"""A page map: name -> JSON-shaped payload (a list of serialized schemas, a single
serialized schema, or None for an absent bank). Values are genuinely heterogeneous
untyped JSON (json.loads / .to_dict() output), hence Any."""


class GameDataCache:
    """Read/write the raw static API pages under ~/.cache/artifactsmmo, keyed by
    API host (static data is server-wide). All-or-nothing: a missing, corrupt,
    stale, or version-mismatched cache reads as None so the caller re-fetches."""

    def __init__(self, api_base_url: str, cache_dir: Path | None = None) -> None:
        host = urlparse(api_base_url).netloc or "default"
        base = cache_dir if cache_dir is not None else Path.home() / ".cache" / "artifactsmmo"
        self.path = base / f"gamedata-{host}.json"

    def read(self, ttl_minutes: int, now: datetime | None = None) -> RawPages | None:
        now = now or datetime.now(tz=timezone.utc)
        try:
            raw = json.loads(self.path.read_text())
            if raw.get("version") != CACHE_VERSION:
                return None
            fetched_at = datetime.fromisoformat(raw["fetched_at"])
            if now - fetched_at >= timedelta(minutes=ttl_minutes):
                return None
            return {k: v for k, v in raw.items() if k not in ("version", "fetched_at")}
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            return None

    def write(self, raw_pages: RawPages, now: datetime | None = None) -> None:
        now = now or datetime.now(tz=timezone.utc)
        payload = {"version": CACHE_VERSION, "fetched_at": now.isoformat(), **raw_pages}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self.path)
