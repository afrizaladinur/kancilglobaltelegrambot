import logging
from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, CallbackQueryHandler
from telegram.ext import filters, MessageHandler
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
        logging.info("Bot initialized")

    async def _set_commands(self):
        try:
            commands = [
                ('start', 'Mulai bot dan lihat menu utama'),
                ('search', 'Cari importir berdasarkan nama/negara/kode HS'),
                ('saved', 'Lihat daftar kontak yang tersimpan'),
                ('credits', 'Cek sisa kredit dan beli kredit'),
                ('stats', 'Lihat statistik penggunaan'),
                ('help', 'Tampilkan panduan lengkap')
            ]
            await self.application.bot.set_my_commands(commands)
            logging.info("Bot commands set successfully")
        except Exception as e:
            logging.error(f"Error setting bot commands: {e}")
            raise

    def _register_handlers(self):
        try:
            self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self.application.add_handler(MessageHandler(filters.Text(['/start']), self.command_handler.start))
            self.application.add_handler(TelegramCommandHandler("help", self.command_handler.help))
            self.application.add_handler(TelegramCommandHandler("search", self.command_handler.search))
            self.application.add_handler(TelegramCommandHandler("saved", self.command_handler.saved))
            self.application.add_handler(TelegramCommandHandler("stats", self.command_handler.stats))
            self.application.add_handler(TelegramCommandHandler("credits", self.command_handler.credits))
            self.application.add_handler(TelegramCommandHandler("givecredits", self.command_handler.give_credits))
            self.application.add_handler(CallbackQueryHandler(self.command_handler.button_callback))
            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {e}")
            raise

    def get_application(self):
        return self.application

    async def setup(self):
        try:
            await self._set_commands()
        except Exception as e:
            logging.error(f"Error in bot setup: {e}")
            raise