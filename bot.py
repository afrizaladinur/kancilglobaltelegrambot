import logging
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import CommandHandler
from monitoring import monitor
from prometheus_client import Counter, Histogram

# Configure logging - using standard logging to maintain consistency with edited code.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('bot_requests_total', 'Total bot requests')
REQUEST_LATENCY = Histogram('bot_request_duration_seconds', 'Request latency')

class TelegramBot:
    _instance = None
    _initialized = False
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def init(self):
        """Initialize the bot with proper async handling"""
        async with self._lock:
            if not self._initialized:
                try:
                    logger.info("Initializing bot...")

                    # Initialize command handler first
                    self.command_handler = CommandHandler()

                    # Initialize bot with default settings and parse_mode
                    default_settings = DefaultBotProperties(
                        parse_mode="HTML"
                    )
                    self.bot = Bot(token=BOT_TOKEN, default=default_settings)
                    self.dp = Dispatcher()

                    # Register handlers
                    self.dp.message.register(self._start_handler, Command("start"))
                    self.dp.message.register(self._saved_handler, Command("saved"))
                    self.dp.message.register(self._credits_handler, Command("credits"))
                    self.dp.message.register(self._orders_handler, Command("orders"))

                    # Register callback query handler
                    self.dp.callback_query.register(self.command_handler.button_callback)

                    # Set commands
                    await self._set_commands()

                    self._initialized = True
                    logger.info("Bot initialized successfully")
                except Exception as e:
                    logger.error(f"Error initializing bot: {e}")
                    monitor.log_error(e, context={'stage': 'bot_initialization'}) #Added monitoring
                    raise

    async def _set_commands(self):
        """Set bot commands"""
        try:
            commands = [
                BotCommand(command='start', description='🏠 Menu Utama'),
                BotCommand(command='saved', description='📁 Kontak Tersimpan'),
                BotCommand(command='credits', description='💳 Kredit Saya'),
                BotCommand(command='orders', description='Daftar Pesanan')
            ]
            await self.bot.set_my_commands(commands)
            logger.info("Bot commands set successfully")
        except Exception as e:
            logger.error(f"Error setting commands: {e}")
            monitor.log_error(e, context={'stage': 'command_setting'}) #Added monitoring
            raise

    @REQUEST_LATENCY.time()
    async def _start_handler(self, message: Message):
        """Handle /start command with metrics"""
        REQUEST_COUNT.inc()
        try:
            await self.command_handler.start(message)
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            await message.answer("Sorry, an error occurred. Please try again later.")

    @REQUEST_LATENCY.time()
    async def _saved_handler(self, message: Message):
        """Handle /saved command with metrics"""
        REQUEST_COUNT.inc()
        try:
            await self.command_handler.saved(message)
        except Exception as e:
            logger.error(f"Error in saved handler: {e}")
            await message.answer("Sorry, an error occurred. Please try again later.")

    @REQUEST_LATENCY.time()
    async def _credits_handler(self, message: Message):
        """Handle /credits command with metrics"""
        REQUEST_COUNT.inc()
        try:
            await self.command_handler.credits(message)
        except Exception as e:
            logger.error(f"Error in credits handler: {e}")
            await message.answer("Sorry, an error occurred. Please try again later.")

    @REQUEST_LATENCY.time()
    async def _orders_handler(self, message: Message):
        """Handle /orders command with metrics"""
        REQUEST_COUNT.inc()
        try:
            await self.command_handler.orders(message)
        except Exception as e:
            logger.error(f"Error in orders handler: {e}")
            await message.answer("Sorry, an error occurred. Please try again later.")

    async def _error_handler(self, update: Message, exception: Exception):
        """Enhanced error handler with proper logging"""
        logger.error(f"Update {update} caused error {exception}")
        monitor.log_error(
            exception,
            context={
                'update': str(update),
                'user_id': update.from_user.id if update.from_user else None,
                'chat_id': update.chat.id if update.chat else None
            }
        )

    async def start(self):
        """Start the bot with proper webhook handling"""
        try:
            replit_url = os.getenv('REPL_SLUG', '')
            if replit_url:
                webhook_url = f"https://{replit_url}.repl.co/webhook/{self.bot.token}"
            else:
                webhook_url = os.getenv('BOT_WEBHOOK_URL', 'https://your-domain.com/webhook')

            await self.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
            return self.dp
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            monitor.log_error(e, context={'stage': 'webhook_setup'}) #Added monitoring
            raise

    async def stop(self):
        """Graceful shutdown"""
        try:
            await self.bot.delete_webhook()
            await self.bot.close()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            monitor.log_error(e, context={'stage': 'bot_shutdown'}) #Added monitoring
            raise