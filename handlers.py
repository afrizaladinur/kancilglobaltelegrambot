import logging
from telegram import Update
from telegram.ext import ContextTypes
from data_store import DataStore
from rate_limiter import RateLimiter
from messages import Messages
from app import app

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        self.rate_limiter = RateLimiter()
        logging.info("CommandHandler initialized")

    async def check_rate_limit(self, update: Update) -> bool:
        """Check rate limit for user"""
        user_id = update.effective_user.id
        if not self.rate_limiter.can_proceed(user_id):
            await update.message.reply_text(Messages.RATE_LIMIT_EXCEEDED)
            return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'start')
            await update.message.reply_text(Messages.START, parse_mode='Markdown')
            logging.info(f"Start command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in start command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'help')
            await update.message.reply_text(Messages.HELP, parse_mode='Markdown')
            logging.info(f"Help command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in help command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'search')

            if not context.args:
                await update.message.reply_text(Messages.SEARCH_NO_QUERY)
                return

            query = ' '.join(context.args)
            logging.info(f"Processing search request from user {user_id} with query: {query}")

            with app.app_context():
                results = self.data_store.search_importers(query)

            logging.info(f"Search results for query '{query}': {len(results)} matches found")

            if not results:
                await update.message.reply_text(Messages.SEARCH_NO_RESULTS)
                return

            response = "Hasil pencarian:\n"
            for importer in results:
                response += Messages.format_importer(importer)

            await update.message.reply_text(response, parse_mode='Markdown')
            logging.info(f"Successfully sent search results to user {user_id}")
        except Exception as e:
            logging.error(f"Error in search command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'stats')
                stats = self.data_store.get_user_stats(user_id)
            await update.message.reply_text(
                Messages.format_stats(stats),
                parse_mode='Markdown'
            )
            logging.info(f"Stats command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in stats command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)