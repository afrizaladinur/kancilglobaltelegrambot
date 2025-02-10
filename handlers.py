import logging
import os
import time
import asyncio
from sqlalchemy import text
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from data_store import DataStore
from rate_limiter import RateLimiter
from messages import Messages
from app import app

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        self.rate_limiter = RateLimiter()
        self.engine = self.data_store.engine
        logging.info("CommandHandler initialized")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            admin_ids = [6422072438]
            is_admin = user_id in admin_ids

            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
                if credits is None:
                    self.data_store.initialize_user_credits(user_id, 10.0 if not is_admin else 999999.0)
                    credits = 10.0 if not is_admin else 999999.0
                self.data_store.track_user_command(user_id, 'start')

            # Check if user is already in community
            try:
                chat_member = await context.bot.get_chat_member(chat_id="@kancilglobalnetwork", user_id=user_id)
                is_member = chat_member.status in ['member', 'administrator', 'creator']
            except Exception as e:
                logging.error(f"Error checking member status: {str(e)}")
                is_member = False

            message_text, reply_markup = self.get_main_menu_markup(user_id, credits, is_member)
            await update.message.reply_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Error in start command: {str(e)}")
            await update.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

    async def credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
                self.data_store.track_user_command(user_id, 'credits')

            keyboard = [
                [InlineKeyboardButton("🎁 Klaim 10 Kredit Gratis", callback_data="redeem_free_credits")],
                [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="order_75")],
                [InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000", callback_data="order_150")],
                [InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000", callback_data="order_250")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await update.message.reply_text(
                f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}")
            await update.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'saved')
                saved_contacts = self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
                await update.message.reply_text(
                    Messages.NO_SAVED_CONTACTS,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            context.user_data['saved_contacts'] = saved_contacts
            context.user_data['saved_page'] = 0

            # Show first page
            items_per_page = 2
            total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
            current_contacts = saved_contacts[:items_per_page]

            for contact in current_contacts:
                message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
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

            # Add pagination buttons
            pagination_buttons = []
            if total_pages > 1:
                pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="show_saved_next"))

            navigation_buttons = [
                [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await update.message.reply_text(
                f"Halaman 1 dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([pagination_buttons] + navigation_buttons)
            )
        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}")
            await update.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

    def get_main_menu_markup(self, user_id: int, credits: float, is_member: bool):
        """Generate main menu markup and message"""
        community_button = [InlineKeyboardButton(
            "🔓 Buka Kancil Global Network" if is_member else "🌟 Gabung Kancil Global Network",
            **{"url": "https://t.me/+kuNU6lDtYoNlMTc1"} if is_member else {"callback_data": "join_community"}
        )]

        keyboard = [
            [InlineKeyboardButton("📤 Kontak Supplier", callback_data="show_suppliers"),
             InlineKeyboardButton("📥 Kontak Buyer", callback_data="show_buyers")],
            [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
            [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits")],
            community_button,
            [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
            [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
        ]

        message_text = f"{Messages.START}\n{Messages.CREDITS_REMAINING.format(credits)}"
        return message_text, InlineKeyboardMarkup(keyboard)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()  # Acknowledge the button press
            logging.info(f"Received callback query: {query.data}")

            # Get user ID
            user_id = query.from_user.id

            # Handle different button callbacks
            if query.data.startswith('buyer_') or query.data.startswith('supplier_'):
                try:
                    category_type, category = query.data.split('_', 1)
                    categories = Messages.SUPPLIER_CATEGORIES if category_type == "supplier" else Messages.BUYER_CATEGORIES

                    cat_data = {}
                    # Handle nested categories
                    for key, data in categories.items():
                        if key.lower().replace(' ', '_') == category:
                            cat_data = data
                            break

                    if not cat_data:
                        await query.message.reply_text("Category not found")
                        return

                    keyboard = []
                    if 'subcategories' in cat_data:
                        with self.engine.connect() as conn:
                            for sub_name, sub_data in cat_data['subcategories'].items():
                                search_term = sub_data['search']

                                # Get count of matching records
                                count_result = conn.execute(text("""
                                    SELECT COUNT(*) 
                                    FROM importers 
                                    WHERE product = :search_term
                                """), {
                                    "search_term": search_term
                                }).scalar()

                                keyboard.append([InlineKeyboardButton(
                                    f"{sub_data['emoji']} {sub_name} ({count_result} kontak)",
                                    callback_data=f"show_results_{search_term}"
                                )])

                    keyboard.append([InlineKeyboardButton(
                        "🔙 Kembali", 
                        callback_data="show_suppliers" if category_type == "supplier" else "show_buyers"
                    )])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih kategori produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}", exc_info=True)
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('show_results_'):
                try:
                    search_pattern = query.data.replace('show_results_', '')
                    logging.info(f"Fetching results for pattern: {search_pattern}")

                    # Get the results from database
                    with self.engine.connect() as conn:
                        results = conn.execute(text("""
                            SELECT *
                            FROM importers 
                            WHERE product = :search_term
                            LIMIT 10
                        """), {
                            "search_term": search_pattern
                        }).fetchall()

                        # Convert results to list of dicts properly
                        results = [dict(row._mapping) for row in results]

                        total_count = len(results)
                        if not results:
                            await query.message.reply_text("Tidak ada hasil yang ditemukan.")
                            return

                        # Store results in context
                        context.user_data['search_results'] = results
                        context.user_data['search_page'] = 0

                        # Show first page (2 results)
                        items_per_page = 2
                        total_pages = (total_count + items_per_page - 1) // items_per_page
                        current_page_results = results[:items_per_page]

                        # Store the last search results for potential save operations
                        context.user_data['last_search_results'] = results

                        # Display results with censored data
                        for result in current_page_results:
                            # Format and send message
                            message_text, _, callback_data = Messages.format_importer(result)
                            save_button = [[InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=callback_data
                            )]] if callback_data else []

                            await query.message.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(save_button) if save_button else None
                            )

                        # Add pagination buttons
                        navigation_buttons = []
                        if total_pages > 1:
                            navigation_buttons.append([
                                InlineKeyboardButton(f"1/{total_pages}", callback_data="page_info"),
                                InlineKeyboardButton("Next ➡️", callback_data="next_page")
                            ])
                        navigation_buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

                        await query.message.reply_text(
                            f"Menampilkan hasil 1-{min(items_per_page, total_count)} dari {total_count} kontak",
                            reply_markup=InlineKeyboardMarkup(navigation_buttons)
                        )

                except Exception as e:
                    logging.error(f"Error showing results: {str(e)}", exc_info=True)
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "back_to_main":
                # Handle back to main menu
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        credits = self.data_store.get_user_credits(user_id)
                        is_member = await self._check_member_status(context, user_id)
                        message_text, reply_markup = self.get_main_menu_markup(user_id, credits, is_member)
                        await query.message.edit_text(
                            text=message_text,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                except Exception as e:
                    logging.error(f"Error returning to main menu: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

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

                # Delete current page messages
                try:
                    # Delete the 2 contact messages and pagination message
                    current_message_id = query.message.message_id
                    for i in range(3):  # Delete current message and 2 previous messages
                        try:
                            await context.bot.delete_message(
                                chat_id=query.message.chat_id,
                                message_id=current_message_id - i
                            )
                        except Exception as e:
                            logging.error(f"Error deleting message {current_message_id - i}: {str(e)}")
                except Exception as e:
                    logging.error(f"Error deleting messages: {str(e)}")

                saved_contacts = context.user_data.get('saved_contacts', [])
                if not saved_contacts:
                    await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                    return

                total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
                current_page = context.user_data.get('saved_page', 0)

                if query.data == "show_saved_prev":
                    current_page = max(0, current_page - 1)
                else:
                    current_page = min(total_pages - 1, current_page + 1)

                context.user_data['saved_page'] = current_page
                start_idx = current_page * items_per_page
                end_idx = min(start_idx + items_per_page, len(saved_contacts))
                current_contacts = saved_contacts[start_idx:end_idx]

                new_messages = []
                for contact in current_contacts:
                    message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
                    keyboard = []
                    if whatsapp_number:
                        keyboard.append([InlineKeyboardButton(
                            "💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )])
                    sent_msg = await query.message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
                    new_messages.append(sent_msg.message_id)

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
                try:
                    user_id = query.from_user.id
                    importer_name = query.data[5:]  # Remove 'save_' prefix

                    with app.app_context():
                        # Track the save action
                        self.data_store.track_user_command(user_id, 'save_contact')

                        # Get current credits first
                        current_credits = self.data_store.get_user_credits(user_id)
                        if current_credits is None or current_credits <= 0:
                            await query.message.reply_text(
                                "⚠️ Kredit Anda tidak mencukupi untuk menyimpan kontak ini."
                            )
                            return

                        # Get the full importer data from last search results
                        results = context.user_data.get('last_search_results', [])
                        # More flexible matching to handle truncated names
                        importer = next(
                            (r for r in results if importer_name.lower() in r['name'].lower()),
                            None
                        )

                        if not importer:
                            logging.error(f"Importer {importer_name} not found in search results")
                            await query.message.reply_text(
                                "⚠️ Kontak tidak ditemukan. Silakan coba cari kembali."
                            )
                            return

                        # Calculate credit cost
                        credit_cost = self.data_store.calculate_credit_cost(importer)
                        if current_credits < credit_cost:
                            await query.message.reply_text(
                                f"⚠️ Kredit tidak mencukupi. Dibutuhkan: {credit_cost} kredit."
                            )
                            return

                        # Try to save the contact
                        save_result = await self.data_store.save_contact(user_id, importer)
                        if save_result:
                            remaining_credits = self.data_store.get_user_credits(user_id)
                            keyboard = [
                                [InlineKeyboardButton("📁 Lihat Kontak Tersimpan", callback_data="show_saved")],
                                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                            ]
                            await query.message.reply_text(
                                f"✅ Kontak berhasil disimpan!\n"
                                f"Sisa kredit Anda: {remaining_credits} kredit",
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                        else:
                            await query.message.reply_text(
                                "⚠️ Terjadi kesalahan saat menyimpan kontak. Silakan coba lagi."
                            )

                except Exception as e:
                    logging.error(f"Error saving contact: {str(e)}", exc_info=True)
                    await query.message.reply_text(
                        "⚠️ Terjadi kesalahan. Silakan coba lagi."
                    )

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

            elif query.data == "show_help":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'help')
                    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
                    await query.message.edit_text(
                        Messages.HELP,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error showing help: {str(e)}")
                    await query.message.reply_text(Messages.ERROR_MESSAGE)
            elif query.data == "show_credits":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'credits')
                        credits = self.data_store.get_user_credits(user_id)

                    keyboard = [
                        [InlineKeyboardButton("🎁 Klaim 10 Kredit Gratis", callback_data="redeem_free_credits")],
                        [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="pay_75_150000")],
                        [InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000", callback_data="pay_150_300000")],
                        [InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000", callback_data="pay_250_399000")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await query.message.edit_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error showing credits: {str(e)}")
                    await query.message.reply_text(Messages.ERROR_MESSAGE)
            elif query.data == "show_suppliers":
                keyboard = []
                for cat, data in Messages.SUPPLIER_CATEGORIES.items():
                    keyboard.append([InlineKeyboardButton(
                        f"{data['emoji']} {cat}",
                        callback_data=f"supplier_{cat.lower().replace(' ', '_')}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])

                await query.message.edit_text(
                    "📤 *Kontak Supplier Indonesia*\n\nPilih kategori produk:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif query.data == "show_buyers":
                keyboard = []
                for cat, data in Messages.BUYER_CATEGORIES.items():
                    keyboard.append([InlineKeyboardButton(
                        f"{data['emoji']} {cat}",
                        callback_data=f"buyer_{cat.lower().replace(' ', '_')}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])

                await query.message.edit_text(
                    "📥 *Kontak Buyer*\n\nPilih kategori buyer:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif query.data.startswith("supplier_") or query.data.startswith("buyer_"):
                try:
                    category_type, category = query.data.split('_', 1)
                    categories = Messages.SUPPLIER_CATEGORIES if category_type == "supplier" else Messages.BUYER_CATEGORIES


                    cat_data = {}
                    # Handle nested categories
                    for key, data in categories.items():
                        if key.lower().replace(' ', '_') == category:
                            cat_data = data
                            break

                    if not cat_data:
                        await query.message.reply_text("Category not found")
                        return

                    keyboard = []
                    if 'subcategories' in cat_data:
                        with self.engine.connect() as conn:
                            for sub_name, sub_data in cat_data['subcategories'].items():
                                search_term = sub_data['search']
                                count = conn.execute(text("""
                                    SELECT COUNT(*) FROM importers 
                                    WHERE Role = :role AND Product LIKE :search
                                """), {
                                    "role": "Exporter" if category_type == "supplier" else "Importer",
                                    "search": f"%{search_term}%"
                                }).scalar()

                                keyboard.append([InlineKeyboardButton(
                                    f"{sub_data['emoji']} {sub_name} ({count} kontak)",
                                    callback_data=f"search_{search_term.replace(' ', '_')}"
                                )])

                    keyboard.append([InlineKeyboardButton(
                        "🔙 Kembali", 
                        callback_data="show_suppliers" if category_type == "supplier" else "show_buyers"
                    )])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "menu_seafood":
                with self.engine.connect() as conn:
                    hs_counts = conn.execute(text("""
                        SELECT 
                            CASE 
                                WHEN LOWER(product) LIKE '%0301%' THEN '0301'
                                WHEN LOWER(product) LIKE '%0302%' THEN '0302'
                                WHEN LOWER(product) LIKE '%0303%' THEN '0303'
                                WHEN LOWER(product) LIKE '%0304%' THEN '0304'
                                WHEN LOWER(product) LIKE '%0305%' OR LOWER(product) LIKE '%anchovy%' THEN '0305'
                            END as hs_code,
                            COUNT(*) as count
                        FROM importers
                        WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'
                        GROUP BY hs_code
                        ORDER BY hs_code;
                    """)).fetchall()

                    counts_dict = {row[0]: row[1] for row in hs_counts}

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
                        [InlineKeyboardButton("🔙 Kembali", callback_data="show_hs_codes")]
                    ]

                    await query.message.reply_text(
                        "🌊 *Produk Laut*",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

            elif query.data == "menu_agriculture":
                with self.engine.connect() as conn:
                    hs_counts = conn.execute(text("""
                        SELECT 
                            CASE 
                                WHEN LOWER(product) LIKE '%0901%' THEN '0901'
                                WHEN LOWER(product) LIKE '%1513%' OR LOWER(product) LIKE '%coconut oil%' THEN '1513'
                            END as hs_code,
                            COUNT(*) as count
                        FROM importers
                        WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                        GROUP BY hs_code
                        ORDER BY hs_code;
                    """)).fetchall()

                    counts_dict = {row[0]: row[1] for row in hs_counts}

                    keyboard = [
                        [InlineKeyboardButton(f"☕ Kopi (0901) - {counts_dict.get('0901', 0)} kontak",
                                             callback_data="search_0901")],
                        [InlineKeyboardButton(f"🥥 Minyak Kelapa - {counts_dict.get('1513', 0)} kontak",
                                             callback_data="search_coconut_oil")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="show_hs_codes")]
                    ]

                    await query.message.reply_text(
                        "🌿 *Produk Agrikultur*",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

            elif query.data == "menu_processed":
                try:
                    with self.engine.connect() as conn:
                        hs_counts = conn.execute(text("""
                            SELECT COUNT(*) as count
                            FROM importers
                            WHERE LOWER(product) LIKE '%44029010%';
                        """)).fetchall()

                        count = hs_counts[0][0] if hs_counts else 0

                        keyboard = [
                            [InlineKeyboardButton(f"🪵 Briket Batok (44029010) - {count} kontak",
                                                 callback_data="search_briket")],
                            [InlineKeyboardButton("🔙 Kembali", callback_data="show_hs_codes")]
                        ]

                        await query.message.reply_text(
                            "🌳 *Produk Olahan*",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logging.error(f"Error getting HS code counts: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan saat mengambil data.")
            elif query.data.startswith('search_'):
                user_id = query.from_user.id
                search_term = query.data.replace('search_', '').replace('_', ' ')
                context.user_data['search_page'] = 0  # Reset page for new search
                try:
                    with self.engine.connect() as conn:
                        results = conn.execute(text("""
                            SELECT *
                            FROM importers 
                            WHERE product = :search_term
                            LIMIT 10
                        """), {
                            "search_term": search_term
                        }).fetchall()

                        # Convert results to list of dicts properly
                        results = [dict(row._mapping) for row in results]

                        total_count = len(results)
                        if not results:
                            await query.message.reply_text("Tidak ada hasil yang ditemukan.")
                            return

                        # Store results in context
                        context.user_data['search_results'] = results
                        context.user_data['search_page'] = 0

                        # Show first page (2 results)
                        items_per_page = 2
                        total_pages = (total_count + items_per_page - 1) // items_per_page
                        current_page_results = results[:items_per_page]

                        # Store the last search results for potential save operations
                        context.user_data['last_search_results'] = results

                        # Display results with censored data
                        for result in current_page_results:
                            # Format and send message
                            message_text, _, callback_data = Messages.format_importer(result)
                            save_button = [[InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=callback_data
                            )]] if callback_data else []

                            await query.message.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(save_button) if save_button else None
                            )

                        # Add pagination buttons
                        navigation_buttons = []
                        if total_pages > 1:
                            navigation_buttons.append([
                                InlineKeyboardButton(f"1/{total_pages}", callback_data="page_info"),
                                InlineKeyboardButton("Next ➡️", callback_data="next_page")
                            ])
                        navigation_buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

                        await query.message.reply_text(
                            f"Menampilkan hasil 1-{min(items_per_page, total_count)} dari {total_count} kontak",
                            reply_markup=InlineKeyboardMarkup(navigation_buttons)
                        )

                except Exception as e:
                    logging.error(f"Error showing results: {str(e)}", exc_info=True)
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('give_'):
                try:
                    _, target_user_id, credit_amount = query.data.split('_')
                    if not self.data_store.get_user_credits(int(target_user_id)):
                        await query.message.reply_text("User tidak ditemukan.")
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
                        await query.message.reply_text("Gagal menambahkan kredit.")
                except Exception as e:
                    logging.error(f"Error giving credits: {str(e)}", exc_info=True)
                    await query.message.reply_text("Gagal menambahkan kredit.")

            elif query.data == "join_community":
                user_id = query.from_user.id
                with app.app_context():
                    credits = self.data_store.get_user_credits(user_id)

                if credits < 5:
                    await query.message.reply_text(
                        "⚠️ Kredit tidak mencukupi untuk bergabung dengan komunitas.\n"
                        "Dibutuhkan: 5 kredit\n"
                        "Sisa kredit Anda: " + str(credits)
                    )
                    return

                if self.data_store.use_credit(user_id, 5):
                    keyboard = [[InlineKeyboardButton(
                        "🚀 Gabung Sekarang",
                        url="https://t.me/+kuNU6lDtYoNlMTc1"
                    )]]
                    sent_message = await query.message.reply_text(
                        Messages.COMMUNITY_INFO,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    # Delete the message after 1 second
                    await asyncio.sleep(1)
                    await sent_message.delete()
                    # Update the original keyboard
                    keyboard = [
                        [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                        [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                        [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                         InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")]
                    ]
                    await query.message.edit_text(
                        text=Messages.MAIN_MENU.format(credits),
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.message.reply_text("Error using credit. Please try again later.")

        except Exception as e:
            logging.error(f"Error in button callback: {str(e)}", exc_info=True)
            await update.callback_query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")


    async def _check_member_status(self, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Check if user is a member of the channel"""
        try:
            chat_member = await context.bot.get_chat_member(chat_id="@kancilglobalnetwork", user_id=user_id)
            return chat_member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logging.error(f"Error checking member status: {str(e)}")
            return False

    async def orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if update.effective_user.id not in [6422072438]:
                await update.message.reply_text("Unauthorized")
                return

            page = context.user_data.get('orders_page', 0)
            items_per_page = 10
            with self.engine.connect() as conn:
                total_orders = conn.execute(text("""
                    SELECT COUNT(*) FROM credit_orders
                """)).scalar()
                total_pages = (total_orders + items_per_page - 1) // items_per_page  # Fixed calculation
                orders = conn.execute(text("""
                    SELECT order_id, user_id, credits, amount, status, created_at
                    FROM credit_orders
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {
                    "limit": items_per_page,
                    "offset": page * items_per_page
                }).fetchall()

            if not orders:
                await update.message.reply_text("No orders found")
                return

            message_text = "Daftar Pesanan Kredit:\n\n"
            for order in orders:
                try:
                    user = await context.bot.get_chat(order.user_id)
                    username = f"@{user.username}" if user.username else "No username"
                except:
                    username = "Unknown"

                message_text += f"Order ID: `{order.order_id}`\n" \
                                f"User ID: `{order.user_id}`\n" \
                                f"Username: {username}\n" \
                                f"Credits: {order.credits}\n" \
                                f"Amount: {order.amount}\n" \
                                f"Status: {order.status}\n" \
                                f"Created At: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            keyboard = []
            if page > 0:
                keyboard.append([InlineKeyboardButton("⬅️ Prev", callback_data="orders_prev")])
            if page < total_pages - 1:
                keyboard.append([InlineKeyboardButton("Next ➡️", callback_data="orders_next")])
            keyboard.append([InlineKeyboardButton("📥 Export to CSV", callback_data="export_orders")])

            await update.message.reply_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )
        except Exception as e:
            logging.error(f"Error in orders command: {str(e)}")
            await update.message.reply_text("Error retrieving orders. Please try again.")