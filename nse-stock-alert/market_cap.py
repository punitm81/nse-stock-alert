"""Market cap and live-quote lookups via Yahoo Finance, used by main.py's mover
filtering, intraday.py's live checks, and build_universe.py's weekly scan.

All calls go through _throttle() to cap the request rate to Yahoo Finance --
important once intraday.py started checking the full ~600-stock universe
(rather than just the top 150) every 15 minutes, since Yahoo has no official
rate limit for this unofficial endpoint but does return 429s under bursts.
"""

import logging
import threading
import time

import yfinance as yf

logger = logging.getLogger(__name__)

CRORE = 1e7

# Conservative pace: comfortably clears a ~600-symbol scan (~200s) within a
# 15-minute window without bursting Yahoo Finance.
_MIN_REQUEST_INTERVAL_SECONDS = 1 / 3  # max ~3 requests/second
_last_request_at = 0.0
_throttle_lock = threading.Lock()


def _throttle():
    global _last_request_at
    with _throttle_lock:
        now = time.monotonic()
        wait = _last_request_at + _MIN_REQUEST_INTERVAL_SECONDS - now
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def get_market_cap_cr(symbol: str):
    """Returns market cap in INR crore for an NSE symbol, or None if unavailable."""
    ticker = f"{symbol}.NS"
    market_cap = None

    try:
        _throttle()
        # yfinance's FastInfo.get() only recognizes camelCase keys (e.g. "marketCap"),
        # not snake_case ("market_cap") -- the latter silently returns the default
        # with no error, before any network call even happens.
        market_cap = yf.Ticker(ticker).fast_info.get("marketCap")
    except Exception:
        market_cap = None

    if not market_cap:
        try:
            _throttle()
            market_cap = yf.Ticker(ticker).info.get("marketCap")
        except Exception as exc:
            logger.warning("Could not fetch market cap for %s: %s", ticker, exc)
            return None

    if not market_cap:
        return None
    return market_cap / CRORE


def get_live_quote(symbol: str):
    """Returns (last_price, previous_close) for an NSE symbol via Yahoo Finance, or None if unavailable."""
    ticker = f"{symbol}.NS"
    try:
        _throttle()
        # See get_market_cap_cr(): FastInfo.get() requires camelCase keys.
        info = yf.Ticker(ticker).fast_info
        last_price = info.get("lastPrice")
        prev_close = info.get("previousClose")
    except Exception as exc:
        logger.warning("Could not fetch live quote for %s: %s", ticker, exc)
        return None

    if not last_price or not prev_close:
        return None
    return last_price, prev_close
