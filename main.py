import logging
import asyncio
from bot import TelegramBot
from app import app
import coloredlogs

# Configure colored logging for ERROR only
coloredlogs.install(
    level='DEBUG',
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level_styles={
        'DEBUG': {'color': 'blue'},
        'INFO': {'color': 'green'},
        'WARNING': {'color': 'yellow'},
        'ERROR': {'color': 'red', 'bold': True},
        'CRITICAL': {'color': 'magenta', 'bold': True},
    },
    field_styles={
        'asctime': {'color': 'cyan'},
        'name': {'color': 'white'},
        'levelname': {'color': 'white', 'bold': True},
    }
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)


async def run_bot():
    """Setup and run the Telegram bot"""
    try:
        # Initialize bot
        bot = TelegramBot()
        application = bot.get_application()

        # Important: Delete webhook and drop pending updates
        await application.bot.delete_webhook(drop_pending_updates=True)
        await bot.setup()

        logger.info("Starting bot...")
        await application.initialize()
        await application.start()

        # Configure update fetching with proper locking settings
        await application.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            read_timeout=10,
            timeout=10,
            bootstrap_retries=3,
            pool_timeout=None,
            write_timeout=30,
            connect_timeout=30)

        try:
            # Keep the bot running
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot stopped")
        finally:
            await application.stop()

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        # Run the bot
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown complete")
