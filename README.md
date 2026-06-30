# Task Reward Telegram Bot

A simple, working Telegram bot for task management and reward distribution,
built with `python-telegram-bot` v21+ and a JSON-backed data layer.

## Features
- User: `/start`, `/tasks`, `/balance`, `/history`, `/referral`, task submission flow
- Admin: `/newtask`, `/queue` (review with inline Approve/Reject buttons), `/stats`, `/mytasks`, `/deactivate`

## Setup

```bash
git clone <your-repo-url>
cd task-reward-bot
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your TELEGRAM_TOKEN from @BotFather
# edit config/admins.json and add your numeric Telegram user ID
python src/bot.py
```

## Docker

```bash
docker-compose up -d
```

## Project Structure

```
task-reward-bot/
├── src/          # bot logic
├── config/       # admins.json, settings.json
├── data/         # JSON data store (users, tasks, submissions, rewards)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Notes
- Data persists as JSON files in `data/`. For production scale, swap `database.py`
  for SQLite/Postgres — the `DB` class methods are the only thing callers depend on.
- Get your Telegram user ID from @userinfobot, then add it to `config/admins.json`.
