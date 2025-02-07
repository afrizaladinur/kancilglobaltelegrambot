import logging
import asyncio
import signal
import os
import tempfile
import fcntl
import psutil
from contextlib import contextmanager
from bot import TelegramBot
from monitoring import monitor
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from data_store import DataStore
from loguru import logger
from prometheus_client import start_http_server

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger.add("logs/main_{time}.log", rotation="1 day", retention="7 days")

logger = logging.getLogger(__name__)
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'telegram_bot.lock')

def kill_existing_bot_processes():
    """Kill any existing Python processes running the bot"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid != os.getpid():
                cmdline = ' '.join(proc.cmdline())
                if "python" in proc.name().lower() and "main.py" in cmdline:
                    logger.info(f"Terminating existing bot process (PID: {proc.pid})")
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    logger.info(f"Process {proc.pid} terminated")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

@contextmanager
def file_lock():
    """Process-level lock using file locking with improved process verification"""
    lock_fd = None
    try:
        kill_existing_bot_processes()

        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                logger.info("Removed old lock file")
            except OSError as e:
                logger.warning(f"Error removing lock file: {e}")

        lock_fd = open(LOCK_FILE, 'w')

        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            os.fsync(lock_fd.fileno())
            logger.info(f"Lock acquired by process {os.getpid()}")
            yield
        except (IOError, OSError) as e:
            logger.error(f"Could not acquire lock: {e}")
            raise RuntimeError("Could not acquire bot lock")

    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                try:
                    os.remove(LOCK_FILE)
                except FileNotFoundError:
                    pass
                logger.info("Lock released and file cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up lock: {e}")

async def setup_webhook(bot: Bot, base_url: str):
    """Configure webhook"""
    webhook_path = f"/webhook/{bot.token}"
    webhook_url = f"{base_url}{webhook_path}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    return webhook_path

async def shutdown(app):
    """Cleanup on shutdown"""
    bot = app['bot']
    data_store = app['data_store']
    await bot.delete_webhook()
    await data_store.close()
    logger.info("Bot and database connections closed")

def setup_app(bot_instance: TelegramBot, data_store: DataStore) -> web.Application:
    """Setup the web application with all routes and handlers"""
    app = web.Application()

    # Store instances in app
    app['bot'] = bot_instance.bot
    app['data_store'] = data_store

    # Add root route handler
    async def index_handler(request):
        return web.Response(
            text="Telegram Bot Service Status: Running",
            content_type='text/html'
        )

    app.router.add_get('/', index_handler)

    # Setup webhook handler
    webhook_handler = SimpleRequestHandler(
        dispatcher=bot_instance.dp,
        bot=bot_instance.bot,
    )

    # Register webhook handler
    webhook_handler.register(app, path=f"/webhook/{bot_instance.bot.token}")

    # Setup shutdown cleanup
    app.on_cleanup.append(shutdown)

    return app

async def init_services():
    """Initialize all services"""
    # Start Prometheus metrics server
    start_http_server(8000)
    logger.info("Metrics server started on port 8000")

    # Initialize database first
    data_store = DataStore()
    await data_store.init_pool()
    logger.info("Database pool initialized")

    # Initialize bot
    bot_instance = TelegramBot()
    await bot_instance.init()
    logger.info("Bot initialized")

    return bot_instance, data_store

def main():
    """Main application entry point with proper event loop handling"""
    try:
        # Initialize event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize services
        bot_instance, data_store = loop.run_until_complete(init_services())

        # Setup application
        app = setup_app(bot_instance, data_store)

        # Start the application
        logger.info("Starting webhook server")
        web.run_app(app, host='0.0.0.0', port=5000)

    except Exception as e:
        logger.exception(f"Error in main: {e}")
        monitor.log_error(e, context={'stage': 'startup'})
        raise
    finally:
        logger.info("Application shutdown complete")

if __name__ == '__main__':
    with file_lock():
        main()