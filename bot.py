import logging
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import CommandHandler

class TelegramBot:
    def __init__(self):
        self.command_handler = CommandHandler()
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self._register_handlers()
        logging.info("Bot initialized")

    def _register_handlers(self):
        """Register command handlers"""
        self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("help", self.command_handler.help))
        self.application.add_handler(TelegramCommandHandler("search", self.command_handler.search))
        self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
        self.application.add_handler(TelegramCommandHandler("stats", self.command_handler.stats))
        self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
        self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

    def get_application(self):
        """Get the configured application instance"""
        return self.application