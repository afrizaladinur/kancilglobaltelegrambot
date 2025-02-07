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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'telegram_bot.lock')

def kill_existing_bot_processes():
    """Kill any existing Python processes running the bot"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid != os.getpid():  # Don't kill ourselves
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
        # Kill any existing bot processes first
        kill_existing_bot_processes()

        # Clean up any existing lock file
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                logger.info("Removed old lock file")
            except OSError as e:
                logger.warning(f"Error removing lock file: {e}")

        # Open the lock file in exclusive mode
        lock_fd = open(LOCK_FILE, 'w')

        try:
            # Try to acquire an exclusive lock
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write current PID to file
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            os.fsync(lock_fd.fileno())  # Ensure PID is written to disk
            logger.info(f"Lock acquired by process {os.getpid()}")
            yield
        except (IOError, OSError) as e:
            logger.error(f"Could not acquire lock: {e}")
            raise RuntimeError("Could not acquire bot lock")

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
        # Monitor system state before cleanup
        health_status = monitor.get_system_health()
        logger.info(f"System health before cleanup: {health_status}")

        # Kill any existing bot processes first
        kill_existing_bot_processes()

        if bot:
            # First, try to stop all running tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()

            # Wait for tasks to complete with timeout
            if tasks:
                await asyncio.wait(tasks, timeout=10)

            # Then cleanup the bot
            await bot.cleanup()

            # Wait for cleanup to complete and verify
            cleanup_timeout = 15  # Increased timeout to 15 seconds
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < cleanup_timeout:
                if not bot._current_application or (
                    hasattr(bot._current_application, 'updater') and 
                    not bot._current_application.updater.running
                ):
                    break
                await asyncio.sleep(1)
            logger.info("Bot cleanup completed")
    except Exception as e:
        monitor.log_error(e, context={'stage': 'cleanup', 'signal': signal_received})
    finally:
        logger.info("Cleanup completed")
        # Ensure lock file is removed during cleanup
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception as e:
                monitor.log_error(e, context={'stage': 'lock_file_cleanup'})

async def run_bot():
    """Setup and run the Telegram bot with improved instance management"""
    bot = None
    try:
        with file_lock():
            # Monitor system health at startup
            health_status = monitor.get_system_health()
            logger.info(f"Initial system health: {health_status}")

            # Kill any existing processes and wait for cleanup
            kill_existing_bot_processes()
            await asyncio.sleep(5)  # Wait for processes to fully terminate

            logger.info("Starting bot initialization...")

            # Initialize bot as singleton
            bot = TelegramBot()

            # Setup bot with proper error handling
            try:
                await bot.setup()
            except Exception as e:
                monitor.log_error(e, context={'stage': 'bot_setup'})
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

            # Start the bot with enhanced monitoring
            await application.initialize()
            await application.start()

            # Ensure clean startup
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)  # Brief pause after webhook deletion

            # Start polling with optimized settings
            await application.updater.start_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True,
                read_timeout=30,
                write_timeout=30,
                pool_timeout=30,
                connect_timeout=30,
                bootstrap_retries=3
            )

            logger.info("Bot started successfully")

            # Periodic health checks
            while True:
                await asyncio.sleep(300)  # Check every 5 minutes
                health_status = monitor.get_system_health()
                db_health = monitor.check_database_health()
                logger.info(f"Health check - System: {health_status}, Database: {db_health}")

    except asyncio.CancelledError:
        logger.info("Bot operation cancelled")
    except Exception as e:
        monitor.log_error(e, context={'stage': 'main_loop'})
        raise
    finally:
        if bot:
            await cleanup(bot)

async def run_bot_with_retries():
    """Run the bot with retries"""
    retry_count = 0
    max_retries = 3
    while retry_count < max_retries:
        try:
            await run_bot()
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"Bot run attempt {retry_count} failed: {str(e)}")
            if retry_count < max_retries:
                logger.info(f"Retrying in 5 seconds...")
                await asyncio.sleep(5)
                continue
            raise

if __name__ == '__main__':
    try:
        # Kill any existing processes before starting
        kill_existing_bot_processes()

        # Clean up any stale lock file
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception as e:
                logger.error(f"Error removing stale lock file: {e}")

        # Run the bot with asyncio
        asyncio.run(run_bot_with_retries())

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}", exc_info=True)
    finally:
        logger.info("Application shutdown complete")