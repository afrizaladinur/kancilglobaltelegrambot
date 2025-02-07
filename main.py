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

@app.route('/health')
def health_check():
    return "OK"

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

        # Get the Replit deployment URL
        repl_owner = os.environ.get('REPL_OWNER')
        repl_slug = os.environ.get('REPL_SLUG')

        if not repl_owner or not repl_slug:
            logger.error("REPL_OWNER or REPL_SLUG not found. Please run this in a Replit environment.")
            return

        # Use the .repl.co domain for webhook
        domain = f"{repl_slug}.{repl_owner}.repl.co"
        webhook_url = f"https://{domain}/webhook"
        logger.info(f"Setting webhook URL to: {webhook_url}")

        # Initialize application
        await application.initialize()
        await application.start()

        # Setup webhook
        try:
            # Remove existing webhook first
            logger.info("Removing existing webhook...")
            await application.bot.delete_webhook()

            # Set new webhook with HTTPS URL
            logger.info(f"Setting new webhook to {webhook_url}...")
            success = await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=["message", "callback_query"]
            )
            if success:
                logger.info("Webhook setup completed successfully")
            else:
                logger.error("Failed to set webhook")
                return
        except Exception as e:
            logger.error(f"Webhook setup failed: {str(e)}")
            raise

        # Start Flask server with SSL
        try:
            app.run(
                host='0.0.0.0',
                port=8443,
                ssl_context='adhoc',  # Use automatic SSL certificate
                debug=False
            )
        except Exception as e:
            logger.error(f"Flask server error: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Run the bot
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown complete")