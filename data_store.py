import logging
import time
from typing import Dict, List, Optional
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

class DataStore:
    def __init__(self):
        self.engine = create_engine(
            os.environ.get('DATABASE_URL'),
            poolclass=QueuePool,
            pool_size=10,           # Increased pool size
            max_overflow=20,        # Allow more overflow connections
            pool_timeout=30,        # Longer timeout
            pool_pre_ping=True,     # Enable connection health checks
            pool_recycle=300,       # Recycle connections every 5 minutes
            connect_args={
                "sslmode": "require",
                "connect_timeout": 30,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            }
        )
        self._init_tables()
        logging.info("DataStore initialized with enhanced PostgreSQL connection pooling")

    def _init_tables(self):
        """Initialize required tables with improved error handling"""
        try:
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

            with self.engine.connect() as conn:
                conn.execute(text(create_saved_contacts_sql))
                conn.execute(text(create_user_stats_sql))
                conn.execute(text(create_user_credits_sql))
                conn.execute(text(create_credit_orders_sql))
                conn.commit()
                logging.info("Tables initialized successfully with optimized indexes")
        except Exception as e:
            logging.error(f"Error creating tables: {str(e)}", exc_info=True)
            raise

    def get_user_credits(self, user_id: int) -> float:
        """Get user's remaining credits with retries"""
        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text(
                        "SELECT credits FROM user_credits WHERE user_id = :user_id"
                    ), {"user_id": user_id}).first()
                    return float(result[0]) if result else 0.0
            except Exception as e:
                logging.error(f"Error getting user credits (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return 0.0

    def initialize_user_credits(self, user_id: int, initial_credits: float = 10.0) -> None:
        """Initialize credits for new user with retry mechanism"""
        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                with self.engine.begin() as conn:
                    # First check if user already has credits
                    result = conn.execute(text(
                        "SELECT credits FROM user_credits WHERE user_id = :user_id FOR UPDATE"
                    ), {"user_id": user_id}).first()

                    if result is None:
                        # Only initialize if user doesn't exist
                        conn.execute(text("""
                            INSERT INTO user_credits (user_id, credits) 
                            VALUES (:user_id, :credits)
                            ON CONFLICT (user_id) DO NOTHING
                        """), {"user_id": user_id, "credits": initial_credits})
                        logging.info(f"Initialized new user {user_id} with {initial_credits} credits")
                return
            except Exception as e:
                logging.error(f"Error initializing user credits (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise

    def calculate_credit_cost(self, importer: Dict) -> float:
        """Calculate credit cost based on contact information availability"""
        try:
            has_whatsapp = importer.get('wa_available', False)
            # WhatsApp available = 3 credits
            if has_whatsapp:
                return 3.0
            # Check if has other contact methods
            has_website = bool(importer.get('website', '').strip())
            has_email = bool(importer.get('email', '').strip())
            has_phone = bool(importer.get('contact', '').strip())

            # Complete contact info without WA = 2 credits
            if has_website and has_email and has_phone:
                return 2.0
            # Partial contact info = 1 credit
            return 1.0
        except Exception as e:
            logging.error(f"Error calculating credit cost: {str(e)}", exc_info=True)
            return 0.5  # Default to minimum cost if error occurs

    def use_credit(self, user_id: int, amount: float) -> bool:
        """Use specified amount of credits for the user. Returns True if successful."""
        try:
            use_credit_sql = """
            WITH credit_update AS (
                UPDATE user_credits
                SET credits = ROUND(CAST(credits - :amount AS NUMERIC), 1),
                    last_updated = CURRENT_TIMESTAMP
                WHERE user_id = :user_id AND credits >= :amount
                RETURNING credits
            )
            SELECT credits FROM credit_update;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text(use_credit_sql),
                        {"user_id": user_id, "amount": float(amount)}
                    ).scalar()
                    if result is not None:
                        logging.info(f"Credit used for user {user_id}. Amount: {amount}, Remaining credits: {result}")
                        return True
                    conn.rollback()
                    return False
        except Exception as e:
            logging.error(f"Error using credit: {str(e)}", exc_info=True)
            return False

    def add_credits(self, user_id: int, amount: int) -> bool:
        """Add credits to user account. Returns True if successful."""
        try:
            add_credits_sql = """
            INSERT INTO user_credits (user_id, credits)
            VALUES (:user_id, :amount)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                credits = user_credits.credits + :amount,
                last_updated = CURRENT_TIMESTAMP
            RETURNING credits;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text(add_credits_sql),
                        {"user_id": user_id, "amount": amount}
                    ).scalar()
                    logging.info(f"Added {amount} credits for user {user_id}. New total: {result}")
                    return result is not None
        except Exception as e:
            logging.error(f"Error adding credits: {str(e)}", exc_info=True)
            return False

    def search_importers(self, query: str) -> List[Dict]:
        """Search importers with improved error handling and retry logic"""
        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                # Clean and prepare search terms
                search_terms = query.strip().lower().split()
                if not search_terms:
                    logging.error("Empty search query")
                    return []

                logging.info(f"Starting search with terms: {search_terms}")

                # Build the search conditions with parameterized queries
                conditions = []
                params = {}

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
                        param_key = f'term_{i}_{search_term}'
                        term_conditions.append(
                            f"(LOWER(name) LIKE :{param_key} OR "
                            f"LOWER(country) LIKE :{param_key} OR "
                            f"LOWER(role) LIKE :{param_key} OR "
                            f"LOWER(product) LIKE :{param_key})"
                        )
                        params[param_key] = f'%{search_term}%'

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

                with self.engine.connect() as conn:
                    try:
                        logging.info(f"Executing search SQL: {search_sql}")
                        logging.info(f"With parameters: {params}")

                        result = conn.execute(
                            text(search_sql), 
                            params
                        ).fetchall()

                        logging.info(f"Search found {len(result)} results for query: '{query}'")

                        formatted_results = []
                        for row in result:
                            try:
                                importer_dict = {
                                    'name': row.name.strip() if row.name else '',
                                    'country': row.country.strip() if row.country else '',
                                    'contact': row.contact.strip() if row.contact else '',
                                    'website': row.website.strip() if row.website else '',
                                    'email': row.email.strip() if row.email else '',
                                    'wa_available': row.wa_availability == 'Available',
                                    'hs_code': row.product.strip() if row.product else '',
                                    'product_description': row.product_description.strip() if row.product_description else ''
                                }
                                formatted_results.append(importer_dict)
                            except Exception as e:
                                logging.error(f"Error formatting row: {str(e)}", exc_info=True)
                                continue

                        return formatted_results

                    except Exception as e:
                        logging.error(f"Database execution error: {str(e)}", exc_info=True)
                        raise

            except Exception as e:
                logging.error(f"Error in search attempt {attempt + 1}: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return []

        logging.error(f"Search failed after {max_retries} attempts")
        return []

    async def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
            logging.info(f"Starting save contact process for user {user_id}")
            logging.info(f"Importer data to save: {importer}")
            credit_cost = self.calculate_credit_cost(importer)
            logging.info(f"Calculated credit cost for contact: {credit_cost}")

            with self.engine.begin() as conn:
                try:
                    # Check credits
                    current_credits = conn.execute(
                        text("SELECT credits FROM user_credits WHERE user_id = :user_id FOR UPDATE"),
                        {"user_id": user_id}
                    ).scalar()

                    if current_credits is None or current_credits < credit_cost:
                        logging.error(f"Insufficient credits. Current: {current_credits}, Required: {credit_cost}")
                        return False

                    # Check if contact already exists
                    existing = conn.execute(
                        text("""
                        SELECT id FROM saved_contacts 
                        WHERE user_id = :user_id AND importer_name = :name
                        """),
                        {"user_id": user_id, "name": importer['name']}
                    ).first()

                    if existing:
                        logging.warning(f"Contact {importer['name']} already saved by user {user_id}")
                        return False

                    # Insert contact if not exists
                    contact_result = conn.execute(
                        text("""
                        INSERT INTO saved_contacts (
                            user_id, importer_name, country, phone, email, 
                            website, wa_availability, hs_code, product_description
                        ) VALUES (
                            :user_id, :name, :country, :phone, :email,
                            :website, :wa_available, :hs_code, :product_description
                        )
                        RETURNING id;
                        """),
                        {
                            "user_id": user_id,
                            "name": importer['name'],
                            "country": importer['country'],
                            "phone": importer.get('contact', ''),
                            "email": importer.get('email', ''),
                            "website": importer.get('website', ''),
                            "wa_available": importer.get('wa_available', False),
                            "hs_code": importer.get('hs_code', ''),
                            "product_description": importer.get('product_description', '')
                        }
                    )

                    if contact_result.rowcount == 0:
                        logging.error("Failed to insert contact")
                        return False

                    # Deduct credits
                    credit_result = conn.execute(
                        text("""
                        UPDATE user_credits 
                        SET credits = ROUND(CAST(credits - :credit_cost AS NUMERIC), 1),
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_id = :user_id 
                        RETURNING credits;
                        """),
                        {"user_id": user_id, "credit_cost": float(credit_cost)}
                    )

                    new_credits = credit_result.scalar()
                    if new_credits is None:
                        logging.error("Failed to update credits")
                        return False

                    logging.info(f"Successfully saved contact and deducted {credit_cost} credits. New balance: {new_credits}")
                    return True

                except Exception as tx_error:
                    logging.error(f"Transaction error: {str(tx_error)}", exc_info=True)
                    return False

        except Exception as e:
            logging.error(f"Error in save_contact: {str(e)}", exc_info=True)
            return False

    def get_saved_contacts(self, user_id: int) -> List[Dict]:
        """Get saved contacts for a user"""
        try:
            get_saved_sql = """
            SELECT importer_name, country, phone, email, website, 
                   wa_availability, saved_at, hs_code, product_description
            FROM saved_contacts
            WHERE user_id = :user_id
            ORDER BY saved_at DESC;
            """
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(get_saved_sql),
                    {"user_id": user_id}
                ).fetchall()

                return [
                    {
                        'name': row.importer_name,
                        'country': row.country,
                        'contact': row.phone,
                        'email': row.email,
                        'website': row.website,
                        'wa_available': row.wa_availability,
                        'saved_at': row.saved_at.strftime("%Y-%m-%d %H:%M"),
                        'hs_code': row.hs_code,
                        'product_description': row.product_description
                    }
                    for row in result
                ]
        except Exception as e:
            logging.error(f"Error getting saved contacts: {str(e)}", exc_info=True)
            return []

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage in PostgreSQL"""
        try:
            update_sql = """
            INSERT INTO user_stats (user_id, command, usage_count, last_used)
            VALUES (:user_id, :command, 1, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, command)
            DO UPDATE SET 
                usage_count = user_stats.usage_count + 1,
                last_used = CURRENT_TIMESTAMP;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    conn.execute(text(update_sql), {"user_id": user_id, "command": command})

            logging.info(f"Command tracked for user {user_id}: {command}")
        except Exception as e:
            logging.error(f"Error tracking command: {str(e)}", exc_info=True)

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics from PostgreSQL"""
        try:
            stats_sql = """
            SELECT command, usage_count
            FROM user_stats
            WHERE user_id = :user_id;
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(stats_sql), {"user_id": user_id}).fetchall()
                commands = {row.command: row.usage_count for row in result}
                total = sum(commands.values())
                return {
                    'total_commands': total,
                    'commands': commands
                }
        except Exception as e:
            logging.error(f"Error getting user stats: {str(e)}", exc_info=True)
            return {'total_commands': 0, 'commands': {}}