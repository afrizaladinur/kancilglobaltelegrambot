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
        # Configure application with optimized connection settings
        self.application = (
            ApplicationBuilder()
            .token(TELEGRAM_TOKEN)
            .concurrent_updates(True)
            .pool_timeout(60)
            .connection_pool_size(128)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .get_updates_read_timeout(30.0)
            .connect_retry_delay(1.0)  # Added retry delay
            .connect_attempts(3)      # Added retry attempts
            .build()
        )
        self.command_handler = CommandHandler()
        self._register_handlers()
        logging.info("Bot initialized")

    async def setup(self):
        """Async setup operations"""
        try:
            await self._set_commands()
            logging.info("Bot commands set successfully")
        except Exception as e:
            logging.error(f"Error in bot setup: {str(e)}", exc_info=True)
            raise

    async def _set_commands(self):
        """Set bot commands with descriptions"""
        try:
            await self.application.bot.delete_my_commands()

            commands = [
                BotCommand('start', '🏠 Menu Utama'),
                BotCommand('contacts', '📦 Kontak Tersedia'),
                BotCommand('saved', '📁 Kontak Tersimpan'),
                BotCommand('credits', '💳 Kredit & Pembelian')
            ]
            await self.application.bot.set_my_commands(commands)
            logging.info("Commands set successfully")
        except Exception as e:
            logging.error(f"Error setting commands: {str(e)}", exc_info=True)
            raise

    def _register_handlers(self):
        """Register command handlers"""
        try:
            handlers = [
                TelegramCommandHandler("start", self.command_handler.start),
                TelegramCommandHandler("saved", self.command_handler.saved),
                TelegramCommandHandler("contacts", self.command_handler.contacts),
                TelegramCommandHandler("credits", self.command_handler.credits),
                TelegramCommandHandler("orders", self.command_handler.orders),   # Admin only
                MessageHandler(filters.Text(['/start']), self.command_handler.start),
                CallbackQueryHandler(self.command_handler.button_callback)
            ]

            for handler in handlers:
                self.application.add_handler(handler)

            logging.info("Handlers registered successfully")
        except Exception as e:
            logging.error(f"Error registering handlers: {str(e)}", exc_info=True)
            raise

    def get_application(self):
        """Get the configured application instance"""
        return self.application