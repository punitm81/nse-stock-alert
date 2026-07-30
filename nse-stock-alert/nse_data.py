"""Fetches NSE's daily full bhavcopy (all-securities OHLC report) and finds big movers."""

import datetime as dt
import io
import logging
import zipfile

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

NSE_HOME_URL = "https://www.nseindia.com/"
# Current, date-stamped daily bhavcopy that NSE actively maintains (UDiFF format).
UDIFF_BHAVCOPY_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
# Older "current day" file, kept only as a fallback if the UDiFF file isn't reachable.
LEGACY_BHAVCOPY_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full.csv"

UDIFF_COLUMN_MAP = {
    "TckrSymb": "SYMBOL",
    "SctySrs": "SERIES",
    "ClsPric": "CLOSE_PRICE",
    "PrvsClsgPric": "PREV_CLOSE",
    "TradDt": "DATE1",
}


def _nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    # NSE requires a warm-up hit on the homepage to hand out cookies before
    # it will serve the archive endpoints.
    session.get(NSE_HOME_URL, timeout=15)
    return session


def _read_udiff_zip(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        csv_name = next(name for name in zf.namelist() if name.lower().endswith(".csv"))
        with zf.open(csv_name) as fh:
            df = pd.read_csv(fh)
    df.columns = [c.strip() for c in df.columns]
    return df.rename(columns=UDIFF_COLUMN_MAP)


def _read_legacy_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    return df


def fetch_bhavcopy(for_date: dt.date | None = None) -> pd.DataFrame:
    """Downloads the official NSE daily bhavcopy for `for_date` (default: today)."""
    target_date = for_date or dt.date.today()
    session = _nse_session()

    udiff_url = UDIFF_BHAVCOPY_URL.format(ymd=target_date.strftime("%Y%m%d"))
    response = session.get(udiff_url, timeout=30)
    if response.ok and response.content[:2] == b"PK":
        logger.info("Fetched UDiFF bhavcopy for %s", target_date)
        df = _read_udiff_zip(response.content)
    else:
        logger.warning(
            "UDiFF bhavcopy unavailable for %s (HTTP %s); falling back to legacy endpoint",
            target_date,
            response.status_code,
        )
        response = session.get(LEGACY_BHAVCOPY_URL, timeout=30)
        response.raise_for_status()
        df = _read_legacy_csv(response.text)

    for col in ("SYMBOL", "SERIES"):
        df[col] = df[col].astype(str).str.strip()

    _verify_freshness(df, target_date)
    return df


def _verify_freshness(df: pd.DataFrame, expected_date: dt.date) -> None:
    """Refuses to proceed on stale/frozen data instead of silently alerting on wrong prices."""
    if "DATE1" not in df.columns:
        logger.warning("Bhavcopy has no date column; cannot verify freshness.")
        return

    dates = pd.to_datetime(df["DATE1"], errors="coerce").dt.date.dropna()
    if dates.empty:
        logger.warning("Could not parse any dates from bhavcopy; cannot verify freshness.")
        return

    data_date = dates.mode().iloc[0]
    if data_date != expected_date:
        raise RuntimeError(
            f"Bhavcopy data is dated {data_date}, not the expected {expected_date}. "
            "NSE likely hasn't published today's file yet (or the source has changed "
            "format) -- refusing to send a possibly-stale alert."
        )


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
