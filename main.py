import logging
import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from bot import TelegramBot
from monitoring import monitor
from data_store import DataStore
from prometheus_client import start_http_server

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

async def setup_webhook(app: web.Application, bot: Bot):
    """Setup webhook after server is running"""
    try:
        replit_slug = os.getenv('REPL_SLUG')
        if not replit_slug:
            logger.warning("REPL_SLUG not found, using default webhook URL")
            return

        webhook_base = f"https://{replit_slug}.repl.co"
        webhook_path = f"/webhook/{bot.token}"
        webhook_url = f"{webhook_base}{webhook_path}"

        # Try to set webhook
        try:
            await bot.delete_webhook()  # Clear any existing webhook
            await bot.set_webhook(webhook_url)
            logger.info(f"Webhook set successfully to {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            # Continue running even if webhook fails - it can be set up later
            pass
    except Exception as e:
        logger.error(f"Error in webhook setup: {e}")

async def on_startup(app: web.Application):
    """Startup handler"""
    if 'bot_instance' in app:
        await setup_webhook(app, app['bot_instance'].bot)

async def on_shutdown(app: web.Application):
    """Cleanup on shutdown"""
    try:
        if 'bot_instance' in app:
            await app['bot_instance'].bot.session.close()
            await app['bot_instance'].bot.delete_webhook()
        if 'data_store' in app:
            await app['data_store'].close()
        logger.info("Cleaned up bot session and connections")
    except Exception as e:
        logger.error(f"Error in shutdown: {e}")

async def create_app():
    """Create and configure application"""
    try:
        # Start metrics server
        start_http_server(8000)
        logger.info("Metrics server started")

        # Initialize bot first
        bot_instance = TelegramBot()
        await bot_instance.init()
        logger.info("Bot initialized")

        # Initialize database
        data_store = DataStore()
        await data_store.init_pool()
        logger.info("Database initialized")

        # Create web application
        app = web.Application()

        # Store instances in app context
        app['bot_instance'] = bot_instance
        app['data_store'] = data_store

        # Configure webhook handler
        webhook_handler = SimpleRequestHandler(
            dispatcher=bot_instance.dp,
            bot=bot_instance.bot
        )

        # Register webhook handler with a dynamic path
        webhook_handler.register(app, path=f"/webhook/{bot_instance.bot.token}")

        # Add lifecycle handlers
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)

        # Add health check endpoint
        app.router.add_get('/', lambda r: web.Response(text='Telegram Bot Service Status: Running'))

        return app

    except Exception as e:
        logger.error(f"Error creating application: {e}")
        monitor.log_error(e, context={'stage': 'startup'})
        raise

def main():
    """Application entry point"""
    try:
        app = asyncio.run(create_app())
        web.run_app(app, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        monitor.log_error(e, context={'stage': 'startup'})
    finally:
        logger.info("Application shutdown complete")

if __name__ == '__main__':
    main()