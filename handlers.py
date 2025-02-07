import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from prometheus_client import Counter, Histogram

from data_store import DataStore
from messages import Messages
from monitoring import monitor

# Prometheus metrics
COMMAND_COUNTER = Counter('bot_commands_total', 'Total bot commands', ['command'])
COMMAND_LATENCY = Histogram('bot_command_duration_seconds', 'Command latency', ['command'])

class CommandHandler:
    def __init__(self):
        self.data_store = DataStore()
        logging.info("CommandHandler initialized")
        self._last_save_time = {}
        self._rate_limit_data = {}

    async def start(self, message: types.Message):
        """Handle /start command with metrics"""
        COMMAND_COUNTER.labels(command='start').inc()
        with COMMAND_LATENCY.labels(command='start').time():
            try:
                user_id = message.from_user.id
                await self.data_store.initialize_user_credits(user_id)

                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="📦 Kontak Tersedia", callback_data="show_hs_codes")
                keyboard.button(text="📁 Kontak Tersimpan", callback_data="show_saved")
                keyboard.button(text="💳 Kredit Saya", callback_data="show_credits")
                keyboard.button(text="💰 Beli Kredit", callback_data="buy_credits")
                keyboard.button(text="❓ Bantuan", callback_data="show_help")
                keyboard.button(text="👨‍💼 Hubungi Admin", url="https://t.me/afrizaladinur")
                keyboard.adjust(2, 2, 1, 1)

                await message.answer(
                    Messages.WELCOME_MESSAGE,
                    reply_markup=keyboard.as_markup()
                )
                logger.info(f"Start command processed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in start command: {e}")
                await message.answer(Messages.ERROR_MESSAGE)

    async def _show_search_results(self, message: types.Message, results: List[Dict], page: int = 0):
        """Display search results with improved error handling and logging"""
        try:
            logger.info(f"Showing search results. Total results: {len(results)}")

            if not results:
                logger.warning("No search results found")
                await message.answer(
                    "❌ Maaf, kontak tidak ditemukan. Silakan coba kata kunci lain.",
                    parse_mode='Markdown'
                )
                return

            items_per_page = 3
            total_pages = (len(results) + items_per_page - 1) // items_per_page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(results))
            current_results = results[start_idx:end_idx]

            logger.info(f"Displaying page {page + 1}/{total_pages} (items {start_idx + 1}-{end_idx} of {len(results)})")

            # Display current results
            for importer in current_results:
                try:
                    message_text, whatsapp_number, credit_cost = Messages.format_importer(importer)
                    keyboard = InlineKeyboardBuilder()

                    # Add WhatsApp button if available
                    if whatsapp_number:
                        keyboard.button(
                            text="💬 Chat di WhatsApp",
                            url=f"https://wa.me/{whatsapp_number}"
                        )

                    # Add save button
                    keyboard.button(
                        text=f"💾 Simpan ({credit_cost} kredit)",
                        callback_data=f"save_{importer['name']}"
                    )
                    keyboard.adjust(1)

                    await message.answer(
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard.as_markup()
                    )
                    logger.info(f"Successfully displayed result: {importer['name']}")
                except Exception as e:
                    logger.error(f"Error displaying result: {str(e)}")
                    continue

            # Add navigation buttons
            nav_keyboard = InlineKeyboardBuilder()
            if page > 0:
                nav_keyboard.button(text="⬅️ Sebelumnya", callback_data="prev_page")
            if end_idx < len(results):
                nav_keyboard.button(text="Selanjutnya ➡️", callback_data="next_page")

            nav_keyboard.button(text="🔄 Cari Lagi", callback_data="regenerate_search")
            nav_keyboard.button(text="🔙 Kembali", callback_data="back_to_categories")
            nav_keyboard.adjust(2, 1, 1)

            # Send navigation message
            await message.answer(
                f"Halaman {page + 1} dari {total_pages}",
                reply_markup=nav_keyboard.as_markup()
            )

            logger.info(f"Search results display completed.")

        except Exception as e:
            logger.error(f"Error in _show_search_results: {str(e)}")
            await message.answer(
                "❌ Mohon maaf, terjadi kesalahan. Silakan coba beberapa saat lagi.",
                parse_mode='Markdown'
            )

    async def search(self, message: types.Message, query: str):
        """Handle search command with metrics"""
        COMMAND_COUNTER.labels(command='search').inc()
        with COMMAND_LATENCY.labels(command='search').time():
            try:
                user_id = message.from_user.id
                logger.info(f"Processing search command for user {user_id}")

                results = await self.data_store.search_importers(query)
                if not results:
                    logger.info(f"No results found for query: {query}")
                    await message.answer("Mohon tunggu beberapa saat lagi.")
                    return

                await self._show_search_results(message, results)

            except Exception as e:
                logger.error(f"Error in search command: {str(e)}")
                await message.answer(Messages.ERROR_MESSAGE)

    async def button_callback(self, callback_query: types.CallbackQuery):
        """Handle button callbacks with metrics"""
        COMMAND_COUNTER.labels(command='button_callback').inc()
        with COMMAND_LATENCY.labels(command='button_callback').time():
            try:
                user_id = callback_query.from_user.id
                data = callback_query.data

                if not await self._check_rate_limit(user_id, f'button_{data}'):
                    await callback_query.answer("Too many requests. Please wait a minute.", show_alert=True)
                    return

                # Handle different button callbacks
                if data == "show_credits":
                    credits = await self.data_store.get_user_credits(user_id)
                    keyboard = InlineKeyboardBuilder()
                    keyboard.button(text="🔙 Back", callback_data="back_to_main")
                    await callback_query.message.edit_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}",
                        reply_markup=keyboard.as_markup()
                    )
                elif data.startswith("search_"):
                    search_term = data.replace("search_", "")
                    await self.search(callback_query.message, search_term)
                elif data == "show_saved":
                    await self.saved(callback_query.message)
                elif data == "back_to_main":
                    await callback_query.message.edit_text("Welcome!", reply_markup=None)
                elif data == "show_hs_codes":
                    await self.show_categories(callback_query.message)

                logger.info(f"Button callback {data} processed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in button callback: {e}")
                await callback_query.message.answer(Messages.ERROR_MESSAGE)

    async def _check_rate_limit(self, user_id: int, command: str) -> bool:
        """Check if user has exceeded rate limit"""
        current_time = datetime.now().timestamp()
        user_key = f"{user_id}:{command}"

        if user_key in self._rate_limit_data:
            timestamps = self._rate_limit_data[user_key]
            timestamps = [ts for ts in timestamps if current_time - ts <= 60]

            if len(timestamps) >= 10:  # Max 10 requests per minute
                logger.warning(f"Rate limit exceeded for user {user_id} on command {command}")
                monitor.log_rate_limit_event(user_id, command)
                return False

            timestamps.append(current_time)
            self._rate_limit_data[user_key] = timestamps
        else:
            self._rate_limit_data[user_key] = [current_time]

        return True

    async def saved(self, message: types.Message):
        """Handle saved contacts command"""
        try:
            if not await self._check_rate_limit(message.from_user.id, 'saved'):
                return

            user_id = message.from_user.id
            saved_contacts = await self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Kembali", callback_data="back_to_main")
                await message.answer(
                    Messages.NO_SAVED_CONTACTS,
                    reply_markup=keyboard.as_markup()
                )
                return

            await self._show_saved_contacts(message, saved_contacts)
            logger.info(f"Saved contacts shown to user {user_id}")

        except Exception as e:
            logger.error(f"Error in saved command: {e}")
            await message.answer(Messages.ERROR_MESSAGE)

    async def _show_saved_contacts(self, message, contacts):
        try:
            page = 0
            items_per_page = 5
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_contacts = contacts[start_idx:end_idx]

            if not page_contacts:
                await message.answer("No more saved contacts.")
                return

            for contact in page_contacts:
                formatted_message, whatsapp_number, _ = Messages.format_importer(
                    contact, saved=True, user_id=message.from_user.id
                )

                keyboard = InlineKeyboardBuilder()
                if whatsapp_number:
                    whatsapp_url = f"https://wa.me/{whatsapp_number}"
                    keyboard.button("💬 Chat WhatsApp", url=whatsapp_url)
                keyboard.adjust(1)

                await message.answer(
                    formatted_message,
                    parse_mode='MarkdownV2',
                    reply_markup=keyboard.as_markup() if keyboard.buttons else None
                )

            #Add Pagination - simplified for brevity

        except Exception as e:
            logger.exception(f"Error showing saved contacts: {e}")
            await message.answer(Messages.ERROR_MESSAGE)

    async def search_contacts(self, query: str, user_id: int) -> Optional[List[Dict]]:
        """Search for contacts with improved error handling and retries"""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                logger.info(f"Executing search query '{query}' (attempt {attempt + 1}/{max_retries}) for user {user_id}")

                results = await self.data_store.search_importers(query)
                if not results:
                    logger.warning(f"No results found for query '{query}' (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return None

                return results

            except asyncio.TimeoutError:
                logger.error(f"Search query '{query}' timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Error in search (attempt {attempt + 1}): {str(e)}")

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue

        logger.error(f"Search for query '{query}' failed after {max_retries} attempts")
        return None

    async def _construct_search_query(self, search_term: str) -> Optional[str]:
        """Construct a more robust search query with fuzzy matching and comprehensive conditions"""
        try:
            if not search_term or len(search_term.strip()) == 0:
                logger.error("Empty search term provided")
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

            logger.info(f"Constructed enhanced search query for term '{search_term}'")
            return complete_query

        except Exception as e:
            logger.error(f"Error constructing search query: {str(e)}", exc_info=True)
            return None

    async def button_callback(self, callback_query: types.CallbackQuery):
        """Handle button callbacks"""
        COMMAND_COUNTER.labels(command='button_callback').inc()
        with COMMAND_LATENCY.labels(command='button_callback').time():
            try:
                user_id = callback_query.from_user.id
                data = callback_query.data

                if not await self._check_rate_limit(user_id, f'button_{data}'):
                    await callback_query.answer("Too many requests. Please wait a minute.", show_alert=True)
                    return

                # Handle different button callbacks
                if data == "show_credits":
                    credits = await self.data_store.get_user_credits(user_id)
                    keyboard = InlineKeyboardBuilder()
                    keyboard.button(text="🔙 Back", callback_data="back_to_main")
                    await callback_query.message.edit_text(
                        f"{Messages.CREDITS_REMAINING.format(credits)}",
                        reply_markup=keyboard.as_markup()
                    )
                elif data.startswith("search_"):
                    search_term = data.replace("search_", "")
                    await self.search(callback_query.message, search_term)
                elif data == "show_saved":
                    await self.saved(callback_query.message)
                elif data == "back_to_main":
                    await callback_query.message.edit_text("Welcome!", reply_markup=None)
                elif data == "show_hs_codes":
                    await self.show_categories(callback_query.message)

                logger.info(f"Button callback {data} processed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in button callback: {e}")
                await callback_query.message.answer(Messages.ERROR_MESSAGE)

    async def show_categories(self, message: types.Message):
        COMMAND_COUNTER.labels(command='show_categories').inc()
        with COMMAND_LATENCY.labels(command='show_categories').time():
            try:
                header_text = """📊 *Kontak Tersedia*
Pilih kategori produk:"""
                async with self.data_store.pool.acquire() as conn: # Assuming asyncpg pool is now in DataStore
                    # Get counts for each category using asyncpg
                    seafood_count = await conn.fetchval("SELECT COUNT(*) FROM importers WHERE LOWER(product) SIMILAR TO '%(0301|0302|0303|0304|0305|anchovy)%'")
                    agriculture_count = await conn.fetchval("SELECT COUNT(*) FROM importers WHERE LOWER(product) SIMILAR TO '%(0901|1513|coconut oil)%'")
                    processed_count = await conn.fetchval("SELECT COUNT(*) FROM importers WHERE LOWER(product) LIKE '%44029010%'")

                keyboard = InlineKeyboardBuilder()
                keyboard.button(text=f"🌊 Produk Laut ({seafood_count} kontak)", callback_data="folder_seafood")
                keyboard.button(text=f"🌿 Produk Agrikultur ({agriculture_count} kontak)", callback_data="folder_agriculture")
                keyboard.button(text=f"🌳 Produk Olahan ({processed_count} kontak)", callback_data="folder_processed")
                keyboard.button(text="🔙 Kembali", callback_data="back_to_main")
                keyboard.adjust(1)

                await message.answer(
                    header_text,
                    reply_markup=keyboard.as_markup(),
                    parse_mode='Markdown'
                )
                logger.info(f"Categories shown")
            except Exception as e:
                logger.error(f"Error showing categories: {str(e)}")
                await message.answer("Mohon tunggu beberapa saat lagi.")


    async def stats(self, message: types.Message):
        COMMAND_COUNTER.labels(command='stats').inc()
        with COMMAND_LATENCY.labels(command='stats').time():
            try:
                if not await self._check_rate_limit(message.from_user.id, 'stats'):
                    return

                user_id = message.from_user.id
                stats = await self.data_store.get_user_stats(user_id)
                await message.answer(Messages.format_stats(stats), parse_mode='Markdown')
                logger.info(f"Stats command processed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in stats command: {str(e)}", exc_info=True)
                await message.answer(Messages.ERROR_MESSAGE)


    async def orders(self, message: types.Message):
        try:
            user_id = message.from_user.id
            admin_ids = [6422072438]  # Admin check

            if user_id not in admin_ids:
                await message.answer("⛔️ You are not authorized to use this command.")
                return

            # Adapt to aiogram and asyncpg.  This is a partial implementation
            #  More complete pagination and error handling would be necessary in a production environment.
            async with self.data_store.pool.acquire() as conn:
                orders = await conn.fetch("""
                    SELECT order_id, user_id, credits, amount, status, created_at
                    FROM credit_orders 
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                """)
                for order in orders:
                    await message.answer(f"Order ID: {order['order_id']}, User ID: {order['user_id']}, Status: {order['status']}")
        except Exception as e:
            logger.exception(f"Error in orders command: {e}")
            await message.answer(Messages.ERROR_MESSAGE)

    async def give_credits(self, message: types.Message, context: types.CallbackQuery):
        try:
            if not await self._check_rate_limit(message.from_user.id, 'give_credits'):
                return

            user_id = message.from_user.id
            admin_ids = [6422072438]  # Your Telegram ID

            if user_id not in admin_ids:
                await message.answer("⛔️ You are not authorized to use this command.")
                return

            # Check command format
            if not context.args or len(context.args) != 2:
                await message.answer("Usage: /givecredits <user_id> <amount>")
                return

            try:
                target_user_id = int(context.args[0])
                credit_amount = int(context.args[1])
            except ValueError:
                await message.answer("Invalid user ID or credit amount. Both must be numbers.")
                return

            if credit_amount <= 0:
                await message.answer("Credit amount must be positive.")
                return

            success = await self.data_store.add_credits(target_user_id, credit_amount)
            if success:
                new_balance = await self.data_store.get_user_credits(target_user_id)
                await message.answer(
                    f"✅ Successfully added {credit_amount} credits to user {target_user_id}\n"
                    f"New balance: {new_balance} credits"
                )
                logger.info(f"Admin {user_id} added {credit_amount} credits to user {target_user_id}")
            else:
                await message.answer("❌ Failed to add credits. User may not exist.")

        except Exception as e:
            logger.exception(f"Error in give_credits command: {e}")
            await message.answer(Messages.ERROR_MESSAGE)

    async def credits(self, message: types.Message):
        COMMAND_COUNTER.labels(command='credits').inc()
        with COMMAND_LATENCY.labels(command='credits').time():
            try:
                if not await self._check_rate_limit(message.from_user.id, 'credits'):
                    return

                user_id = message.from_user.id
                credits = await self.data_store.get_user_credits(user_id)

                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Kembali", callback_data="back_to_main")
                await message.answer(
                    f"{Messages.CREDITS_REMAINING.format(credits)}\n\n{Messages.BUY_CREDITS_INFO}",
                    reply_markup=keyboard.as_markup()
                )
                logger.info(f"Credits command processed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in credits command: {str(e)}", exc_info=True)
                await message.answer(Messages.ERROR_MESSAGE)

    async def saved(self, message: types.Message):
        """Handle saved contacts command"""
        try:
            if not await self._check_rate_limit(message.from_user.id, 'saved'):
                return

            user_id = message.from_user.id
            saved_contacts = await self.data_store.get_saved_contacts(user_id)

            if not saved_contacts:
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Kembali", callback_data="back_to_main")
                await message.answer(
                    Messages.NO_SAVED_CONTACTS,
                    reply_markup=keyboard.as_markup()
                )
                return

            await self._show_saved_contacts(message, saved_contacts)
            logger.info(f"Saved contacts shown to user {user_id}")

        except Exception as e:
            logger.error(f"Error in saved command: {e}")
            await message.answer(Messages.ERROR_MESSAGE)