import logging
import os
import time
from sqlalchemy import text
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from data_store import DataStore
from rate_limiter import RateLimiter
from messages import Messages
from app import app
from app import app
import xendit

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        self.rate_limiter = RateLimiter()
        self.engine = self.data_store.engine
        logging.info("CommandHandler initialized")

    async def check_rate_limit(self, update: Update) -> bool:
        """Check rate limit for user"""
        try:
            user_id = update.effective_user.id
            if not self.rate_limiter.can_proceed(user_id):
                await update.message.reply_text(Messages.RATE_LIMIT_EXCEEDED)
                return False
            # Initialize user credits if not exists
            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
                if credits is None:
                    self.data_store.initialize_user_credits(user_id, 10.0)
            return True
        except Exception as e:
            logging.error(f"Rate limit check error: {str(e)}")
            return True  # Allow operation on error to prevent blocking

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command and message handler"""
        try:
            # Skip rate limit for /start command
            if update.message and update.message.text == '/start':
                pass
            elif not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                # Initialize user credits first
                credits = self.data_store.get_user_credits(user_id)
                # Then track command usage
                self.data_store.track_user_command(user_id, 'start')

            # Check if user has redeemed free credits
            with self.engine.connect() as conn:
                has_redeemed = conn.execute(text(
                    "SELECT has_redeemed_free_credits FROM user_credits WHERE user_id = :user_id"
                ), {"user_id": user_id}).scalar() or False

            keyboard = [
                [InlineKeyboardButton("🔍 Cari Importir", callback_data="start_search")],
                [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                 InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                [InlineKeyboardButton("📊 Statistik", callback_data="show_stats"),
                 InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
            ]

            if not has_redeemed:
                keyboard.insert(1, [InlineKeyboardButton("🎁 Cairkan 10 Kredit Gratis", callback_data="redeem_free_credits")])

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
            keyboard = [[InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")]]
            with app.app_context():
                self.data_store.track_user_command(user_id, 'help')
            await update.message.reply_text(
                Messages.HELP,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
                try:
                    self.data_store.track_user_command(user_id, 'search')
                except Exception as db_error:
                    logging.error(f"Database error tracking command: {str(db_error)}")
                    # Continue execution even if tracking fails

            if not context.args:
                keyboard = [[InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")]]
                await update.message.reply_text(
                    Messages.SEARCH_NO_QUERY,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                return

            query = ' '.join(context.args)
            context.user_data['last_search_query'] = query
            logging.info(f"Processing search request from user {user_id} with query: {query}")

            with app.app_context():
                try:
                    results = self.data_store.search_importers(query)
                    # Store results in context for pagination
                    context.user_data['last_search_results'] = results
                    context.user_data['search_page'] = 0  # Reset to first page
                except Exception as search_error:
                    logging.error(f"Search error: {str(search_error)}")
                    await update.message.reply_text(
                        "Search service is temporarily unavailable. Please try again later."
                    )
                    return

            if not results:
                await update.message.reply_text(
                    Messages.SEARCH_NO_RESULTS.format(query)
                )
                return

            logging.info(f"Found {len(results)} results for query: {query}")

            # Initialize page in context
            page = context.user_data.get('search_page', 0)
            items_per_page = 2
            total_pages = (len(results) + items_per_page - 1) // items_per_page

            # Get current page results
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_results = results[start_idx:end_idx]

            for importer in current_results:
                try:
                    message_text, _, callback_data = Messages.format_importer(importer)

                    keyboard = [[InlineKeyboardButton(
                        "💾 Simpan Kontak",
                        callback_data=f"save_{importer['name']}"
                    )]]

                    await update.message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as format_error:
                    logging.error(f"Error formatting importer {importer.get('name')}: {str(format_error)}", exc_info=True)
                    continue

            # Add pagination buttons
            pagination_buttons = []
            if page > 0:
                pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
            pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="search_page_info"))
            if page < total_pages - 1:
                pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="search_next"))

            # Add regenerate button as a separate row
            regenerate_button = [
                [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await update.message.reply_text(
                f"Halaman {page + 1} dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([pagination_buttons] + regenerate_button)
            )

            logging.info(f"Successfully sent search results to user {user_id}")
        except Exception as e:
            logging.error(f"Error in search command: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "An error occurred while processing your request. Please try again later."
            )

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            page = getattr(context.user_data, 'saved_page', 0)
            items_per_page = 2

            with app.app_context():
                self.data_store.track_user_command(user_id, 'saved')
                saved_contacts = self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                await update.message.reply_text(Messages.NO_SAVED_CONTACTS)
                return

            total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_contacts = saved_contacts[start_idx:end_idx]

            for contact in current_contacts:
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

            # Add pagination buttons
            pagination_buttons = []
            if page > 0:
                pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="saved_prev"))
            pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="page_info"))
            if page < total_pages - 1:
                pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="saved_next"))

            export_buttons = [
                [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]
            await update.message.reply_text(
                f"Halaman {page + 1} dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
            )

            logging.info(f"Successfully sent saved contacts to user {user_id}")
        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()  # Acknowledge the button press
            logging.info(f"Received callback query: {query.data}")

            with app.app_context():
                if query.data == "start_search":
                    await query.message.reply_text(
                        Messages.SEARCH_NO_QUERY,
                        parse_mode='Markdown'
                    )
                elif query.data == "show_saved":
                    user_id = query.from_user.id
                    page = context.user_data.get('show_saved_page', 0)
                    items_per_page = 2

                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'saved')
                        saved_contacts = self.data_store.get_saved_contacts(user_id)

                    if not saved_contacts:
                        await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                        return

                    total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
                    start_idx = page * items_per_page
                    end_idx = start_idx + items_per_page
                    current_contacts = saved_contacts[start_idx:end_idx]

                    for contact in current_contacts:
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

                            await query.message.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                            )
                        except Exception as e:
                            logging.error(f"Error formatting contact {contact.get('name')}: {str(e)}", exc_info=True)
                            continue

                    # Add pagination buttons
                    pagination_buttons = []
                    if page > 0:
                        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="show_saved_prev"))
                    pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="show_saved_page_info"))
                    if page < total_pages - 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="show_saved_next"))

                    export_buttons = [
                        [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]
                    await query.message.reply_text(
                        f"Halaman {page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
                    )
                elif query.data == "export_contacts":
                    try:
                        user_id = query.from_user.id
                        with app.app_context():
                            contacts = self.data_store.get_saved_contacts(user_id)

                        if not contacts:
                            await query.message.reply_text("No contacts to export.")
                            return

                        import csv
                        import io

                        # Create CSV in memory
                        output = io.StringIO()
                        fieldnames = ['product_description', 'name', 'country', 'contact', 'email', 'website', 'wa_available', 'hs_code', 'saved_at']
                        writer = csv.DictWriter(output, fieldnames=fieldnames)

                        # Write custom headers
                        writer.writerow({
                            'product_description': 'Peran',
                            'name': 'Nama Perusahaan',
                            'country': 'Negara',
                            'contact': 'Telepon',
                            'email': 'E-mail',
                            'website': 'Website',
                            'wa_available': 'WhatsApp',
                            'hs_code': 'HS Code',
                            'saved_at': 'Tanggal Penyimpanan'
                        })

                        # Process and write rows
                        for contact in contacts:
                            # Convert WhatsApp status
                            contact['wa_available'] = 'Tersedia' if contact['wa_available'] else 'Tidak Tersedia'
                            # Process HS Code to show only last 4 digits
                            if contact['hs_code']:
                                digits = ''.join(filter(str.isdigit, contact['hs_code']))
                                contact['hs_code'] = digits[-4:] if len(digits) >= 4 else digits
                            writer.writerow(contact)

                        # Convert to bytes for sending
                        csv_bytes = output.getvalue().encode('utf-8')
                        output.close()

                        # Send CSV file
                        from io import BytesIO
                        bio = BytesIO(csv_bytes)
                        bio.name = f'saved_contacts_{user_id}.csv'

                        await query.message.reply_document(
                            document=bio,
                            filename=f'saved_contacts_{user_id}.csv',
                            caption="Berikut adalah daftar kontak yang tersimpan!"
                        )

                    except Exception as e:
                        logging.error(f"Error exporting contacts: {str(e)}")
                        await query.message.reply_text("Error exporting contacts. Please try again later.")
                elif query.data == "show_stats":
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'stats')
                        stats = self.data_store.get_user_stats(user_id)
                    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
                    await query.message.reply_text(
                        Messages.format_stats(stats),
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif query.data == "regenerate_search":
                    # Get the original search query
                    if 'last_search_query' in context.user_data:
                        query_text = context.user_data.get('last_search_query', '')
                        results = self.data_store.search_importers(query_text)

                        if not results:
                            await query.message.reply_text(
                                Messages.SEARCH_NO_RESULTS.format(query_text)
                            )
                            return

                        # Reset pagination
                        context.user_data['last_search_results'] = results
                        context.user_data['search_page'] = 0

                        # Show first page results
                        page = 0
                        items_per_page = 2
                        total_pages = (len(results) + items_per_page - 1) // items_per_page
                        start_idx = page * items_per_page
                        end_idx = start_idx + items_per_page
                        current_results = results[start_idx:end_idx]

                        for importer in current_results:
                            message_text, _, _ = Messages.format_importer(importer)
                            keyboard = [[InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=f"save_{importer['name'][:50]}"
                            )]]
                            await query.message.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )

                        # Add pagination buttons
                        pagination_buttons = []
                        if page > 0:
                            pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
                        pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="search_page_info"))
                        if page < total_pages - 1:
                            pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="search_next"))

                        # Add regenerate button
                        regenerate_button = [
                            [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                        ]

                        await query.message.reply_text(
                            f"Halaman {page + 1} dari {total_pages}",
                            reply_markup=InlineKeyboardMarkup([pagination_buttons] + regenerate_button)
                        )
                    else:
                        await query.message.reply_text("Silakan lakukan pencarian baru terlebih dahulu.")

                elif query.data == "back_to_main":
                    # Delete current message and show main menu
                    await query.message.delete()
                    keyboard = [
                        [InlineKeyboardButton("🔍 Cari Importir", callback_data="start_search")],
                        [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                        [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                         InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                        [InlineKeyboardButton("📊 Statistik", callback_data="show_stats"),
                         InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                        [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                        [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
                    ]
                    await query.message.reply_text(
                        Messages.START,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                elif query.data == "show_help":
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'help')
                    keyboard = [
                        [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]
                    await query.message.reply_text(
                        Messages.HELP,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif query.data == "saved_prev" or query.data == "saved_next":
                    user_id = query.from_user.id
                    items_per_page = 2  # Define pagination size

                    with app.app_context():
                        saved_contacts = self.data_store.get_saved_contacts(user_id)

                    if not saved_contacts:
                        await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                        return

                    total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
                    current_page = context.user_data.get('saved_page', 0)

                    if query.data == "saved_prev":
                        current_page = max(0, current_page - 1)
                    else:
                        current_page = min(total_pages - 1, current_page + 1)

                    context.user_data['saved_page'] = current_page
                    start_idx = current_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(saved_contacts))
                    current_contacts = saved_contacts[start_idx:end_idx]

                    for contact in current_contacts:
                        message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
                        keyboard = []
                        if whatsapp_number:
                            keyboard.append([InlineKeyboardButton(
                                "💬 Chat di WhatsApp",
                                url=f"https://wa.me/{whatsapp_number}"
                            )])
                        await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                        )

                    # Add pagination buttons
                    pagination_buttons = []
                    if current_page > 0:
                        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="saved_prev"))
                    pagination_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="page_info"))
                    if current_page < total_pages - 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="saved_next"))

                    await query.message.reply_text(
                        f"Halaman {current_page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons])
                    )
                elif query.data in ["page_info", "search_page_info"]:
                    await query.answer("Halaman saat ini", show_alert=False)
                elif query.data in ["search_prev", "search_next"]:
                    # Get current search results from context
                    results = context.user_data.get('last_search_results', [])
                    if not results:
                        await query.message.reply_text("Hasil pencarian tidak tersedia. Silakan cari lagi.")
                        return

                    items_per_page = 2
                    total_pages = (len(results) + items_per_page - 1) // items_per_page
                    current_page = context.user_data.get('search_page', 0)

                    if query.data == "search_prev":
                        current_page = max(0, current_page - 1)
                    else:
                        current_page = min(total_pages - 1, current_page + 1)

                    context.user_data['search_page'] = current_page
                    start_idx = current_page * items_per_page
                    end_idx = start_idx + items_per_page
                    current_results = results[start_idx:end_idx]

                    for importer in current_results:
                        message_text, _, _ = Messages.format_importer(importer)
                        # Truncate name to fit Telegram's 64-byte callback data limit
                        truncated_name = importer['name'][:50]  # Leave room for 'save_' prefix
                        keyboard = [[InlineKeyboardButton(
                            "💾 Simpan Kontak",
                            callback_data=f"save_{truncated_name}"
                        )]]
                        await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )

                    # Update pagination buttons
                    pagination_buttons = []
                    if current_page > 0:
                        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
                    pagination_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="search_page_info"))
                    if current_page < total_pages - 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="search_next"))

                    # Add Cari Lagi button as a separate row
                    cari_lagi_button = [
                        [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await query.message.reply_text(
                        f"Halaman {current_page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons] + cari_lagi_button)
                    )
                elif query.data == "show_credits":
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'credits')
                        credits = self.data_store.get_user_credits(user_id)
                    keyboard = [
                        [InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]
                    await query.message.reply_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif query.data == "buy_credits":
                    keyboard = [
                        [InlineKeyboardButton("🛒 Beli 20 Kredit - Rp 50.000", callback_data="pay_20_50000")],
                        [InlineKeyboardButton("🛒 Beli 45 Kredit - Rp 100.000", callback_data="pay_45_100000")],
                        [InlineKeyboardButton("🛒 Beli 100 Kredit - Rp 200.000", callback_data="pay_100_200000")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]
                    await query.message.reply_text(
                        "Pilih paket kredit yang ingin Anda beli:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif query.data.startswith('pay_'):
                    try:
                        _, credits, amount = query.data.split('_')
                        user_id = query.from_user.id
                        username = query.from_user.username or str(user_id)
                        order_id = f"BOT_{user_id}_{int(time.time())}"

                        payment_message = (
                            f"💳 *Detail Pembayaran*\n\n"
                            f"Order ID: `{order_id}`\n"
                            f"Jumlah Kredit: {credits}\n"
                            f"Total: Rp {int(amount):,}\n\n"
                            f"*Metode Pembayaran:*\n\n"
                            f"1️⃣ *Transfer BCA*\n"
                            f"Nama: Nanda Amalia\n"
                            f"No. Rek: `4452385892`\n"
                            f"Kode Bank: 014\n\n"
                            f"2️⃣ *Transfer Jenius/SMBC*\n"
                            f"Nama: Nanda Amalia\n"
                            f"No. Rek: `90020380969`\n"
                            f"$cashtag: `$kancilglobalbot`\n\n"
                            f"Setelah melakukan pembayaran, silakan kirim bukti transfer ke admin."
                        )

                        keyboard = [[
                            InlineKeyboardButton(
                                "📎 Kirim Bukti Pembayaran",
                                url="https://t.me/afrizaladinur"
                            )
                        ]]

                        await query.message.reply_text(
                            payment_message,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )

                        # Notify admin
                        admin_message = (
                            f"🔔 *Pesanan Kredit Baru!*\n\n"
                            f"Order ID: `{order_id}`\n"
                            f"User ID: `{user_id}`\n"
                            f"Username: @{username}\n"
                            f"Jumlah Kredit: {credits}\n"
                            f"Total: Rp {int(amount):,}"
                        )

                        admin_keyboard = [[InlineKeyboardButton(
                            f"✅ Berikan {credits} Kredit",
                            callback_data=f"give_{user_id}_{credits}"
                        )]]

                        admin_ids = [6422072438]
                        for admin_id in admin_ids:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=admin_message,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(admin_keyboard)
                            )

                        logging.info(f"Manual payment order created: {order_id}")

                    except Exception as e:
                        logging.error(f"Error processing payment: {str(e)}", exc_info=True)
                        await query.message.reply_text(
                            "Maaf, terjadi kesalahan dalam memproses pembayaran.\n"
                            "Admin akan segera menghubungi Anda untuk proses manual."
                        )


                    except Exception as e:
                        logging.error(f"Error processing payment: {str(e)}", exc_info=True)
                        await query.message.reply_text(
                            "Pesanan tetap diproses! Admin akan segera menghubungi Anda."
                        )
                elif query.data.startswith('order_'):
                    try:
                        credit_amount = query.data.split('_')[1]
                        user_id = query.from_user.id
                        username = query.from_user.username or "NoUsername"
                        order_id = f"ORD{user_id}{int(time.time())}"

                        # Notify admin
                        admin_message = (
                            f"🔔 Pesanan Kredit Baru!\n\n"
                            f"Order ID: `{order_id}`\n"
                            f"User ID: `{user_id}`\n"
                            f"Username: @{username}\n"
                            f"Jumlah Kredit: {credit_amount}"
                        )

                        admin_keyboard = [[InlineKeyboardButton(
                            f"✅ Berikan {credit_amount} Kredit",
                            callback_data=f"give_{user_id}_{credit_amount}"
                        )]]

                        admin_ids = [6422072438]  # Your admin ID
                        for admin_id in admin_ids:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=admin_message,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(admin_keyboard)
                            )

                        # Notify user
                        await query.message.reply_text(
                            f"✅ Pesanan dibuat!\n\n"
                            f"ID Pesanan: `{order_id}`\n"
                            f"Jumlah Kredit: {credit_amount}\n\n"
                            "Admin akan segera menghubungi Anda.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logging.error(f"Error processing order: {str(e)}")
                        await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi nanti.")
                elif query.data == "show_saved_prev" or query.data == "show_saved_next":
                    user_id = query.from_user.id
                    items_per_page = 2

                    with app.app_context():
                        saved_contacts = self.data_store.get_saved_contacts(user_id)

                    if not saved_contacts:
                        await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                        return

                    total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
                    current_page = context.user_data.get('show_saved_page', 0)

                    if query.data == "show_saved_prev":
                        current_page = max(0, current_page - 1)
                    else:
                        current_page = min(total_pages - 1, current_page + 1)

                    context.user_data['show_saved_page'] = current_page
                    start_idx = current_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(saved_contacts))
                    current_contacts = saved_contacts[start_idx:end_idx]

                    for contact in current_contacts:
                        message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
                        keyboard = []
                        if whatsapp_number:
                            keyboard.append([InlineKeyboardButton(
                                "💬 Chat di WhatsApp",
                                url=f"https://wa.me/{whatsapp_number}"
                            )])
                        await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                        )

                    # Add pagination buttons
                    pagination_buttons = []
                    if current_page > 0:
                        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="show_saved_prev"))
                    pagination_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="show_saved_page_info"))
                    if current_page < total_pages - 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="show_saved_next"))

                    export_buttons = [
                        [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]
                    await query.message.reply_text(
                        f"Halaman {current_page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
                    )
                elif query.data == "show_saved_page_info":
                    await query.answer("Halaman saat ini", show_alert=False)
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
                elif query.data == "redeem_free_credits":
                    user_id = query.from_user.id
                    try:
                        with self.engine.begin() as conn:
                            # Check if already redeemed with row lock
                            result = conn.execute(text("""
                                SELECT has_redeemed_free_credits, credits 
                                FROM user_credits 
                                WHERE user_id = :user_id
                                FOR UPDATE
                            """), {"user_id": user_id}).first()

                            if not result:
                                # Initialize user if not exists
                                conn.execute(text("""
                                    INSERT INTO user_credits (user_id, credits, has_redeemed_free_credits)
                                    VALUES (:user_id, 10, true)
                                """), {"user_id": user_id})
                                new_balance = 10.0
                            else:
                                has_redeemed, current_credits = result

                                if has_redeemed:
                                    await query.message.reply_text("Anda sudah pernah mengklaim kredit gratis!")
                                    return

                                # Add credits and mark as redeemed
                                conn.execute(text("""
                                    UPDATE user_credits 
                                    SET credits = credits + 10,
                                        has_redeemed_free_credits = true
                                    WHERE user_id = :user_id
                                """), {"user_id": user_id})
                                new_balance = current_credits + 10.0

                        await query.message.reply_text(
                            f"🎉 Selamat! 10 kredit gratis telah ditambahkan ke akun Anda!\n"
                            f"Saldo saat ini: {new_balance:.1f} kredit"
                        )
                    except Exception as e:
                        logging.error(f"Error redeeming free credits: {str(e)}")
                        await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi nanti.")

                elif query.data == "show_hs_codes":
                    try:
                        with self.engine.connect() as conn:
                            hs_counts = conn.execute(text("""
                                SELECT 
                                    CASE 
                                        WHEN LOWER(product) LIKE '%0301%' THEN '0301'
                                        WHEN LOWER(product) LIKE '%0302%' THEN '0302'
                                        WHEN LOWER(product) LIKE '%0303%' THEN '0303'
                                        WHEN LOWER(product) LIKE '%0304%' THEN '0304'
                                        WHEN LOWER(product) LIKE '%0305%' OR LOWER(product) LIKE '%anchovy%' THEN '0305'
                                        WHEN LOWER(product) LIKE '%0901%' THEN '0901'
                                        WHEN LOWER(product) LIKE '%1513%' OR LOWER(product) LIKE '%coconut oil%' THEN '1513'
                                        WHEN LOWER(product) LIKE '%44029010%' THEN '44029010'
                                    END as hs_code,
                                    COUNT(*) as count
                                FROM importers
                                WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|0901|1513|44029010|anchovy|coconut oil)%'
                                GROUP BY hs_code
                                ORDER BY hs_code;
                            """)).fetchall()

                            counts_dict = {row[0]: row[1] for row in hs_counts}

                            # Build header text
                            header_text = """📊 *Kontak Tersedia*

🌊 *Produk Laut*"""

                            # Build keyboard with sections
                            keyboard = [
                                [InlineKeyboardButton(f"🐟 Ikan Hidup (0301) - {counts_dict.get('0301', 0)} kontak", 
                                                    callback_data="search_0301")],
                                [InlineKeyboardButton(f"🐠 Ikan Segar (0302) - {counts_dict.get('0302', 0)} kontak",
                                                    callback_data="search_0302")],
                                [InlineKeyboardButton(f"❄️ Ikan Beku (0303) - {counts_dict.get('0303', 0)} kontak",
                                                    callback_data="search_0303")],
                                [InlineKeyboardButton(f"🍣 Fillet Ikan (0304) - {counts_dict.get('0304', 0)} kontak",
                                                    callback_data="search_0304")],
                                [InlineKeyboardButton(f"🐟 Anchovy - {counts_dict.get('0305', 0)} kontak",
                                                    callback_data="search_anchovy")],
                                [InlineKeyboardButton("🌿 *PRODUK AGRIKULTUR*", callback_data="section_agriculture")],
                                [InlineKeyboardButton(f"☕ Kopi (0901) - {counts_dict.get('0901', 0)} kontak",
                                                    callback_data="search_0901")],
                                [InlineKeyboardButton(f"🥥 Minyak Kelapa - {counts_dict.get('1513', 0)} kontak",
                                                    callback_data="search_coconut_oil")],
                                [InlineKeyboardButton("🌳 *PRODUK OLAHAN*", callback_data="section_processed")],
                                [InlineKeyboardButton(f"🪵 Briket Batok (44029010) - {counts_dict.get('44029010', 0)} kontak",
                                                    callback_data="search_briket")],
                                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                            ]
                        await query.message.reply_text(
                            hs_guide,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logging.error(f"Error getting HS code counts: {str(e)}")
                        await query.message.reply_text("Maaf, terjadi kesalahan saat mengambil data.")
                elif query.data.startswith('search_'):
                    search_term = query.data.replace('search_', '')
                    search_terms = {
                        '0301': '0301',
                        '0302': '0302',
                        '0303': '0303', 
                        '0304': '0304',
                        'anchovy': 'anchovy',
                        '0901': '0901',
                        'coconut_oil': 'coconut oil',
                        'briket': '44029010'
                    }
                    
                    if search_term in search_terms:
                        # Simulate /search command
                        context.args = [search_terms[search_term]]
                        await self.search(update.callback_query, context)
                    else:
                        await query.message.reply_text("Pencarian tidak tersedia")
                
                elif query.data.startswith('section_'):
                    # Just ignore section headers
                    await query.answer()
                
                elif query.data.startswith('give_'):
                    try:
                        _, target_user_id, credit_amount = query.data.split('_')
                        if query.from_user.id not in [6422072438]:  # Admin check
                            await query.answer("Not authorized", show_alert=True)
                            return

                        if self.data_store.add_credits(int(target_user_id), int(credit_amount)):
                            new_balance = self.data_store.get_user_credits(int(target_user_id))
                            await query.message.edit_text(
                                f"{query.message.text}\n\n✅ Kredit telah ditambahkan!\nSaldo baru: {new_balance}",
                                parse_mode='Markdown'
                            )
                            # Notify user
                            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
                            await context.bot.send_message(
                                chat_id=int(target_user_id),
                                text=f"✅ {credit_amount} kredit telah ditambahkan ke akun Anda!\nSaldo saat ini: {new_balance} kredit",
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                        else:
                            await query.answer("Failed to add credits", show_alert=True)
                    except Exception as e:
                        logging.error(f"Error giving credits: {str(e)}")
                        await query.answer("Error processing request", show_alert=True)
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

    async def give_credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /givecredits command for admins"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            admin_ids = [6422072438]  # Your Telegram ID

            if user_id not in admin_ids:
                await update.message.reply_text("⛔️ You are not authorized to use this command.")
                return

            # Check command format
            if not context.args or len(context.args) != 2:
                await update.message.reply_text("Usage: /givecredits <user_id> <amount>")
                return

            try:
                target_user_id = int(context.args[0])
                credit_amount = int(context.args[1])
            except ValueError:
                await update.message.reply_text("Invalid user ID or credit amount. Both must be numbers.")
                return

            if credit_amount <= 0:
                await update.message.reply_text("Credit amount must be positive.")
                return

            with app.app_context():
                if self.data_store.add_credits(target_user_id, credit_amount):
                    new_balance = self.data_store.get_user_credits(target_user_id)
                    await update.message.reply_text(
                        f"✅ Successfully added {credit_amount} credits to user {target_user_id}\n"
                        f"New balance: {new_balance} credits"
                    )
                else:
                    await update.message.reply_text("❌ Failed to add credits. User may not exist.")

        except Exception as e:
            logging.error(f"Error in give_credits command: {str(e)}", exc_info=True)
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

            keyboard = [[InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")]]

            await update.message.reply_text(
                f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Credits command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)