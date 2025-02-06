import logging
import asyncio
from bot import TelegramBot
from app import app

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def cleanup(application):
    """Handle cleanup of the application"""
    try:
        await application.stop()
        await application.shutdown()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

async def run_bot():
    """Setup and run the Telegram bot"""
    try:
        # Initialize bot
        bot = TelegramBot()
        await bot.setup()
        application = bot.get_application()

        logger.info("Starting bot...")
        # Ensure clean startup
        await application.initialize()
        await application.start()

        try:
            # Keep the bot running
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot stopped")
        finally:
            await cleanup(application)

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
        raise