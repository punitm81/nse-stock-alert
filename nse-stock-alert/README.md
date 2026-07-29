# NSE 5% Stock Move Alert

Every trading day, shortly after the NSE market close (15:30 IST), this checks
every NSE-listed equity and alerts you (email + SMS) about any stock whose
close price moved **5% or more (up or down)** from the previous close, among
stocks with **market cap > 10,000 Cr**.

It runs automatically via GitHub Actions — no server of your own required.

## How it works

1. `nse_data.py` downloads NSE's full daily bhavcopy (`sec_bhavdata_full.csv`),
   which has the close/previous-close for every listed security, and computes
   `% change` for the `EQ` series.
2. Rows with `|% change| >= 5%` are kept, then `market_cap.py` looks up each
   candidate's market cap via Yahoo Finance (`SYMBOL.NS`) and drops anything
   under 10,000 Cr. Market cap is only looked up for the day's movers, so this
   stays fast even though the full NSE universe is ~2,000 symbols.
3. If any stocks qualify, `notify_email.py` emails a full table and
   `notify_sms.py` texts a short summary (top 10 movers) via Twilio.
4. If nothing qualifies, no message is sent (the run just logs "no movers").

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
3. Get a Twilio phone number (trial accounts get one free) — this is your
   `TWILIO_FROM_NUMBER`, e.g. `+15017122661`.
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

### 4. Enable the workflow

The workflow at `.github/workflows/nse-stock-alert.yml` runs automatically
Mon–Fri at 15:35 IST once merged to the default branch. You can also trigger
it manually any time from the **Actions** tab → "NSE Stock Alert" →
**Run workflow**, which is the easiest way to test your secrets are correct
before waiting for the next trading day.

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
python main.py
```

## Known limitations

- NSE's bhavcopy is only published/updated after the market closes, and NSE
  occasionally changes response format or rate-limits scrapers without
  notice — if a run fails, check the Actions log; it will simply skip that
  day rather than send a false alert.
- Market holidays: NSE won't publish fresh data, so the fetch will either
  fail (run marked failed, no message sent) or return stale data with zero
  movers — either way you won't get spammed.
- Market cap comes from Yahoo Finance, not NSE itself, and can lag real-time
  by a day for less-liquid names.
