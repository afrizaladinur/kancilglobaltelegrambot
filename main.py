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
        # Add a small delay to ensure cleanup is complete
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    finally:
        logger.info("Cleanup completed")

async def run_bot():
    """Setup and run the Telegram bot"""
    try:
        # Add initial delay to ensure any previous instances are cleaned up
        await asyncio.sleep(5)
        logger.info("Starting bot initialization...")

        # Initialize bot as singleton
        bot = TelegramBot()
        await bot.setup()

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(cleanup(bot, s))
            )

        application = bot.get_application()

        # Ensure clean startup
        await application.initialize()
        await application.start()

        # Clear any existing updates and ensure webhook is deleted
        await application.bot.delete_webhook(drop_pending_updates=True)
        # Add a small delay before starting polling
        await asyncio.sleep(2)

        # Start polling with proper error handling
        await application.updater.start_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True,
            close_loop=False  # Don't close the loop on stop
        )

        logger.info("Bot started successfully")

        # Keep the bot running
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Bot operation cancelled")
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise
    finally:
        await cleanup(bot)

if __name__ == '__main__':
    try:
        # Run the bot
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
    finally:
        logger.info("Application shutdown complete")