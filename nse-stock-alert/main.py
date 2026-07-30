"""
NSE 5% Stock Move Alert
========================
Fetches NSE's full daily bhavcopy, finds all equities whose close price moved
>= PCT_CHANGE_THRESHOLD percent (either direction) from the previous close,
keeps only those with market cap above MARKET_CAP_THRESHOLD_CR crore, and
emails + SMS-alerts the result. Designed to be run once per trading day
(see .github/workflows/nse-stock-alert.yml).
"""

import datetime as dt
import logging
import sys

import config
from nse_data import fetch_bhavcopy, find_pct_movers
from notify_email import send_email_alert
from notify_sms import send_sms_alert
from state import load_alerted_today
from universe import load_universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nse_alert")

MAX_SMS_ROWS = 10


def build_email_html(rows, data_date, is_stale):
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
    stale_notice = (
        "<p style=\"color:#b00\"><b>Note:</b> today's NSE bhavcopy wasn't published yet when this "
        f"ran, so this is the most recent available trading day's data ({data_date}).</p>"
        if is_stale
        else ""
    )
    return f"""
    <h2>NSE Stocks that moved &ge;{config.PCT_CHANGE_THRESHOLD:.0f}% on {data_date}</h2>
    {stale_notice}
    <p>Universe: all NSE equities with market cap &gt; {config.MARKET_CAP_THRESHOLD_CR:,.0f} Cr</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
      <tr>
        <th>Symbol</th><th>Close</th><th>Prev Close</th><th>% Change</th><th>Mkt Cap (Cr)</th>
      </tr>
      {table_rows}
    </table>
    """


def build_sms_text(rows, data_date, is_stale):
    top = rows[:MAX_SMS_ROWS]
    lines = "\n".join(f"{r['SYMBOL']} {r['PCT_CHANGE']:+.1f}%" for r in top)
    label = f"{data_date} (prev trading day)" if is_stale else str(data_date)
    text = f"NSE {config.PCT_CHANGE_THRESHOLD:.0f}%+ movers ({label}):\n{lines}"
    if len(rows) > MAX_SMS_ROWS:
        text += f"\n+{len(rows) - MAX_SMS_ROWS} more, see email"
    return text


def main():
    today = dt.date.today()

    try:
        universe = load_universe()
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)

    logger.info("Fetching NSE bhavcopy...")
    try:
        bhav, data_date = fetch_bhavcopy(today)
    except Exception as exc:
        logger.error("Failed to fetch bhavcopy (market holiday or NSE blocked the request): %s", exc)
        sys.exit(1)

    is_stale = data_date != today

    movers = find_pct_movers(bhav, config.PCT_CHANGE_THRESHOLD)
    movers = movers[movers["SYMBOL"].isin(universe)]
    logger.info(
        "%d stocks with |change| >= %.1f%% and market cap > %.0f Cr",
        len(movers),
        config.PCT_CHANGE_THRESHOLD,
        config.MARKET_CAP_THRESHOLD_CR,
    )

    # Skip anything the intraday checker already alerted on today, so this
    # end-of-day summary doesn't duplicate a notification you already got.
    already_alerted = load_alerted_today()
    movers = movers[~movers["SYMBOL"].isin(already_alerted)]

    qualified = [
        {
            "SYMBOL": row["SYMBOL"],
            "CLOSE_PRICE": row["CLOSE_PRICE"],
            "PREV_CLOSE": row["PREV_CLOSE"],
            "PCT_CHANGE": row["PCT_CHANGE"],
            "MARKET_CAP_CR": universe[row["SYMBOL"]],
        }
        for _, row in movers.iterrows()
    ]

    logger.info("%d new stock(s) to alert on (not already sent intraday today)", len(qualified))

    if not qualified:
        logger.info("No qualifying movers on %s; no alert sent.", data_date)
        return

    qualified.sort(key=lambda r: abs(r["PCT_CHANGE"]), reverse=True)

    stale_tag = " [prev trading day]" if is_stale else ""
    subject = (
        f"NSE Alert: {len(qualified)} stock(s) moved >={config.PCT_CHANGE_THRESHOLD:.0f}% "
        f"on {data_date}{stale_tag}"
    )
    send_email_alert(subject, build_email_html(qualified, data_date, is_stale))
    send_sms_alert(build_sms_text(qualified, data_date, is_stale))


if __name__ == "__main__":
    main()
