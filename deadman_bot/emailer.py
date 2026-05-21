from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from config import Settings


def send_email(settings: Settings, recipient: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = recipient
    msg["Subject"] = "Scheduled message"
    msg.set_content(body)

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(
        settings.smtp_host,
        settings.smtp_port,
        context=ssl.create_default_context(),
    ) as smtp:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            smtp.starttls(context=ssl.create_default_context())
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
