
import logging
import threading
from bot import TelegramBot
from app import app
import asyncio
import nest_asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

def run_flask():
    """Run Flask server"""
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Error running Flask server: {e}")
        raise

async def run_bot():
    """Run the Telegram bot"""
    try:
        bot = TelegramBot()
        app = bot.get_application()
        logger.info("Starting bot...")
        await bot._set_commands()
        await app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

def main():
    """Start the bot and Flask server."""
    try:
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask server started")

        # Create new event loop for the bot
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
    except Exception as e:
        logger.error(f"Error running application: {e}")
        raise
    finally:
        logger.info("Application shutdown complete")

if __name__ == '__main__':
    main()
