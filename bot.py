import logging
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import CommandHandler

BOT_INFO = {
    'name': 'Direktori Ekspor Impor',
    'username': 'kancilglobalbot'
}

class TelegramBot:
    def __init__(self):
        self.command_handler = CommandHandler()
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self._register_handlers()
        self._set_commands()
        logging.info("Bot initialized")

    def _set_commands(self):
        """Set bot commands with descriptions"""
        commands = [
            ('start', 'Mulai bot dan lihat menu utama'),
            ('saved', 'Lihat daftar kontak tersimpan'),
            ('credits', 'Cek sisa kredit dan beli kredit'),
            ('help', 'Panduan lengkap')
        ]
        self.application.bot.set_my_commands(commands)

    def _register_handlers(self):
        """Register command handlers"""
        # Register commands with explicit filters
        from telegram.ext import filters, MessageHandler
        # Add both command and message handlers for /start
        self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        self.application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("help", self.command_handler.help, filters.COMMAND))
        self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved, filters.COMMAND))
        self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits, filters.COMMAND))
        self.application.add_handler(TelegramCommandHandler("givecredits", self.command_handler.give_credits, filters.COMMAND))
        self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

    def get_application(self):
        """Get the configured application instance"""
        return self.application