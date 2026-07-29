"""Fetches NSE's daily full bhavcopy (all-securities OHLC report) and finds big movers."""

import io
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

NSE_HOME_URL = "https://www.nseindia.com/"
BHAVCOPY_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full.csv"


def _nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    # NSE requires a warm-up hit on the homepage to hand out cookies before
    # it will serve the archive endpoints.
    session.get(NSE_HOME_URL, timeout=15)
    return session


def fetch_bhavcopy() -> pd.DataFrame:
    """Downloads today's full bhavcopy (close price for every listed security)."""
    session = _nse_session()
    response = session.get(BHAVCOPY_URL, timeout=30)
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))
    df.columns = [c.strip() for c in df.columns]
    for col in ("SYMBOL", "SERIES"):
        df[col] = df[col].astype(str).str.strip()
    return df


def find_pct_movers(df: pd.DataFrame, pct_threshold: float) -> pd.DataFrame:
    """Returns EQ-series rows whose close vs previous close moved >= pct_threshold, either direction."""
    eq = df[df["SERIES"] == "EQ"].copy()
    eq["PREV_CLOSE"] = pd.to_numeric(eq["PREV_CLOSE"], errors="coerce")
    eq["CLOSE_PRICE"] = pd.to_numeric(eq["CLOSE_PRICE"], errors="coerce")
    eq = eq.dropna(subset=["PREV_CLOSE", "CLOSE_PRICE"])
    eq = eq[eq["PREV_CLOSE"] > 0]

    eq["PCT_CHANGE"] = (eq["CLOSE_PRICE"] - eq["PREV_CLOSE"]) / eq["PREV_CLOSE"] * 100
    movers = eq[eq["PCT_CHANGE"].abs() >= pct_threshold]
    return movers.sort_values("PCT_CHANGE", key=lambda s: s.abs(), ascending=False)
