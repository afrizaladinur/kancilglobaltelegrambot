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
        await application.updater.start_polling(
            poll_interval=1.0,
            timeout=30,
            bootstrap_retries=5,
            read_timeout=30,
            write_timeout=30,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query', 'my_chat_member'],
            max_retries=3
        )

        try:
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
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown complete")