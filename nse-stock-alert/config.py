"""Runtime configuration, all overridable via environment variables / GitHub Actions secrets."""

import os

# --- Screening thresholds ---
PCT_CHANGE_THRESHOLD = float(os.environ.get("PCT_CHANGE_THRESHOLD", "5.0"))
MARKET_CAP_THRESHOLD_CR = float(os.environ.get("MARKET_CAP_THRESHOLD_CR", "10000"))

# How many of the largest (by market cap) qualifying stocks the 5-minute intraday
# check polls. NSE's own live-quote API blocks GitHub Actions' cloud IPs, so
# intraday instead polls Yahoo Finance per-symbol; keeping this list small (rather
# than the full ~600-stock universe) keeps request volume safely within Yahoo's
# rate limits. The full universe still gets complete coverage once a day at
# 19:00 IST via the official NSE bhavcopy (main.py), which isn't IP-blocked.
INTRADAY_WATCHLIST_SIZE = int(os.environ.get("INTRADAY_WATCHLIST_SIZE", "150"))

# --- Recipients ---
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "punitmoto2019@gmail.com")
ALERT_PHONE_TO = os.environ.get("ALERT_PHONE_TO", "+918130423851")

# --- Email (SMTP) sender credentials ---
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# --- Twilio SMS credentials ---
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")
