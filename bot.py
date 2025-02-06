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
                if self._current_application:
                    await self.cleanup()
                    await asyncio.sleep(2)  # Wait for cleanup to complete

                self._current_application = ApplicationBuilder().token(BOT_TOKEN).build()
                self._register_handlers()
                logging.info("Bot application initialized successfully")
                return self._current_application
            except Exception as e:
                logging.error(f"Error initializing application: {str(e)}")
                raise

    async def cleanup(self):
        """Cleanup bot resources with proper locking"""
        async with self._lock:
            if self._current_application:
                try:
                    # Stop polling first
                    if hasattr(self._current_application, 'updater') and self._current_application.updater.running:
                        await self._current_application.updater.stop()
                        logging.info("Polling stopped successfully")

                    # Then stop and shutdown the application
                    await self._current_application.stop()
                    await self._current_application.shutdown()
                    self._current_application = None
                    self._polling_start_time = None
                    logging.info("Bot resources cleaned up successfully")
                except Exception as e:
                    logging.error(f"Error during cleanup: {str(e)}")
                    raise

    async def setup(self):
        """Async setup operations with proper initialization"""
        try:
            self.application = await self.initialize_application()
            await self._set_commands()
            self._polling_start_time = asyncio.get_event_loop().time()
            logging.info("Bot setup completed successfully")
        except Exception as e:
            logging.error(f"Error in setup: {str(e)}")
            await self.cleanup()
            raise

    async def _set_commands(self):
        """Set bot commands with descriptions"""
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")

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
        except Exception as e:
            logging.error(f"Error setting commands: {str(e)}")
            raise

    def _register_handlers(self):
        """Register command handlers"""
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

    def get_application(self):
        """Get the configured application instance"""
        if not self._current_application:
            raise RuntimeError("Bot application not initialized")
        return self._current_application