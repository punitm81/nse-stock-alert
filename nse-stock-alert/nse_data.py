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
# How many calendar days to step backwards looking for the most recent published
# bhavcopy, if today's isn't out yet (covers weekends plus a holiday or two).
MAX_LOOKBACK_DAYS = 7

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


def fetch_bhavcopy(for_date: dt.date | None = None) -> tuple[pd.DataFrame, dt.date]:
    """Downloads the official NSE daily bhavcopy for `for_date` (default: today).

    If that day's file isn't published yet, steps backwards to the most recent
    trading day that is available. Returns (dataframe, actual_data_date) so the
    caller can clearly label the alert when it isn't today's session.
    """
    target_date = for_date or dt.date.today()
    session = _nse_session()

    for offset in range(MAX_LOOKBACK_DAYS + 1):
        candidate = target_date - dt.timedelta(days=offset)
        udiff_url = UDIFF_BHAVCOPY_URL.format(ymd=candidate.strftime("%Y%m%d"))
        response = session.get(udiff_url, timeout=30)

        if not (response.ok and response.content[:2] == b"PK"):
            logger.info("No bhavcopy for %s (HTTP %s)", candidate, response.status_code)
            continue

        df = _read_udiff_zip(response.content)
        for col in ("SYMBOL", "SERIES"):
            df[col] = df[col].astype(str).str.strip()
        data_date = _extract_data_date(df) or candidate

        if offset == 0:
            logger.info("Fetched bhavcopy for %s (today)", data_date)
        else:
            logger.warning(
                "Today's (%s) bhavcopy isn't published yet; using the most recent "
                "available trading day's data instead: %s",
                target_date,
                data_date,
            )
        return df, data_date

    raise RuntimeError(
        f"Could not find any NSE bhavcopy in the {MAX_LOOKBACK_DAYS} days up to {target_date}. "
        "NSE may have changed its file format, or the source is unreachable."
    )


LIVE_SNAPSHOT_URL = "https://www.nseindia.com/api/equity-stockIndices?index={index}"


def fetch_live_snapshot(index: str = "NIFTY 500") -> pd.DataFrame:
    """Fetches one bulk live-quote snapshot (all constituents of `index` in a single
    request) -- used for fast intraday checks instead of per-symbol polling, which
    would need hundreds of individual requests every few minutes and risk NSE
    blocking the session.
    """
    session = _nse_session()
    session.headers.update({"Accept": "application/json"})
    url = LIVE_SNAPSHOT_URL.format(index=index.replace(" ", "%20"))
    response = session.get(url, timeout=20)
    response.raise_for_status()

    rows = response.json().get("data", [])
    df = pd.DataFrame(rows)
    df = df.rename(columns={"symbol": "SYMBOL", "lastPrice": "CLOSE_PRICE", "previousClose": "PREV_CLOSE"})
    df["SERIES"] = "EQ"
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip()
    # The index snapshot includes a summary row for the index itself (e.g. "NIFTY 500").
    df = df[~df["SYMBOL"].str.upper().eq(index.upper())]
    df["PREV_CLOSE"] = pd.to_numeric(df["PREV_CLOSE"], errors="coerce")
    df["CLOSE_PRICE"] = pd.to_numeric(df["CLOSE_PRICE"], errors="coerce")
    return df


def _extract_data_date(df: pd.DataFrame) -> dt.date | None:
    if "DATE1" not in df.columns:
        return None
    dates = pd.to_datetime(df["DATE1"], errors="coerce").dt.date.dropna()
    if dates.empty:
        return None
    return dates.mode().iloc[0]


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
