import logging
import asyncio
from bot import TelegramBot
from app import app
import os
from flask import request, Response

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

@app.route('/health')
def health_check():
    return "OK"

# Single webhook route
@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming updates from Telegram"""
    try:
        if request.is_json:
            update = request.get_json()
            # Pass update to bot application
            await app.bot.application.update_queue.put(update)
            return Response('', status=200)
        return Response('', status=400)
    except Exception as e:
        logger.error(f"Error in webhook handler: {str(e)}")
        return Response('', status=500)

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

        # Get Replit domain from environment
        replit_domain = os.environ.get('REPLIT_DOMAIN')
        if not replit_domain:
            logger.error("REPLIT_DOMAIN environment variable is missing")
            raise ValueError("REPLIT_DOMAIN environment variable is missing")

        # Construct webhook URL using the actual Replit domain
        webhook_url = f"https://{replit_domain}/webhook"
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
            app.run(host='0.0.0.0', port=8080)

        Thread(target=run_flask, daemon=True).start()

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