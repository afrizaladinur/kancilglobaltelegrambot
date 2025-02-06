import logging
import time
import asyncio
from datetime import datetime
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlalchemy import text

from data_store import DataStore
from app import app
from messages import Messages

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        self.engine = self.data_store.engine
        logging.info("CommandHandler initialized")
        self._last_save_time = {} # Initialize _last_save_time here

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            admin_ids = [6422072438]  # Admin user IDs
            is_admin = user_id in admin_ids

            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
                if credits is None:
                    self.data_store.initialize_user_credits(user_id, 10.0 if not is_admin else 999999.0)
                    credits = 10.0 if not is_admin else 999999.0
                self.data_store.track_user_command(user_id, 'start')

            keyboard = [
                [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                 InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
            ]

            await update.message.reply_text(
                f"{Messages.START}\n{Messages.CREDITS_REMAINING.format(credits)}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Start command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in start command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'saved')
                saved_contacts = self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                await update.message.reply_text(Messages.NO_SAVED_CONTACTS)
                return

            for contact in saved_contacts[:2]:  # Show first 2 contacts
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

            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
            await update.message.reply_text(
                "Gunakan tombol navigasi untuk melihat kontak lainnya.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'credits')
                credits = self.data_store.get_user_credits(user_id)

            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
            await update.message.reply_text(
                Messages.CREDITS_INFO.format(credits),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /orders command - Admin only"""
        if update.effective_user.id not in [6422072438]:  # Admin check
            await update.message.reply_text("⛔️ You are not authorized to use this command.")
            return

        with self.engine.connect() as conn:
            orders = conn.execute(text("""
                SELECT * FROM credit_orders 
                ORDER BY created_at DESC 
                LIMIT 5
            """)).fetchall()

        if not orders:
            await update.message.reply_text("No orders found.")
            return

        for order in orders:
            status_emoji = "✅" if order.status == "fulfilled" else "⏳"
            try:
                user = await context.bot.get_chat(order.user_id)
                username = f"@{user.username}" if user.username else "No username"
            except:
                username = "Unknown"

            message = f"""
*Order ID:* `{order.order_id}`
*User ID:* `{order.user_id}`
*Username:* {username}
*Credits:* {order.credits}
*Amount:* Rp {order.amount:,}
*Status:* {status_emoji} {order.status}
*Date:* {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
            keyboard = []
            if order.status != "fulfilled":
                keyboard.append([InlineKeyboardButton(
                    "✅ Fulfill Order",
                    callback_data=f"fulfill_{order.order_id}"
                )])

            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )


    async def save_contact(self, query: Update, context: ContextTypes.DEFAULT_TYPE, importer_name: str) -> None:
        """Handle saving a contact with rate limiting and improved error handling"""
        try:
            user_id = query.from_user.id

            # Add rate limiting check
            if hasattr(self, '_last_save_time') and self._last_save_time.get(user_id):
                time_diff = time.time() - self._last_save_time[user_id]
                if time_diff < 3:  # 3 seconds cooldown
                    await query.message.reply_text(
                        "⚠️ Mohon tunggu beberapa detik sebelum menyimpan kontak lagi."
                    )
                    return

            logging.info(f"Starting save_contact process for user {user_id}")
            logging.info(f"Attempting to save contact for importer: {importer_name}")

            # Get the user's last search results from context
            last_results = context.user_data.get('last_search_results', [])

            if not last_results:
                logging.error("No search results found in context")
                await query.message.reply_text(
                    "Kontak tidak ditemukan. Silakan lakukan pencarian ulang terlebih dahulu."
                )
                return

            # Find the matching importer with improved matching logic
            importer = None
            logging.info(f"Looking for importer: {importer_name}")

            # Try exact match first
            for result in last_results:
                if result.get('name') == importer_name:
                    importer = result
                    logging.info(f"Found exact matching importer: {importer}")
                    break

            # If no exact match, try partial match
            if not importer:
                for result in last_results:
                    if importer_name in result.get('name', ''):
                        importer = result
                        logging.info(f"Found partial matching importer: {importer}")
                        break

            if not importer:
                logging.error(f"Importer {importer_name} not found in last_search_results")
                await query.message.reply_text(
                    "Kontak tidak ditemukan. Silakan coba cari kembali.\n"
                    "Pastikan Anda melakukan pencarian terlebih dahulu."
                )
                return

            # Update last save time for rate limiting
            if not hasattr(self, '_last_save_time'):
                self._last_save_time = {}
            self._last_save_time[user_id] = time.time()

            with app.app_context():
                result = await self.data_store.save_contact(user_id, importer)

            if result:
                with app.app_context():
                    credits = self.data_store.get_user_credits(user_id)

                await query.message.reply_text(
                    f"✅ Kontak berhasil disimpan!\n\nKredit tersisa: {credits}"
                )
                logging.info(f"Successfully saved contact for user {user_id}")
            else:
                await query.message.reply_text(
                    "⚠️ Kredit tidak mencukupi atau kontak sudah tersimpan sebelumnya."
                )
                logging.warning(f"Failed to save contact for user {user_id} - insufficient credits or duplicate")

        except Exception as e:
            logging.error(f"Error saving contact: {str(e)}", exc_info=True)
            await query.message.reply_text(
                "Terjadi kesalahan. Silakan coba lagi nanti.\n"
                "Jika masalah berlanjut, hubungi admin."
            )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()

            if query.data.startswith('save_'):
                # Extract full importer name from callback data
                importer_name = query.data[5:]  # Remove 'save_' prefix
                await self.save_contact(query, context, importer_name)
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

                # Get saved contacts
                with app.app_context():
                    saved_contacts = self.data_store.get_saved_contacts(user_id)
                if not saved_contacts:
                    await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                    return

                # Calculate pagination
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

                # Send paginated contacts
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

                # Send pagination controls
                sent_msg = await query.message.reply_text(
                    f"Halaman {current_page + 1} dari {total_pages}",
                    reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
                )
                new_messages.append(sent_msg.message_id)
                context.user_data['current_search_messages'] = new_messages

            elif query.data == "show_saved_page_info":
                await query.answer("Halaman saat ini", show_alert=False)
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
                    # Delete current message
                    await query.message.delete()

                    header_text = """📊 *Kontak Tersedia*

                    Pilih kategori produk:"""

                    # Count contacts for each category
                    with self.engine.connect() as conn:
                        seafood_count = conn.execute(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'
                        """)).scalar()

                        agriculture_count = conn.execute(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                        """)).scalar()

                        processed_count = conn.execute(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) LIKE '%44029010%'
                        """)).scalar()

                    keyboard = [
                        [InlineKeyboardButton(f"🌊 Produk Laut ({seafood_count} kontak)", callback_data="folder_seafood")],
                        [InlineKeyboardButton(f"🌿 Produk Agrikultur ({agriculture_count} kontak)", callback_data="folder_agriculture")],
                        [InlineKeyboardButton(f"🌳 Produk Olahan ({processed_count} kontak)", callback_data="folder_processed")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await query.message.reply_text(
                        header_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error getting HS code counts: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan saat mengambil data.")

            elif query.data == "folder_seafood":
                try:
                    # Delete previous message
                    await query.message.delete()

                    folder_text = """🌊 *Produk Laut*

                    Pilih produk:"""
                    with self.engine.connect() as conn:
                        counts = {
                            '0301': conn.execute(text("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%0301%'")).scalar(),
                            '0302': conn.execute(text("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%0302%'")).scalar(),
                            '0303': conn.execute(text("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%0303%'")).scalar(),
                            '0304': conn.execute(text("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%0304%'")).scalar(),
                            'anchovy': conn.execute(text("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%anchovy%'")).scalar()
                        }

                    keyboard = [
                        [InlineKeyboardButton(f"🐟 Ikan Hidup ({counts['0301']} kontak)", callback_data="search_0301")],
                        [InlineKeyboardButton(f"🐠 Ikan Segar ({counts['0302']} kontak)", callback_data="search_0302")],
                        [InlineKeyboardButton(f"❄️ Ikan Beku ({counts['0303']} kontak)", callback_data="search_0303")],
                        [InlineKeyboardButton(f"🍣 Fillet Ikan ({counts['0304']} kontak)", callback_data="search_0304")],
                        [InlineKeyboardButton(f"🐟 Anchovy ({counts['anchovy']} kontak)", callback_data="search_anchovy")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
                    ]
                    await query.message.reply_text(
                        folder_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error in folder_seafood handler: {str(e)}")
                    await query.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "folder_agriculture":
                # Delete previous message
                await query.message.delete()

                folder_text = """🌿 *Produk Agrikultur*

                Pilih produk:"""
                with self.engine.connect() as conn:
                    coffee_count = conn.execute(text("""
                        SELECT COUNT(*) FROM importers 
                        WHERE LOWER(product) LIKE '%0901%'
                    """)).scalar()

                    manggis_count = conn.execute(text("""
                        SELECT COUNT(*) FROM importers 
                        WHERE LOWER(product) SIMILAR TO '%(0810|manggis|mangosteen)%'
                    """)).scalar()

                keyboard = [
                    [InlineKeyboardButton(f"☕ Kopi ({coffee_count} kontak)", callback_data="search_0901")],
                    [InlineKeyboardButton(f"🫐 Manggis ({manggis_count} kontak)", callback_data="search_manggis")],
                    [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
                ]
                await query.message.reply_text(
                    folder_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif query.data == "folder_processed":
                # Delete previous message
                await query.message.delete()

                folder_text = """🌳 *Produk Olahan*

                Pilih produk:"""
                with self.engine.connect() as conn:
                    briket_count = conn.execute(text("""
                        SELECT COUNT(*) FROM importers 
                        WHERE LOWER(product) LIKE '%44029010%'
                    """)).scalar()

                    coconut_count = conn.execute(text("""
                        SELECT COUNT(*) FROM importers 
                        WHERE LOWER(product) SIMILAR TO '%(1513|coconut oil|minyak kelapa)%'
                    """)).scalar()

                keyboard = [
                    [InlineKeyboardButton(f"🪵 Briket Batok ({briket_count} kontak)", callback_data="search_briket")],
                    [InlineKeyboardButton(f"🥥 Minyak Kelapa ({coconut_count} kontak)", callback_data="search_coconut_oil")],
                    [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
                ]
                await query.message.reply_text(
                    folder_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

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
                search_term = query.data.replace('search_', '')
                search_terms = {
                    '0301': '0301',
                    '0302': '0302',
                    '0303': '0303', 
                    '0304': '0304',
                    'anchovy': 'anchovy',
                    '0901': '0901',
                    'coconut_oil': 'coconut oil',
                    'briket': '44029010',
                    'manggis': 'mangosteen'
                }

                if search_term in search_terms:
                    # Set up context.args manually
                    search_query = search_terms[search_term]
                    context.args = [search_query]

                    # Get results directly 
                    results = self.data_store.search_importers(search_query)

                    if not results:
                        await query.message.reply_text(
                            f"Tidak ada hasil untuk pencarian '{search_query}'"
                        )
                        return

                    # Store results and reset page
                    context.user_data['last_search_results'] = results
                    context.user_data['search_page'] = 0
                    context.user_data['last_search_query'] = search_query

                    # Show first page
                    page = 0
                    items_per_page = 2
                    total_pages = (len(results) + items_per_page - 1) // items_per_page
                    start_idx = page * items_per_page
                    end_idx = start_idx + items_per_page
                    current_results = results[start_idx:end_idx]

                    new_messages = []
                    for importer in current_results:
                        message_text, _, _ = Messages.format_importer(importer, user_id=user_id)
                        keyboard = [[InlineKeyboardButton(
                            "💾 Simpan Kontak",
                            callback_data=f"save_{importer['name']}"  # Use full name
                        )]]
                        sent_msg = await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        new_messages.append(sent_msg.message_id)

                    # Add pagination buttons
                    pagination_buttons = []
                    if page > 0:
                        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
                    pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="search_page_info"))
                    if page < total_pages - 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="search_next"))

                    ## Add regenerate button
                    regenerate_button = [
                        [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="backto_categories")]
                    ]

                    sent_msg = await query.message.reply_text(
                        f"Halaman {page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons] + regenerate_button)
                    )
                    new_messages.append(sent_msg.message_id)
                    context.user_data['current_search_messages'] = new_messages

            elif query.data.startswith('section_'):
                # Just ignore section headers
                await query.answer()

            elif query.data in ["orders_prev", "orders_next"]:
                if query.from_user.id not in [6422072438]:  # Admin check
                    await query.answer("Not authorized", show_alert=True)
                    return

                page = context.user_data.get('orders_page', 0)
                if query.data == "orders_prev":
                    page = max(0, page - 1)
                else:
                    page = page + 1

                context.user_data['orders_page'] = page
                await self.orders(update, context)

            elif query.data == "export_orders":
                if query.from_user.id not in [6422072438]:  # Admin check
                    await query.answer("Not authorized", show_alert=True)
                    return

                try:
                    with self.engine.connect() as conn:
                        orders = conn.execute(text("""
                            SELECT * FROM credit_orders 
                            ORDER BY created_at DESC
                        """)).fetchall()

                    if not orders:
                        await query.message.reply_text("No orders to export.")
                        return

                    csv_content = "Order ID,User ID,Credits,Amount,Status,Created At\n"
                    for order in orders:
                        csv_content += f"{order.order_id},{order.user_id},{order.credits},"
                        csv_content += f"{order.amount},{order.status},{order.created_at}\n"

                    await query.message.reply_document(
                        document=csv_content.encode(),
                        filename="orders.csv",
                        caption="Here's your orders export."
                    )
                except Exception as e:
                    logging.error(f"Error exporting orders: {str(e)}")
                    await query.message.reply_text("Error exporting orders.")

            elif query.data.startswith('fulfill_'):
                if query.from_user.id not in [6422072438]:  # Admin check
                    await query.answer("Not authorized", show_alert=True)
                    return

                order_id = '_'.join(query.data.split('_')[1:])  # Handle order IDs with underscores
                try:
                    with self.engine.begin() as conn:
                        # Get order details
                        order = conn.execute(text("""
                            SELECT user_id, credits, status
                            FROM credit_orders 
                            WHERE order_id = :order_id
                            FOR UPDATE
                        """), {"order_id": order_id}).first()

                        if not order:
                            await query.answer("Order not found", show_alert=True)
                            return

                        if order.status == "fulfilled":
                            await query.answer("Order already fulfilled", show_alert=True)
                            return

                        # Add credits to user
                        if self.data_store.add_credits(order.user_id, order.credits):
                            # Update order status
                            conn.execute(text("""
                                UPDATE credit_orders 
                                SET status = 'fulfilled', 
                                    fulfilled_at = CURRENT_TIMESTAMP
                                WHERE order_id = :order_id
                            """), {"order_id": order_id})

                            # Delete the order message
                            await query.message.delete()

                            # Notify user
                            await context.bot.send_message(
                                chat_id=order.user_id,
                                text=f"✅ Your order (ID: {order_id}) has been fulfilled!\n{order.credits} credits have been added to your account."
                            )
                        else:
                            await query.answer("Failed to add credits", show_alert=True)

                except Exception as e:
                    logging.error(f"Error fulfilling order: {str(e)}")
                    await query.answer("Error processing order", show_alert=True)

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
                         InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                        [InlineKeyboardButton("🔓 Buka Kancil Global Network", url="https://t.me/+kuNU6lDtYoNlMTc1")],
                        [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                        [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
                    ]
                    await query.message.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.message.reply_text("Terjadi kesalahan, silakan coba lagi.")

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

                    keyboard = [                    [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="pay_75_150000")],
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

    async def orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /orders command for admins"""
        try:
            user_id = update.effective_user.id
            admin_ids = [6422072438]  # Admin check

            if user_id not in admin_ids:
                await update.message.reply_text("⛔️ You are not authorized to use this command.")
                return

            # Fetch orders from database with pagination
            with self.engine.connect() as conn:
                # Get total count
                total_count = conn.execute(text("""
                    SELECT COUNT(*) FROM credit_orders WHERE status = 'pending'
                """)).scalar()

                # Get current page from context
                page = context.user_data.get('orders_page', 0)
                items_per_page = 5

                # Calculate offset
                offset = page * items_per_page
                orders = conn.execute(text("""
                    SELECT order_id, user_id, credits, amount, status, created_at
                    FROM credit_orders 
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {
                    "limit": items_per_page,
                    "offset": offset
                }).fetchall()

                total_pages = (total_count + items_per_page - 1) // items_per_page

                # Format order messages
                for order in orders:
                    status_emoji = "✅" if order.status == "fulfilled" else "⏳"
                    # Get user info from Telegram
                    try:
                        user = await context.bot.get_chat(order.user_id)
                        username = f"@{user.username}" if user.username else "No username"
                    except:
                        username = "Unknown"

                    message = f"""
                    *Order ID:* `{order.order_id}`
                    *User ID:* `{order.user_id}`
                    *Username:* {username}
                    *Credits:* {order.credits}
                    *Amount:* Rp {order.amount:,}
                    *Status:* {status_emoji} {order.status}
                    *Date:* {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}
                """
                    keyboard = []
                    if order.status != "fulfilled":
                        keyboard.append([InlineKeyboardButton(
                            "✅ Fulfill Order",
                            callback_data=f"fulfill_{order.order_id}"
                        )])
                    elif order.status == "fulfilled":
                        message += "\n✅ *Order fulfilled*"

                    await update.message.reply_text(
                        message,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )

                # Add pagination buttons
                pagination_buttons = []
                if page > 0:
                    pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="orders_prev"))
                pagination_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="orders_page"))
                if page < total_pages - 1:
                    pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="orders_next"))

                # Add export button
                export_buttons = [
                    [InlineKeyboardButton("📥 Export Orders", callback_data="export_orders")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ]

                await update.message.reply_text(
                    f"Page {page + 1} of {total_pages}",
                    reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
                )

        except Exception as e:
            logging.error(f"Error in orders command: {str(e)}", exc_info=True)
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

            keyboard = [
                [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="pay_75_150000")],
                [InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000", callback_data="pay_150_300000")],
                [InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000", callback_data="pay_250_399000")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await update.message.reply_text(
                f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Credits command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)
            logging.info(f"Credits command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search command"""
        try:
            user_id = update.effective_user.id
            logging.info(f"Processing search command for user {user_id}")

            if not context.args:
                logging.info("No search query provided")
                keyboard = [[InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")]]
                await update.message.reply_text(
                    "Silakan masukkan kata kunci pencarian.\n"
                    "Contoh: /search ikan atau /search coffee",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                return

            query = ' '.join(context.args)
            logging.info(f"Search query from user {user_id}: {query}")

            with app.app_context():
                self.data_store.track_user_command(user_id, 'search')
                results = self.data_store.search_importers(query)

                if not results:
                    logging.info(f"No results found for query: {query}")
                    await update.message.reply_text(
                        f"Tidak ada hasil untuk pencarian '{query}'\n"
                        "Silakan coba kata kunci lain."
                    )
                    return

                # Clear previous search results and store new ones
                context.user_data.clear()  # Clear previous data
                context.user_data['last_search_results'] = results
                context.user_data['search_page'] = 0
                context.user_data['last_search_query'] = query

                logging.info(f"Stored {len(results)} results in context for user {user_id}")
                logging.debug(f"Context keys after storage: {context.user_data.keys()}")

                # Show first page results
                page = 0
                items_per_page = 2
                total_pages = (len(results) + items_per_page - 1) // items_per_page
                start_idx = page * items_per_page
                end_idx = start_idx + items_per_page
                current_results = results[start_idx:end_idx]

                for importer in current_results:
                    message_text, _, _ = Messages.format_importer(importer, user_id=user_id)
                    # Store the full name as callback data
                    keyboard = [[InlineKeyboardButton(
                        "💾 Simpan Kontak",
                        callback_data=f"save_{importer['name']}"
                    )]]

                    await update.message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                # Add navigation buttons
                navigation = []
                if total_pages > 1:
                    navigation.append(InlineKeyboardButton("Next ➡️", callback_data="search_next"))

                back_button = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]

                if navigation:
                    await update.message.reply_text(
                        f"Halaman {page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([navigation] + back_button)
                    )
                else:
                    await update.message.reply_text(
                        "Gunakan tombol di bawah untuk navigasi",
                        reply_markup=InlineKeyboardMarkup(back_button)
                    )

        except Exception as e:
            logging.error(f"Error in search command: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "Terjadi kesalahan dalam pencarian.\n"
                "Silakan coba lagi nanti."
            )

    async def check_rate_limit(self, update: Update) -> bool:
        """Check rate limits for commands"""
        user_id = update.effective_user.id
        command = update.message.text.split()[0] if update.message else None
        with app.app_context():
            return self.data_store.check_rate_limit(user_id, command)