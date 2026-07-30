"""
Fast intraday check: polls Yahoo Finance for stocks in the static market-cap-
qualified universe (see build_universe.py) and alerts on any symbol crossing
PCT_CHANGE_THRESHOLD for the first time today.

NSE's own live-quote API blocks requests from GitHub Actions' cloud IPs
(confirmed by testing -- it 404s even with the correct endpoint and index
name), so this polls Yahoo Finance per-symbol instead (same source
market_cap.py already uses, rate-limited there to stay well under Yahoo's
undocumented limits). config.INTRADAY_WATCHLIST_SIZE caps how many of the
largest-by-market-cap symbols get checked each run; its default covers the
full universe (~600 stocks). At ~3 requests/second that's ~3-4 minutes per
run, comfortably inside the 15-minute check interval (see
.github/workflows/nse-intraday-alert.yml). The end-of-day scan (main.py)
remains a complete-coverage backstop regardless.
"""

import datetime as dt
import logging
import sys
from zoneinfo import ZoneInfo

import config
from market_cap import get_live_quote
from notify_email import send_email_alert
from notify_sms import send_sms_alert
from state import load_alerted_today, mark_alerted
from universe import load_universe, top_symbols_by_market_cap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nse_intraday_alert")

IST = ZoneInfo("Asia/Kolkata")


def build_email_html(rows, now_str, watchlist_size):
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
    <p>Watchlist: {watchlist_size} NSE stocks with market cap
       &gt; {config.MARKET_CAP_THRESHOLD_CR:,.0f} Cr. First alert of the day for each stock --
       see the end-of-day email for the full daily summary across all qualifying stocks.</p>
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

    watchlist = top_symbols_by_market_cap(universe, config.INTRADAY_WATCHLIST_SIZE)
    already_alerted = load_alerted_today()
    to_check = [s for s in watchlist if s not in already_alerted]
    logger.info(
        "Watchlist: %d symbols, %d already alerted today, checking %d",
        len(watchlist),
        len(watchlist) - len(to_check),
        len(to_check),
    )

    qualified = []
    for symbol in to_check:
        quote = get_live_quote(symbol)
        if quote is None:
            continue
        last_price, prev_close = quote
        if prev_close <= 0:
            continue
        pct_change = (last_price - prev_close) / prev_close * 100
        if abs(pct_change) < config.PCT_CHANGE_THRESHOLD:
            continue
        qualified.append(
            {
                "SYMBOL": symbol,
                "CLOSE_PRICE": last_price,
                "PREV_CLOSE": prev_close,
                "PCT_CHANGE": pct_change,
                "MARKET_CAP_CR": universe[symbol],
            }
        )

    if not qualified:
        logger.info("No new qualifying movers this check.")
        return

    qualified.sort(key=lambda r: abs(r["PCT_CHANGE"]), reverse=True)

    subject = (
        f"NSE Intraday Alert: {len(qualified)} stock(s) crossed "
        f"{config.PCT_CHANGE_THRESHOLD:.0f}% ({now_str} IST)"
    )
    send_email_alert(subject, build_email_html(qualified, now_str, len(watchlist)))
    send_sms_alert(build_sms_text(qualified, now_str))

    mark_alerted([r["SYMBOL"] for r in qualified])


if __name__ == "__main__":
    main()
