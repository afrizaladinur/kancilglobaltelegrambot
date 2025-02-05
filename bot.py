import logging
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import CommandHandler
from telegram.ext import filters, MessageHandler 
from telegram import BotCommand, CallbackQuery

BOT_INFO = {
    'name': 'Direktori Ekspor Impor',
    'username': 'kancilglobalbot'
}

class TelegramBot:
    def __init__(self):
        # Configure detailed logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.DEBUG
        )
        self.logger = logging.getLogger(__name__)
        self.command_handler = CommandHandler()
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self._register_handlers()
        self.logger.info("Bot initialized with handlers registered")

    async def setup(self):
        """Async setup operations"""
        try:
            await self._set_commands()
            self.logger.info("Bot commands setup completed")
        except Exception as e:
            self.logger.error(f"Error in setup: {str(e)}", exc_info=True)
            raise

    async def _set_commands(self):
        """Set bot commands with descriptions"""
        try:
            # First, delete all existing commands
            await self.application.bot.delete_my_commands()
            self.logger.debug("Existing commands deleted")

            # Then set new commands
            commands = [
                BotCommand('start', '🏠 Menu Utama'),
                BotCommand('saved', '📁 Kontak Tersimpan'),
                BotCommand('contacts', '📦 Kontak Tersedia'),
                BotCommand('credits', '💳 Kredit & Pembelian')
            ]
            await self.application.bot.set_my_commands(commands)
            self.logger.info("New commands registered successfully")
        except Exception as e:
            self.logger.error(f"Error setting commands: {str(e)}", exc_info=True)
            raise

    def _register_handlers(self):
        """Register command handlers"""
        try:
            # Only register the essential command handlers
            self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self.application.add_handler(TelegramCommandHandler("contacts", self.command_handler.contacts))
            self.application.add_handler(TelegramCommandHandler("orders", self.command_handler.orders))

            # Add the text handler for /start as fallback
            self.application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))

            # Add callback query handler for button interactions
            self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

            self.logger.info("All handlers registered successfully")
        except Exception as e:
            self.logger.error(f"Error registering handlers: {str(e)}", exc_info=True)
            raise

    def get_application(self):
        """Get the configured application instance"""
        return self.application