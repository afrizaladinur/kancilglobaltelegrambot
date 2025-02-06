import logging
import asyncio
from bot import TelegramBot
from app import app

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

async def run_bot():
    """Setup and run the Telegram bot"""
    try:
        bot = TelegramBot()
        await bot.setup()
        application = bot.get_application()

        logger.info("Starting bot...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)

        try:
            await application.updater.stop_on_signal()
        except Exception as e:
            logger.error(f"Error in bot polling: {str(e)}")
        finally:
            logger.info("Stopping bot...")
            await application.stop()
            await application.shutdown()

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