import logging
import asyncio
from telegram.ext import Application, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
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
        """Initialize the bot application with proper locking"""
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

                # Delete any webhook first
                temp_app = Application.builder().token(BOT_TOKEN).build()
                await temp_app.bot.delete_webhook(drop_pending_updates=True)
                await temp_app.shutdown()
                await asyncio.sleep(2)

                # Create new application with error handlers
                self._current_application = (
                    Application.builder()
                    .token(BOT_TOKEN)
                    .connect_timeout(30)
                    .read_timeout(30)
                    .write_timeout(30)
                    .pool_timeout(30)
                    .get_updates_read_timeout(30)
                    .concurrent_updates(True)
                    .build()
                )

                # Delete webhook again to ensure clean polling
                await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(2)

                # Setup handlers and commands
                self._register_handlers()
                await self._set_commands()
                logging.info("Bot application initialized successfully")
                return self._current_application

            except Exception as e:
                logging.error(f"Fatal error in initialization: {str(e)}")
                if self._current_application:
                    await self.cleanup()
                raise

    async def cleanup(self):
        """Cleanup bot resources with proper verification"""
        async with self._lock:
            if self._current_application:
                try:
                    logging.info("Starting application cleanup")
                    # Stop polling first
                    if hasattr(self._current_application, 'updater') and self._current_application.updater.running:
                        await self._current_application.updater.stop()
                        await asyncio.sleep(2)

                    # Stop and shutdown application
                    await self._current_application.stop()
                    await self._current_application.shutdown()

                    # Ensure webhook is deleted
                    try:
                        await self._current_application.bot.delete_webhook(drop_pending_updates=True)
                    except Exception as e:
                        logging.warning(f"Error deleting webhook during cleanup: {e}")

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

        commands = [
            BotCommand('start', '🏠 Menu Utama'),
            BotCommand('saved', '📁 Kontak Tersimpan'),
            BotCommand('credits', '💳 Kredit Saya')
        ]
        await self._current_application.bot.set_my_commands(commands)
        logging.info("Bot commands registered successfully")

    def _register_handlers(self):
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

        try:
            # Clear existing handlers if any
            if hasattr(self._current_application, 'handlers'):
                self._current_application.handlers.clear()

            # Register handlers
            self._current_application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self._current_application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self._current_application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self._current_application.add_handler(TelegramCommandHandler("orders", self.command_handler.orders))

            # Add fallback handler
            self._current_application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^/start$'), self.command_handler.start))

            # Add callback query handler
            self._current_application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

            # Set error handler
            self._current_application.add_error_handler(self._error_handler)

            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {str(e)}")
            raise

    async def _error_handler(self, update, context):
        """Global error handler for the bot"""
        logging.error(f"Update {update} caused error: {context.error}")