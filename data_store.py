import logging
import asyncio
from typing import Dict, List, Optional
import os
import asyncpg
from datetime import datetime
from loguru import logger
from prometheus_client import Counter, Histogram

# Prometheus metrics
DB_QUERY_COUNT = Counter('db_queries_total', 'Total database queries')
DB_QUERY_LATENCY = Histogram('db_query_duration_seconds', 'Query latency')

class DataStore:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.pool = None
            self._init_logger()
            self._initialized = True

    def _init_logger(self):
        """Initialize structured logging"""
        logger.add(
            "logs/database_{time}.log",
            rotation="1 day",
            retention="7 days",
            format="{time} {level} {message}"
        )

    async def init_pool(self):
        """Initialize connection pool with enhanced settings and retries"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                if self.pool is not None:
                    # Close existing pool if any
                    await self.pool.close()

                self.pool = await asyncpg.create_pool(
                    os.environ.get('DATABASE_URL'),
                    min_size=5,
                    max_size=20,
                    max_inactive_connection_lifetime=300.0,
                    command_timeout=30.0,
                    statement_cache_size=1000,
                    max_cached_statement_lifetime=300.0
                )

                # Test the connection
                async with self.pool.acquire() as conn:
                    await conn.execute('SELECT 1')

                logger.info("Database pool initialized successfully")
                # Initialize tables after successful connection
                await self._init_tables()
                return True

            except Exception as e:
                logger.error(f"Error initializing pool (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                raise

    async def _init_tables(self):
        """Initialize required tables with improved error handling"""
        create_saved_contacts_sql = """
        CREATE TABLE IF NOT EXISTS saved_contacts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            importer_name VARCHAR(255) NOT NULL,
            country VARCHAR(100),
            phone VARCHAR(50),
            email VARCHAR(255),
            website TEXT,
            wa_availability BOOLEAN,
            hs_code VARCHAR(255),
            product_description TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_saved_contacts_user_id ON saved_contacts(user_id);
        CREATE INDEX IF NOT EXISTS idx_saved_contacts_saved_at ON saved_contacts(saved_at);
        """

        create_user_stats_sql = """
        CREATE TABLE IF NOT EXISTS user_stats (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            command VARCHAR(50) NOT NULL,
            usage_count INTEGER DEFAULT 1,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, command)
        );
        CREATE INDEX IF NOT EXISTS idx_user_stats_user_id ON user_stats(user_id);
        """

        create_credit_orders_sql = """
        CREATE TABLE IF NOT EXISTS credit_orders (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(50) NOT NULL UNIQUE,
            user_id BIGINT NOT NULL,
            credits INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fulfilled_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_credit_orders_user_id ON credit_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_credit_orders_status ON credit_orders(status);
        """

        create_user_credits_sql = """
        DO $$ 
        BEGIN
            CREATE TABLE IF NOT EXISTS user_credits (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                credits NUMERIC(10,1) NOT NULL DEFAULT 3.0 CHECK (credits >= 0),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                has_redeemed_free_credits BOOLEAN DEFAULT FALSE,
                CONSTRAINT positive_credits CHECK (credits >= 0)
            );

            -- Add has_redeemed_free_credits column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='user_credits' 
                AND column_name='has_redeemed_free_credits'
            ) THEN
                ALTER TABLE user_credits 
                ADD COLUMN has_redeemed_free_credits BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
        CREATE INDEX IF NOT EXISTS idx_user_credits_user_id ON user_credits(user_id);
        """

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(create_saved_contacts_sql)
                    await conn.execute(create_user_stats_sql)
                    await conn.execute(create_user_credits_sql)
                    await conn.execute(create_credit_orders_sql)
                    logger.info("Tables initialized successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise

    async def close(self):
        """Close the database pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    @DB_QUERY_LATENCY.time()
    async def get_user_credits(self, user_id: int) -> float:
        """Get user credits with improved error handling"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT credits FROM user_credits WHERE user_id = $1',
                    user_id
                )
                return float(row['credits']) if row else 0.0
        except Exception as e:
            logger.error(f"Error getting user credits: {e}")
            return 0.0

    @DB_QUERY_LATENCY.time()
    async def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save contact with transaction support"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Check credits
                    current_credits = await conn.fetchval(
                        'SELECT credits FROM user_credits WHERE user_id = $1 FOR UPDATE',
                        user_id
                    )

                    credit_cost = self.calculate_credit_cost(importer)
                    if current_credits is None or current_credits < credit_cost:
                        return False

                    # Save contact
                    await conn.execute('''
                        INSERT INTO saved_contacts (
                            user_id, importer_name, country, phone, email,
                            website, wa_availability, hs_code, product_description
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ''', user_id, importer['name'], importer['country'],
                    importer.get('contact', ''), importer.get('email', ''),
                    importer.get('website', ''), importer.get('wa_available', False),
                    importer.get('hs_code', ''), importer.get('product_description', ''))

                    # Update credits
                    await conn.execute(
                        'UPDATE user_credits SET credits = credits - $1 WHERE user_id = $2',
                        credit_cost, user_id
                    )

                    logger.info(f"Contact saved for user {user_id}")
                    return True
        except asyncpg.UniqueViolationError:
            logger.info(f"Contact already saved for user {user_id}")
            return "duplicate"
        except asyncpg.InsufficientPrivilegeError:
            logger.error(f"Database permission error for user {user_id}")
            return "permission"
        except Exception as e:
            logger.error(f"Error saving contact: {e}")
            return "error"

    def calculate_credit_cost(self, importer: Dict) -> float:
        """Calculate credit cost with validation"""
        try:
            has_whatsapp = importer.get('wa_available', False)
            if has_whatsapp:
                return 3.0

            has_website = bool(importer.get('website', '').strip())
            has_email = bool(importer.get('email', '').strip())
            has_phone = bool(importer.get('contact', '').strip())

            if has_website and has_email and has_phone:
                return 2.0
            return 1.0
        except Exception as e:
            logger.error(f"Error calculating credit cost: {e}")
            return 1.0  # Default to minimum cost on error

    @DB_QUERY_LATENCY.time()
    async def get_saved_contacts(self, user_id: int) -> List[Dict]:
        """Get saved contacts for a user"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT importer_name, country, phone, email, website, 
                           wa_availability, saved_at, hs_code, product_description
                    FROM saved_contacts
                    WHERE user_id = $1
                    ORDER BY saved_at DESC;
                """, user_id)
                return [
                    {
                        'name': row['importer_name'],
                        'country': row['country'],
                        'contact': row['phone'],
                        'email': row['email'],
                        'website': row['website'],
                        'wa_available': row['wa_availability'],
                        'saved_at': row['saved_at'].strftime("%Y-%m-%d %H:%M"),
                        'hs_code': row['hs_code'],
                        'product_description': row['product_description']
                    } for row in rows
                ]
        except Exception as e:
            logger.error(f"Error getting saved contacts: {e}")
            return []

    @DB_QUERY_LATENCY.time()
    async def track_user_command(self, user_id: int, command: str):
        """Track user command usage in PostgreSQL"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_stats (user_id, command, usage_count, last_used)
                    VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, command)
                    DO UPDATE SET 
                        usage_count = user_stats.usage_count + 1,
                        last_used = CURRENT_TIMESTAMP;
                """, user_id, command)
            logger.info(f"Command tracked for user {user_id}: {command}")
        except Exception as e:
            logger.error(f"Error tracking command: {str(e)}")

    @DB_QUERY_LATENCY.time()
    async def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics from PostgreSQL"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT command, usage_count
                    FROM user_stats
                    WHERE user_id = $1;
                """, user_id)
                commands = {row['command']: row['usage_count'] for row in rows}
                total = sum(commands.values())
                return {
                    'total_commands': total,
                    'commands': commands
                }
        except Exception as e:
            logger.error(f"Error getting user stats: {str(e)}")
            return {'total_commands': 0, 'commands': {}}

    @DB_QUERY_LATENCY.time()
    async def search_importers(self, query: str) -> List[Dict]:
        """Search importers with improved error handling and retry logic"""
        DB_QUERY_COUNT.inc()
        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                # Clean and prepare search terms
                search_terms = query.strip().lower().split()
                if not search_terms:
                    logger.error("Empty search query")
                    return []

                logger.info(f"Starting search with terms: {search_terms}")

                # Build the search conditions with parameterized queries
                conditions = []
                params = []

                # Convert search terms to include common variations
                product_mappings = {
                    'ikan': ['fish', 'seafood', 'tuna', 'salmon'],
                    'fish': ['ikan', 'seafood', 'tuna', 'salmon'],
                    'kelapa': ['coconut', 'cocos', 'kopra'],
                    'minyak': ['oil', 'virgin', 'vco'],
                    'arang': ['charcoal', 'briket', 'briquette']
                }

                for i, term in enumerate(search_terms):
                    term_conditions = []
                    term_lower = term.lower()

                    # Get mapped terms if available
                    search_terms_for_word = [term_lower]
                    if term_lower in product_mappings:
                        search_terms_for_word.extend(product_mappings[term_lower])

                    # Build conditions for all terms including mappings
                    for search_term in search_terms_for_word:
                        term_conditions.append(
                            f"(LOWER(name) LIKE '%' || ${(i+1)*len(search_terms_for_word) + search_terms_for_word.index(search_term) +1} || '%' OR "
                            f"LOWER(country) LIKE '%' || ${(i+1)*len(search_terms_for_word) + search_terms_for_word.index(search_term) +1} || '%' OR "
                            f"LOWER(role) LIKE '%' || ${(i+1)*len(search_terms_for_word) + search_terms_for_word.index(search_term) +1} || '%' OR "
                            f"LOWER(product) LIKE '%' || ${(i+1)*len(search_terms_for_word) + search_terms_for_word.index(search_term) +1} || '%')"
                        )
                        params.append(search_term)


                    conditions.append("(" + " OR ".join(term_conditions) + ")")

                # Search SQL with ranking and proper indexing
                search_sql = """
                WITH ranked_results AS (
                    SELECT DISTINCT ON (name)
                        name, 
                        country, 
                        phone as contact, 
                        website, 
                        email_1 as email, 
                        wa_availability,
                        product,
                        role as product_description,
                        CASE 
                            WHEN phone IS NOT NULL AND email_1 IS NOT NULL AND website IS NOT NULL THEN 3
                            WHEN (phone IS NOT NULL AND email_1 IS NOT NULL) OR 
                                 (phone IS NOT NULL AND website IS NOT NULL) OR 
                                 (email_1 IS NOT NULL AND website IS NOT NULL) THEN 2
                            ELSE 1
                        END as contact_score
                    FROM importers
                    WHERE (phone IS NOT NULL OR email_1 IS NOT NULL OR website IS NOT NULL)
                    AND ({conditions})
                )
                SELECT * FROM ranked_results 
                ORDER BY contact_score DESC, name ASC
                LIMIT 50;
                """.format(conditions=' AND '.join(conditions))

                async with self.pool.acquire() as conn:
                    try:
                        logger.info(f"Executing search SQL: {search_sql}")
                        logger.info(f"With parameters: {params}")

                        result = await conn.fetch(search_sql, *params)

                        logger.info(f"Search found {len(result)} results for query: '{query}'")

                        formatted_results = []
                        for row in result:
                            try:
                                importer_dict = {
                                    'name': row['name'].strip() if row['name'] else '',
                                    'country': row['country'].strip() if row['country'] else '',
                                    'contact': row['contact'].strip() if row['contact'] else '',
                                    'website': row['website'].strip() if row['website'] else '',
                                    'email': row['email'].strip() if row['email'] else '',
                                    'wa_available': row['wa_availability'] == 'Available',
                                    'hs_code': row['product'].strip() if row['product'] else '',
                                    'product_description': row['product_description'].strip() if row['product_description'] else ''
                                }
                                formatted_results.append(importer_dict)
                            except Exception as e:
                                logger.error(f"Error formatting row: {str(e)}")
                                continue

                        return formatted_results

                    except Exception as e:
                        logger.error(f"Database execution error: {str(e)}")
                        raise

            except Exception as e:
                logger.error(f"Error in search attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return []

        logger.error(f"Search failed after {max_retries} attempts")
        return []

    @DB_QUERY_LATENCY.time()
    async def initialize_user_credits(self, user_id: int, initial_credits: float = 10.0) -> None:
        """Initialize credits for new user with retry mechanism"""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT credits FROM user_credits WHERE user_id = $1 FOR UPDATE", user_id
                )
                if result is None:
                    await conn.execute(
                        """
                        INSERT INTO user_credits (user_id, credits) 
                        VALUES ($1, $2)
                        ON CONFLICT (user_id) DO NOTHING
                        """, user_id, initial_credits
                    )
                    logger.info(f"Initialized new user {user_id} with {initial_credits} credits")
        except Exception as e:
            logger.error(f"Error initializing user credits: {e}")
            raise

    @DB_QUERY_LATENCY.time()
    async def use_credit(self, user_id: int, amount: float) -> bool:
        """Use specified amount of credits for the user. Returns True if successful."""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchval(
                        """
                        WITH credit_update AS (
                            UPDATE user_credits
                            SET credits = ROUND(CAST(credits - $1 AS NUMERIC), 1),
                                last_updated = CURRENT_TIMESTAMP
                            WHERE user_id = $2 AND credits >= $1
                            RETURNING credits
                        )
                        SELECT credits FROM credit_update;
                        """, amount, user_id
                    )
                    if result is not None:
                        logger.info(f"Credit used for user {user_id}. Amount: {amount}, Remaining credits: {result}")
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error using credit: {str(e)}")
            return False

    @DB_QUERY_LATENCY.time()
    async def add_credits(self, user_id: int, amount: int) -> bool:
        """Add credits to user account. Returns True if successful."""
        DB_QUERY_COUNT.inc()
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchval(
                        """
                        INSERT INTO user_credits (user_id, credits)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET 
                            credits = user_credits.credits + $2,
                            last_updated = CURRENT_TIMESTAMP
                        RETURNING credits;
                        """, user_id, amount
                    )
                    logger.info(f"Added {amount} credits for user {user_id}. New total: {result}")
                    return result is not None
        except Exception as e:
            logger.error(f"Error adding credits: {str(e)}")
            return False