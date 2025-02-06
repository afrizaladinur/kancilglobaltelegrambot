import logging
import asyncio
import signal
from bot import TelegramBot
from app import app

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

async def cleanup(bot, signal_received=None):
    """Cleanup function to properly shutdown the bot"""
    if signal_received:
        logger.info(f"Received signal: {signal_received}")
    logger.info("Starting cleanup...")
    try:
        await bot.cleanup()
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    finally:
        logger.info("Cleanup completed")

async def run_bot():
    """Setup and run the Telegram bot"""
    try:
        # Initialize bot as singleton
        bot = TelegramBot()
        await bot.setup()
        application = bot.get_application()

        # Set up signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(cleanup(bot, s))
            )

        logger.info("Starting bot...")
        # Ensure clean startup
        await application.initialize()
        await application.start()

        # Clear any existing updates and set up polling
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.updater.start_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )

        try:
            # Keep the bot running
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot operation cancelled")
        finally:
            await cleanup(bot)

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