import logging
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import CommandHandler
from telegram.ext import filters, MessageHandler
from telegram import BotCommand

BOT_INFO = {
    'name': 'Direktori Ekspor Impor',
    'username': 'kancilglobalbot'
}

class TelegramBot:
    def __init__(self):
        self.command_handler = CommandHandler()
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self._register_handlers()
        logging.info("Bot initialized")

    async def setup(self):
        """Async setup operations"""
        await self._set_commands()

    async def _set_commands(self):
        """Set bot commands with descriptions"""
        # First, delete all existing commands
        await self.application.bot.delete_my_commands()

        # Then set new commands
        commands = [
            BotCommand('start', '🏠 Menu Utama'),
            BotCommand('saved', '📁 Kontak Tersimpan'),
            BotCommand('credits', '💳 Kredit Saya')
        ]
        await self.application.bot.set_my_commands(commands)

    def _register_handlers(self):
        """Register command handlers"""
        # Only register the three essential command handlers
        self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
        self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))

        # Add the text handler for /start as fallback
        self.application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))

        # Add callback query handler for button interactions
        self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

    def get_application(self):
        """Get the configured application instance"""
        return self.application