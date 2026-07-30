# NSE 5% Stock Move Alert

Alerts you (email + SMS) about any NSE stock with **market cap > 10,000 Cr**
whose price moves **5% or more (up or down)** from the previous close.

Two layers, both running automatically via GitHub Actions:

- **Intraday** (`intraday.py`): checks every ~5 minutes during market hours
  (9:15 AM - 3:30 PM IST) and alerts within minutes of a stock crossing the
  threshold. Each stock only alerts once per day.
- **End-of-day** (`main.py`): a full daily sweep of every NSE-listed equity
  at 19:00 IST, as a complete-coverage safety net (catches anything the
  intraday check's snapshot might have missed), skipping anything already
  alerted intraday.

Both are filtered against a **static list of market-cap-qualified symbols**
(`data/universe.json`), refreshed weekly by `build_universe.py`, instead of
looking up market cap on every check — market cap barely changes day to day,
and this keeps the 5-minute intraday check to a single fast network request
instead of hundreds.

## How it works

1. **Weekly** (`build_universe.py`): scans every NSE equity's market cap via
   Yahoo Finance and saves the ones above `MARKET_CAP_THRESHOLD_CR` to
   `data/universe.json` (~2,000 lookups, so this takes 15-30+ minutes).
2. **Every 5 minutes during market hours** (`intraday.py`): fetches one bulk
   live-quote snapshot from NSE (all ~500 "NIFTY 500" constituents in a
   single request), filters it down to `data/universe.json`, and alerts on
   any symbol crossing the threshold for the first time that day. Already-
   alerted symbols are tracked in `data/alerted_today.json` (auto-resets
   daily) so you don't get the same stock every 5 minutes for the rest of
   the day.
3. **Once at 19:00 IST** (`main.py`): downloads NSE's full official daily
   bhavcopy (all listed securities, not just the ~500 in the live snapshot),
   filters it the same way, and alerts on anything new that intraday didn't
   already cover. Falls back to the most recent published trading day's data
   (clearly labeled) if today's file isn't out yet.

## One-time setup

### 1. Gmail app password (for the email alert)

1. Turn on 2-Step Verification on the Gmail account you want to send *from*.
2. Go to https://myaccount.google.com/apppasswords and create an app password
   (any name, e.g. "NSE Alert").
3. Copy the 16-character password — you'll paste it into a GitHub secret below.

### 2. Twilio account (for the SMS alert)

1. Sign up for a free trial at https://www.twilio.com/try-twilio.
2. From the [Twilio Console](https://console.twilio.com/), copy your
   **Account SID** and **Auth Token**.
3. Get a Twilio phone number — pick a **US number** (Indian local numbers need
   extra KYC docs trial accounts can't complete); this is your
   `TWILIO_FROM_NUMBER`, e.g. `+15017122661`. Buying a number draws from your
   trial credit, it isn't a real charge.
4. **Trial account limitation:** Twilio trial accounts can only send SMS to
   phone numbers you've *verified* in the console. Verify `+91 8130423851`
   under Console → Phone Numbers → Verified Caller IDs, or upgrade
   (add billing) to remove that restriction.

### 3. Add GitHub Actions secrets

In this repo: **Settings → Secrets and variables → Actions → New repository
secret**, add:

| Secret name           | Value                                   |
|-----------------------|------------------------------------------|
| `EMAIL_ADDRESS`       | The Gmail address you're sending *from*  |
| `EMAIL_APP_PASSWORD`  | The 16-char app password from step 1     |
| `TWILIO_ACCOUNT_SID`  | From the Twilio console                  |
| `TWILIO_AUTH_TOKEN`   | From the Twilio console                  |
| `TWILIO_FROM_NUMBER`  | Your Twilio phone number, e.g. +15017122661 |

The recipient email (`punitmoto2019@gmail.com`) and phone (`+91 8130423851`)
are already defaulted in `config.py`. Override them by adding
`ALERT_EMAIL_TO` / `ALERT_PHONE_TO` secrets or repo variables if you ever
want to change the destination without editing code.

### 4. Allow the workflows to write back to the repo

The intraday and weekly-refresh workflows commit small state files
(`data/alerted_today.json`, `data/universe.json`) back to the repo. If pushes
from those workflows fail with a permissions error, go to **Settings →
Actions → General → Workflow permissions** and select **"Read and write
permissions"**.

### 5. Bootstrap the universe list (required before the first real alert)

The alert scripts refuse to run until `data/universe.json` exists. Go to the
**Actions** tab → **"NSE Universe Refresh"** → **Run workflow**, and wait for
it to finish (15-30+ minutes — it's checking market cap for every NSE
equity). After that it refreshes automatically every Sunday at 20:00 IST.

### 6. Enable the workflows

All three workflows run automatically once merged to the default branch:

| Workflow | Schedule |
|---|---|
| `nse-universe-refresh.yml` | Weekly, Sunday 20:00 IST |
| `nse-intraday-alert.yml` | Every ~5 min, market hours (9:15 AM-3:30 PM IST), Mon-Fri |
| `nse-stock-alert.yml` | Once daily, 19:00 IST, Mon-Fri |

Each also supports manual triggering from the **Actions** tab → pick the
workflow → **Run workflow**, useful for testing without waiting for the
schedule (though `intraday.py` and `main.py` will both error out until step 5
above has been done at least once).

## Configuration

All tunable via environment variables (set as repo variables/secrets, or
edit the defaults in `config.py`):

| Variable                   | Default   | Meaning                                  |
|----------------------------|-----------|-------------------------------------------|
| `PCT_CHANGE_THRESHOLD`     | `5.0`     | % move (either direction) that triggers an alert |
| `MARKET_CAP_THRESHOLD_CR`  | `10000`   | Minimum market cap (in Cr) to include     |
| `ALERT_EMAIL_TO`           | punitmoto2019@gmail.com | Alert recipient email       |
| `ALERT_PHONE_TO`           | +918130423851 | Alert recipient phone (E.164 format) |

## Running locally

```bash
cd nse-stock-alert
pip install -r requirements.txt
export EMAIL_ADDRESS=you@gmail.com
export EMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
export TWILIO_ACCOUNT_SID=ACxxxxxxxx
export TWILIO_AUTH_TOKEN=xxxxxxxx
export TWILIO_FROM_NUMBER=+15017122661
python build_universe.py   # once, to create data/universe.json
python intraday.py         # fast check, run anytime during market hours
python main.py             # full end-of-day scan
```

## Known limitations

- NSE occasionally changes response formats or rate-limits scrapers without
  notice — if a run fails, check the Actions log rather than assuming the
  data is fine.
- Market holidays: `main.py` falls back to (and clearly labels) the most
  recent trading day's data; `intraday.py` will just find no live movers.
- Market cap comes from Yahoo Finance, not NSE itself, refreshed weekly — a
  company that crosses the 10,000 Cr line mid-week won't be picked up until
  the next Sunday refresh (or you can trigger it manually).
- The intraday live snapshot ("NIFTY 500", ~500 stocks) covers virtually all
  >10,000 Cr market-cap names, since NIFTY 500's inclusion cutoff is far
  below that, but isn't a strict guarantee for one at the margin — the
  19:00 IST end-of-day scan (which reads the full official bhavcopy, not a
  snapshot) is the complete-coverage backstop for that gap.
- GitHub disables scheduled workflows after 60 days of repo inactivity — if
  alerts silently stop, check the Actions tab for a "workflow disabled"
  notice and re-enable it.
