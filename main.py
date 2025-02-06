import logging
import asyncio
import signal
import os
import tempfile
import fcntl
from contextlib import contextmanager
from bot import TelegramBot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'telegram_bot.lock')

@contextmanager
def file_lock():
    """Process-level lock using file locking with improved error handling"""
    lock_fd = None
    try:
        # Open the lock file in exclusive mode
        lock_fd = open(LOCK_FILE, 'w')

        try:
            # Try to acquire an exclusive lock
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write PID to file
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            os.fsync(lock_fd.fileno())  # Ensure PID is written to disk
            logger.info(f"Lock acquired by process {os.getpid()}")
            yield
        except (IOError, OSError) as e:
            logger.error(f"Could not acquire lock: {e}")
            # Check if another process holds the lock
            try:
                with open(LOCK_FILE, 'r') as f:
                    other_pid = f.read().strip()
                    logger.error(f"Lock is held by process {other_pid}")
            except:
                pass
            raise RuntimeError("Another bot instance is already running")

    except Exception as e:
        logger.error(f"Error with lock file: {e}")
        raise
    finally:
        if lock_fd:
            try:
                # Release the lock and close/remove the file
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                try:
                    os.remove(LOCK_FILE)
                except FileNotFoundError:
                    pass  # File might have been removed by another process
                logger.info("Lock released and file cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up lock: {e}")

async def cleanup(bot, signal_received=None):
    """Cleanup function to properly shutdown the bot"""
    if signal_received:
        logger.info(f"Received signal: {signal_received}")
    logger.info("Starting cleanup...")
    try:
        if bot:
            await bot.cleanup()
            # Wait for cleanup to complete and verify
            cleanup_timeout = 10  # 10 seconds timeout
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < cleanup_timeout:
                if not bot._current_application or not bot._current_application.updater.running:
                    break
                await asyncio.sleep(1)
            logger.info("Bot cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    finally:
        logger.info("Cleanup completed")
        # Ensure lock file is removed during cleanup
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception as e:
                logger.error(f"Error removing lock file during cleanup: {e}")

async def run_bot():
    """Setup and run the Telegram bot with improved instance management"""
    bot = None
    try:
        with file_lock():
            # Wait for any previous instances to fully shut down
            await asyncio.sleep(2)
            logger.info("Starting bot initialization...")

            # Initialize bot as singleton
            bot = TelegramBot()

            # Ensure previous instance is cleaned up
            if not await bot.wait_for_cleanup():
                logger.error("Failed to cleanup existing bot instance")
                return

            # Setup bot with proper error handling
            try:
                await bot.setup()
            except Exception as e:
                logger.error(f"Error during bot setup: {str(e)}")
                await cleanup(bot)
                return

            # Set up signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(cleanup(bot, s))
                )

            application = bot.get_application()

            # Ensure clean startup
            await application.initialize()
            await application.start()

            # Clear any existing updates and ensure webhook is deleted
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)  # Brief pause after webhook deletion

            # Start polling with proper error handling
            logger.info("Starting polling...")
            await application.updater.start_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True,
                read_timeout=30,
                write_timeout=30,
                pool_timeout=30,
                connect_timeout=30
            )

            logger.info("Bot started successfully")

            # Keep the bot running
            while True:
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Bot operation cancelled")
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise
    finally:
        if bot:
            await cleanup(bot)

if __name__ == '__main__':
    try:
        # Cleanup any stale lock file before starting
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception as e:
                logger.error(f"Error removing stale lock file: {e}")

        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
    finally:
        logger.info("Application shutdown complete")