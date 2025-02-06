import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import BOT_TOKEN
from handlers import CommandHandler
from telegram.ext import filters, MessageHandler
from telegram import BotCommand
from telegram import Update
from telegram.ext import ContextTypes
import telegram

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
    _polling_lock = asyncio.Lock()

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
                # Force cleanup of any existing instance first
                if self._current_application:
                    logging.info("Cleaning up existing application before initialization")
                    await self.cleanup()
                    await asyncio.sleep(5)  # Wait for cleanup

                logging.info("Starting fresh application initialization")
                self._polling_start_time = None
                self._retry_count = 0

                # Delete any existing webhook first to ensure clean slate
                temp_app = ApplicationBuilder().token(BOT_TOKEN).build()
                await temp_app.bot.delete_webhook(drop_pending_updates=True)
                await temp_app.shutdown()
                await asyncio.sleep(2)

                while self._retry_count < self._max_retries:
                    try:
                        # Initialize application with higher timeouts
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

                        # Ensure clean slate for polling
                        async with self._polling_lock:
                            await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                            await asyncio.sleep(2)

                            try:
                                # Test get_updates without the unsupported parameter
                                await self._current_application.bot.get_updates(
                                    timeout=1,
                                    offset=-1,
                                    allowed_updates=['message', 'callback_query']
                                )
                                await asyncio.sleep(2)
                                break  # If successful, break the retry loop
                            except telegram.error.Conflict as e:
                                logging.warning(f"Polling conflict detected: {e}")
                                await self.cleanup()
                                await asyncio.sleep(5)
                                self._retry_count += 1
                                continue
                            except Exception as e:
                                logging.error(f"Get updates test failed: {e}")
                                await asyncio.sleep(5)
                                self._retry_count += 1
                                continue

                        # Setup handlers and commands
                        self._register_handlers()
                        await self._set_commands()
                        logging.info("Bot application initialized successfully")
                        return self._current_application

                    except Exception as e:
                        self._retry_count += 1
                        logging.error(f"Initialization attempt {self._retry_count} failed: {str(e)}")
                        if self._retry_count < self._max_retries:
                            await asyncio.sleep(5)
                            continue
                        raise

                if self._retry_count >= self._max_retries:
                    raise RuntimeError("Failed to initialize bot after maximum retries")

            except Exception as e:
                logging.error(f"Fatal error in initialization: {str(e)}")
                if self._current_application:
                    await self.cleanup()
                raise

    async def cleanup(self):
        """Cleanup bot resources with proper locking and verification"""
        async with self._lock:
            if self._current_application:
                try:
                    logging.info("Starting application cleanup")
                    # Stop polling first
                    if hasattr(self._current_application, 'updater') and self._current_application.updater.running:
                        await self._current_application.updater.stop()
                        await asyncio.sleep(2)

                    # Stop the application
                    if hasattr(self._current_application, 'stop'):
                        await self._current_application.stop()
                        await asyncio.sleep(1)
                    if hasattr(self._current_application, 'shutdown'):
                        await self._current_application.shutdown()
                        await asyncio.sleep(1)

                    # Ensure webhook is deleted
                    await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                    await asyncio.sleep(2)

                    # Clear instance
                    self._current_application = None
                    self._polling_start_time = None
                    self._retry_count = 0
                    logging.info("Bot cleanup completed successfully")
                except Exception as e:
                    logging.error(f"Error during cleanup: {str(e)}")
                    raise

    async def setup(self):
        try:
            self.application = await self.initialize_application()
            self._polling_start_time = asyncio.get_event_loop().time()
            logging.info("Bot setup completed successfully")
        except Exception as e:
            logging.error(f"Error in setup: {str(e)}")
            await self.cleanup()
            raise

    def get_application(self):
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")
        return self._current_application

    async def _set_commands(self):
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # Clear existing commands first
                await self._current_application.bot.delete_my_commands()
                await asyncio.sleep(1)

                # Set new commands
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
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

        try:
            # Clear existing handlers
            if hasattr(self._current_application, 'handlers'):
                self._current_application.handlers.clear()

            # Register handlers
            self._current_application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self._current_application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self._current_application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self._current_application.add_handler(TelegramCommandHandler("orders", self.command_handler.orders))

            # Add fallback handler
            self._current_application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))

            # Add callback query handler
            self._current_application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

            # Set error handler
            self._current_application.add_error_handler(self._error_handler)

            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {str(e)}")
            raise

    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for the bot"""
        logging.error(f"Update {update} caused error: {context.error}")
        if isinstance(context.error, telegram.error.Conflict):
            logging.error("Detected polling conflict, attempting cleanup...")
            await self.cleanup()
            await asyncio.sleep(5)  # Wait before potential restart

    async def wait_for_cleanup(self):
        """Wait for any existing bot instance to cleanup with improved verification"""
        retry_count = 0
        max_retries = 5
        retry_delay = 3

        while retry_count < max_retries:
            try:
                # Ensure no existing instance is running
                if self._current_application and hasattr(self._current_application, 'updater'):
                    if self._current_application.updater.running:
                        logging.info(f"Attempt {retry_count + 1}: Cleaning up running instance")
                        await self.cleanup()
                        await asyncio.sleep(retry_delay)

                # Verify no other instances are running
                async with self._polling_lock:
                    try:
                        temp_app = ApplicationBuilder().token(BOT_TOKEN).build()
                        await temp_app.bot.get_updates(timeout=1, offset=-1)
                        await temp_app.shutdown()
                        return True
                    except Exception as e:
                        logging.warning(f"Verification failed: {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            continue
                        return False

            except Exception as e:
                logging.warning(f"Cleanup attempt {retry_count + 1} failed: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(retry_delay)

        return False