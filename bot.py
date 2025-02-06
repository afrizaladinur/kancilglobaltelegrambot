import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import BOT_TOKEN
from handlers import CommandHandler
from telegram.ext import filters, MessageHandler
from telegram import BotCommand

BOT_INFO = {
    'name': 'Direktori Ekspor Impor',
    'username': 'kancilglobalbot'
}

class TelegramBot:
    _instance = None
    _initialized = False
    _lock = asyncio.Lock()
    _current_application = None
    _polling_start_time = None
    _retry_count = 0
    _max_retries = 3

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.command_handler = CommandHandler()
            self._initialized = True
            logging.info("Bot initialized as singleton instance")

    async def initialize_application(self):
        """Initialize the bot application with proper locking and retry mechanism"""
        async with self._lock:
            try:
                # Force cleanup of any existing instance
                if self._current_application:
                    logging.info("Cleaning up existing application before initialization")
                    await self.cleanup()
                    await asyncio.sleep(5)  # Increased wait time for cleanup

                logging.info("Starting fresh application initialization")
                self._polling_start_time = None
                self._retry_count = 0

                while self._retry_count < self._max_retries:
                    try:
                        # Initialize application with higher timeouts and better retry settings
                        self._current_application = (
                            ApplicationBuilder()
                            .token(BOT_TOKEN)
                            .connect_timeout(30)
                            .read_timeout(30)
                            .write_timeout(30)
                            .pool_timeout(30)
                            .get_updates_read_timeout(30)
                            .build()
                        )

                        # Ensure webhook is deleted
                        await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                        await asyncio.sleep(2)  # Wait for webhook deletion

                        self._register_handlers()
                        logging.info("Bot application initialized successfully")
                        return self._current_application

                    except Exception as e:
                        self._retry_count += 1
                        logging.error(f"Initialization attempt {self._retry_count} failed: {str(e)}")
                        if self._retry_count < self._max_retries:
                            await asyncio.sleep(5)  # Wait before retry
                            continue
                        raise

            except Exception as e:
                logging.error(f"Error initializing application: {str(e)}")
                # Attempt cleanup on initialization failure
                if self._current_application:
                    try:
                        await self.cleanup()
                    except:
                        pass
                raise

    async def cleanup(self):
        """Cleanup bot resources with proper locking and verification"""
        async with self._lock:
            if self._current_application:
                try:
                    logging.info("Starting application cleanup")
                    # Stop polling first if it's running
                    if hasattr(self._current_application, 'updater') and self._current_application.updater.running:
                        logging.info("Stopping updater...")
                        await self._current_application.updater.stop()
                        logging.info("Updater stopped successfully")

                    # Then stop and shutdown the application
                    if hasattr(self._current_application, 'stop'):
                        await self._current_application.stop()
                    if hasattr(self._current_application, 'shutdown'):
                        await self._current_application.shutdown()

                    # Force delete webhook one last time
                    try:
                        await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                    except:
                        pass

                    # Clear the application instance
                    self._current_application = None
                    self._polling_start_time = None
                    self._retry_count = 0
                    logging.info("Bot resources cleaned up successfully")
                except Exception as e:
                    logging.error(f"Error during cleanup: {str(e)}")
                    raise

    async def setup(self):
        """Async setup operations with proper initialization and retry mechanism"""
        try:
            self.application = await self.initialize_application()
            await self._set_commands()
            self._polling_start_time = asyncio.get_event_loop().time()
            logging.info("Bot setup completed successfully")
        except Exception as e:
            logging.error(f"Error in setup: {str(e)}")
            await self.cleanup()
            raise

    async def wait_for_cleanup(self):
        """Wait for any existing bot instance to cleanup with improved verification"""
        retry_count = 0
        max_retries = 5  # Increased retries
        retry_delay = 3  # Increased delay

        while retry_count < max_retries:
            try:
                if self._current_application and hasattr(self._current_application, 'updater'):
                    if self._current_application.updater.running:
                        logging.info(f"Attempt {retry_count + 1}: Cleaning up running instance")
                        await self.cleanup()
                        await asyncio.sleep(retry_delay)
                    else:
                        return True
                else:
                    return True
            except Exception as e:
                logging.warning(f"Cleanup attempt {retry_count + 1} failed: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(retry_delay)

        return False

    def get_application(self):
        """Get the configured application instance"""
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")
        return self._current_application

    async def _set_commands(self):
        """Set bot commands with descriptions and proper error handling"""
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # First, delete all existing commands
                await self._current_application.bot.delete_my_commands()

                # Then set new commands
                commands = [
                    BotCommand('start', '🏠 Menu Utama'),
                    BotCommand('saved', '📁 Kontak Tersimpan'),
                    BotCommand('credits', '💳 Kredit Saya')
                ]
                await self._current_application.bot.set_my_commands(commands)
                logging.info("Bot commands registered successfully")
                break
            except Exception as e:
                retry_count += 1
                logging.error(f"Error setting commands (attempt {retry_count}): {str(e)}")
                if retry_count < max_retries:
                    await asyncio.sleep(2)
                else:
                    raise

    def _register_handlers(self):
        """Register command handlers with proper error checking"""
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

        try:
            # Register handlers
            self._current_application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self._current_application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self._current_application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self._current_application.add_handler(TelegramCommandHandler("orders", self.command_handler.orders))

            # Add the text handler for /start as fallback
            self._current_application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))

            # Add callback query handler for button interactions
            self._current_application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {str(e)}")
            raise