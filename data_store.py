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
                "sslmode": "require",
                "connect_timeout": 30
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
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            """

            with self.engine.connect() as conn:
                conn.execute(text(create_saved_contacts_sql))
                conn.execute(text(create_user_stats_sql))
                conn.execute(text(create_user_credits_sql))
                conn.execute(text(create_credit_orders_sql))
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

    def initialize_user_credits(self, user_id: int, initial_credits: float = 10.0) -> None:
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
        """Search importers by query"""
        try:
            with self.engine.connect() as conn:
                results = conn.execute(text("""
                    SELECT * FROM importers 
                    WHERE LOWER(product) LIKE :query
                    OR LOWER(name) LIKE :query
                    OR LOWER(country) LIKE :query
                    LIMIT 100
                """), {
                    "query": f"%{query.lower()}%"
                }).fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}")
            return []

    def search_importers_by_role(self, query: str, role: str) -> List[Dict]:
        """Search importers by query and role"""
        try:
            # Remove any role prefix from search term
            clean_query = query.replace('Exporter ', '').replace('Importer ', '')

            with self.engine.connect() as conn:
                results = conn.execute(text("""
                    SELECT * FROM importers 
                    WHERE LOWER(product) LIKE :query
                    AND role = :role
                    LIMIT 100
                """), {
                    "query": f"%{clean_query.lower()}%",
                    "role": role
                }).fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logging.error(f"Error searching importers by role: {str(e)}")
            return []

    async def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
            logging.info(f"Starting save contact process for user {user_id}")
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
                            "phone": importer['contact'],
                            "email": importer['email'],
                            "website": importer['website'],
                            "wa_available": importer['wa_available'],
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

    def get_contacts_by_category(self, category_type: str, specific_category: str = None) -> tuple[List[Dict], int]:
        """Get contacts and count for a specific category"""
        try:
            # Base SQL query for counting
            count_sql = """
            SELECT COUNT(*) 
            FROM importers 
            WHERE 1=1
            """

            # Base SQL query for fetching contacts
            contact_sql = """
            SELECT name, country, phone as contact, website, 
                   email as email, wa_available as wa_availability, product,
                   role as product_description
            FROM importers 
            WHERE 1=1
            """

            params = {}

            # Add role filter based on category type
            if category_type == "supplier":
                count_sql += " AND role = 'Exporter'"
                contact_sql += " AND role = 'Exporter'"

                # Add specific category filter for suppliers if provided
                if specific_category:
                    if specific_category == 'marine':
                        product_pattern = '%(0301|0302|0303|0304|0305|seafood|fish|marine)%'
                    elif specific_category == 'agriculture':
                        product_pattern = '%(0901|1513|agriculture|farming|crops)%'
                    elif specific_category == 'spices':
                        product_pattern = '%(0904|0908|spices|herbs)%'
                    elif specific_category == 'nuts':
                        product_pattern = '%(0801|0802|nuts|peanuts|cashews)%'
                    elif specific_category == 'industrial':
                        product_pattern = '%(44029010|industrial|manufacturing)%'
                    else:
                        product_pattern = f'%{specific_category}%'

                    count_sql += " AND (LOWER(product) SIMILAR TO :pattern OR LOWER(product_description) SIMILAR TO :pattern)"
                    contact_sql += " AND (LOWER(product) SIMILAR TO :pattern OR LOWER(product_description) SIMILAR TO :pattern)"
                    params['pattern'] = product_pattern

            elif category_type == "buyer":
                count_sql += " AND role = 'Importer'"
                contact_sql += " AND role = 'Importer'"

                if specific_category:
                    # Handle ID/WW prefix for buyers
                    category_parts = specific_category.split("_", 1)
                    if len(category_parts) == 2:
                        location, product = category_parts
                        count_sql += " AND country_type = :country_type"
                        contact_sql += " AND country_type = :country_type"

                        # Add product category filter
                        if product == 'marine':
                            product_pattern = '%(0301|0302|0303|0304|0305|seafood|fish|marine)%'
                        elif product == 'agriculture':
                            product_pattern = '%(0901|1513|agriculture|farming|crops)%'
                        elif product == 'spices':
                            product_pattern = '%(0904|0908|spices|herbs)%'
                        else:
                            product_pattern = f'%{product}%'

                        count_sql += " AND (LOWER(product) SIMILAR TO :pattern OR LOWER(product_description) SIMILAR TO :pattern)"
                        contact_sql += " AND (LOWER(product) SIMILAR TO :pattern OR LOWER(product_description) SIMILAR TO :pattern)"

                        params['country_type'] = location
                        params['pattern'] = product_pattern

            # Add ordering and limit for contact query
            contact_sql += " ORDER BY RANDOM() LIMIT 10"

            logging.info(f"Executing category query with params: {params}")

            with self.engine.connect() as conn:
                # Get total count
                total_count = conn.execute(text(count_sql), params).scalar() or 0
                logging.info(f"Found {total_count} total contacts for category")

                # Get contacts
                results = conn.execute(text(contact_sql), params).fetchall()
                contacts = []
                for row in results:
                    contact = {
                        'name': row.name,
                        'country': row.country,
                        'contact': row.contact,
                        'website': row.website,
                        'email': row.email,
                        'wa_available': row.wa_availability,
                        'product': row.product,
                        'product_description': row.product_description
                    }
                    contacts.append(contact)

                logging.info(f"Returning {len(contacts)} contacts")
                return contacts, total_count

        except Exception as e:
            logging.error(f"Error in get_contacts_by_category: {str(e)}", exc_info=True)
            return [], 0
    
    def search_importers_by_pattern(self, pattern: str, page: int = 0, per_page: int = 2) -> tuple[List[Dict], int]:
        """Search importers by specific pattern (e.g., 'ID 1511')"""
        try:
            offset = page * per_page

            # Extract the search type and value
            pattern_parts = pattern.split(' ')
            if len(pattern_parts) != 2:
                return [], 0

            search_type, search_value = pattern_parts

            # Build the query based on the search type
            base_query = """
                SELECT * FROM importers 
                WHERE 1=1
            """

            if search_type == 'ID':
                base_query += " AND country_type = :search_value"
            elif search_type == 'WW':
                base_query += " AND country_type != 'ID'"

            # Count total results
            count_query = f"SELECT COUNT(*) FROM ({base_query}) as count_query"

            # Add pagination to the main query
            main_query = base_query + """
                ORDER BY name
                LIMIT :limit OFFSET :offset
            """

            with self.engine.connect() as conn:
                # Get total count
                total_count = conn.execute(
                    text(count_query),
                    {"search_value": search_value}
                ).scalar() or 0

                # Get paginated results
                results = conn.execute(
                    text(main_query),
                    {
                        "search_value": search_value,
                        "limit": per_page,
                        "offset": offset
                    }
                ).fetchall()

                # Convert to list of dicts and censor sensitive data
                contacts = []
                for row in results:
                    contact = dict(row)
                    # Censor sensitive data
                    if 'email' in contact:
                        email = contact['email']
                        contact['email'] = f"{email[:3]}...@{email.split('@')[1]}" if '@' in email else "***@***.com"
                    if 'contact' in contact:
                        phone = contact['contact']
                        contact['contact'] = f"{phone[:4]}..." if phone else "***"
                    contacts.append(contact)

                logging.info(f"Found {total_count} results for pattern {pattern}, returning page {page + 1}")
                return contacts, total_count

        except Exception as e:
            logging.error(f"Error searching importers by pattern: {str(e)}", exc_info=True)
            return [], 0