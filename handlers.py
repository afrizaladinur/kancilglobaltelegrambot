import logging
import os
import time
import asyncio
from sqlalchemy import text
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CallbackContext
from telegram.error import BadRequest  # Add this import
from data_store import DataStore
from rate_limiter import RateLimiter
from messages import Messages
from app import app
import csv
import tempfile

class CommandHandler:

    def __init__(self):
        self.data_store = DataStore()
        self.rate_limiter = RateLimiter()
        self.engine = self.data_store.engine
        logging.info("CommandHandler initialized")

    async def check_admin_status(self, user_id: int) -> bool:
        """Check if user is admin"""
        admin_ids = [6422072438]
        return user_id in admin_ids

    async def initialize_credits(self, user_id: int, is_admin: bool) -> float:
        """Initialize or get user credits"""
        with app.app_context():
            credits = self.data_store.get_user_credits(user_id)
            if credits is None:
                initial_credits = 999999.0 if is_admin else 10.0
                self.data_store.initialize_user_credits(user_id, initial_credits)
                credits = initial_credits
            self.data_store.track_user_command(user_id, 'start')
        return credits

    async def check_community_membership(self, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Check if user is community member"""
        try:
            # Use numeric ID instead of username
            group_id = -1002349486618  
            
            # Verify group exists
            try:
                chat = await context.bot.get_chat(chat_id=group_id)
                logging.info(f"Checking membership for group: {chat.title}")
            except Exception as e:
                logging.error(f"Group not found: {e}")
                return False
                
            # Check member status
            member = await context.bot.get_chat_member(
                chat_id=group_id,
                user_id=user_id
            )
            return member.status in ['member', 'administrator', 'creator']
            
        except Exception as e:
            logging.error(f"Membership check failed: {e}")
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            is_admin = await self.check_admin_status(user_id)
            credits = await self.initialize_credits(user_id, is_admin)
            is_member = await self.check_community_membership(context, user_id)

            # Get message and markup as tuple
            message_text, keyboard_markup = await self.get_main_menu_markup(
                user_id=user_id,
                credits=credits,
                is_member=is_member
            )

            await update.message.reply_text(
                text=message_text,
                parse_mode='Markdown',
                reply_markup=keyboard_markup  # Pass InlineKeyboardMarkup directly
            )

        except Exception as e:
            logging.error(f"Start command error: {e}")
            await update.message.reply_text(
                "Maaf, terjadi kesalahan. Silakan coba lagi."
            )

    async def credits(self, update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            user_id = update.effective_user.id
            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
                self.data_store.track_user_command(user_id, 'credits')

            keyboard = [
                [
                    InlineKeyboardButton("🎁 Klaim 20 Kredit Gratis",
                                         callback_data="redeem_free_credits")
                ],
                [
                    InlineKeyboardButton("🛒 Beli 75 Kredit - Rp 150.000",
                                         callback_data="order_75")
                ],
                [
                    InlineKeyboardButton("🛒 Beli 150 Kredit - Rp 300.000",
                                         callback_data="order_150")
                ],
                [
                    InlineKeyboardButton("🛒 Beli 250 Kredit - Rp 399.000",
                                         callback_data="order_250")
                ],
                [
                    InlineKeyboardButton("🔙 Kembali",
                                         callback_data="back_to_main")
                ]
            ]

            await update.message.reply_text(
                f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logging.error(f"Error in credits command: {str(e)}")
            await update.message.reply_text(
                "Maaf, terjadi kesalahan. Silakan coba lagi.")

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reply_to=None):
        """Show saved contacts with pagination"""
        try:
            user_id = update.effective_user.id
            message = reply_to or update.message
            
            with self.engine.connect() as conn:
                saved_contacts = conn.execute(text("""
                    SELECT 
                        sc.id,
                        sc.importer_name as name,
                        sc.phone as contact,
                        sc.email,
                        sc.website,
                        sc.hs_code as product,
                        sc.product_description as role,
                        sc.country,
                        sc.wa_availability as wa_available,
                        sc.saved_at
                    FROM saved_contacts sc
                    WHERE sc.user_id = :user_id 
                    ORDER BY sc.saved_at DESC
                """), {"user_id": user_id}).fetchall()
                
                saved_contacts = [{
                    'id': row.id,
                    'name': row.name,
                    'contact': row.contact,
                    'email': row.email,
                    'website': row.website,
                    'product': row.product,
                    'role': row.role or 'Importer',  # Default role
                    'country': row.country,
                    'wa_available': row.wa_available,
                    'saved_at': row.saved_at
                } for row in saved_contacts]

            if not saved_contacts:
                await message.reply_text("❌ Anda belum memiliki kontak tersimpan.")
                return

            # Store for pagination
            context.user_data['saved_contacts'] = saved_contacts
            context.user_data['saved_page'] = 0
            context.user_data['current_message_ids'] = []

            # Show first page
            items_per_page = 2
            total_pages = (len(saved_contacts) + items_per_page - 1) // items_per_page
            current_contacts = saved_contacts[:items_per_page]

            message_ids = []
            
            # Display contacts
            for contact in current_contacts:
                message_text, whatsapp_number, _ = Messages.format_importer(contact, saved=True)
                buttons = []
                
                if whatsapp_number:
                    buttons.append([
                        InlineKeyboardButton("💬 Chat WhatsApp", url=f"https://wa.me/{whatsapp_number}")
                    ])
                    
                sent_msg = await message.reply_text(
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
                )
                message_ids.append(sent_msg.message_id)

            # Navigation buttons
            # Fix navigation buttons construction
            keyboard = []
            navigation_row = []
            bottom_buttons = []
            # Navigation buttons
            if total_pages > 1:
                navigation_row.append(InlineKeyboardButton(f"1/{total_pages}", callback_data="page_info")),
                navigation_row.append(InlineKeyboardButton("Next ➡️", callback_data="show_saved_next"))

            # Bottom buttons
            bottom_buttons.extend([
                [InlineKeyboardButton("📥 Export to CSV", callback_data="export_saved_contacts")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ])
            
            # Combine all buttons
            keyboard = [navigation_row] + bottom_buttons

            nav_msg = await message.reply_text(
                f"Halaman 1 dari {total_pages}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            message_ids.append(nav_msg.message_id)

            context.user_data['current_message_ids'] = message_ids

        except Exception as e:
            logging.error(f"Error in saved command: {str(e)}")
            if reply_to:
                await reply_to.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")
            elif update.message:
                await update.message.reply_text("Maaf, terjadi kesalahan. Silakan coba lagi.")

    async def get_main_menu_markup(self, user_id: int, credits: int = 0, is_member: bool = False) -> tuple[str, InlineKeyboardMarkup]:
        """Generate main menu keyboard markup based on user status"""
        try:
            # Get user credits
            with app.app_context():
                credits = self.data_store.get_user_credits(user_id)
            
            # Check member status
            group_id = -1002349486618
            try:
                member = await self.bot.get_chat_member(
                    chat_id=group_id,
                    user_id=user_id
                )
                is_member = member.status not in ['left', 'kicked']
            except Exception:
                is_member = False
            
            if is_member:
                community_button = [
                    InlineKeyboardButton(
                        "🔓 Buka Kancil Global Network",
                        url="https://t.me/+kuNU6lDtYoNlMTc1"
                    )
                ]
            else:
                community_button = [
                    InlineKeyboardButton(
                        "🌟 Gabung Kancil Global Network",
                        callback_data="join_community"
                    )
                ]

            keyboard = [[
                InlineKeyboardButton("📤 Kontak Supplier", callback_data="show_suppliers"),
                InlineKeyboardButton("📥 Kontak Buyer", callback_data="show_buyers")
            ],
                    [
                        InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="saved")
                    ],
                    [
                        InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits")
                    ], community_button,
                    [
                        InlineKeyboardButton("❓ Bantuan", callback_data="show_help")
                    ],
                    [
                        InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")
                    ]]

            message_text = f"{Messages.START}\n{Messages.CREDITS_REMAINING.format(credits)}"
            return message_text, InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logging.error(f"Error generating main menu: {str(e)}")
            # Return basic menu on error
            return Messages.START, InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data="start")
            ]])
    async def button_callback(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()  # Acknowledge the button press
            logging.info(f"Received callback query: {query.data}")

            # Get user ID
            user_id = query.from_user.id

            # Handle different button callbacks
            if query.data.startswith('buyer_') or query.data.startswith(
                    'supplier_'):
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
                            for sub_name, sub_data in cat_data[
                                    'subcategories'].items():
                                search_term = sub_data['search']
                                count = conn.execute(
                                    text("""
                                    SELECT COUNT(*) FROM importers 
                                    WHERE Role = :role 
                                    AND LOWER(Product) LIKE LOWER(:search)
                                    AND Phone IS NOT NULL 
                                    AND Phone != ''
                                    """), {
                                        "role": "Exporter" if category_type == "supplier" else "Importer",
                                        "search": f"%{search_term}%"
                                    }).scalar()

                                keyboard.append([
                                    InlineKeyboardButton(
                                        f"{sub_data['emoji']} {sub_name} ({count} kontak)",
                                        callback_data=
                                        f"search_{search_term.replace(' ', '_')}"
                                    )
                                ])

                    keyboard.append([
                        InlineKeyboardButton("🔙 Kembali",
                                             callback_data="back_to_main")
                    ])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard))

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}",
                                  exc_info=True)
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('search_'):
                await self.show_results(
                    update, context,
                    query.data.replace('search_', '').replace('_', ' '))
                
            elif query.data == "export_saved_contacts":
                await self.export_saved_contacts(update, context)

            elif query.data == "export_orders":
                await self.export_orders(update, context)

            elif query.data == "orders_prev" or query.data == "orders_next":
                try:
                    page = context.user_data.get('order_page', 0)
                    pending_orders = context.user_data.get('pending_orders', [])

                    if not pending_orders:
                        await query.message.reply_text("No pending orders found.")
                        return

                    # Update page
                    total_pages = len(pending_orders)
                    if query.data == "orders_prev":
                        page = max(0, page - 1)
                    else:
                        page = min(total_pages - 1, page + 1)

                    context.user_data['order_page'] = page
                    current_order = pending_orders[page]

                    # Format message
                    message_text = (
                        f"📦 Pending Order {page + 1}/{total_pages}\n\n"
                        f"🔖 Order ID: `{current_order['order_id']}`\n"
                        f"👤 User ID: `{current_order['user_id']}`\n"
                    )

                    user = await context.bot.get_chat(current_order['user_id'])
                    username = f"@{user.username}" if user.username else "No username"
                    message_text += f"Username: {username}\n"
                    message_text += (
                        f"💳 Credits: {current_order['credits']}\n"
                        f"💰 Amount: Rp {current_order['amount']:,}\n"
                        f"⏱️ Waiting since: {current_order['created_at'].strftime('%Y-%m-%d %H:%M:%S')}"
                    )

                    # Build keyboard
                    keyboard = []
                    nav_row = []
                    if page > 0:
                        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data="orders_prev"))
                    if page < total_pages - 1:
                        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="orders_next"))
                    if nav_row:
                        keyboard.append(nav_row)

                    keyboard.append([
                        InlineKeyboardButton("✅ Fulfill Order", 
                            callback_data=f"give_{current_order['user_id']}_{current_order['credits']}")
                    ])
                    keyboard.append([
                        InlineKeyboardButton("📥 Export to CSV", callback_data="export_orders")
                    ])

                    await query.message.edit_text(
                        message_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                    await query.answer()

                except Exception as e:
                    logging.error(f"Error in orders pagination: {str(e)}")
                    await query.message.reply_text("Error navigating orders. Please try again.")

            elif query.data == "next_page" or query.data == "prev_page":
                try:
                    results = context.user_data.get('search_results', [])
                    current_page = context.user_data.get('search_page', 0)

                    if not results:
                        await query.message.reply_text(
                            "Tidak ada hasil pencarian yang tersedia.")
                        return

                    # Delete previous messages
                    message_ids = context.user_data.get(
                        'current_message_ids', [])
                    chat_id = query.message.chat_id

                    # Delete all previous messages
                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(chat_id=chat_id,
                                                             message_id=msg_id)
                        except Exception as e:
                            logging.error(
                                f"Error deleting message {msg_id}: {str(e)}")

                    # Update page number
                    items_per_page = 2
                    total_pages = (len(results) + items_per_page -
                                   1) // items_per_page
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
                        save_button = [[
                            InlineKeyboardButton(
                                "💾 Simpan Kontak",
                                callback_data=
                                f"save_{result['id']}" 
                            )
                        ]]

                        sent_msg = await query.message.reply_text(
                            message_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(save_button))
                        new_message_ids.append(sent_msg.message_id)

                    # Add pagination buttons in a single row
                    navigation_row = []
                    if current_page > 0:
                        navigation_row.append(
                            InlineKeyboardButton("⬅️ Prev",
                                                 callback_data="prev_page"))
                    navigation_row.append(
                        InlineKeyboardButton(
                            f"{current_page + 1}/{total_pages}",
                            callback_data="page_info"))
                    if current_page < total_pages - 1:
                        navigation_row.append(
                            InlineKeyboardButton("Next ➡️",
                                                 callback_data="next_page"))

                    bottom_buttons = [
                        [
                            InlineKeyboardButton(
                                "🔄 Cari Kembali",
                                callback_data="regenerate_search")
                        ],
                        [
                            InlineKeyboardButton(
                                "🔙 Kembali",
                                callback_data="back_to_categories")
                        ]
                    ]

                    nav_msg = await query.message.reply_text(
                        f"Halaman {current_page + 1} dari {total_pages}",
                        reply_markup=InlineKeyboardMarkup([navigation_row] +
                                                          bottom_buttons))
                    new_message_ids.append(nav_msg.message_id)

                    # Store new message IDs
                    context.user_data['current_message_ids'] = new_message_ids

                except Exception as e:
                    logging.error(f"Error in pagination: {str(e)}",
                                  exc_info=True)
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "regenerate_search":
                try:
                    # Get the last search parameters
                    last_search = context.user_data.get(
                        'last_search_context', {})
                    if not last_search:
                        await query.message.reply_text(
                            "Tidak ada riwayat pencarian sebelumnya.")
                        return

                    # Delete all current messages
                    message_ids = context.user_data.get(
                        'current_message_ids', [])
                    chat_id = query.message.chat_id

                    try:
                        await query.message.delete()
                    except Exception as e:
                        logging.error(
                            f"Error deleting query message: {str(e)}")

                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(chat_id=chat_id,
                                                             message_id=msg_id)
                        except Exception as e:
                            logging.error(
                                f"Error deleting message {msg_id}: {str(e)}")

                    # Re-execute the search with the same parameters
                    search_pattern = last_search.get('pattern')
                    if search_pattern:
                        await self.show_results(update, context,
                                                search_pattern)
                    else:
                        await query.message.reply_text(
                            "Tidak dapat mengulang pencarian sebelumnya.")

                except Exception as e:
                    logging.error(f"Error in regenerate search: {str(e)}")
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan saat mengulang pencarian.")

            elif query.data == "page_info":
                await query.answer("Halaman saat ini", show_alert=False)

            elif query.data == "back_to_main":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        credits = self.data_store.get_user_credits(user_id)
                        is_member = await self.check_community_membership(context, user_id)
                        message_text, reply_markup = await self.get_main_menu_markup(
                            user_id=user_id,
                            credits=credits,
                            is_member=is_member
                        )
                        
                        try:
                            await query.message.edit_text(
                                text=message_text,
                                parse_mode='Markdown',
                                reply_markup=reply_markup
                            )
                        except telegram.error.BadRequest as e:
                            if "message is not modified" in str(e).lower():
                                # Just answer the callback if content hasn't changed
                                await query.answer()
                                return
                            raise  # Re-raise other BadRequest errors
                            
                        await query.answer()
                        
                except Exception as e:
                    logging.error(f"Error returning to main menu: {str(e)}")
                    if "message is not modified" not in str(e).lower():
                        await query.message.reply_text(
                            "Maaf, terjadi kesalahan. Silakan coba lagi."
                        )

            elif query.data.startswith('order_'):
                try:
                    # Define valid credit packages
                    credit_prices = {
                        '75': 150000,
                        '150': 300000,
                        '250': 399000
                    }
                    
                    # Parse credit amount
                    _, credits = query.data.split('_')
                    
                    # Validate credit amount
                    if credits not in credit_prices:
                        await query.message.reply_text(
                            "Paket kredit tidak valid. Silakan pilih paket yang tersedia."
                        )
                        return
                        
                    amount = credit_prices[credits]
                    user_id = query.from_user.id
                    username = query.from_user.username or str(user_id)
                    order_id = f"BOT_{user_id}_{int(time.time())}"

                    # Insert order
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
            
                    # Payment instructions
                    payment_message = (
                        f"💳 *Detail Pembayaran*\n\n"
                        f"Order ID: `{order_id}`\n"
                        f"Jumlah Kredit: {credits}\n"
                        f"Total: Rp {int(amount):,}\n\n"
                        f"*Cara Pembayaran:*\n\n"
                        f"1. Pilih salah satu metode pembayaran:\n\n"
                        f"   *Transfer BCA*\n"
                        f"   • Nama: Nanda Amalia\n"
                        f"   • No. Rek: `4452385892`\n"
                        f"   • Kode Bank: 014\n\n"
                        f"   *Transfer Jenius/SMBC*\n" 
                        f"   • Nama: Nanda Amalia\n"
                        f"   • No. Rek: `90020380969`\n"
                        f"   • $cashtag: `$kancilglobalbot`\n\n"
                        f"2. Transfer tepat sejumlah Rp {int(amount):,}\n"
                        f"3. Simpan bukti transfer\n"
                        f"4. Kirim bukti transfer ke admin dengan menyertakan Order ID\n"
                        f"5. Kredit akan ditambahkan setelah verifikasi"
                    )
            
                    keyboard = [
                        [InlineKeyboardButton(
                            "📎 Kirim Bukti Transfer",
                            url="https://t.me/afrizaladinur"
                        )],
                        [InlineKeyboardButton(
                            "🔙 Kembali",
                            callback_data="back_to_main"
                        )]
                    ]
            
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
                        f"Total: Rp {int(amount):,}\n\n"
                        f"Status: ⏳ Menunggu Pembayaran"
                    )
            
                    admin_keyboard = [[InlineKeyboardButton(
                        f"✅ Verifikasi & Berikan {credits} Kredit",
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
            
                    logging.info(f"Payment order created: {order_id}")
            
                except Exception as e:
                    logging.error(f"Error processing payment: {str(e)}", exc_info=True)
                    await query.message.reply_text(
                        "Pesanan tetap diproses! Admin akan segera menghubungi Anda."
                    )
            elif query.data == "show_saved_prev" or query.data == "show_saved_next":
                user_id = query.from_user.id
                items_per_page = 2

                # Delete current page messages
                try:
                    # Delete the 2 contact messages and pagination message
                    current_message_id = query.message.message_id
                    for i in range(
                            3
                    ):  # Delete current message and 2 previous messages
                        try:
                            await context.bot.delete_message(
                                chat_id=query.message.chat_id,
                                message_id=current_message_id - i)
                        except Exception as e:
                            logging.error(
                                f"Error deleting message {current_message_id - i}: {str(e)}"
                            )
                except Exception as e:
                    logging.error(f"Error deleting messages: {str(e)}")

                saved_contacts = context.user_data.get('saved_contacts', [])
                if not saved_contacts:
                    await query.message.reply_text(Messages.NO_SAVED_CONTACTS)
                    return

                total_pages = (len(saved_contacts) + items_per_page -
                               1) // items_per_page
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
                    message_text, whatsapp_number, _ = Messages.format_importer(
                        contact, saved=True)
                    keyboard = []
                    if whatsapp_number:
                        keyboard.append([
                            InlineKeyboardButton(
                                "💬 Chat di WhatsApp",
                                url=f"https://wa.me/{whatsapp_number}")
                        ])
                    sent_msg = await query.message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                        if keyboard else None)
                    new_messages.append(sent_msg.message_id)

                # Add pagination buttons
                pagination_buttons = []
                if current_page > 0:
                    pagination_buttons.append(
                        InlineKeyboardButton("⬅️ Prev",
                                             callback_data="show_saved_prev"))
                pagination_buttons.append(
                    InlineKeyboardButton(f"{current_page + 1}/{total_pages}",
                                         callback_data="show_saved_page_info"))
                if current_page < total_pages - 1:
                    pagination_buttons.append(
                        InlineKeyboardButton("Next ➡️",
                                             callback_data="show_saved_next"))

                export_buttons = [[
                    InlineKeyboardButton("📥 Simpan ke CSV",
                                         callback_data="export_saved_contacts")
                ],
                                  [
                                      InlineKeyboardButton(
                                          "🔙 Kembali",
                                          callback_data="back_to_main")
                                  ]]
                await query.message.reply_text(
                    f"Halaman {current_page + 1} dari {total_pages}",
                    reply_markup=InlineKeyboardMarkup([pagination_buttons] +
                                                      export_buttons))
            elif query.data == "show_saved_page_info":
                await query.answer("Halaman saat ini", show_alert=False)

            elif query.data == "saved":
                await self.saved(update, context, reply_to=query.message)
                await query.answer()
                
            elif query.data == "back_to_categories":
                # Handle going back to category selection
                try:
                    search_context = context.user_data.get(
                        'last_search_context', {})
                    category_type = search_context.get(
                        'category_type',
                        'buyer')  # Default to buyer if not found

                    if category_type == 'supplier':
                        # Go back to supplier categories
                        keyboard = []
                        for cat, data in Messages.SUPPLIER_CATEGORIES.items():
                            keyboard.append([
                                InlineKeyboardButton(
                                    f"{data['emoji']} {cat}",
                                    callback_data=
                                    f"supplier_{cat.lower().replace(' ', '_')}"
                                )
                            ])
                        keyboard.append([
                            InlineKeyboardButton("🔙 Kembali",
                                                 callback_data="back_to_main")
                        ])

                        await query.message.edit_text(
                            "📤 *Kontak Supplier Indonesia*\n\nPilih kategori produk:",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        # Go back to buyer categories
                        keyboard = []
                        for cat, data in Messages.BUYER_CATEGORIES.items():
                            keyboard.append([
                                InlineKeyboardButton(
                                    f"{data['emoji']} {cat}",
                                    callback_data=
                                    f"buyer_{cat.lower().replace(' ', '_')}")
                            ])
                        keyboard.append([
                            InlineKeyboardButton("🔙 Kembali",
                                                 callback_data="back_to_main")
                        ])

                        await query.message.edit_text(
                            "📥 *Kontak Buyer*\n\nPilih kategori buyer:",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    logging.error(f"Error returning to categories: {str(e)}")
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data.startswith('save_'):
                await self.save_contact(user_id, query.data[5:], update)

            elif query.data == "redeem_free_credits":
                user_id = query.from_user.id
                try:
                    with self.engine.begin() as conn:
                        # Check if already redeemed with row lock
                        result = conn.execute(
                            text("""
                            SELECT has_redeemed_free_credits, credits 
                            FROM user_credits 
                            WHERE user_id = :user_id
                            FOR UPDATE
                        """), {
                                "user_id": user_id
                            }).first()

                        if not result:
                            # Initialize user if not exists
                            conn.execute(
                                text("""
                                INSERT INTO user_credits (user_id, credits, has_redeemed_free_credits)
                                VALUES (:user_id, 20, true)
                            """), {"user_id": user_id})
                            new_balance = 20.0
                        else:
                            has_redeemed, current_credits = result

                            if has_redeemed:
                                await query.message.reply_text(
                                    "Anda sudah pernah mengklaim kredit gratis!"
                                )
                                return

                            # Add credits and mark as redeemed
                            conn.execute(
                                text("""
                                UPDATE user_credits 
                                SET credits = credits + 10,
                                    has_redeemed_free_credits = true
                                WHERE user_id = :user_id
                            """), {"user_id": user_id})
                            new_balance = current_credits + 10.0

                    await query.message.reply_text(
                        f"🎉 Selamat! 10 kredit gratis telah ditambahkan ke akun Anda!\n"
                        f"Saldo saat ini: {new_balance:.1f} kredit")
                except Exception as e:
                    logging.error(f"Error redeeming free credits: {str(e)}")
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi nanti.")

            elif query.data == "show_help":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'help')
                    keyboard = [[
                        InlineKeyboardButton("🔙 Kembali",
                                             callback_data="back_to_main")
                    ]]
                    await query.message.edit_text(
                        Messages.HELP,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    logging.error(f"Errorshowing help: {str(e)}")
                    await query.message.reply_text(Messages.ERROR_MESSAGE)
            elif query.data == "show_credits":
                try:
                    user_id = query.from_user.id
                    with app.app_context():
                        self.data_store.track_user_command(user_id, 'credits')
                        credits = self.data_store.get_user_credits(
                            user_id)  # Fixed typo here

                    keyboard = [[
                        InlineKeyboardButton(
                            "🎁 Klaim 20 KreditGratis",
                            callback_data="redeem_free_credits")
                    ],
                               [
                                   InlineKeyboardButton(
                                       "🛒 Beli 75 Kredit - Rp 150.000",
                                       callback_data="order_75")
                               ],
                               [
                                   InlineKeyboardButton(
                                       "🛒 Beli 150 Kredit - Rp 300.000",
                                       callback_data="order_150")
                               ],
                               [
                                   InlineKeyboardButton(
                                       "🛒 Beli 250 Kredit - Rp 399.000",
                                       callback_data="order_250")
                               ],
                               [
                                   InlineKeyboardButton(
                                       "🔙 Kembali",
                                       callback_data="back_to_main")
                               ]]

                    await query.message.edit_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                        reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    logging.error(f"Error showing credits: {str(e)}")
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi.")

            elif query.data == "show_suppliers":
                keyboard = []
                for cat, data in Messages.SUPPLIER_CATEGORIES.items():
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{data['emoji']} {cat}",
                            callback_data=
                            f"supplier_{cat.lower().replace(' ', '_')}")
                    ])
                keyboard.append([
                    InlineKeyboardButton("🔙 Kembali",
                                         callback_data="back_to_main")
                ])

                await query.message.edit_text(
                    "📤 *Kontak Supplier Indonesia*\n\nPilih kategori produk:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))

            elif query.data == "show_buyers":
                # Build keyboard for buyers categories
                keyboard = []
                for cat, data in Messages.BUYER_CATEGORIES.items():
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{data['emoji']} {cat}",
                            callback_data=
                            f"buyer_{cat.lower().replace(' ', '_')}")
                    ])
                keyboard.append([
                    InlineKeyboardButton("🔙 Kembali",
                                         callback_data="back_to_main")
                ])

                await query.message.edit_text(
                    "📥 *Kontak Buyer*\n\nPilih kategori buyer:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))

            elif query.data.startswith("supplier_") or query.data.startswith(
                    "buyer_"):
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
                            for sub_name, sub_data in cat_data[
                                    'subcategories'].items():
                                search_term = sub_data['search']
                                count = conn.execute(
                                    text("""
                                    SELECT COUNT(*) FROM importers 
                                    WHERE Role = :role 
                                    AND LOWER(Product) LIKE LOWER(:search)
                                    AND Phone IS NOT NULL 
                                    AND Phone != ''
                                    """), {
                                        "role": "Exporter" if category_type == "supplier" else "Importer",
                                        "search": f"%{search_term}%"
                                    }).scalar()

                                keyboard.append([
                                    InlineKeyboardButton(
                                        f"{sub_data['emoji']} {sub_name} ({count} kontak)",
                                        callback_data=
                                        f"search_{search_term.replace(' ', '_')}"
                                    )
                                ])

                    keyboard.append([
                        InlineKeyboardButton("🔙 Kembali",
                                             callback_data="back_to_main")
                    ])

                    await query.message.edit_text(
                        f"📂 *{category.replace('_', ' ').title()}*\n\nPilih produk:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard))

                except Exception as e:
                    logging.error(f"Error in category navigation: {str(e)}",
                                  exc_info=True)
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi.")

            
            elif query.data.startswith('search_'):
                try:
                    search_pattern = query.data.replace('search_',
                                                        '').replace('_', ' ')
                    logging.info(f"Searching for pattern: {search_pattern}")

                    # Clean up any existing messages first
                    message_ids = context.user_data.get(
                        'current_message_ids', [])
                    chat_id = query.message.chat_id

                    for msg_id in message_ids:
                        try:
                            await context.bot.delete_message(chat_id=chat_id,
                                                             message_id=msg_id)
                        except Exception as e:
                            logging.error(
                                f"Error deleting message {msg_id}: {str(e)}")

                    # Get results from database
                    with self.engine.connect() as conn:
                        results = conn.execute(
                            text("""
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
                            await query.message.reply_text(
                                "Tidak ada hasil yang ditemukan.")
                            return

                        # Store results and initialize page
                        context.user_data['search_results'] = results
                        context.user_data['search_page'] = 0
                        context.user_data['current_message_ids'] = [
                        ]  # Initialize message tracking
                        context.user_data['last_search_context'] = {
                            'pattern': search_pattern
                        }

                        # Show first page (2 results)
                        items_per_page = 2
                        total_pages = (len(results) + items_per_page -
                                       1) // items_per_page
                        current_results = results[:items_per_page]

                        # Store message IDs for later cleanup
                        message_ids = []

                        # Get the appropriate message object for replies
                        reply_to = update.callback_query.message if hasattr(
                            update, 'callback_query') else update.message

                        # Display results
                        for result in current_results:
                            message_text, _, _ = Messages.format_importer(
                                result)
                            save_button = [[
                                InlineKeyboardButton(
                                    "💾 Simpan Kontak",
                                    callback_data=
                                    f"save_{result['id']}"  # Use name instead of id
                                )
                            ]]

                            sent_msg = await reply_to.reply_text(
                                message_text,
                                parse_mode='Markdown',
                                reply_markup=InlineKeyboardMarkup(save_button))
                            message_ids.append(sent_msg.message_id)

                        # Add pagination buttons in a single row
                        navigation_row = []
                        if total_pages > 1:
                            navigation_row.append(
                                InlineKeyboardButton(
                                    "Next ➡️", callback_data="next_page"))
                        navigation_row.append(
                            InlineKeyboardButton(f"1/{total_pages}",
                                                 callback_data="page_info"))

                        # Add bottom navigation buttons
                        bottom_buttons = [
                            [
                                InlineKeyboardButton(
                                    "🔄 Cari Kembali",
                                    callback_data="regenerate_search")
                            ],
                            [
                                InlineKeyboardButton(
                                    "🔙 Kembali",
                                    callback_data="back_to_categories")
                            ]
                        ]

                        nav_msg = await reply_to.reply_text(
                            f"Halaman 1 dari {total_pages}",
                            reply_markup=InlineKeyboardMarkup(
                                [navigation_row] + bottom_buttons))
                        message_ids.append(nav_msg.message_id)

                        # Store message IDs in context
                        context.user_data['current_message_ids'] = message_ids

                except Exception as e:
                    logging.error(f"Error in search results: {str(e)}",
                                  exc_info=True)
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi."
                    )

            elif query.data.startswith('give_'):
                try:
                    _, target_user_id, credit_amount = query.data.split('_')
                    if not self.data_store.get_user_credits(
                            int(target_user_id)):
                        await query.message.reply_text("User tidak ditemukan.")
                        return

                    if self.data_store.add_credits(int(target_user_id),
                                                   int(credit_amount)):
                        new_balance = self.data_store.get_user_credits(
                            int(target_user_id))
                        await query.message.edit_text(
                            f"{query.message.text}\n\n✅ Kredit telah ditambahkan!\nSaldo baru: {new_balance}",
                            parse_mode='Markdown')
                        # Notify user
                        keyboard = [[
                            InlineKeyboardButton("🔙 Kembali",
                                                 callback_data="back_to_main")
                        ]]
                        await context.bot.send_message(
                            chat_id=int(target_user_id),
                            text=
                            f"✅ {credit_amount} kredit telah ditambahkan ke akun Anda!\nSaldo saat ini: {new_balance} kredit",
                            reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        await query.message.reply_text(
                            "Gagal menambahkan kredit.")
                except Exception as e:
                    logging.error(f"Error giving credits: {str(e)}",
                                  exc_info=True)
                    await query.message.reply_text("Gagal menambahkan kredit.")

            elif query.data == "join_community":
                try:
                    user_id = query.from_user.id
                    group_id = -1002349486618
                    
                    # Verify membership
                    try:
                        member = await context.bot.get_chat_member(
                            chat_id=group_id,
                            user_id=user_id
                        )
                        if member.status not in ['left', 'kicked']:
                            await query.message.reply_text(
                                "✅ Anda sudah menjadi anggota komunitas!"
                            )
                            return
                    except BadRequest as e:
                        if "Chat not found" in str(e):
                            logging.error(f"Group not found: {group_id}")
                            await query.message.reply_text(
                                "Maaf, grup tidak ditemukan. Silakan hubungi admin."
                            )
                            return
                    
                    # Check credits
                    with app.app_context():
                        credits = self.data_store.get_user_credits(user_id)
            
                    if credits < 5:
                        await query.message.reply_text(
                            "⚠️ Kredit tidak mencukupi untuk bergabung dengan komunitas.\n"
                            "Dibutuhkan: 5 kredit\n"
                            "Sisa kredit Anda: " + str(credits)
                        )
                        return
            
                    # Show join info
                    keyboard = [[
                        InlineKeyboardButton(
                            "🚀 Gabung Sekarang", 
                            callback_data="join_now"
                        )
                    ]]
                    
                    sent_message = await query.message.reply_text(
                        Messages.COMMUNITY_INFO,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    context.user_data['join_message_id'] = sent_message.message_id
            
                except Exception as e:
                    pass
            
            elif query.data == "join_now":
                try:
                    user_id = query.from_user.id
                    
                    # Check credits
                    with app.app_context():
                        credits = self.data_store.get_user_credits(user_id)
                        
                    if credits < 5:
                        await query.message.reply_text(
                            "⚠️ Kredit tidak mencukupi untuk bergabung dengan komunitas.\n"
                            "Dibutuhkan: 5 kredit\n"
                            f"Sisa kredit Anda: {credits}"
                        )
                        return

                    # Deduct credits and join
                    with app.app_context():
                        if self.data_store.use_credit(user_id, 5):
                            group_id = -1002349486618
                            try:
                                invite_link = await context.bot.create_chat_invite_link(
                                    chat_id=group_id,
                                    member_limit=1
                                )
                                # Automatically open invite link
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=f"🔓 Anda telah bergabung dengan komunitas Kancil Global Network! Klik [di sini]({invite_link.invite_link}) untuk membuka grup.",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logging.error(f"Error adding user to group: {str(e)}")
                                await query.message.reply_text(
                                    "Gagal menambahkan Anda ke grup. Silakan coba lagi."
                                )
                        else:
                            await query.message.reply_text(
                                "Gagal menggunakan kredit. Silakan coba lagi."
                            )
                except Exception as e:
                    logging.error(f"Error in join community: {str(e)}")
                    await query.message.reply_text(
                        "Maaf, terjadi kesalahan. Silakan coba lagi."
                    )

                # Update main menu
                message_text, keyboard = await self.get_main_menu_markup(user_id)
                await query.message.edit_text(
                    text=message_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )

        except Exception as e:
            logging.error(f"Error in button callback: {str(e)}", exc_info=True)
            await update.callback_query.message.reply_text(
                "Maaf, terjadi kesalahan. Silakan coba lagi.")

    async def check_member_status(self, context, user_id):
        try:
            group_id = -1002349486618  # Community group ID
            
            member = await context.bot.get_chat_member(
                chat_id=group_id,
                user_id=user_id
            )
            return member.status not in ['left', 'kicked']
            
        except telegram.error.BadRequest as e:
            if "Chat not found" in str(e):
                logging.error(f"Community group not found or bot not added to group. ID: {group_id}")
                return False
        except Exception as e:
            logging.error(f"Error checking member status: {str(e)}")
            return False
            
        return False
    async def orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reply_to=None):
        """Show pending orders with pagination"""
        try:
            message = reply_to or update.message
            if update.effective_user.id not in [6422072438]:
                await message.reply_text("⛔️ Unauthorized")
                return

            # Get pending orders for display
            with self.engine.connect() as conn:
                pending_orders = conn.execute(text("""
                    SELECT * FROM credit_orders 
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                """)).fetchall()

                if not pending_orders:
                    await message.reply_text("No pending orders found.")
                    return

                # Store for pagination
                context.user_data['pending_orders'] = [dict(row._mapping) for row in pending_orders]
                context.user_data['order_page'] = 0

                # Show first order
                current_order = pending_orders[0]
                total_pages = len(pending_orders)

                # Format message
                message_text = (
                    f"📦 Pending Order 1/{total_pages}\n\n"
                    f"🔖 Order ID: `{current_order.order_id}`\n"
                    f"👤 User ID: `{current_order.user_id}`\n"
                )

                user = await context.bot.get_chat(current_order.user_id)
                username = f"@{user.username}" if user.username else "No username"
                message_text += f"Username: {username}\n"
                message_text += (
                    f"💳 Credits: {current_order.credits}\n"
                    f"💰 Amount: Rp {current_order.amount:,}\n"
                    f"⏱️ Waiting since: {current_order.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Build keyboard
                keyboard = []
                nav_row = []
                if total_pages > 1:
                    nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="orders_next"))
                if nav_row:
                    keyboard.append(nav_row)

                keyboard.append([
                    InlineKeyboardButton("✅ Fulfill Order", 
                        callback_data=f"give_{current_order.user_id}_{current_order.credits}")
                ])
                keyboard.append([
                    InlineKeyboardButton("📥 Export to CSV", callback_data="export_orders")
                ])

                await message.reply_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )

        except Exception as e:
            logging.error(f"Error in orders command: {str(e)}")
            if message:
                await message.reply_text("Error retrieving orders. Please try again.")
    async def export_saved_contacts(self, update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        saved_contacts = self.data_store.get_saved_contacts(user_id)
        if not saved_contacts:
            await update.message.reply_text("No saved contacts to export")
            return
        csv_data = self.data_store.format_saved_contacts_to_csv(saved_contacts)
        await context.bot.send_document(update.effective_chat.id,
                                        document=csv_data,
                                        filename='saved_contacts.csv')

    async def export_orders(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if update.effective_user.id not in [6422072438]:
            await update.message.reply_text("Unauthorized")
            return
        try:
            user_id = query.from_user.id
            csv_data = self.data_store.format_orders_to_csv(user_id)
            
            if csv_data == "No orders found":
                await query.message.reply_text("Tidak ada pesanan untuk diekspor.")
                return
            
            # Create temp file
            with tempfile.NamedTemporaryFile(
                mode='w+', 
                suffix='.csv',
                delete=False,
                encoding='utf-8'
            ) as tmp:
                tmp.write(csv_data)
                tmp.flush()
                tmp_path = tmp.name

            # Send file
            with open(tmp_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=f'orders_{user_id}.csv',
                    caption="📥 Daftar pesanan kredit"
                )

            # Cleanup
            os.unlink(tmp_path)
            await query.answer("CSV berhasil diekspor!")

        except Exception as e:
            logging.error(f"Error exporting orders: {str(e)}")
            await query.message.reply_text("Maaf, terjadi kesalahan saat ekspor.")

    async def show_results(self, update: Update,
                        context: ContextTypes.DEFAULT_TYPE,
                        search_pattern: str):
        """Show randomized search results with pagination"""
        try:
            # Get random results from database
            with self.engine.connect() as conn:
                results = conn.execute(
                    text("""
                    SELECT * FROM importers 
                    WHERE LOWER(product) SIMILAR TO :pattern
                    OR LOWER(name) SIMILAR TO :pattern
                    OR LOWER(country) SIMILAR TO :pattern
                    ORDER BY RANDOM()  -- Randomize results
                    LIMIT 100
                    """), {
                        "pattern": f"%{search_pattern.lower()}%"
                    }).fetchall()

                results = [dict(row._mapping) for row in results]

            if not results:
                reply_to = update.callback_query.message if hasattr(
                    update, 'callback_query') else update.message
                await reply_to.reply_text("Tidak ada hasil yang ditemukan.")
                return

            # Store randomized results
            context.user_data['search_results'] = results
            context.user_data['search_page'] = 0
            context.user_data['current_message_ids'] = []
            context.user_data['last_search_context'] = {
                'pattern': search_pattern
            }

            # Show first page
            items_per_page = 2
            total_pages = (len(results) + items_per_page - 1) // items_per_page
            current_results = results[:items_per_page]

            message_ids = []
            reply_to = update.callback_query.message if hasattr(
                update, 'callback_query') else update.message

            # Display results
            for result in current_results:
                message_text, _, _ = Messages.format_importer(result)
                save_button = [[
                    InlineKeyboardButton(
                        "💾 Simpan Kontak",
                        callback_data=f"save_{result['id']}"
                    )
                ]]

                sent_msg = await reply_to.reply_text(
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(save_button))
                message_ids.append(sent_msg.message_id)

            # Navigation buttons
            navigation_row = []
            if total_pages > 1:
                navigation_row.append(
                    InlineKeyboardButton("Next ➡️", callback_data="next_page"))
            navigation_row.append(
                InlineKeyboardButton(f"1/{total_pages}", callback_data="page_info"))

            bottom_buttons = [[
                InlineKeyboardButton("🔄 Cari Kembali",
                                    callback_data="regenerate_search")
            ], [
                InlineKeyboardButton("🔙 Kembali",
                                    callback_data="back_to_categories")
            ]]

            nav_msg = await reply_to.reply_text(
                f"Halaman 1 dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([navigation_row] + bottom_buttons))
            message_ids.append(nav_msg.message_id)

            context.user_data['current_message_ids'] = message_ids

        except Exception as e:
            logging.error(f"Error in show_results: {str(e)}", exc_info=True)
            try:
                reply_to = update.callback_query.message if hasattr(
                    update, 'callback_query') else update.message
                await reply_to.reply_text(
                    "Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi."
                )
            except Exception as inner_e:
                logging.error(f"Error sending error message: {str(inner_e)}",
                            exc_info=True)

    async def save_contact(self, user_id: int, contact_id: str,
                           update: Update):
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
                result = conn.execute(
                    text("""
                    SELECT 
                        id,
                        name as importer_name,
                        phone,                      
                        website,
                        email_1 as email,
                        product as hs_code,
                        country,
                        CASE 
                            WHEN wa_availability = 'Available' THEN true
                            ELSE false
                        END as wa_available,
                        role as product_description,
                        CURRENT_TIMESTAMP as saved_at
                    FROM importers 
                    WHERE id = :id
                """), {
                        "id": contact_id
                    }).first()

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
                        user_id=user_id, importer=importer)

                    if success:
                        new_balance = self.data_store.get_user_credits(user_id)
                        await update.callback_query.message.reply_text(
                            f"✅ Kontak berhasil disimpan!\n\n"
                            f"💳 Sisa kredit: {new_balance} kredit\n\n"
                            f"Gunakan /saved untuk melihat kontak tersimpan.")
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
                "Maaf, terjadi kesalahan saat menyimpan kontak.")

    async def export_saved_contacts(self, update: Update, context: CallbackContext) -> None:
        """Export saved contacts to CSV"""
        query = update.callback_query
        try:
            user_id = query.from_user.id
            
            # Get CSV data
            with app.app_context():
                csv_data = self.data_store.format_saved_contacts_to_csv(user_id)

            if csv_data == "No saved contacts found":
                await query.message.reply_text("Tidak ada kontak tersimpan untuk diekspor.")
                return

            # Create temporary file with CSV data
            
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(csv_data)
                temp_file.flush()

                # Send the CSV file
                with open(temp_file.name, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename=f'saved_contacts_{user_id}.csv',
                        caption="📥 Daftar kontak tersimpan Anda"
                    )

                # Clean up temp file
                os.unlink(temp_file.name)

            await query.message.reply_text("✅ File CSV berhasil dikirim!")
            await query.answer()

        except Exception as e:
            logging.error(f"Error exporting contacts to CSV: {str(e)}", exc_info=True)
            await query.message.reply_text("Maaf, terjadi kesalahan saat mengekspor kontak.")