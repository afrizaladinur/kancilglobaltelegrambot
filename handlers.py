import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes, CallbackQueryHandler
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
                # Initialize user credits first
                credits = self.data_store.get_user_credits(user_id)
                # Then track command usage
                self.data_store.track_user_command(user_id, 'start')

            keyboard = [
                [InlineKeyboardButton("🔍 Cari Importir", callback_data="start_search")],
                [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                 InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                [InlineKeyboardButton("📊 Statistik", callback_data="show_stats"),
                 InlineKeyboardButton("❓ Bantuan", callback_data="show_help")]
            ]

            await update.message.reply_text(
                f"{Messages.START}\n{Messages.CREDITS_REMAINING.format(credits)}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Start command processed for user {user_id} with {credits} credits")
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

            if not results:
                await update.message.reply_text(
                    Messages.SEARCH_NO_RESULTS.format(query)
                )
                return

            for importer in results:
                message_text = f"""
🏢 *{importer['name']}*
🌏 Negara: {importer['country']}
📦 HS Code: {importer['hs_code']}
📝 Deskripsi: {importer['product_description']}
"""
                keyboard = [[InlineKeyboardButton(
                    "💾 Simpan Kontak",
                    callback_data=f"save_{importer['name']}"
                )]]

                await update.message.reply_text(
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            logging.info(f"Successfully sent search results to user {user_id}")
        except Exception as e:
            logging.error(f"Error in search command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.SEARCH_ERROR)

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command to show saved contacts"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'saved')
                saved_contacts = self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                await update.message.reply_text(Messages.NO_SAVED_CONTACTS)
                return

            for contact in saved_contacts:
                try:
                    message_text, whatsapp_number, _ = Messages.format_importer(
                        contact, saved=True
                    )
                    keyboard = []
                    if whatsapp_number:
                        keyboard.append([InlineKeyboardButton(
                            "💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )])

                    await update.message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
                except Exception as e:
                    logging.error(f"Error formatting contact {contact.get('name')}: {str(e)}", exc_info=True)
                    continue

            logging.info(f"Successfully sent saved contacts to user {user_id}")
        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query: CallbackQuery = update.callback_query
            await query.answer()  # Acknowledge the button press
            logging.info(f"Received callback query: {query.data}")

            with app.app_context():
                if query.data == "start_search":
                    await query.message.reply_text(
                        "Gunakan perintah /search diikuti dengan kata kunci pencarian.\n"
                        "Contoh: /search Indonesia"
                    )
                elif query.data == "show_saved":
                    await self.saved(update, context)
                elif query.data == "show_stats":
                    await self.stats(update, context)
                elif query.data == "show_help":
                    await self.help(update, context)
                elif query.data == "show_credits":
                    await self.credits(update, context)
                elif query.data == "buy_credits":
                    await query.message.reply_text(Messages.BUY_CREDITS_INFO)
                elif query.data.startswith('save_'):
                    importer_name = query.data[5:]  # Remove 'save_' prefix
                    user_id = query.from_user.id

                    # Search for the importer details
                    results = self.data_store.search_importers(importer_name)
                    if results:
                        importer = next((imp for imp in results if imp['name'] == importer_name), None)
                        if importer:
                            # Calculate credit cost before saving
                            credit_cost = self.data_store.calculate_credit_cost(importer)
                            credits = self.data_store.get_user_credits(user_id)

                            if credits < credit_cost:
                                await query.message.reply_text(Messages.NO_CREDITS)
                                return

                            if self.data_store.save_contact(user_id, importer):
                                remaining_credits = self.data_store.get_user_credits(user_id)
                                await query.message.reply_text(
                                    Messages.CONTACT_SAVED.format(remaining_credits)
                                )
                                logging.info(f"Successfully saved contact {importer_name} for user {user_id}")
                            else:
                                await query.message.reply_text(Messages.CONTACT_SAVE_FAILED)
                        else:
                            await query.message.reply_text(Messages.CONTACT_SAVE_FAILED)
                            logging.warning(f"Failed to save contact {importer_name} for user {user_id}")
                    else:
                        logging.error(f"Could not find importer {importer_name} to save")
                        await query.message.reply_text(Messages.ERROR_MESSAGE)
                else:
                    logging.warning(f"Unknown callback query data: {query.data}")

        except Exception as e:
            logging.error(f"Error in button callback: {str(e)}", exc_info=True)
            await update.callback_query.message.reply_text(Messages.ERROR_MESSAGE)


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

    async def credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'credits')
                credits = self.data_store.get_user_credits(user_id)

            # Create keyboard with buy credits button
            keyboard = [[InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")]]

            await update.message.reply_text(
                f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Credits command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)