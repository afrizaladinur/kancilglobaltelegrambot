import logging
import os
import time
from sqlalchemy import text
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
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
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'start')
                credits = self.data_store.get_user_credits(user_id)
                if credits is None:
                    self.data_store.initialize_user_credits(user_id, 10.0)
                    credits = 10.0

            keyboard = [
                [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="trigger_contacts")],
                [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="trigger_saved")],
                [InlineKeyboardButton("💳 Kredit & Pembelian", callback_data="show_credits")],
                [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
            ]
            await update.message.reply_text(
                Messages.START,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Start command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in start command: {str(e)}", exc_info=True)
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
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Credits command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def give_credits_helper(self, user_id: int, credits: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Helper method to give credits to a user"""
        try:
            with app.app_context():
                if self.data_store.add_credits(user_id, credits):
                    # Update order status
                    with self.engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE credit_orders 
                            SET status = 'fulfilled', fulfilled_at = CURRENT_TIMESTAMP 
                            WHERE user_id = :user_id AND credits = :credits AND status = 'pending'
                        """), {"user_id": user_id, "credits": credits})

                    # Notify user
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ {credits} kredit telah ditambahkan ke akun Anda!"
                    )
                    return True
                return False
        except Exception as e:
            logging.error(f"Error giving credits: {str(e)}")
            return False

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        chat_id = query.message.chat_id
        user_id = query.from_user.id

        await query.answer()

        try:
            if query.data == "back_to_main":
                # Delete current message and show main menu
                await query.message.delete()
                keyboard = [
                    [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="trigger_contacts")],
                    [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="trigger_saved")],
                    [InlineKeyboardButton("💳 Kredit & Pembelian", callback_data="show_credits")],
                    [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                    [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
                ]
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text=Messages.START,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif query.data == "trigger_contacts":
                try:
                    # Delete current message
                    await query.message.delete()

                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'contacts')

                    # Show HS code categories menu
                    header_text = """📊 *Kontak Tersedia*\n\nPilih kategori produk:"""

                    try:
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

                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=header_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                            logging.info(f"Contacts menu shown successfully for user {user_id}")
                    except Exception as e:
                        logging.error(f"Database error in trigger_contacts: {str(e)}")
                        raise

                except Exception as e:
                    logging.error(f"Error in trigger_contacts: {str(e)}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Terjadi kesalahan. Silakan coba lagi."
                    )

            elif query.data == "trigger_saved":
                try:
                    # Delete current message
                    await query.message.delete()

                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'saved')
                        saved_contacts = self.data_store.get_saved_contacts(user_id)

                    if not saved_contacts:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=Messages.NO_SAVED_CONTACTS
                        )
                        return

                    items_per_page = 2
                    total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
                    current_page = 0
                    start_idx = current_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(saved_contacts))
                    current_contacts = saved_contacts[start_idx:end_idx]

                    for contact in current_contacts:
                        try:
                            message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
                            keyboard = []
                            if whatsapp_number:
                                keyboard.append([InlineKeyboardButton(
                                    "💬 Chat di WhatsApp",
                                    url=f"https://wa.me/{whatsapp_number}"
                                )])

                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                            )
                        except Exception as e:
                            logging.error(f"Error sending contact message: {str(e)}")
                            continue

                    # Add pagination buttons
                    pagination_buttons = []
                    if total_pages > 1:
                        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="saved_next"))

                    export_buttons = [
                        [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"Halaman 1 dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
                    )
                    logging.info(f"Saved contacts shown successfully for user {user_id}")
                except Exception as e:
                    logging.error(f"Error in trigger_saved: {str(e)}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Terjadi kesalahan. Silakan coba lagi."
                    )

            elif query.data == "show_credits":
                try:
                    # Delete current message to avoid clutter
                    await query.message.delete()

                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'credits')
                        credits = self.data_store.get_user_credits(user_id)

                    keyboard = [
                        [InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000", callback_data="pay_75_150000")],
                        [InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000", callback_data="pay_150_300000")],
                        [InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000", callback_data="pay_250_399000")],
                        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
                    ]

                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    logging.info(f"Credits menu shown successfully for user {user_id}")
                except Exception as e:
                    logging.error(f"Error in show_credits: {str(e)}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Terjadi kesalahan. Silakan coba lagi."
                    )

            elif query.data.startswith('pay_'):
                try:
                    _, credits, amount = query.data.split('_')
                    user_id = query.from_user.id
                    chat_id = query.message.chat_id
                    username = query.from_user.username or str(user_id)
                    order_id = f"BOT_{user_id}_{int(time.time())}"

                    # Insert order into database
                    with self.engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO credit_orders (order_id, user_id, credits, amount, status)
                            VALUES (:order_id, :user_id, :credits, :amount, 'pending')
                        """), {
                            "order_id": order_id,
                            "user_id": user_id,
                            "credits": int(credits),
                            "amount": int(amount)
                        })

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

                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=payment_message,
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

                    # Send notification to admin
                    admin_ids = [6422072438]
                    for admin_id in admin_ids:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(admin_keyboard)
                        )

                    logging.info(f"Manual payment order created successfully: {order_id}")

                except Exception as e:
                    logging.error(f"Error processing payment: {str(e)}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Maaf, terjadi kesalahan dalam memproses pembayaran.\n"
                             "Admin akan segera menghubungi Anda untuk proses manual."
                    )

            elif query.data == "show_help":
                keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
                await query.message.reply_text(
                    Messages.HELP,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif query.data.startswith("folder_"):
                try:
                    category = query.data.split("_")[1]

                    # Delete current message
                    await query.message.delete()

                    with self.engine.connect() as conn:
                        if category == "seafood":
                            where_clause = "LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'"
                        elif category == "agriculture":
                            where_clause = "LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'"
                        elif category == "processed":
                            where_clause = "LOWER(product) LIKE '%44029010%'"
                        else:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="Kategori tidak valid"
                            )
                            return

                        result = conn.execute(text(f"""
                            SELECT DISTINCT product, role
                            FROM importers 
                            WHERE {where_clause}
                            ORDER BY product
                        """)).fetchall()

                        if not result:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="Tidak ada subkategori ditemukan."
                            )
                            return

                        # Group products into subcategories and create buttons
                        keyboard = []
                        for row in result:
                            product = row.product or "Uncategorized"
                            description = row.role or "No description"
                            keyboard.append([InlineKeyboardButton(
                                f"📦 {product}",
                                callback_data=f"product_{product}"
                            )])

                        # Add back button
                        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="trigger_contacts")])

                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="Pilih subkategori produk:",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )

                        if not result:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="Tidak ada kontak ditemukan untuk kategori ini."
                            )
                            return

                        items_per_page = 2
                        total_pages = (len(result) + items_per_page - 1) // items_per_page
                        current_page = 0
                        start_idx = current_page * items_per_page
                        end_idx = min(start_idx + items_per_page, len(result))
                        current_contacts = result[start_idx:end_idx]

                        # Delete previous messages if they exist
                        if query.message:
                            await query.message.delete()

                        for row in current_contacts:
                            importer = dict(row._mapping)
                            name = Messages._censor_contact(importer.get('name', ''), 'name')
                            email = Messages._censor_contact(importer.get('email_1', ''), 'email')
                            phone = Messages._censor_contact(importer.get('contact', ''), 'phone')
                            website = Messages._censor_contact(importer.get('website', ''), 'website')
                            wa_status = "✅ Tersedia" if importer.get('wa_availability') == 'Available' else "❌ Tidak Tersedia"

                            message_text = (
                                f"🏢 {name}\n"
                                f"🌏 Negara: {importer.get('country', 'N/A')}\n"
                                f"📦 Kode HS/Product: {importer.get('product', 'N/A')}\n"
                                f"📱 Kontak: {phone}\n"
                                f"📧 Email: {email}\n"
                                f"🌐 Website: {website}\n"
                                f"📱 WhatsApp: {wa_status}\n\n"
                                f"💾 Belum tersimpan\n\n"
                                f"💳 Biaya kredit yang diperlukan:\n"
                                f"1 kredit - Kontak tidak lengkap tanpa WhatsApp\n\n"
                                f"💡 Simpan kontak untuk melihat informasi lengkap"
                            )

                            keyboard = []
                            save_button = [[InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=f"save_{importer['id']}"
                            )]]

                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(save_button)
                            )

                        # Add navigation buttons
                        nav_buttons = []
                        if total_pages > 1:
                            if current_page > 0:
                                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"folder_prev_{category}_{current_page}"))
                            if current_page < total_pages - 1:
                                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"folder_next_{category}_{current_page}"))
                        
                        nav_buttons.append(InlineKeyboardButton("🔙 Kembali", callback_data="trigger_contacts"))
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"Halaman {current_page + 1} dari {total_pages}",
                            reply_markup=InlineKeyboardMarkup([nav_buttons])
                        )

                            keyboard = []
                            if importer['phone']:
                                phone = str(importer['phone']).replace('+', '').replace(' ', '')
                                keyboard.append([InlineKeyboardButton(
                                    "💬 Chat di WhatsApp",
                                    url=f"https://wa.me/{phone}"
                                )])

                            keyboard.append([InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=f"save_{importer['id']}"
                            )])

                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )

                        # Add navigation buttons
                        nav_buttons = [[
                            InlineKeyboardButton("🔙 Kembali", callback_data="trigger_contacts")
                        ]]

                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="Gunakan tombol di bawah untuk navigasi:",
                            reply_markup=InlineKeyboardMarkup(nav_buttons)
                        )

                except Exception as e:
                    logging.error(f"Error in folder callback: {str(e)}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=Messages.ERROR_MESSAGE
                    )

            elif query.data == "export_contacts":
                try:
                    with app.app_context():
                        saved_contacts = self.data_store.get_saved_contacts(user_id)

                    if not saved_contacts:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="Tidak ada kontak tersimpan untuk diekspor."
                        )
                        return

                    # Create CSV content
                    csv_rows = []
                    for contact in saved_contacts:
                        contact_dict = dict(contact._mapping)
                        csv_rows.append(f'"{contact_dict["company"]}","{contact_dict["contact_name"]}","{contact_dict["email"]}","{contact_dict["phone"]}","{contact_dict["product"]}","{contact_dict["country"]}"')

                    csv_content = "Company,Contact Name,Email,Phone,Product,Country\n" + "\n".join(csv_rows)

                    # Send as document
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=csv_content.encode(),
                        filename="saved_contacts.csv",
                        caption="📊 Kontak Tersimpan"
                    )
                except Exception as e:
                    logging.error(f"Error exporting contacts: {str(e)}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Gagal mengekspor kontak"
                    )

            elif query.data == "export_orders" and query.from_user.id in [6422072438]:  # Admin check
                try:
                    with self.engine.connect() as conn:
                        orders = conn.execute(text("""
                            SELECT order_id, user_id, credits, amount, status, created_at, fulfilled_at
                            FROM credit_orders 
                            ORDER BY created_at DESC
                        """)).fetchall()

                        csv_content = "Order ID,User ID,Credits,Amount,Status,Created At,Fulfilled At\n"
                        for order in orders:
                            csv_content += f"{order.order_id},{order.user_id},{order.credits},{order.amount},"
                            csv_content += f"{order.status},{order.created_at},{order.fulfilled_at or ''}\n"

                        # Send as document
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=csv_content.encode(),
                            filename="orders.csv",
                            caption="📊 Orders Export"
                        )
                except Exception as e:
                    logging.error(f"Error exporting orders: {str(e)}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Failed to export orders"
                    )

            elif query.data.startswith("fulfill_"):
                try:
                    if query.from_user.id not in [6422072438]:  # Admin check
                        await query.message.reply_text("⛔️ You are not authorized for this action.")
                        return

                    order_id = query.data.split("_")[1]
                    
                    with self.engine.begin() as conn:
                        # Get order details and update status atomically
                        order = conn.execute(text("""
                            UPDATE credit_orders 
                            SET status = 'fulfilled', fulfilled_at = CURRENT_TIMESTAMP
                            WHERE order_id = :order_id AND status = 'pending'
                            RETURNING order_id, user_id, credits, status
                        """), {"order_id": order_id}).first()

                        if not order:
                            await query.message.reply_text("❌ Order not found or already fulfilled")
                            return

                        # Add credits
                        if self.data_store.add_credits(order.user_id, order.credits):
                            # Notify user
                            await context.bot.send_message(
                                chat_id=order.user_id,
                                text=f"✅ {order.credits} kredit telah ditambahkan ke akun Anda!"
                            )
                            
                            # Update message buttons
                            await query.edit_message_reply_markup(
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("✅ Credits Added", callback_data="noop")
                                ]])
                            )
                        else:
                            await query.message.reply_text("❌ Failed to add credits")

                    # Add credits to user
                    with self.engine.begin() as conn:
                        if self.data_store.add_credits(order.user_id, order.credits):
                            # Update order status
                            conn.execute(text("""
                                UPDATE credit_orders 
                                SET status = 'fulfilled', fulfilled_at = CURRENT_TIMESTAMP 
                                WHERE order_id = :order_id
                            """), {"order_id": order_id})

                            # Notify user
                            await context.bot.send_message(
                                chat_id=order.user_id,
                                text=f"✅ {order.credits} kredit telah ditambahkan ke akun Anda!"
                            )

                            # Notify admin
                            await query.message.reply_text(
                                f"✅ Order {order_id} fulfilled successfully\n"
                                f"Added {order.credits} credits to user {order.user_id}"
                            )
                        else:
                            await query.message.reply_text("❌ Failed to add credits")

                except Exception as e:
                    logging.error(f"Error fulfilling order: {str(e)}")
                    await query.message.reply_text("❌ An error occurred while fulfilling the order")

            elif query.data.startswith("give_"):
                try:
                    _, user_id_to_credit, credits = query.data.split("_")
                    admin_ids = [6422072438]  # Admin check

                    if query.from_user.id not in admin_ids:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="⛔️ You are not authorized for this action."
                        )
                        return

                    # Update order status first
                    with self.engine.begin() as conn:
                        order = conn.execute(text("""
                            UPDATE credit_orders 
                            SET status = 'fulfilled', fulfilled_at = CURRENT_TIMESTAMP
                            WHERE user_id = :user_id AND credits = :credits AND status = 'pending'
                            RETURNING order_id
                        """), {
                            "user_id": int(user_id_to_credit),
                            "credits": int(credits)
                        }).first()

                        if not order:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="❌ Order already fulfilled or not found"
                            )
                            return

                        # Add credits
                        if self.data_store.add_credits(int(user_id_to_credit), int(credits)):
                            # Update button to show credits added
                            await query.edit_message_reply_markup(
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("✅ Credits Added", callback_data="noop")
                                ]])
                            )
                            
                            # Notify user
                            current_credits = self.data_store.get_user_credits(int(user_id_to_credit))
                            await context.bot.send_message(
                                chat_id=int(user_id_to_credit),
                                text=f"✅ {credits} kredit telah ditambahkan! Saldo Anda sekarang: {current_credits} kredit"
                            )
                        else:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="❌ Failed to add credits"
                            )

                except Exception as e:
                    logging.error(f"Error in give_credits callback: {str(e)}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ An error occurred while processing credits"
                    )

            else:
                logging.warning(f"Unknown callback query data: {query.data}")

        except Exception as e:
            logging.error(f"Error in button callback: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text="Terjadi kesalahan. Silakan coba lagi."
            )

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

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command"""
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

            items_per_page = 2
            total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
            current_page = 0
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

                await update.message.reply_text(
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )

            # Add pagination buttons
            pagination_buttons = []
            if total_pages > 1:
                pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="saved_next"))

            export_buttons = [
                [InlineKeyboardButton("📥 Simpan ke CSV", callback_data="export_contacts")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]
            await update.message.reply_text(
                f"Halaman 1 dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([pagination_buttons] + export_buttons)
            )

            logging.info(f"Saved contacts command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def contacts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /contacts command"""
        try:
            if not await self.check_rate_limit(update):
                return

            user_id = update.effective_user.id
            with app.app_context():
                self.data_store.track_user_command(user_id, 'contacts')

            # Show HS code categories menu
            header_text = """📊 *Kontak Tersedia*\n\nPilih kategori produk:"""
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

            await update.message.reply_text(
                header_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logging.info(f"Contacts command processed for user {user_id}")
        except Exception as e:
            logging.error(f"Error in contacts command: {str(e)}", exc_info=True)
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