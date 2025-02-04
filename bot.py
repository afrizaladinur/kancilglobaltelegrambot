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
            ('search', 'Cari importir berdasarkan nama/negara/kode HS'),
            ('saved', 'Lihat daftar kontak yang tersimpan'),
            ('credits', 'Cek sisa kredit dan beli kredit'),
            ('stats', 'Lihat statistik penggunaan'),
            ('help', 'Tampilkan panduan lengkap')
        ]
        self.application.bot.set_my_commands(commands)

    def _register_handlers(self):
        """Register command handlers"""
        self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("help", self.command_handler.help))
        self.application.add_handler(TelegramCommandHandler("search", self.command_handler.search))
        self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
        self.application.add_handler(TelegramCommandHandler("stats", self.command_handler.stats))
        self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
        self.application.add_handler(TelegramCommandHandler("givecredits", self.command_handler.give_credits))
        self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))

    def get_application(self):
        """Get the configured application instance"""
        return self.application