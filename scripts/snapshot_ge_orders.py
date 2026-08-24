"""Capture the LIVE Grand-Exchange order book into the committed scenario bundle.

The disk cache deliberately excludes the order book — `GameDataCache.write` only
ever sees the ten static `_fetch_*` pages, and `GameData.load` fetches orders
afterwards against the live client, because the cache's whole TTL contract is
that what it stores is static and an order book is not. So the scenario fixture
could not express a market at all: twelve call sites across ten production
modules read `ge_best_sell_order`/`ge_best_buy_order` and every one of them was
dead offline. A standing sell order is exactly what stalled a character for
hours (fixed at `dd946539`); reproducing it needed an order injected by hand.

This script closes that, WITHOUT touching the cache writer:

    uv run python scripts/snapshot_ge_orders.py

It pages both sides of the live book and merges them into
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json` under a new `ge_orders`
key, leaving every catalogue key exactly as captured. Two deliberate choices:

* **Orders are stored VERBATIM** — every open order the API returned, several per
  item, as `GEOrderSchema.to_dict()` round-trips them. Not a pre-reduced
  best-per-item index: the reduction (`ai/ge_order_index.index_best_ge_orders`)
  is production code, and a fixture that baked in its answer could not exercise
  it. Nothing here filters, reprices or invents an order.
* **The book carries its OWN `fetched_at`**, separate from the bundle's. The
  catalogue and the market were captured 49 days apart; one timestamp would have
  claimed otherwise. The catalogue is not re-captured here — that is a bundle
  refresh, and it moves every census.

The committed book is a fixed WITNESS, not live data: "this is a market that
existed, and here is how the planner behaves in it" — the same epistemic status
the rest of the bundle already has.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_api_client.models.ge_order_type import GEOrderType
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

BUNDLE = (Path(__file__).resolve().parents[1] / "tests" / "test_ai" / "scenarios"
          / "fixtures" / "gamedata_bundle.json")


def main() -> None:
    cfg = Config.from_token_file()
    mgr = ClientManager()
    mgr.initialize(cfg)
    rows = []
    for side in (GEOrderType.BUY, GEOrderType.SELL):
        rows.extend(o.to_dict() for o in GameData._page_ge_orders(mgr.client, side))
    bundle = json.loads(BUNDLE.read_text())
    bundle["ge_orders"] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "orders": rows,
    }
    BUNDLE.write_text(json.dumps(bundle))
    codes = {r["code"] for r in rows}
    print(f"captured {len(rows)} open orders over {len(codes)} item codes -> {BUNDLE}")


if __name__ == "__main__":
    main()
