import logging
import asyncio
import signal
from bot import TelegramBot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    raise SystemExit

def main():
    """Start the bot."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot = TelegramBot()
        app = bot.get_application()
        logger.info("Starting bot...")
        app.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by signal")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise
    finally:
        logger.info("Bot shutdown complete")

if __name__ == '__main__':
    main()