# RA Telegram Bot

This is a Telegram bot to show events from Resident Advisor.

## Features

- Browse events by date (prev / today / next)
- Free text search (event or club name)
- Save favorites (optional)
- Extendable to include reminders and more

## Setup

1. Clone this repo:

```bash
git clone https://github.com/yourusername/ra-bot.git
cd ra-bot
```

2. Create a `.env` file from the example:

```bash
cp .env.example .env
# then edit and paste your TELEGRAM_TOKEN
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the bot:

```bash
python bot.py
```

## Hosting Suggestions

- [Render](https://render.com)
- [Railway](https://railway.app)
- Replit (for development)

## License

MIT