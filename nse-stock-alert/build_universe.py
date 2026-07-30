"""
Weekly job: scans every NSE-listed equity's market cap and saves the ones above
config.MARKET_CAP_THRESHOLD_CR to data/universe.json. The fast intraday checker
and the end-of-day scan both filter against this static list instead of calling
Yahoo Finance for market cap on every run (which wouldn't scale at 5-minute
intervals). Meant to run weekly (see .github/workflows/nse-universe-refresh.yml)
since market cap doesn't meaningfully change day to day.
"""

import datetime as dt
import json
import logging
import sys
import time
from pathlib import Path

import config
from market_cap import get_market_cap_cr
from nse_data import fetch_bhavcopy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("build_universe")

UNIVERSE_PATH = Path(__file__).parent / "data" / "universe.json"
REQUEST_PAUSE_SECONDS = 0.3  # be polite to Yahoo Finance across ~2000 lookups


def main():
    logger.info("Fetching NSE bhavcopy for the full symbol list...")
    try:
        bhav, data_date = fetch_bhavcopy()
    except Exception as exc:
        logger.error("Failed to fetch bhavcopy: %s", exc)
        sys.exit(1)

    symbols = sorted(bhav.loc[bhav["SERIES"] == "EQ", "SYMBOL"].unique())
    logger.info("Checking market cap for %d equities (this takes a while)...", len(symbols))

    companies = {}
    for i, symbol in enumerate(symbols, start=1):
        mcap_cr = get_market_cap_cr(symbol)
        if mcap_cr is not None and mcap_cr > config.MARKET_CAP_THRESHOLD_CR:
            companies[symbol] = round(mcap_cr, 1)
        if i % 200 == 0:
            logger.info("Checked %d/%d symbols, %d qualify so far", i, len(symbols), len(companies))
        time.sleep(REQUEST_PAUSE_SECONDS)

    logger.info(
        "%d/%d symbols have market cap > %.0f Cr (as of bhavcopy date %s)",
        len(companies),
        len(symbols),
        config.MARKET_CAP_THRESHOLD_CR,
        data_date,
    )

    if not companies:
        logger.error("No qualifying companies found -- refusing to overwrite universe.json with an empty list.")
        sys.exit(1)

    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSE_PATH.write_text(
        json.dumps(
            {
                "generated_at": dt.date.today().isoformat(),
                "bhavcopy_date": data_date.isoformat(),
                "market_cap_threshold_cr": config.MARKET_CAP_THRESHOLD_CR,
                "companies": companies,
            },
            indent=2,
        )
    )
    logger.info("Wrote %s", UNIVERSE_PATH)


if __name__ == "__main__":
    main()
