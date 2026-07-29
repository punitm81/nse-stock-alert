"""Sends the alert email over SMTP (Gmail by default)."""

import logging
import smtplib
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def send_email_alert(subject: str, html_body: str) -> None:
    if not config.EMAIL_ADDRESS or not config.EMAIL_APP_PASSWORD:
        logger.warning("EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set; skipping email alert.")
        return

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_ADDRESS
    msg["To"] = config.ALERT_EMAIL_TO

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
        server.sendmail(config.EMAIL_ADDRESS, [config.ALERT_EMAIL_TO], msg.as_string())

    logger.info("Email alert sent to %s", config.ALERT_EMAIL_TO)
