from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import Settings, load_settings
from emailer import send_email
from storage import Storage

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SECONDS_PER_DAY = 86400


def _format_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _parse_days(value: str) -> int:
    cleaned = value.strip().lower()
    if cleaned.endswith("d"):
        cleaned = cleaned[:-1]
    if not cleaned.isdigit():
        raise ValueError("Days must be a whole number")
    days = int(cleaned)
    if days <= 0:
        raise ValueError("Days must be greater than zero")
    return days


def _validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def _build_email_body(message: str) -> str:
    return (
        "This email was scheduled by a Telegram Deadman Bot.\n\n"
        f"Message:\n{message}\n\n"
        "If you received this, the timer expired without being extended."
    )


def _days_left(due_at: int, now_ts: int) -> int:
    remaining = max(due_at - now_ts, 0)
    return max(math.ceil(remaining / SECONDS_PER_DAY), 0)


def _ensure_message(update: Update) -> bool:
    return update.message is not None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_message(update):
        return
    await update.message.reply_text(
        "Send a delayed email when you stop checking in.\n\n"
        "Commands:\n"
        "/schedule <days> <email> <message> - set the countdown\n"
        "/extend <days> - add days to the countdown\n"
        "/status - see your current timer\n"
        "/cancel - remove the scheduled email"
    )


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_message(update):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /schedule <days> <email> <message>\n"
            "Example: /schedule 30 friend@example.com I miss you."
        )
        return

    days_raw, email = context.args[0], context.args[1]
    message = " ".join(context.args[2:]).strip()

    try:
        days = _parse_days(days_raw)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    if not _validate_email(email):
        await update.message.reply_text("Please provide a valid email address.")
        return

    if not message:
        await update.message.reply_text("Please include the message to send.")
        return

    now_ts = int(time.time())
    due_at = now_ts + days * SECONDS_PER_DAY

    storage: Storage = context.application.bot_data["storage"]
    storage.upsert_entry(update.message.chat_id, email, message, due_at, now_ts)

    await update.message.reply_text(
        f"Saved. Your message will be sent on {_format_ts(due_at)} "
        f"({days} days). Use /extend to add more time."
    )


async def extend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_message(update):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /extend <days>")
        return

    try:
        days = _parse_days(context.args[0])
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    storage: Storage = context.application.bot_data["storage"]
    entry = storage.get_active_entry(update.message.chat_id)
    if not entry:
        await update.message.reply_text("You don't have an active schedule.")
        return

    now_ts = int(time.time())
    new_due_at = entry["due_at"] + days * SECONDS_PER_DAY
    storage.update_due_at(entry["id"], new_due_at, now_ts)

    await update.message.reply_text(
        f"Extended. New send time: {_format_ts(new_due_at)}."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_message(update):
        return

    storage: Storage = context.application.bot_data["storage"]
    entry = storage.get_active_entry(update.message.chat_id)
    if not entry:
        await update.message.reply_text("No active schedule. Use /schedule first.")
        return

    now_ts = int(time.time())
    days_left = _days_left(entry["due_at"], now_ts)
    await update.message.reply_text(
        f"Your message is scheduled for {_format_ts(entry['due_at'])} "
        f"({days_left} days left)."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_message(update):
        return

    storage: Storage = context.application.bot_data["storage"]
    removed = storage.delete_active_entry(update.message.chat_id)

    if removed:
        await update.message.reply_text("Cancelled your scheduled message.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def _watcher_loop(application: Application) -> None:
    storage: Storage = application.bot_data["storage"]
    settings = application.bot_data["settings"]

    while True:
        try:
            now_ts = int(time.time())
            due_entries = storage.get_due_entries(now_ts)
            for entry in due_entries:
                try:
                    send_email(settings, entry["email"], _build_email_body(entry["message"]))
                    storage.mark_sent(entry["id"], now_ts)
                    await application.bot.send_message(
                        chat_id=entry["chat_id"],
                        text=f"Email sent to {entry['email']}.",
                    )
                except Exception:
                    logging.exception("Failed to send email for entry %s", entry["id"])
            await asyncio.sleep(settings.check_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Watcher loop error")
            await asyncio.sleep(settings.check_interval_seconds)


def _register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("extend", extend))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))


async def _post_init(application: Application) -> None:
    application.create_task(_watcher_loop(application))


def build_application(settings: Settings, storage: Storage) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_post_init)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["storage"] = storage
    _register_handlers(application)
    return application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    storage = Storage(settings.database_path)
    application = build_application(settings, storage)

    application.run_polling()


if __name__ == "__main__":
    main()
