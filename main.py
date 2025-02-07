import logging
import asyncio
from bot import TelegramBot
from app import app
import os

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
        # Set bot instance in app
        from app import app
        import app as app_module
        app_module.bot = bot

        # Get Replit domain
        repl_slug = os.environ.get('REPL_SLUG')
        repl_owner = os.environ.get('REPL_OWNER')
        webhook_url = f"https://{repl_slug}.{repl_owner}.repl.co/webhook"
        logger.info(f"Setting webhook URL to: {webhook_url}")

        logger.info(f"Starting bot with webhook at {webhook_url}")
        await application.initialize()
        await application.start()

        # Remove any existing webhook
        await application.bot.delete_webhook()
        # Set webhook
        await application.bot.set_webhook(webhook_url)

        # Start webhook server
        await application.run_webhook(
            listen="0.0.0.0",
            port=8080,
            url_path="webhook",
            webhook_url=webhook_url
        )

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot stopped")
            await application.bot.delete_webhook()
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