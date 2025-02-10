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
                                count = conn.execute(text("""
                                    SELECT COUNT(*) FROM importers 
                                    WHERE Role = :role AND LOWER(Product) LIKE LOWER(:search)
                                    """), {
                                    "role": "Exporter" if category_type == "supplier" else "Importer",
                                    "search": f"%{search_term}%"
                                }).scalar()

                                keyboard.append([InlineKeyboardButton(
                                    f"{sub_data['emoji']} {sub_name} ({count} kontak)",
                                    callback_data=f"search_{search_term.replace(' ', '_')}"
                                )])

                    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}", exc_info=True)
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('search_'):
                await self.show_results(update, context, query.data.replace('search_', '').replace('_', ' '))

            elif query.data == "next_page" or query.data == "prev_page":
                try:
                    results = context.user_data.get('search_results', [])
                    current_page = context.user_data.get('search_page', 0)

                    if not results:
                        await query.message.reply_text("Tidak ada hasil pencarian yang tersedia.")
                        return

                    # Delete previous messages
                    message_ids = context.user_data.get('current_message_ids', [])
                    chat_id = query.message.chat_id

                    # Delete all previous messages
                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        except Exception as e:
                            logging.error(f"Error deleting message {msg_id}: {str(e)}")

                    # Update page number
                    items_per_page = 2
                    total_pages = (len(results) + items_per_page - 1) // items_per_page
                    if query.data == "prev_page":
                        current_page = max(0, current_page - 1)
                    else:  # next_page
                        current_page = min(total_pages - 1, current_page + 1)

                    context.user_data['search_page'] = current_page
                    start_idx = current_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(results))
                    current_results = results[start_idx:end_idx]

                    # Store new message IDs
                    new_message_ids = []

                    # Display new results
                    for result in current_results:
                        message_text, _, _ = Messages.format_importer(result)
                        save_button = [[InlineKeyboardButton(
                            "💾 Simpan Kontak",
                            callback_data=f"save_{result['name']}"  # Using name instead of id
                        )]]

                        sent_msg = await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(save_button)
                        )
                        new_message_ids.append(sent_msg.message_id)

                    # Add pagination buttons in a single row
                    navigation_row = []
                    if current_page > 0:
                        navigation_row.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev_page"))
                    navigation_row.append(InlineKeyboardButton(
                        f"{current_page + 1}/{total_pages}",
                        callback_data="page_info"
                    ))
                    if current_page < total_pages - 1:
                        navigation_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))

                    bottom_buttons = [
                        [InlineKeyboardButton("🔄 Cari Kembali", callback_data="regenerate_search")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
                    ]

                    nav_msg = await query.message.reply_text(
                        f"Halaman {current_page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([navigation_row] + bottom_buttons)
                    )
                    new_message_ids.append(nav_msg.message_id)

                    # Store new message IDs
                    context.user_data['current_message_ids'] = new_message_ids

                except Exception as e:
                    logging.error(f"Error in pagination: {str(e)}", exc_info=True)
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "regenerate_search":
                try:
                    # Get the last search parameters
                    last_search = context.user_data.get('last_search_context', {})
                    if not last_search:
                        await query.message.reply_text("Tidak ada riwayat pencarian sebelumnya.")
                        return

                    # Delete all current messages
                    message_ids = context.user_data.get('current_message_ids', [])
                    chat_id = query.message.chat_id

                    try:
                        await query.message.delete()
                    except Exception as e:
                        logging.error(f"Error deleting query message: {str(e)}")

                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        except Exception as e:
                            logging.error(f"Error deleting message {msg_id}: {str(e)}")

                    # Re-execute the search with the same parameters
                    search_pattern = last_search.get('pattern')
                    if search_pattern:
                        await self.show_results(update, context, search_pattern)
                    else:
                        await query.message.reply_text("Tidak dapat mengulang pencarian sebelumnya.")

                except Exception as e:
                    logging.error(f"Error in regenerate search: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan saat mengulang pencarian.")

            elif query.data == "page_info":
                await query.answer("Halaman saat ini", show_alert=False)

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
            elif query.data == "back_to_categories":
                # Handle going back to category selection
                try:
                    search_context = context.user_data.get('last_search_context', {})
                    category_type = search_context.get('category_type', 'buyer')  # Default to buyer if not found

                    if category_type == 'supplier':
                        # Go back to supplier categories
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
                    else:
                        # Go back to buyer categories
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
                except Exception as e:
                    logging.error(f"Error returning to categories: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('save_'):
                await self.save_contact(user_id, query.data[5:], update)

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
                    logging.error(f"Errorshowing help: {str(e)}")
                    await query.message.reply_text(Messages.ERROR_MESSAGE)
            elif query.data == "show_credits":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'credits')
                        credits = self.data_store.get_user_credits(user_id)  # Fixed typo here

                    keyboard = [
                        [InlineKeyboardButton("🎁 Klaim 10 KreditGratis", callback_data="redeem_free_credits")],
                        [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="order_75")],
                        [InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000", callback_data="order_150")],
                        [InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000", callback_data="order_250")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await query.message.edit_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error showing credits: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

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
                # Build keyboard for buyers categories
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
                                    WHERE Role = :role AND LOWER(Product) LIKE LOWER(:search)
                                    """), {
                                    "role": "Exporter" if category_type == "supplier" else "Importer",
                                    "search": f"%{search_term}%"
                                }).scalar()

                                keyboard.append([InlineKeyboardButton(
                                    f"{sub_data['emoji']} {sub_name} ({count} kontak)",
                                    callback_data=f"search_{search_term.replace(' ', '_')}"
                                )])

                    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}", exc_info=True)
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
                            COUNT(*) as count                        FROM importers
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
                                WHEN LOWER(product) LIKE '%1513%' OR LOWER(product) LIKE '%coconut oil%' THEN '1513'END as hs_code,
                            COUNT(*) as count
                        FROM importers
                        WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                        GROUP BY hs_code;
                        ORDER BY hscode;
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
                try:
                    search_pattern = query.data.replace('search_', '').replace('_', ' ')
                    logging.info(f"Searching for pattern: {search_pattern}")

                    # Clean up any existing messages first
                    message_ids = context.user_data.get('current_message_ids', [])
                    chat_id = query.message.chat_id

                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(
                                chat_id=chat_id,
                                message_id=msg_id
                            )
                        except Exception as e:
                            logging.error(f"Error deleting message {msg_id}: {str(e)}")

                    # Get results from database
                    with self.engine.connect() as conn:
                        results = conn.execute(text("""
                            SELECT *
                            FROM importers 
                            WHERE LOWER(product) LIKE LOWER(:search_term)
                            ORDER BY name
                            LIMIT 10
                        """), {
                            "search_term": f"%{search_pattern}%"
                        }).fetchall()

                        # Convert results to list of dicts
                        results = [dict(row._mapping) for row in results]

                        if not results:
                            await query.message.reply_text("Tidak ada hasil yang ditemukan.")
                            return

                        # Store results and initialize page
                        context.user_data['search_results'] = results
                        context.user_data['search_page'] = 0
                        context.user_data['current_message_ids'] = []  # Initialize message tracking
                        context.user_data['last_search_context'] = {'pattern': search_pattern}

                        # Show first page (2 results)
                        items_per_page = 2
                        total_pages = (len(results) + items_per_page - 1) // items_per_page
                        current_results = results[:items_per_page]

                        # Store message IDs for later cleanup
                        message_ids = []

                        # Display results
                        for result in current_results:
                            message_text, _, _ = Messages.format_importer(result)
                            save_button = [[InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=f"save_{result['name']}"  # Using name instead of id
                            )]]

                            sent_msg = await query.message.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(save_button)
                            )
                            message_ids.append(sent_msg.message_id)

                        # Add pagination buttons in a single row
                        navigation_row = []
                        if total_pages > 1:
                            navigation_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
                        navigation_row.append(InlineKeyboardButton(
                            f"1/{total_pages}",
                            callback_data="page_info"
                        ))

                        bottom_buttons = [
                            [InlineKeyboardButton("🔄 Cari Kembali", callback_data="regenerate_search")],
                            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
                        ]

                        nav_msg = await query.message.reply_text(
                            f"Halaman 1 dari {total_pages}",
                            reply_markup=InlineKeyboardMarkup([navigation_row] + bottom_buttons)
                        )
                        message_ids.append(nav_msg.message_id)

                        # Store message IDs in context
                        context.user_data['current_message_ids'] = message_ids

                except Exception as e:
                    logging.error(f"Error in search results: {str(e)}", exc_info=True)
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi."
                    )

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
                total_pages = (total_orders + items_per_page - 1) // items_per_page
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

    async def export_saved_contacts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        saved_contacts = self.data_store.get_saved_contacts(user_id)
        if not saved_contacts:
            await update.message.reply_text("No saved contacts to export")
            return
        csv_data = self.data_store.format_saved_contacts_to_csv(saved_contacts)
        await context.bot.send_document(update.effective_chat.id, document=csv_data, filename='saved_contacts.csv')

    async def export_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [6422072438]:
            await update.message.reply_text("Unauthorized")
            return
        csv_data = self.data_store.format_orders_to_csv()
        await context.bot.send_document(update.effective_chat.id, document=csv_data, filename='credit_orders.csv')

    async def show_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, search_pattern: str):
        """Show search results with pagination"""
        try:
            # Get results from database
            with self.engine.connect() as conn:
                results = conn.execute(text("""
                    SELECT * FROM importers 
                    WHERE LOWER(product) SIMILAR TO :pattern
                    OR LOWER(name) SIMILAR TO :pattern
                    OR LOWER(country) SIMILAR TO :pattern
                    ORDER BY name
                    LIMIT 100
                """), {
                    "pattern": f"%{search_pattern.lower()}%"
                }).fetchall()

                # Convert results to list of dicts
                results = [dict(row._mapping) for row in results]

            if not results:
                reply_to = update.callback_query.message if hasattr(update, 'callback_query') else update.message
                await reply_to.reply_text("Tidak ada hasil yang ditemukan.")
                return

            # Store results and initialize page
            context.user_data['search_results'] = results
            context.user_data['search_page'] = 0
            context.user_data['current_message_ids'] = []  # Initialize message tracking
            context.user_data['last_search_context'] = {'pattern': search_pattern}

            # Show first page (2 results)
            items_per_page = 2
            total_pages = (len(results) + items_per_page - 1) // items_per_page
            current_results = results[:items_per_page]

            # Store message IDs for later cleanup
            message_ids = []

            # Get the appropriate message object for replies
            reply_to = update.callback_query.message if hasattr(update, 'callback_query') else update.message

            # Display results
            for result in current_results:
                message_text, _, _ = Messages.format_importer(result)
                save_button = [[InlineKeyboardButton(
                    "💾 Simpan Kontak",
                    callback_data=f"save_{result['name']}"  # Use name instead of id
                )]]

                sent_msg = await reply_to.reply_text(
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(save_button)
                )
                message_ids.append(sent_msg.message_id)

            # Add pagination buttons in a single row
            navigation_row = []
            if total_pages > 1:
                navigation_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
            navigation_row.append(InlineKeyboardButton(
                f"1/{total_pages}",
                callback_data="page_info"
            ))

            # Add bottom navigation buttons
            bottom_buttons = [
                [InlineKeyboardButton("🔄 Cari Kembali", callback_data="regenerate_search")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
            ]

            nav_msg = await reply_to.reply_text(
                f"Halaman 1 dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([navigation_row] + bottom_buttons)
            )
            message_ids.append(nav_msg.message_id)

            # Store message IDs in context
            context.user_data['current_message_ids'] = message_ids

        except Exception as e:
            logging.error(f"Error in show_results: {str(e)}", exc_info=True)
            try:
                reply_to = update.callback_query.message if hasattr(update, 'callback_query') else update.message
                await reply_to.reply_text(
                    "Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi."
                )
            except Exception as inner_e:
                logging.error(f"Error sending error message: {str(inner_e)}", exc_info=True)

    async def save_contact(self, user_id: int, contact_name: str, update: Update):
        """Save contact to user's saved list"""
        try:
            logging.info(f"Starting save contact process for user {user_id}")
            
            # Get current credits
            current_credits = self.data_store.get_user_credits(user_id)
            if current_credits is None or current_credits <= 0:
                await update.callback_query.message.reply_text(
                    "⚠️ Kredit Anda tidak mencukupi untuk menyimpan kontak ini."
                )
                return

            # Get importer data
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        id,
                        name as importer_name,
                        phone,                      
                        website,
                        email_1 as email,
                        product as hs_code,
                        country,
                        wa_availability as wa_available,
                        role as product_description,
                        CURRENT_TIMESTAMP as saved_at
                    FROM importers 
                    WHERE name = :name
                """), {"name": contact_name}).first()

                if not result:
                    await update.callback_query.message.reply_text(
                        "⚠️ Kontak tidak ditemukan. Silakan coba cari kembali."
                    )
                    return

                importer = dict(result._mapping)
                logging.debug(f"Found importer data: {importer}")

                # Save contact with transaction
                try:
                    # Deduct credit first
                    self.data_store.use_credit(user_id, 1)
                    
                    # Then save contact
                    success = await self.data_store.save_contact(
                        user_id=user_id,
                        importer=importer
                    )

                    if success:
                        new_balance = self.data_store.get_user_credits(user_id)
                        await update.callback_query.message.reply_text(
                            f"✅ Kontak berhasil disimpan!\n\n"
                            f"💳 Sisa kredit: {new_balance} kredit\n\n"
                            f"Gunakan /saved untuk melihat kontak tersimpan."
                        )
                    else:
                        # Rollback credit deduction if save fails
                        self.data_store.add_credits(user_id, 1)
                        await update.callback_query.message.reply_text(
                            "⚠️ Gagal menyimpan kontak. Silakan coba lagi atau hubungi admin jika masalah berlanjut."
                        )

                except Exception as e:
                    logging.error(f"Transaction error: {str(e)}")
                    conn.rollback()
                    raise

        except Exception as e:
            logging.error(f"Error saving contact: {str(e)}", exc_info=True)
            await update.callback_query.message.reply_text(
                "Maaf, terjadi kesalahan saat menyimpan kontak."
            )