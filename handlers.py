import logging
import time
import asyncio
from datetime import datetime
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlalchemy import text

from data_store import DataStore
from app import app, RATE_LIMIT_WINDOW, MAX_REQUESTS
from messages import Messages

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        self.engine = self.data_store.engine
        logging.info("CommandHandler initialized")
        self._last_save_time = {}

    async def search_contacts(self, query: str, context: ContextTypes.DEFAULT_TYPE):
        """Search for contacts with improved error handling and retries"""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                logging.info(f"Executing search query '{query}' (attempt {attempt + 1}/{max_retries}) for user {context.user_data.get('user_id', 'unknown')}")

                async with self.engine.connect() as conn:
                    async with conn.begin():
                        # Clear existing results
                        if 'last_search_results' in context.user_data:
                            context.user_data.pop('last_search_results')

                        # Execute search with timeout
                        result = await asyncio.wait_for(
                            conn.execute(text(query)),
                            timeout=10.0
                        )
                        rows = await result.fetchall()

                        if not rows:
                            logging.warning(f"No results found for query '{query}' (attempt {attempt + 1})")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                continue
                            return None

                        # Format results
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
                                    'product_description': row.product_description.strip() if row.product_description else '',
                                    'search_timestamp': datetime.now().isoformat()
                                }
                                formatted_results.append(formatted_result)
                            except Exception as e:
                                logging.error(f"Error formatting row: {str(e)}", exc_info=True)
                                continue

                        if not formatted_results:
                            logging.warning("No valid results after formatting for query '{query}'")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                continue
                            return None

                        # Store results in context
                        context.user_data['last_search_results'] = formatted_results
                        context.user_data['last_search_timestamp'] = datetime.now().isoformat()
                        logging.info(f"Successfully stored {len(formatted_results)} results for query '{query}'")

                        return formatted_results

            except asyncio.TimeoutError:
                logging.error(f"Search query '{query}' timeout (attempt {attempt + 1})")
            except Exception as e:
                logging.error(f"Error in search (attempt {attempt + 1}): {str(e)}", exc_info=True)

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue

        logging.error(f"Search for query '{query}' failed after {max_retries} attempts")
        return None

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()
            logging.info(f"Processing button callback '{query.data}' from user {query.from_user.id}")

            if query.data == "folder_seafood":
                keyboard = [[InlineKeyboardButton("Kembali", callback_data="back_to_main")]]
                await query.message.reply_text(
                    "Menu Seafood",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logging.info(f"Seafood menu shown to user {query.from_user.id}")

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
                    logging.info(f"Seafood options shown to user {query.from_user.id}")

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
                    logging.info(f"Agriculture options shown to user {query.from_user.id}")

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
                        logging.info(f"Processed products shown to user {query.from_user.id}")
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
                    search_query = await self._construct_search_query(search_term)
                    if not search_query:
                        await query.message.reply_text("Mohon tunggu beberapa saat lagi.")
                        return

                    # Perform search with retries
                    results = await self.search_contacts(search_query, context)
                    if not results:
                        logging.warning(f"Search failed after multiple attempts for term: {search_term}")
                        await query.message.reply_text("Mohon tunggu beberapa saat lagi.")
                        return

                    # Store results and reset page
                    context.user_data['last_search_results'] = results
                    context.user_data['search_page'] = 0
                    context.user_data['last_search_query'] = search_query
                    #Show first page of results
                    await self._show_search_results(query.message, context)
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
                    logging.info(f"Orders exported by user {query.from_user.id}")
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
                            logging.info(f"Order {order_id} fulfilled by user {query.from_user.id}")
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
                    logging.info(f"User {user_id} joined community")
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
                    logging.info(f"Help shown to user {user_id}")
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
                    logging.info(f"Credits shown to user {user_id}")
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
            if not await self._check_rate_limit(update):
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
                logging.info(f"Orders shown to admin user {user_id}")

        except Exception as e:
            logging.error(f"Error in orders command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def give_credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /givecredits command for admins"""
        try:
            if not await self._check_rate_limit(update):
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
                    logging.info(f"Admin {user_id} added {credit_amount} credits to user {target_user_id}")
                else:
                    await update.message.reply_text("❌ Failed to add credits. User may not exist.")

        except Exception as e:
            logging.error(f"Error in give_credits command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)

    async def credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            if not await self._check_rate_limit(update):
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
            results = await self.search_contacts(await self._construct_search_query(query), context)

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

    async def _check_rate_limit(self, update: Update) -> bool:
        """
        Check if the user has exceeded rate limits.
        Returns True if the user can proceed, False if rate limited.
        """
        try:
            user_id = update.effective_user.id
            current_time = time.time()

            # Initialize user's rate limit data if not exists
            if user_id not in self._last_save_time:
                self._last_save_time[user_id] = {
                    'timestamps': [],
                    'last_warning': 0
                }

            # Clean up old timestamps
            window_start = current_time - RATE_LIMIT_WINDOW
            self._last_save_time[user_id]['timestamps'] = [
                t for t in self._last_save_time[user_id]['timestamps'] 
                if t > window_start
            ]

            # Add current timestamp
            self._last_save_time[user_id]['timestamps'].append(current_time)

            # Check if rate limited
            if len(self._last_save_time[user_id]['timestamps']) > MAX_REQUESTS:
                # Only send warning message once per window
                if current_time - self._last_save_time[user_id]['last_warning'] > RATE_LIMIT_WINDOW:
                    await update.message.reply_text(Messages.RATE_LIMIT_EXCEEDED)
                    self._last_save_time[user_id]['last_warning'] = current_time
                return False

            return True

        except Exception as e:
            logging.error(f"Error in rate limit check: {str(e)}")
            return True  # Allow operation on rate limit check failure

    async def _construct_search_query(self, search_term: str) -> Optional[str]:
        """Construct a more robust search query with fuzzy matching and comprehensive conditions"""
        try:
            if not search_term or len(search_term.strip()) == 0:
                logging.error("Empty search term provided")
                return None

            # Define search conditions based on product type with expanded terms
            conditions = {
                # Fish products with multiple terms
                "0301": "LOWER(product) SIMILAR TO '%(0301|fish|ikan|seafood)%'",
                "0302": "LOWER(product) SIMILAR TO '%(0302|fresh fish|ikan segar|fresh seafood)%'",
                "0303": "LOWER(product) SIMILAR TO '%(0303|frozen fish|ikan beku|frozen seafood)%'",
                "0304": "LOWER(product) SIMILAR TO '%(0304|fillet|fish fillet|ikan fillet)%'",
                "anchovy": "LOWER(product) SIMILAR TO '%(anchovy|0305|teri|ikan teri)%'",

                #Agricultural products
                "0901": "LOWER(product) SIMILAR TO '%(0901|coffee|kopi|arabica|robusta)%'",
                "manggis": "LOWER(product) SIMILAR TO '%(0810|manggis|mangosteen|garcinia)%'",
                "1513": "LOWER(product) SIMILAR TO '%(1513|coconut|kelapa|VCO|virgin)%'",

                # Processed products
                "44029010": "LOWER(product) SIMILAR TO '%(44029010|charcoal|arang|briket|briquette)%'"
            }

            # Enhanced base query with better ranking
            base_query = """
            WITH ranked_results AS (
                SELECT DISTINCT ON (name)
                    name, 
                    email_1 as email, 
                    phone as contact, 
                    website, 
                    country, 
                    wa_availability as wa_available, 
                    product, 
                    role as product_description,
                    CASE 
                        WHEN wa_availability = 'Available' THEN 4  -- Prioritize WhatsApp availability
                        WHEN phone IS NOT NULL AND email_1 IS NOT NULL AND website IS NOT NULL THEN 3  -- All contact methods
                        WHEN (phone IS NOT NULL AND email_1 IS NOT NULL) OR 
                             (phone IS NOT NULL AND website IS NOT NULL) OR 
                             (email_1 IS NOT NULL AND website IS NOT NULL) THEN 2  -- Two contact methods
                        ELSE 1  -- At least one contact method
                    END as contact_score,
                    CASE
                        WHEN LOWER(name) LIKE '%{term}%' THEN 3  -- Direct name match
                        WHEN LOWER(product) SIMILAR TO '%(hs|{term})%' THEN 2  -- Product/HS code match
                        ELSE 1  -- Other matches
                    END as relevance_score
                FROM importers
                WHERE (phone IS NOT NULL OR email_1 IS NOT NULL OR website IS NOT NULL)
                AND {where_clause}
            )
            SELECT * FROM ranked_results 
            ORDER BY contact_score DESC, relevance_score DESC, name ASC
            LIMIT 50;
            """

            # Get condition or create a comprehensive search
            search_term_lower = search_term.lower().strip()
            if search_term_lower in conditions:
                where_clause = conditions[search_term_lower]
            else:
                # Comprehensive search for non-standard terms
                where_clause = f"""(
                    LOWER(name) LIKE '%{search_term_lower}%'
                    OR LOWER(product) SIMILAR TO '%({search_term_lower}|hs)%'
                    OR LOWER(role) LIKE '%{search_term_lower}%'
                    OR LOWER(country) LIKE '%{search_term_lower}%'
                )"""

            # Format query with search term for relevance scoring
            complete_query = base_query.format(
                where_clause=where_clause,
                term=search_term_lower
            )

            logging.info(f"Constructed enhanced search query for term '{search_term}'")
            return complete_query

        except Exception as e:
            logging.error(f"Error constructing search query: {str(e)}", exc_info=True)
            return None

    async def _show_search_results(self, message, context: ContextTypes.DEFAULT_TYPE):
        """Display search results with improved error handling and logging"""
        try:
            results = context.user_data.get('last_search_results', [])
            logging.info(f"Showing search results. Total results: {len(results)}")

            if not results:
                logging.warning("No search results found in context")
                await message.reply_text(
                    "❌ Maaf, kontak tidak ditemukan. Silakan coba kata kunci lain.",
                    parse_mode='Markdown'
                )
                return

            page = context.user_data.get('search_page', 0)
            items_per_page = 3
            total_pages = (len(results) + items_per_page - 1) // items_per_page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(results))
            current_results = results[start_idx:end_idx]

            logging.info(f"Displaying page {page + 1}/{total_pages} (items {start_idx + 1}-{end_idx} of {len(results)})")

            # Clean up previous messages
            new_messages = []
            if 'current_search_messages' in context.user_data:
                for msg_id in context.user_data['current_search_messages']:
                    try:
                        await message.bot.delete_message(
                            chat_id=message.chat_id,
                            message_id=msg_id
                        )
                    except Exception as e:
                        logging.error(f"Error deleting message {msg_id}: {str(e)}")

            # Display current results
            for importer in current_results:
                try:
                    message_text, whatsapp_number, credit_cost = Messages.format_importer(importer)
                    keyboard = []

                    # Add WhatsApp button if available
                    if whatsapp_number:
                        keyboard.append([InlineKeyboardButton(
                            "💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )])

                    # Add save button
                    keyboard.append([InlineKeyboardButton(
                        f"💾 Simpan ({credit_cost} kredit)",
                        callback_data=f"save_{importer['name']}"
                    )])

                    sent_msg = await message.reply_text(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    new_messages.append(sent_msg.message_id)
                    logging.info(f"Successfully displayed result: {importer['name']}")
                except Exception as e:
                    logging.error(f"Error displaying result: {str(e)}", exc_info=True)
                    continue

            # Add navigation buttons
            navigation_buttons = []
            if page > 0:
                navigation_buttons.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data="prev_page"))
            if end_idx < len(results):
                navigation_buttons.append(InlineKeyboardButton("Selanjutnya ➡️", callback_data="next_page"))

            # Add navigation bar
            button_rows = []
            if navigation_buttons:
                button_rows.append(navigation_buttons)
            button_rows.extend([
                [InlineKeyboardButton("🔄 Cari Lagi", callback_data="regenerate_search")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_categories")]
            ])

            # Send navigation message
            sent_msg = await message.reply_text(
                f"Halaman {page + 1} dari {total_pages}",
                reply_markup=InlineKeyboardMarkup(button_rows)
            )
            new_messages.append(sent_msg.message_id)

            # Store message IDs for future cleanup
            context.user_data['current_search_messages'] = new_messages
            logging.info(f"Search results display completed. Total messages: {len(new_messages)}")

        except Exception as e:
            logging.error(f"Error in _show_search_results: {str(e)}", exc_info=True)
            await message.reply_text(
                "❌ Mohon maaf, terjadi kesalahan. Silakan coba beberapa saat lagi.",
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
            logging.info(f"Categories shown")
        except Exception as e:
            logging.error(f"Error showing categories: {str(e)}")
            await message.reply_text("Mohon tunggu beberapa saat lagi.")

    async def _check_rate_limit(self, update: Update) -> bool:
        """Check rate limiting for commands"""
        user_id = update.effective_user.id
        command = update.message.text.split()[0] if update.message else None
        try:
            with app.app_context():
                result = self.data_store.check_rate_limit(user_id, command)
                if not result:
                    await update.message.reply_text(
                        "⚠️ Mohon tunggu beberapa detik sebelum mencoba lagi.",
                        parse_mode='Markdown'
                    )
                return result
        except Exception as e:
            logging.error(f"Error in rate limit check: {str(e)}")
            return True  # Allow operation on rate limit check failure

    def check_rate_limit(self, user_id: int, command: Optional[str]) -> bool:
        """Check if the user has exceeded rate limits"""
        try:
            current_time = time.time()
            user_key = f"{user_id}:{command}" if command else str(user_id)

            # Get last command time
            last_time = self._last_save_time.get(user_key, 0)

            # 3 second cooldown
            if current_time - last_time < 3:
                return False

            self._last_save_time[user_key] = current_time
            return True

        except Exception as e:
            logging.error(f"Error in rate limit check: {str(e)}")
            return True  # Allow operation on rate limit check failure

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            logging.info(f"Processing /start command for user {update.effective_user.id}")
            user_id = update.effective_user.id

            with app.app_context():
                self.data_store.track_user_command(user_id, 'start')
                credits = self.data_store.get_user_credits(user_id)
                logging.info(f"User {user_id} has {credits} credits")

            keyboard = [
                [InlineKeyboardButton("📦 Kontak Tersedia", callback_data="show_hs_codes")],
                [InlineKeyboardButton("📁 Kontak Tersimpan", callback_data="show_saved")],
                [InlineKeyboardButton("💳 Kredit Saya", callback_data="show_credits"),
                 InlineKeyboardButton("💰 Beli Kredit", callback_data="buy_credits")],
                [InlineKeyboardButton("🌐 Gabung Komunitas", callback_data="join_community")],
                [InlineKeyboardButton("❓ Bantuan", callback_data="show_help")],
                [InlineKeyboardButton("👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")]
            ]

            await update.message.reply_text(
                Messages.WELCOME_MESSAGE.format(credits),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            logging.info(f"Start command processed successfully for user {user_id}")

        except Exception as e:
            logging.error(f"Error in start command: {str(e)}", exc_info=True)
            await update.message.reply_text(Messages.ERROR_MESSAGE)