"""
Fast intraday check: fetches one bulk live-quote snapshot from NSE, filters it
down to the static market-cap-qualified universe (see build_universe.py), and
alerts on any symbol crossing PCT_CHANGE_THRESHOLD for the first time today.
Meant to run every ~5 minutes during market hours (see
.github/workflows/nse-intraday-alert.yml). The end-of-day full scan in main.py
still runs once a day as a complete-coverage safety net.
"""

import datetime as dt
import logging
import sys
from zoneinfo import ZoneInfo

import config
from nse_data import fetch_live_snapshot, find_pct_movers
from notify_email import send_email_alert
from notify_sms import send_sms_alert
from state import load_alerted_today, mark_alerted
from universe import load_universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nse_intraday_alert")

IST = ZoneInfo("Asia/Kolkata")


def build_email_html(rows, now_str):
    table_rows = "".join(
        "<tr>"
        f"<td>{r['SYMBOL']}</td>"
        f"<td>{r['CLOSE_PRICE']:.2f}</td>"
        f"<td>{r['PREV_CLOSE']:.2f}</td>"
        f"<td style=\"color:{'green' if r['PCT_CHANGE'] >= 0 else 'red'}\">{r['PCT_CHANGE']:+.2f}%</td>"
        f"<td>{r['MARKET_CAP_CR']:,.0f}</td>"
        "</tr>"
        for r in rows
    )
    return f"""
    <h2>NSE Intraday Alert: &ge;{config.PCT_CHANGE_THRESHOLD:.0f}% move as of {now_str} IST</h2>
    <p>Universe: NSE equities with market cap &gt; {config.MARKET_CAP_THRESHOLD_CR:,.0f} Cr.
       First alert of the day for each stock -- see the end-of-day email for the full daily summary.</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
      <tr><th>Symbol</th><th>Price</th><th>Prev Close</th><th>% Change</th><th>Mkt Cap (Cr)</th></tr>
      {table_rows}
    </table>
    """


def build_sms_text(rows, now_str):
    lines = "\n".join(f"{r['SYMBOL']} {r['PCT_CHANGE']:+.1f}%" for r in rows)
    return f"NSE intraday {config.PCT_CHANGE_THRESHOLD:.0f}%+ ({now_str} IST):\n{lines}"


def main():
    now_str = dt.datetime.now(IST).strftime("%H:%M")

    try:
        universe = load_universe()
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)

    logger.info("Fetching live NSE snapshot...")
    try:
        snapshot = fetch_live_snapshot()
    except Exception as exc:
        logger.error("Failed to fetch live snapshot: %s", exc)
        sys.exit(1)

    movers = find_pct_movers(snapshot, config.PCT_CHANGE_THRESHOLD)
    movers = movers[movers["SYMBOL"].isin(universe)]

    already_alerted = load_alerted_today()
    new_movers = movers[~movers["SYMBOL"].isin(already_alerted)]
    logger.info(
        "%d qualifying live movers, %d already alerted today, %d new",
        len(movers),
        len(already_alerted),
        len(new_movers),
    )

    if new_movers.empty:
        return

    qualified = [
        {
            "SYMBOL": row["SYMBOL"],
            "CLOSE_PRICE": row["CLOSE_PRICE"],
            "PREV_CLOSE": row["PREV_CLOSE"],
            "PCT_CHANGE": row["PCT_CHANGE"],
            "MARKET_CAP_CR": universe[row["SYMBOL"]],
        }
        for _, row in new_movers.iterrows()
    ]
    qualified.sort(key=lambda r: abs(r["PCT_CHANGE"]), reverse=True)

    subject = (
        f"NSE Intraday Alert: {len(qualified)} stock(s) crossed "
        f"{config.PCT_CHANGE_THRESHOLD:.0f}% ({now_str} IST)"
    )
    send_email_alert(subject, build_email_html(qualified, now_str))
    send_sms_alert(build_sms_text(qualified, now_str))

    mark_alerted([r["SYMBOL"] for r in qualified])


if __name__ == "__main__":
    main()
