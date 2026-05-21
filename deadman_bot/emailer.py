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
    ssl_context = ssl.create_default_context()
    with smtp_class(
        settings.smtp_host,
        settings.smtp_port,
        context=ssl_context,
    ) as smtp:
        smtp.ehlo()
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            if not smtp.has_extn("starttls"):
                raise RuntimeError("SMTP server does not support STARTTLS")
            smtp.starttls(context=ssl_context)
            smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
