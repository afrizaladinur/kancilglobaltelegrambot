import logging
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.command_handler = CommandHandler()
            self.application = ApplicationBuilder().token(BOT_TOKEN).build()
            self._register_handlers()
            self._initialized = True
            logging.info("Bot initialized as singleton instance")

    async def cleanup(self):
        """Cleanup bot resources"""
        if hasattr(self, 'application') and self.application:
            await self.application.stop()
            await self.application.shutdown()
            logging.info("Bot resources cleaned up")

    async def setup(self):
        """Async setup operations"""
        try:
            await self._set_commands()
            logging.info("Bot commands set up successfully")
        except Exception as e:
            logging.error(f"Error in setup: {str(e)}")
            await self.cleanup()
            raise

    async def _set_commands(self):
        """Set bot commands with descriptions"""
        try:
            # First, delete all existing commands
            await self.application.bot.delete_my_commands()

            # Then set new commands
            commands = [
                BotCommand('start', '🏠 Menu Utama'),
                BotCommand('saved', '📁 Kontak Tersimpan'),
                BotCommand('credits', '💳 Kredit Saya')
            ]
            await self.application.bot.set_my_commands(commands)
            logging.info("Bot commands registered successfully")
        except Exception as e:
            logging.error(f"Error setting commands: {str(e)}")
            raise

    def _register_handlers(self):
        """Register command handlers"""
        try:
            # Only register the essential command handlers
            self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self.application.add_handler(TelegramCommandHandler("orders", self.command_handler.orders))

            # Add the text handler for /start as fallback
            self.application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))

            # Add callback query handler for button interactions
            self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {str(e)}")
            raise

    def get_application(self):
        """Get the configured application instance"""
        return self.application