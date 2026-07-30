"""Market cap lookups, used only to filter the (small) list of daily movers."""

import logging

import yfinance as yf

logger = logging.getLogger(__name__)

CRORE = 1e7


def get_market_cap_cr(symbol: str):
    """Returns market cap in INR crore for an NSE symbol, or None if unavailable."""
    ticker = f"{symbol}.NS"
    market_cap = None

    try:
        market_cap = yf.Ticker(ticker).fast_info.get("market_cap")
    except Exception:
        market_cap = None

    if not market_cap:
        try:
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
        info = yf.Ticker(ticker).fast_info
        last_price = info.get("last_price")
        prev_close = info.get("previous_close")
    except Exception as exc:
        logger.warning("Could not fetch live quote for %s: %s", ticker, exc)
        return None

    if not last_price or not prev_close:
        return None
    return last_price, prev_close
