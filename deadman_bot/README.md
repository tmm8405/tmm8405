# Telegram Deadman Bot

A Telegram bot that schedules an email to be sent after a set number of days if you don't extend the timer.

## Features
- `/schedule` to store the email + message + countdown
- `/extend` to add more days before the email is sent
- `/status` to check the remaining time
- `/cancel` to remove the schedule

## Setup
1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and grab the token.
2. Pick an email provider. Free options include **SendGrid** or **Mailgun** (they have limited free tiers). If you don't want that, use **Gmail** with an app password.
3. Copy `.env.example` to `.env` and fill in the values.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the bot:

```bash
python main.py
```

## Bot Commands
- `/schedule <days> <email> <message>`
- `/extend <days>`
- `/status`
- `/cancel`

## Notes
- The SQLite database is stored in `data/deadman.sqlite` by default.
- The watcher checks for expired timers every 60 seconds (configure with `CHECK_INTERVAL_SECONDS`).
- If your SMTP provider requires SSL on connect (port 465), set `SMTP_USE_SSL=true` and `SMTP_USE_TLS=false`.
- Failed email sends are retried with `RETRY_DELAY_SECONDS` and stop after `MAX_SEND_ATTEMPTS`.
- Email validation is intentionally basic; use standard mailbox addresses.
