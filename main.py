import logging
import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from bot import TelegramBot
from monitoring import monitor
from data_store import DataStore
from prometheus_client import start_http_server
from config import BOT_TOKEN

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

async def setup_webhook(bot: Bot):
    """Setup webhook handler"""
    try:
        replit_slug = os.getenv('REPL_SLUG')
        if replit_slug:
            webhook_base = f"https://{replit_slug}.repl.co"
            webhook_path = f"/webhook/{BOT_TOKEN}"
            webhook_url = f"{webhook_base}{webhook_path}"

            logger.info(f"Setting up webhook to {webhook_url}")

            # Wrap the webhook operations in a single task
            async def webhook_operations():
                async with bot.session:
                    # First delete existing webhook
                    await bot.delete_webhook(drop_pending_updates=True)
                    # Then set new webhook
                    await bot.set_webhook(webhook_url)

            # Create and run the task with timeout
            await asyncio.wait_for(webhook_operations(), timeout=30.0)
            logger.info("Webhook setup completed successfully")

    except asyncio.TimeoutError:
        logger.error("Webhook setup timed out")
        raise
    except Exception as e:
        logger.error(f"Error in webhook setup: {str(e)}")
        monitor.log_error(e, context={'stage': 'webhook_setup'})
        raise

async def on_startup(app: web.Application):
    """Startup handler"""
    try:
        bot_instance = app['bot_instance']
        if bot_instance and bot_instance.bot:
            await setup_webhook(bot_instance.bot)
    except Exception as e:
        logger.error(f"Error in startup: {e}")
        monitor.log_error(e, context={'stage': 'startup'})

async def on_shutdown(app: web.Application):
    """Shutdown handler"""
    try:
        if 'bot_instance' in app:
            bot = app['bot_instance'].bot
            await bot.delete_webhook()
            await bot.session.close()
        if 'data_store' in app:
            await app['data_store'].close()
        logger.info("Cleaned up connections")
    except Exception as e:
        logger.error(f"Error in shutdown: {e}")
        monitor.log_error(e, context={'stage': 'shutdown'})

async def create_app():
    """Initialize services and setup web application"""
    try:
        # Start metrics server
        start_http_server(8000)
        logger.info("Metrics server started")

        # Initialize bot
        bot_instance = TelegramBot()
        await bot_instance.init()
        logger.info("Bot initialized")

        # Initialize database
        data_store = DataStore()
        await data_store.init_pool()
        logger.info("Database initialized")

        # Create web application
        app = web.Application()

        # Store instances
        app['bot_instance'] = bot_instance
        app['data_store'] = data_store

        # Setup webhook handler
        webhook_handler = SimpleRequestHandler(
            dispatcher=bot_instance.dp,
            bot=bot_instance.bot
        )

        # Register webhook handler
        webhook_handler.register(app, path=f"/webhook/{BOT_TOKEN}")

        # Add lifecycle handlers
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)

        # Add health check endpoint
        app.router.add_get('/', lambda r: web.Response(text='Telegram Bot Service Status: Running'))

        return app
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        monitor.log_error(e, context={'stage': 'app_creation'})
        raise

if __name__ == '__main__':
    try:
        # Create and configure event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create and run application
        app = loop.run_until_complete(create_app())
        web.run_app(app, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        monitor.log_error(e, context={'stage': 'startup'})
    finally:
        logger.info("Application shutdown complete")