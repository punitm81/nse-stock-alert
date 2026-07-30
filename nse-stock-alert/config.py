"""Runtime configuration, all overridable via environment variables / GitHub Actions secrets."""

import os

# --- Screening thresholds ---
PCT_CHANGE_THRESHOLD = float(os.environ.get("PCT_CHANGE_THRESHOLD", "5.0"))
MARKET_CAP_THRESHOLD_CR = float(os.environ.get("MARKET_CAP_THRESHOLD_CR", "10000"))

# How many of the largest (by market cap) qualifying stocks the intraday check
# polls -- default is set higher than the universe is ever expected to be, so
# it effectively watches the whole thing. NSE's own live-quote API blocks
# GitHub Actions' cloud IPs, so intraday instead polls Yahoo Finance per-symbol
# (rate-limited in market_cap.py); lower this if you want faster/lighter
# checks over just the biggest names instead of full coverage.
INTRADAY_WATCHLIST_SIZE = int(os.environ.get("INTRADAY_WATCHLIST_SIZE", "5000"))

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
