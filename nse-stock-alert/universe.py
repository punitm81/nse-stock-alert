"""Loads the weekly-refreshed static list of NSE symbols with market cap above
config.MARKET_CAP_THRESHOLD_CR (see build_universe.py). Both the intraday and
end-of-day scripts filter against this instead of calling Yahoo Finance for
market cap on every run.
"""

import datetime as dt
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

UNIVERSE_PATH = Path(__file__).parent / "data" / "universe.json"
STALE_AFTER_DAYS = 10


def load_universe() -> dict:
    """Returns {"NMDC": 25000.0, ...} (symbol -> market cap in Cr)."""
    if not UNIVERSE_PATH.exists():
        raise RuntimeError(
            f"{UNIVERSE_PATH} doesn't exist yet. Run the 'NSE Universe Refresh' "
            "workflow manually once (Actions tab) before the alert scripts can run."
        )

    payload = json.loads(UNIVERSE_PATH.read_text())
    generated_at = dt.date.fromisoformat(payload["generated_at"])
    age_days = (dt.date.today() - generated_at).days
    if age_days > STALE_AFTER_DAYS:
        logger.warning(
            "Universe list is %d days old (generated %s) -- the weekly refresh "
            "workflow may not be running; market caps could be out of date.",
            age_days,
            generated_at,
        )

    return payload["companies"]


def top_symbols_by_market_cap(companies: dict, n: int) -> list:
    return [symbol for symbol, _ in sorted(companies.items(), key=lambda kv: kv[1], reverse=True)[:n]]
