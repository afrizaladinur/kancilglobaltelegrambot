import logging
from typing import Dict, List, Optional
import os
from sqlalchemy import create_engine, text

class DataStore:
    def __init__(self):
        self.engine = create_engine(
            os.environ.get('DATABASE_URL'),
            pool_pre_ping=True,  # Enable connection health checks
            pool_recycle=300,    # Recycle connections every 5 minutes
            connect_args={
                "sslmode": "require"  # Enforce SSL
            }
        )
        self._init_tables()
        logging.info("DataStore initialized with PostgreSQL")

    def _init_tables(self):
        """Initialize required tables"""
        try:
            # Don't drop tables on init
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
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, importer_name)
            );
            """

            create_user_stats_sql = """
            DROP TABLE IF EXISTS user_stats;
            CREATE TABLE IF NOT EXISTS user_stats (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                command VARCHAR(50) NOT NULL,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, command)
            );
            """

            create_user_credits_sql = """
            CREATE TABLE IF NOT EXISTS user_credits (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                credits NUMERIC(10,1) NOT NULL DEFAULT 3.0 CHECK (credits >= 0),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT positive_credits CHECK (credits >= 0)
            );
            """

            with self.engine.connect() as conn:
                conn.execute(text(create_saved_contacts_sql))
                conn.execute(text(create_user_stats_sql))
                conn.execute(text(create_user_credits_sql))
                conn.commit()
                logging.info("Tables initialized successfully")
        except Exception as e:
            logging.error(f"Error creating tables: {str(e)}", exc_info=True)

    def get_user_credits(self, user_id: int) -> float:
        """Get user's remaining credits"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT credits FROM user_credits WHERE user_id = :user_id"
                ), {"user_id": user_id}).first()
                return result[0] if result else 0.0
        except Exception as e:
            logging.error(f"Error getting user credits: {str(e)}")
            return None

    def initialize_user_credits(self, user_id: int, initial_credits: float = 3.0) -> None:
        """Initialize credits for new user"""
        try:
            with self.engine.begin() as conn:
                # First check if user already has credits
                result = conn.execute(text(
                    "SELECT credits FROM user_credits WHERE user_id = :user_id"
                ), {"user_id": user_id}).first()

                if result is None:
                    # Only initialize if user doesn't exist
                    conn.execute(text("""
                        INSERT INTO user_credits (user_id, credits) 
                        VALUES (:user_id, :credits)
                    """), {"user_id": user_id, "credits": initial_credits})
                    logging.info(f"Initialized new user {user_id} with {initial_credits} credits")
        except Exception as e:
            logging.error(f"Error initializing user credits: {str(e)}")

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
        """Search importers by name, country, product/HS code"""
        try:
            # Clean and prepare search terms
            terms = query.strip().lower().split()
            if not terms:
                logging.error("Empty search query")
                return []

            logging.info(f"Starting search with terms: {terms}")

            # Build the search conditions
            conditions = []
            params = {}

            for i, term in enumerate(terms):
                param_name = f"term_{i}"
                # Check if term looks like an HS code (contains digits)
                if any(c.isdigit() for c in term):
                    conditions.append(f"LOWER(product) LIKE :{param_name}")
                else:
                    conditions.append(f"(LOWER(name) LIKE :{param_name} OR LOWER(country) LIKE :{param_name})")
                params[param_name] = f"%{term}%"

            # Default ranking based on first term
            rank_case = f"""
                CASE 
                    WHEN LOWER(country) LIKE :term_0 THEN 0
                    WHEN LOWER(name) LIKE :term_0 THEN 1
                    ELSE 2 
                END
            """

            search_sql = f"""
            WITH ranked_results AS (
                SELECT 
                    name, 
                    country, 
                    phone as contact, 
                    website, 
                    email_1 as email, 
                    wa_availability,
                    product,
                    role as product_description,
                    {rank_case} as match_type
                FROM importers
                WHERE {' AND '.join(conditions)}
            )
            SELECT 
                name, country, contact, website, email,
                CASE 
                    WHEN wa_availability = 'Available' THEN true
                    ELSE false
                END as wa_available,
                product as hs_code,
                product_description
            FROM ranked_results
            ORDER BY RANDOM()
            LIMIT 10;
            """

            with self.engine.connect() as conn:
                try:
                    # Log the actual SQL query for debugging
                    logging.info(f"Executing search SQL: {search_sql}")
                    logging.info(f"With parameters: {params}")

                    result = conn.execute(
                        text(search_sql), 
                        params
                    ).fetchall()

                    logging.info(f"Search found {len(result)} results for query: '{query}'")

                    # Convert result to list of dicts
                    formatted_results = []
                    for row in result:
                        importer_dict = {
                            'name': row.name,
                            'country': row.country,
                            'contact': row.contact,
                            'website': row.website or '',
                            'email': row.email or '',
                            'wa_available': row.wa_available,
                            'hs_code': row.hs_code,
                            'product_description': row.product_description or ''
                        }
                        logging.debug(f"Formatted result: {importer_dict}")
                        formatted_results.append(importer_dict)

                    return formatted_results

                except Exception as e:
                    logging.error(f"Database execution error: {str(e)}", exc_info=True)
                    conn.rollback()
                    raise

        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []

    def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
            logging.info(f"Attempting to save contact for user {user_id}")
            credit_cost = self.calculate_credit_cost(importer)
            logging.info(f"Calculated credit cost for contact: {credit_cost}")

            # Use a single transaction for both operations
            with self.engine.begin() as conn:
                # First check if we have enough credits
                check_credits_sql = """
                SELECT credits FROM user_credits 
                WHERE user_id = :user_id AND credits >= :credit_cost
                FOR UPDATE;
                """
                credits = conn.execute(
                    text(check_credits_sql),
                    {"user_id": user_id, "credit_cost": credit_cost}
                ).scalar()

                if credits is None:
                    logging.error("Insufficient credits")
                    return False

                # Save contact first
                save_contact_sql = """
                INSERT INTO saved_contacts (
                    user_id, importer_name, country, phone, email, 
                    website, wa_availability, hs_code, product_description
                ) VALUES (
                    :user_id, :name, :country, :phone, :email,
                    :website, :wa_available, :hs_code, :product_description
                )
                ON CONFLICT (user_id, importer_name) DO NOTHING
                RETURNING id;
                """
                result = conn.execute(
                    text(save_contact_sql),
                    {
                        "user_id": user_id,
                        "name": importer['name'],
                        "country": importer['country'],
                        "phone": importer['contact'],
                        "email": importer['email'],
                        "website": importer['website'],
                        "wa_available": importer['wa_available'],
                        "hs_code": importer.get('hs_code', ''),
                        "product_description": importer.get('product_description', '')
                    }
                )

                if result.rowcount > 0:
                    # Deduct credits in the same transaction
                    update_credits_sql = """
                    UPDATE user_credits 
                    SET credits = CAST(credits - :credit_cost AS NUMERIC(10,1)),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                    """
                    conn.execute(
                        text(update_credits_sql),
                        {"user_id": user_id, "credit_cost": credit_cost}
                    )
                    logging.info(f"Successfully saved contact and deducted {credit_cost} credits")
                    return True

                return False
        except Exception as e:
            logging.error(f"Error saving contact: {str(e)}", exc_info=True)
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