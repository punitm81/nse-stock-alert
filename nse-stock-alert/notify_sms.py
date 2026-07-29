"""Sends the alert SMS via Twilio."""

import logging

from twilio.rest import Client

import config

logger = logging.getLogger(__name__)


def send_sms_alert(body: str) -> None:
    if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_FROM_NUMBER):
        logger.warning("Twilio credentials not fully set; skipping SMS alert.")
        return

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=body,
        from_=config.TWILIO_FROM_NUMBER,
        to=config.ALERT_PHONE_TO,
    )
    logger.info("SMS alert sent to %s", config.ALERT_PHONE_TO)
