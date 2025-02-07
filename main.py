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

        # Get Replit domain from environment, with fallbacks
        replit_domain = os.environ.get('REPLIT_DOMAIN')
        replit_slug = os.environ.get('REPLIT_SLUG')

        if replit_domain:
            domain = replit_domain
        elif replit_slug:
            domain = f"{replit_slug}.repl.co"
        else:
            logger.error("No valid domain found for webhook setup")
            raise ValueError("Missing required domain configuration")

        # Construct webhook URL
        webhook_url = f"https://{domain}/webhook"
        logger.info(f"Setting webhook URL to: {webhook_url}")

        # Initialize application
        await application.initialize()
        await application.start()

        # Setup webhook in a task
        async def setup_webhook():
            try:
                # Remove existing webhook
                logger.info("Removing existing webhook...")
                await application.bot.delete_webhook()

                # Set new webhook
                logger.info(f"Setting new webhook to {webhook_url}...")
                success = await application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query"]
                )
                if success:
                    logger.info("Webhook setup completed successfully")
                else:
                    raise ValueError("Failed to set webhook")
            except Exception as e:
                logger.error(f"Webhook setup failed: {str(e)}")
                raise

        # Create and run webhook setup task with timeout
        webhook_task = asyncio.create_task(setup_webhook())
        try:
            await asyncio.wait_for(webhook_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Webhook setup timed out")
            raise
        except Exception as e:
            logger.error(f"Error in webhook setup: {str(e)}")
            raise

        # Start Flask server in a separate thread
        from threading import Thread
        def run_flask():
            try:
                app.run(
                    host='0.0.0.0',
                    port=8443,
                    ssl_context='adhoc',
                    debug=False  # Disable debug mode in production
                )
            except Exception as e:
                logger.error(f"Flask server error: {str(e)}")
                raise

        Thread(target=run_flask, daemon=True).start()
        logger.info("Flask server started successfully")

        # Keep the bot running
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