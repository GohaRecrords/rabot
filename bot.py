import logging
import os
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

try:
    # These imports are optional and only needed when running the bot
    # in an environment where the python‑telegram‑bot package is available.
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
except ImportError:
    # In environments without python‑telegram‑bot (e.g. this coding sandbox)
    # we fall back to dummy values so that the module can still be imported
    # and its non‑Telegram functions (such as fetching events) can be used.
    Update = None  # type: ignore
    CallbackContext = None  # type: ignore

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")
app = ApplicationBuilder().token(token)
RA_GRAPHQL_URL = "https://ra.co/graphql"
BERLIN_AREA_ID = 34

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_events_for_date(date_str: str):
    try:
        start = f"{date_str}T00:00:00.000Z"
        end = f"{date_str}T23:59:59.999Z"
        query = f'''
        query {{
            eventListings(filters: {{
                areas: {{ eq: {BERLIN_AREA_ID} }},
                listingDate: {{ gte: "{start}", lte: "{end}" }}
            }}, page: 1, pageSize: 20) {{
                data {{
                    event {{
                        title
                        date
                        startTime
                        endTime
                        contentUrl
                        venue {{ name }}
                    }}
                }}
                totalResults
            }}
        }}
        '''
        response = requests.get(RA_GRAPHQL_URL,
                                params={"query": query},
                                headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            events = data["data"]["eventListings"]["data"]
            return [e["event"] for e in events]
        else:
            logger.error(
                f"GraphQL Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []


def format_event(event: dict) -> str:
    """Format a single event into a nicely structured Markdown string.

    The Telegram API will render this Markdown to show the event title in bold,
    followed by the time, venue and a link to the event on Resident Advisor.

    Args:
        event: A dictionary returned from the Resident Advisor API containing at
            least the keys 'title', 'startTime', 'endTime', 'venue' and 'contentUrl'.

    Returns:
        A string formatted using Telegram's MarkdownV2 format with newlines
        separating each piece of event information. If an event is missing
        start or end times or a venue, fallback values are used.
    """
    # Construct a human‑readable time string. If either start or end is missing
    # the entire time is omitted.
    start_time = event.get('startTime')
    end_time = event.get('endTime')
    if start_time and end_time:
        time_str = f"{start_time}–{end_time}"
    else:
        time_str = "Time N/A"

    # Determine the venue name if available. Some events may have a null venue.
    venue_data = event.get('venue')
    if venue_data and 'name' in venue_data and venue_data['name']:
        venue = venue_data['name']
    else:
        venue = "Venue N/A"

    # Use a single string literal with embedded newlines to avoid syntax errors.
    return (f"*{event['title']}*\n"
            f"🕒 {time_str}\n"
            f"📍 {venue}\n"
            f"🔗 [View Event](https://ra.co{event['contentUrl']})")


def events_command(update, context) -> None:
    """Handle the /events command by fetching and returning events for a given date.

    Users can provide a date in the format ``YYYY-MM-DD`` or one of the keywords
    ``today``/``tomorrow``. If no argument is provided, the bot defaults to
    today's date in the Europe/Berlin timezone. Invalid dates will result in a
    helpful usage message.

    Args:
        update: The update provided by telegram when the command is issued.
        context: Contextual information including command arguments.
    """
    # Determine the date string based on user input
    import pytz  # Lazy import so module remains importable without telegram
    berlin_tz = pytz.timezone('Europe/Berlin')
    now_berlin = datetime.now(berlin_tz)

    if context.args:
        # Join all args to handle dates like "2025-01-01" (split by spaces)
        date_input = " ".join(context.args).strip().lower()
        if date_input in {"today", "td"}:
            date_str = now_berlin.strftime("%Y-%m-%d")
        elif date_input in {"tomorrow", "tm", "tmr", "tomo"}:
            tomorrow = now_berlin + timedelta(days=1)
            date_str = tomorrow.strftime("%Y-%m-%d")
        else:
            # Try to parse the provided date using multiple common formats
            parsed = None
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]:
                try:
                    parsed = datetime.strptime(date_input, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                update.message.reply_text(
                    "Please provide a valid date in YYYY-MM-DD format or use 'today'/'tomorrow'."
                )
                return
            date_str = parsed.strftime("%Y-%m-%d")
    else:
        # Default to today's date in Berlin if no argument is given
        date_str = now_berlin.strftime("%Y-%m-%d")

    update.message.reply_text(f"Searching events for *{date_str}* in Berlin…",
                              parse_mode='Markdown')
    events = fetch_events_for_date(date_str)
    if not events:
        update.message.reply_text("No events found for that date.")
        return
    # Limit the number of events sent to avoid flooding the chat
    for event in events[:10]:
        update.message.reply_text(format_event(event),
                                  parse_mode='Markdown')


def start_command(update, context):
    update.message.reply_text(
        "👋 Welcome! Use /events YYYY-MM-DD to get Berlin events for a date. Try /events today."
    )
if __name__ == "__main__":
    main()


from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, Filters

# Keep track of user states for search input
user_states = {}

def start(update: Update, context: CallbackContext) -> None:
    today = datetime.utcnow().date().isoformat()
    send_events_for_date(update, context, today)

def send_events_for_date(update_or_query, context: CallbackContext, date_str: str):
    events = fetch_events_for_date(date_str)
    text = f"🎉 Events for {date_str}:"
    
    if not events:
        text += "No events found."
    else:
        for ev in events:
            text += f"• {ev['title']} ({ev['venue']['name']})"
            

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Previous Day", callback_data=f"date:{date_str}:-1"),
            InlineKeyboardButton("📅 Today", callback_data=f"date:{datetime.utcnow().date().isoformat()}:0"),
            InlineKeyboardButton("➡️ Next Day", callback_data=f"date:{date_str}:1")
        ],
        [InlineKeyboardButton("🔍 Search", callback_data="search")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update_or_query, 'message'):
        update_or_query.message.reply_text(text, reply_markup=reply_markup)
    elif hasattr(update_or_query, 'edit_message_text'):
        update_or_query.edit_message_text(text, reply_markup=reply_markup)

def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    data = query.data

    if data.startswith("date:"):
        _, current_date, offset = data.split(":")
        new_date = (datetime.fromisoformat(current_date) + timedelta(days=int(offset))).date().isoformat()
        send_events_for_date(query, context, new_date)

    elif data == "search":
        user_id = query.from_user.id
        user_states[user_id] = "awaiting_search"
        query.message.reply_text("🔍 Please enter the event name or club:")

def search_handler(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_states.get(user_id) == "awaiting_search":
        search_term = update.message.text.lower()
        del user_states[user_id]

        # Fetch all events today and filter
        date_str = datetime.utcnow().date().isoformat()
        events = fetch_events_for_date(date_str)

        filtered = [ev for ev in events if search_term in ev['title'].lower() or search_term in ev['venue']['name'].lower()]
        text = f"🔎 Results for '{search_term}':"
        
        if not filtered:
            text += "No matching events found."
        else:
            for ev in filtered:
                text += f"• {ev['title']} ({ev['venue']['name']})"

        update.message.reply_text(text)

# Add these to the main function that sets up the bot
def main():
    dp = app

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, search_handler))

    app.run_polling()
    

if __name__ == '__main__':
    main()
