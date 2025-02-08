import logging
import asyncio
from bot import TelegramBot
from app import app
import os
from flask import request, Response
from functools import partial
import sys

# Configure logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

# Required environment variables
REQUIRED_ENV_VARS = [
    'TELEGRAM_TOKEN',
    'FLASK_SECRET_KEY',
    'DATABASE_URL',
    'PGDATABASE',
    'PGHOST',
    'PGPORT',
    'PGUSER',
    'PGPASSWORD'
]

def check_environment():
    """Verify all required environment variables are set"""
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}")
    return True

@app.route('/health')
def health_check():
    """Enhanced health check endpoint"""
    try:
        # Add basic checks here (e.g., database connection)
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}, 500

async def setup_webhook(application, webhook_url):
    """Setup webhook with retry logic"""
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
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
                return True
            raise ValueError("Failed to set webhook")

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Webhook setup attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"All webhook setup attempts failed: {str(e)}")
                raise

async def run_bot():
    """Setup and run the Telegram bot with enhanced error handling"""
    try:
        # Verify environment variables
        check_environment()

        # Initialize bot
        bot = TelegramBot()
        await bot.setup()
        application = bot.get_application()

        # Set bot instance in app
        from app import app
        import app as app_module
        app_module.bot = bot

        # Determine deployment URL
        if os.environ.get('WEBHOOK_DOMAIN'):
            domain = os.environ['WEBHOOK_DOMAIN']
        elif 'REPL_SLUG' in os.environ and 'REPL_OWNER' in os.environ:
            domain = f"{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.dev"
        else:
            port = int(os.environ.get('PORT', 80))
            domain = os.environ.get('REPL_HOSTNAME', f'0.0.0.0:{port}')

        webhook_url = f"https://{domain}/webhook"
        logger.info(f"Using webhook URL: {webhook_url}")

        # Initialize application
        await application.initialize()
        await application.start()

        # Setup webhook with timeout
        webhook_task = asyncio.create_task(setup_webhook(application, webhook_url))
        try:
            await asyncio.wait_for(webhook_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Webhook setup timed out")
            raise
        except Exception as e:
            logger.error(f"Error in webhook setup: {str(e)}")
            raise

        # Start Flask server
        def run_flask():
            port = int(os.environ.get('PORT', 8080))
            app.run(host='0.0.0.0', port=port, debug=False)

        from threading import Thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Keep the bot running with graceful shutdown
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Initiating graceful shutdown...")
            await application.bot.delete_webhook()
            await application.stop()
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error(f"Runtime error: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Critical error running bot: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        # Set up asyncio policy for Windows compatibility
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Application shutdown complete")