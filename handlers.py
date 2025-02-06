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


    async def search_contacts(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Search for contacts with improved error handling and retries"""
        max_retries = 3
        retry_delay = 1  # seconds
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with self.engine.begin() as conn:
                    # Clear any existing search results first
                    if 'last_search_results' in context.user_data:
                        context.user_data.pop('last_search_results')

                    # Execute query with proper transaction
                    result = await conn.execute(query)
                    rows = await result.fetchall()

                    if not rows:
                        logging.info(f"No results found for query (attempt {retry_count + 1})")
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            continue
                        return None

                    # Format results properly before storing in context
                    formatted_results = []
                    for row in rows:
                        try:
                            formatted_result = {
                                'name': row.name.strip() if row.name else '',
                                'email': row.email.strip() if row.email else '',
                                'contact': row.contact.strip() if row.contact else '',
                                'website': row.website.strip() if row.website else '',
                                'country': row.country.strip() if row.country else '',
                                'wa_available': bool(row.wa_available),
                                'hs_code': row.product.strip() if row.product else '',
                                'search_timestamp': datetime.now().isoformat()
                            }
                            formatted_results.append(formatted_result)
                        except Exception as e:
                            logging.error(f"Error formatting row {row}: {str(e)}")
                            continue

                    if not formatted_results:
                        logging.warning("No valid results after formatting")
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            continue
                        return None

                    # Store formatted results in context with timestamp
                    context.user_data['last_search_results'] = formatted_results
                    context.user_data['last_search_timestamp'] = datetime.now().isoformat()
                    logging.info(f"Stored {len(formatted_results)} formatted results in context")

                    return formatted_results

            except Exception as e:
                logging.error(f"Error in search_contacts (attempt {retry_count + 1}): {str(e)}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(retry_delay)
                    continue
                return None

        logging.error(f"Search failed after {max_retries} attempts")
        return None

    def _construct_search_query(self, search_term: str) -> Optional[str]:
        """Construct a robust search query with proper error handling"""
        try:
            base_query = """
            SELECT DISTINCT ON (name)
                name, email, contact, website, country, wa_available, product
            FROM importers
            WHERE true
        """

            # Handle different search terms
            if search_term == "0301":
                where_clause = "AND LOWER(product) LIKE '%0301%'"
            elif search_term == "0302":
                where_clause = "AND LOWER(product) LIKE '%0302%'"
            elif search_term == "0303":
                where_clause = "AND LOWER(product) LIKE '%0303%'"
            elif search_term == "0304":
                where_clause = "AND LOWER(product) LIKE '%0304%'"
            elif search_term.lower() == "anchovy":
                where_clause = "AND LOWER(product) SIMILAR TO '%(anchovy|0305)%'"
            elif search_term == "0901":
                where_clause = "AND LOWER(product) LIKE '%0901%'"
            elif search_term.lower() == "manggis":
                where_clause = "AND LOWER(product) SIMILAR TO '%(0810|manggis|mangosteen)%'"
            elif search_term == "44029010":
                where_clause = "AND LOWER(product) LIKE '%44029010%'"
            else:
                where_clause = f"AND LOWER(name) LIKE '%{search_term.lower()}%'"


            complete_query = f"""
            {base_query}
            {where_clause}
            ORDER BY name, country
            LIMIT 50
        """

            logging.info(f"Constructed query for term '{search_term}': {complete_query}")
            return complete_query

        except Exception as e:
            logging.error(f"Error constructing search query: {str(e)}", exc_info=True)
            return None

    async def save_contact(self, query: Update, context: ContextTypes.DEFAULT_TYPE, importer_name: str) -> None:
        """Handle saving a contact with improved transaction management and error handling"""
        try:
            user_id = query.from_user.id
            logging.info(f"Starting save_contact process for user {user_id} with importer: {importer_name}")

            # Rate limiting check
            if hasattr(self, '_last_save_time') and self._last_save_time.get(user_id):
                time_diff = time.time() - self._last_save_time[user_id]
                if time_diff < 3:  # 3 seconds cooldown
                    await query.message.reply_text(
                        "⚠️ Mohon tunggu sebentar (3 detik) sebelum menyimpan kontak lagi.",
                        parse_mode='Markdown'
                    )
                    return

            # Get and validate search results from context
            last_results = context.user_data.get('last_search_results', [])
            if not last_results:
                logging.error(f"No search results found in context for user {user_id}")
                await query.message.reply_text(
                    "Mohon tunggu beberapa saat lagi.",
                    parse_mode='Markdown'
                )
                return

            # Find matching importer in search results
            importer = None
            for result in last_results:
                if result['name'].strip() == importer_name.strip():
                    importer = result
                    break

            if not importer:
                # Try partial match if exact match fails
                for result in last_results:
                    if importer_name.strip() in result['name'].strip():
                        importer = result
                        break

            if not importer:
                logging.error(f"Importer {importer_name} not found in search results for user {user_id}")
                await query.message.reply_text(
                    "Mohon tunggu beberapa saat lagi.",
                    parse_mode='Markdown'
                )
                return

            # Update rate limit timestamp
            if not hasattr(self, '_last_save_time'):
                self._last_save_time = {}
            self._last_save_time[user_id] = time.time()

            # Perform save operation with proper transaction management
            async with self.engine.connect() as conn:
                async with conn.begin():
                    try:
                        # Lock user credits for update
                        credits_result = await conn.execute(
                            text("SELECT credits FROM user_credits WHERE user_id = :user_id FOR UPDATE"),
                            {"user_id": user_id}
                        )
                        credits = await credits_result.scalar()

                        if credits is None:
                            await query.message.reply_text(
                                "⚠️ Terjadi kesalahan. Silakan coba lagi.",
                                parse_mode='Markdown'
                            )
                            return

                        # Calculate credit cost
                        credit_cost = Messages._calculate_credit_cost(importer)

                        if credits < credit_cost:
                            await query.message.reply_text(
                                Messages.NO_CREDITS,
                                parse_mode='Markdown'
                            )
                            return

                        # Check if contact already saved
                        exists_result = await conn.execute(
                            text("SELECT COUNT(*) FROM saved_contacts WHERE user_id = :user_id AND importer_name = :name"),
                            {"user_id": user_id, "name": importer['name']}
                        )
                        already_saved = await exists_result.scalar()

                        if already_saved:
                            await query.message.reply_text(
                                "⚠️ Kontak ini sudah tersimpan sebelumnya.",
                                parse_mode='Markdown'
                            )
                            return

                        # Save contact
                        await conn.execute(
                            text("""
                                INSERT INTO saved_contacts 
                                (user_id, importer_name, email, contact, website, country, wa_available, product)
                                VALUES (:user_id, :name, :email, :contact, :website, :country, :wa_available, :product)
                            """),
                            {
                                "user_id": user_id,
                                "name": importer['name'],
                                "email": importer['email'],
                                "contact": importer['contact'],
                                "website": importer['website'],
                                "country": importer['country'],
                                "wa_available": importer['wa_available'],
                                "product": importer['hs_code']
                            }
                        )

                        # Update credits
                        await conn.execute(
                            text("UPDATE user_credits SET credits = credits - :cost WHERE user_id = :user_id"),
                            {"cost": credit_cost, "user_id": user_id}
                        )

                        # Get updated credits
                        new_credits_result = await conn.execute(
                            text("SELECT credits FROM user_credits WHERE user_id = :user_id"),
                            {"user_id": user_id}
                        )
                        new_credits = await new_credits_result.scalar()

                        await query.message.reply_text(
                            f"✅ Kontak berhasil disimpan!\n\nSisa kredit: {new_credits} kredit",
                            parse_mode='Markdown'
                        )
                        logging.info(f"Successfully saved contact for user {user_id}")

                    except Exception as e:
                        logging.error(f"Database error while saving contact: {str(e)}", exc_info=True)
                        await query.message.reply_text(
                            "Mohon tunggu beberapa saat lagi.",
                            parse_mode='Markdown'
                        )
                        raise
        except Exception as e:
            logging.error(f"Error in save_contact: {str(e)}", exc_info=True)
            await query.message.reply_text(
                "Mohon tunggu beberapa saat lagi.",
                parse_mode='Markdown'
            )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks with improved error handling and retries"""
        try:
            query = update.callback_query
            await query.answer()

            if query.data.startswith('search_'):
                user_id = query.from_user.id
                search_term = query.data.replace('search_', '')
                logging.info(f"User {user_id} searching for term: {search_term}")

                # Clear existing search data
                if 'last_search_results' in context.user_data:
                    context.user_data.pop('last_search_results')
                if 'search_page' in context.user_data:
                    context.user_data.pop('search_page')

                # Construct and execute search with retries
                max_retries = 3
                retry_delay = 1
                retry_count = 0
                results = None

                while retry_count < max_retries:
                    try:
                        search_query = self._construct_search_query(search_term)
                        if not search_query:
                            logging.error("Failed to construct search query")
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(retry_delay)
                                continue
                            await query.message.reply_text("Mohon maaf, terjadi kesalahan. Silakan coba lagi.")
                            return

                        # Execute search with proper error handling
                        results = await self.search_contacts(text(search_query), context)
                        if results and len(results) > 0:
                            break

                        logging.warning(f"Search attempt {retry_count + 1} returned no results")
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            continue
                    except Exception as e:
                        logging.error(f"Search attempt {retry_count + 1} failed: {str(e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            continue

                if not results:
                    await query.message.reply_text(
                        "❌ Maaf, kontak tidak ditemukan. Silakan coba kata kunci lain.",
                        parse_mode='Markdown'
                    )
                    return

                # Store search results and show first page
                context.user_data['last_search_results'] = results
                context.user_data['search_page'] = 0
                await self._show_search_results(query.message, context)

            elif query.data == "prev_page" or query.data == "next_page":
                try:
                    results = context.user_data.get('last_search_results', [])
                    if not results:
                        await query.message.reply_text("❌ Hasil pencarian tidak tersedia. Silakan cari ulang.")
                        return

                    current_page = context.user_data.get('search_page', 0)
                    if query.data == "prev_page":
                        current_page = max(0, current_page - 1)
                    else:
                        max_page = (len(results) - 1) // 3
                        current_page = min(max_page, current_page + 1)

                    context.user_data['search_page'] = current_page

                    # Delete previous messages if any
                    if 'current_result_messages' in context.user_data:
                        for msg_id in context.user_data['current_result_messages']:
                            try:
                                await context.bot.delete_message(
                                    chat_id=query.message.chat_id,
                                    message_id=msg_id
                                )
                            except Exception as e:
                                logging.error(f"Error deleting message: {str(e)}")

                    await self._show_search_results(query.message, context)

                except Exception as e:
                    logging.error(f"Error handling pagination: {str(e)}")
                    await query.message.reply_text(
                        "❌ Terjadi kesalahan saat menampilkan hasil. Silakan coba lagi.",
                        parse_mode='Markdown'
                    )

            # Handle other button callbacks...
            elif query.data.startswith('save_'):
                # Extract full importer name from callback data
                importer_name = query.data[5:]  # Remove 'save_' prefix
                await self.save_contact(query, context, importer_name)
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
                    await query.message.reply_text("Mohon tunggu beberapa saat lagi.")

            elif query.data == "folder_agriculture":
                try:
                    # Delete previous message
                    await query.message.delete()

                    folder_text = """🌿 *Produk Agrikultur*

                    Pilih produk:"""
                    async with self.engine.connect() as conn:
                        # Get counts for each category
                        coffee_count = await conn.scalar(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) LIKE '%0901%'
                        """))

                        manggis_count = await conn.scalar(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) SIMILAR TO '%(0810|manggis|mangosteen)%'
                        """))


                    keyboard = []
                    if coffee_count:
                        keyboard.append([InlineKeyboardButton(
                            f"☕ Kopi ({coffee_count} kontak)",
                            callback_data="search_0901"
                        )])
                    if manggis_count:
                        keyboard.append([InlineKeyboardButton(
                            f"🫐 Manggis ({manggiscount} kontak)",
                            callback_data="search_manggis"
                        )])

                    # Add pagination and navigation buttons
                    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

                    await query.message.reply_text(
                        folder_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error in agriculture folder: {str(e)}")
                    await query.message.reply_text("Mohon tunggu beberapa saat lagi.")

            elif query.data == "folder_processed":
                # Delete previous message
                await query.message.delete()

                folder_text = """🌳 *Produk Olahan*

                Pilih produk:"""
                try:
                    async with self.engine.connect() as conn:
                        result = await conn.execute(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) LIKE '%44029010%';
                        """))
                        hs_counts = await result.fetchall()

                        count = hs_counts[0][0] if hs_counts else 0

                        keyboard = [
                            [InlineKeyboardButton(
                                f"🪵 Briket Batok (44029010) - {count} kontak",
                                callback_data="search_briket"
                            )],
                            [InlineKeyboardButton(
                                "🔙 Kembali",
                                callback_data="back_to_categories"
                            )]
                        ]

                        await query.message.reply_text(
                            folder_text,
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logging.error(f"Error in menu_seafood handler: {str(e)}")
                    await query.message.reply_text("Mohon tunggu beberapa saat lagi.")

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
                                WHEN LOWER(product) LIKE '%1513%' OR LOWER(product) LIKE '%coconut oil%' THEN '1513%' THEN '1513'
                            END as hs_code,
                            COUNT(*) as count
                        FROM importers
                        WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                        GROUP BY hs_code
                        ORDER BY hs_code;
                    """)).fetchall()

                    counts_dict = {row[0]: row[1] for row in hs_counts}

                    keyboard = []
                    if counts_dict.get('0901'):
                        keyboard.append([InlineKeyboardButton(
                            f"☕ Kopi ({counts_dict['0901']} kontak)",
                            callback_data="search_0901"
                        )])
                    if counts_dict.get('1513'):
                        keyboard.append([InlineKeyboardButton(
                            f"🥥 Minyak Kelapa ({counts_dict['1513']} kontak)",
                            callback_data="search_coconut_oil"
                        )])

                    # Add pagination and navigation buttons
                    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

                    await query.message.reply_text(
                        "🌿 *Produk Agrikultur*",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

            elif query.data == "menu_processed":
                try:
                    async with self.engine.connect() as conn:
                        result = await conn.execute(text("""
                            SELECT COUNT(*) FROM importers 
                            WHERE LOWER(product) LIKE '%44029010%';
                        """))
                        hs_counts = await result.fetchall()

                        count = hs_counts[0][0] if hs_counts else 0

                        keyboard = [
                            [InlineKeyboardButton(
                                f"🪵 Briket Batok (44029010) - {count} kontak",
                                callback_data="search_briket"
                            )],
                            [InlineKeyboardButton(
                                "🔙 Kembali",
                                callback_data="back_to_categories"
                            )]
                        ]

                        await query.message.reply_text(
                            "🌳 *Produk Olahan*",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logging.error(f"Error getting HS code counts: {str(e)}")
                    await query.message.reply_text("Mohon tunggu beberapa saat lagi.")

            elif query.data.startswith('search_'):
                user_id = query.from_user.id
                search_term = query.data.replace('search_', '')

                # Log the search attempt
                logging.info(f"User {user_id} searching for term: {search_term}")

                try:
                    # Clear previous search data
                    context.user_data.clear()

                    # Construct search query based on term
                    search_query = self._construct_search_query(search_term)
                    if not search_query:
                        await query.message.reply_text("Mohon tunggu beberapa saat lagi.")
                        return

                    # Perform search with retries
                    retry_count = 0
                    max_retries = 3
                    results = None

                    while retry_count < max_retries and not results:
                        try:
                            conn = await self.engine.connect()
                            try:
                                result = await conn.execute(text(search_query))
                                rows = await result.fetchall()
                                if rows:
                                    results = []
                                    for row in rows:
                                        results.append({
                                            'name': row.name,
                                            'email': row.email,
                                            'contact': row.contact,
                                            'website': row.website,
                                            'country': row.country,
                                            'wa_available': row.wa_available,
                                            'hs_code': row.product
                                        })
                                    break
                            finally:
                                await conn.close()
                        except Exception as e:
                            logging.error(f"Search attempt {retry_count + 1} failed: {str(e)}")
                            retry_count += 1
                            await asyncio.sleep(1)  # Brief pause between retries

                    if not results:
                        logging.warning(f"Search failed after {max_retries} attempts")
                        await query.message.reply_text("Mohon tunggu beberapa saat lagi.")
                        return

                    # Store results and reset page
                    context.user_data['last_search_results'] = results
                    context.user_data['search_page'] = 0
                    context.user_data['last_search_query'] = search_query

                    # Show first page of results
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
                    logging.error(f"Error in search handler: {str(e)}", exc_info=True)
                    await query.message.reply_text("Mohon tunggu beberapa saat lagi.")

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
            try:
                await update.callback_query.message.reply_text(Messages.ERROR_MESSAGE)
            except:
                pass

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

            # Use the new search_contacts function
            results = await self.search_contacts(text(f"SELECT * FROM importers WHERE LOWER(name) LIKE '%{query.lower()}%'"), context)

            if not results:
                logging.info(f"No results found for query: {query}")
                await update.message.reply_text(
                    "Mohon tunggu beberapa saat lagi."
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

    def _construct_search_query(self, search_term):
        search_terms = {
            '0301': "SELECT * FROM importers WHERE LOWER(product) LIKE '%0301%' ORDER BY RANDOM() LIMIT 10",
            '0302': "SELECT * FROM importers WHERE LOWER(product) LIKE '%0302%' ORDER BY RANDOM() LIMIT 10",
            '0303': "SELECT * FROM importers WHERE LOWER(product) LIKE '%0303%' ORDER BY RANDOM() LIMIT 10",
            '0304': "SELECT * FROM importers WHERE LOWER(product) LIKE '%0304%' ORDER BY RANDOM() LIMIT 10",
            'anchovy': "SELECT * FROM importers WHERE LOWER(product) LIKE '%anchovy%' ORDER BY RANDOM() LIMIT 10",
            '0901': "SELECT * FROM importers WHERE LOWER(product) LIKE '%0901%' ORDER BY RANDOM() LIMIT 10",
            'coconut_oil': "SELECT * FROM importers WHERE LOWER(product) SIMILAR TO '%(1513|coconut oil|minyak kelapa)%' ORDER BY RANDOM() LIMIT 10",
            'briket': "SELECT * FROM importers WHERE LOWER(product) LIKE '%44029010%' ORDER BY RANDOM() LIMIT 10",
            'manggis': "SELECT * FROM importers WHERE LOWER(product) SIMILAR TO '%(0810|manggis|mangosteen)%' ORDER BY RANDOM() LIMIT 10"
        }
        return search_terms.get(search_term)

    async def _show_search_results(self, message, context):
        """Display search results with pagination"""
        try:
            results = context.user_data.get('last_search_results', [])
            if not results:
                await message.reply_text("Mohon tunggu beberapa saat lagi.")
                return

            page = context.user_data.get('search_page', 0)
            items_per_page = 2
            total_pages = (len(results) + items_per_page - 1) // items_per_page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(results))
            current_results = results[start_idx:end_idx]

            # Delete previous messages if they exist
            if 'current_search_messages' in context.user_data:
for msg_id in context.user_data['current_search_messages']:
                    try:
                        await message.bot.delete_message(
                            chat_id=message.chat_id,
                            message_id=msg_id
                        )
                    except Exception as e:
                        logging.error(f"Error deleting message: {str(e)}")

            new_messages = []
            for importer in current_results:
                message_text, _, _ = Messages.format_importer(importer)
                keyboard = [[InlineKeyboardButton(
                    "💾 Simpan Kontak",
                    callback_data=f"save_{importer['name']}"
                )]]
                sent_msg = await message.reply_text(
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

            regenerate_button = [
                [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
            ]

            sent_msg = await message.reply_text(
                f"Halaman {page + 1} dari {total_pages}",
                reply_markup=InlineKeyboardMarkup([pagination_buttons] + regenerate_button)
            )
            new_messages.append(sent_msg.message_id)
            context.user_data['current_search_messages'] = new_messages

        except Exception as e:
            logging.error(f"Error showing search results: {str(e)}", exc_info=True)
            await message.reply_text("Mohon tunggu beberapa saat lagi.")

    async def show_categories(self, message):
        """Show main categories with contact counts"""
        try:
            header_text = """📊 *Kontak Tersedia*

Pilih kategori produk:"""

            async with self.engine.connect() as conn:
                # Get counts for each category
                seafood_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'
                """))

                agriculture_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                """))

                processed_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) LIKE '%44029010%'
                """))

            keyboard = [
                [InlineKeyboardButton(f"🌊 Produk Laut ({seafood_count} kontak)", callback_data="folder_seafood")],
                [InlineKeyboardButton(f"🌿 Produk Agrikultur ({agriculture_count} kontak)", callback_data="folder_agriculture")],
                [InlineKeyboardButton(f"🌳 Produk Olahan ({processed_count} kontak)", callback_data="folder_processed")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await message.reply_text(
                header_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Error showing categories: {str(e)}")
            await message.reply_text("Mohon tunggu beberapa saat lagi.")

    async def _show_search_results(self, message, context: ContextTypes.DEFAULT_TYPE):
        """Display search results with improved error handling"""
        try:
            results = context.user_data.get('last_search_results', [])
            if not results:
                await message.reply_text(
                    "❌ Maaf, kontak tidak ditemukan atau terjadi kesalahan. Silakan coba lagi.",
                    parse_mode='Markdown'
                )
                return

            page = context.user_data.get('search_page', 0)
            items_per_page = 3
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(results))
            current_results = results[start_idx:end_idx]

            if not current_results:
                await message.reply_text(
                    "❌ Maaf, tidak ada hasil yang ditemukan pada halaman ini.",
                    parse_mode='Markdown'
                )
                return

            # Send results with proper formatting
            for result in current_results:
                try:
                    message_text, whatsapp_number, credit_cost = Messages.format_importer(result)
                    keyboard = []
                    save_button = [InlineKeyboardButton(
                        f"💾 Simpan ({credit_cost} kredit)",
                        callback_data=f"save_{result['name']}"
                    )]
                    if whatsapp_number:
                        keyboard.append([InlineKeyboardButton(
                            "💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )])
                    keyboard.append(save_button)

                    await message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error displaying result {result}: {str(e)}", exc_info=True)
                    continue

            # Add navigation buttons
            navigation = []
            if page > 0:
                navigation.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data="prev_page"))
            if end_idx < len(results):
                navigation.append(InlineKeyboardButton("Selanjutnya ➡️", callback_data="next_page"))

            footer_buttons = [navigation] if navigation else []
            footer_buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

            await message.reply_text(
                f"Halaman {page + 1} dari {(len(results) + items_per_page - 1) // items_per_page}",
                reply_markup=InlineKeyboardMarkup(footer_buttons)
            )

        except Exception as e:
            logging.error(f"Error in _show_search_results: {str(e)}", exc_info=True)
            await message.reply_text(
                "❌ Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi.",
                parse_mode='Markdown'
            )

    async def show_categories(self, message):
        """Show main categories with contact counts"""
        try:
            header_text = """📊 *Kontak Tersedia*

Pilih kategori produk:"""

            async with self.engine.connect() as conn:
                # Get counts for each category
                seafood_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'
                """))

                agriculture_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'
                """))

                processed_count = await conn.scalar(text("""
                    SELECT COUNT(*) FROM importers 
                    WHERE LOWER(product) LIKE '%44029010%'
                """))

            keyboard = [
                [InlineKeyboardButton(f"🌊 Produk Laut ({seafood_count} kontak)", callback_data="folder_seafood")],
                [InlineKeyboardButton(f"🌿 Produk Agrikultur ({agriculture_count} kontak)", callback_data="folder_agriculture")],
                [InlineKeyboardButton(f"🌳 Produk Olahan ({processed_count} kontak)", callback_data="folder_processed")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]

            await message.reply_text(
                header_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Error showing categories: {str(e)}")
            await message.reply_text("Mohon tunggu beberapa saat lagi.")

    async def _show_search_results(self, message, context: ContextTypes.DEFAULT_TYPE):
        """Display search results with improved error handling"""
        try:
            results = context.user_data.get('last_search_results', [])
            if not results:
                await message.reply_text(
                    "❌ Maaf, kontak tidak ditemukan atau terjadi kesalahan. Silakan coba lagi.",
                    parse_mode='Markdown'
                )
                return

            page = context.user_data.get('search_page', 0)
            items_per_page = 3
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(results))
            current_results = results[start_idx:end_idx]

            if not current_results:
                await message.reply_text(
                    "❌ Maaf, tidak ada hasil yang ditemukan pada halaman ini.",
                    parse_mode='Markdown'
                )
                return

            # Send results with proper formatting
            for result in current_results:
                try:
                    message_text, whatsapp_number, credit_cost = Messages.format_importer(result)
                    keyboard = []
                    save_button = [InlineKeyboardButton(
                        f"💾 Simpan ({credit_cost} kredit)",
                        callback_data=f"save_{result['name']}"
                    )]
                    if whatsapp_number:
                        keyboard.append([InlineKeyboardButton(
                            "💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )])
                    keyboard.append(save_button)

                    await message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logging.error(f"Error displaying result {result}: {str(e)}", exc_info=True)
                    continue

            # Add navigation buttons
            navigation = []
            if page > 0:
                navigation.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data="prev_page"))
            if end_idx < len(results):
                navigation.append(InlineKeyboardButton("Selanjutnya ➡️", callback_data="next_page"))

            footer_buttons = [navigation] if navigation else []
            footer_buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")])

            await message.reply_text(
                f"Halaman {page + 1} dari {(len(results) + items_per_page - 1) // items_per_page}",
                reply_markup=InlineKeyboardMarkup(footer_buttons)
            )

        except Exception as e:
            logging.error(f"Error in _show_search_results: {str(e)}", exc_info=True)
            await message.reply_text(
                "❌ Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi.",
                parse_mode='Markdown'
            )