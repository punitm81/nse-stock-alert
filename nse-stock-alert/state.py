"""Tracks which symbols have already triggered an alert today, so the intraday
checker doesn't re-alert on the same stock every 5 minutes for the rest of the day.
"""

import datetime as dt
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent / "data" / "alerted_today.json"


def load_alerted_today() -> set:
    if not STATE_PATH.exists():
        return set()
    try:
        payload = json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s: %s", STATE_PATH, exc)
        return set()

    if payload.get("date") != dt.date.today().isoformat():
        return set()
    return set(payload.get("symbols", []))


def mark_alerted(symbols) -> None:
    if not symbols:
        return
    already = load_alerted_today()
    already.update(symbols)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"date": dt.date.today().isoformat(), "symbols": sorted(already)}, indent=2)
    )
    logger.info("Marked %d symbol(s) as alerted today", len(symbols))
