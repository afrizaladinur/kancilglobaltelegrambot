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
            create_saved_contacts_sql = """
            CREATE TABLE IF NOT EXISTS saved_contacts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                importer_name VARCHAR(255) NOT NULL,
                country VARCHAR(100),
                phone VARCHAR(50),
                email VARCHAR(255),
                website TEXT,
                wa_availability BOOLEAN,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, importer_name)
            );
            """

            create_user_stats_sql = """
            CREATE TABLE IF NOT EXISTS user_stats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                command VARCHAR(50) NOT NULL,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, command)
            );
            """

            create_user_credits_sql = """
            CREATE TABLE IF NOT EXISTS user_credits (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                credits INTEGER NOT NULL DEFAULT 3 CHECK (credits >= 0),
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

    def get_user_credits(self, user_id: int) -> int:
        """Get remaining credits for a user"""
        try:
            with self.engine.connect() as conn:
                with conn.begin():
                    # Try to insert a new user with default credits
                    insert_sql = """
                    INSERT INTO user_credits (user_id, credits)
                    VALUES (:user_id, 3)
                    ON CONFLICT (user_id) DO 
                    UPDATE SET credits = 
                        CASE 
                            WHEN user_credits.credits = 0 THEN 3
                            ELSE user_credits.credits
                        END,
                        last_updated = 
                        CASE 
                            WHEN user_credits.credits = 0 THEN CURRENT_TIMESTAMP
                            ELSE user_credits.last_updated
                        END
                    RETURNING credits;
                    """

                    result = conn.execute(
                        text(insert_sql),
                        {"user_id": user_id}
                    ).scalar()

                    logging.info(f"Credits for user {user_id}: {result}")
                    return result or 3

        except Exception as e:
            logging.error(f"Error getting user credits: {str(e)}", exc_info=True)
            return 3  # Return 3 credits as fallback
    
    def calculate_credit_cost(self, importer: Dict) -> float:
        """Calculate credit cost based on contact information availability"""
        try:
            has_whatsapp = importer.get('wa_available', False)
            has_website = bool(importer.get('website'))
            has_email = bool(importer.get('email'))
            has_phone = bool(importer.get('contact'))

            logging.info(f"Calculating credit cost - WhatsApp: {has_whatsapp}, "
                      f"Website: {has_website}, Email: {has_email}, Phone: {has_phone}")

            # All contact methods including WhatsApp (2 credits)
            if has_whatsapp and has_website and has_email and has_phone:
                return 2.0
            # All contact methods except WhatsApp (1 credit)
            elif not has_whatsapp and has_website and has_email and has_phone:
                return 1.0
            # Missing some contact methods and no WhatsApp (0.5 credits)
            else:
                return 0.5
        except Exception as e:
            logging.error(f"Error calculating credit cost: {str(e)}", exc_info=True)
            return 0.5  # Default to minimum cost if error occurs

    def use_credit(self, user_id: int, amount: float) -> bool:
        """Use specified amount of credits for the user. Returns True if successful."""
        try:
            use_credit_sql = """
            UPDATE user_credits
            SET credits = CASE 
                WHEN credits >= :amount THEN credits - :amount
                ELSE credits
            END,
            last_updated = CURRENT_TIMESTAMP
            WHERE user_id = :user_id AND credits >= :amount
            RETURNING credits;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text(use_credit_sql),
                        {"user_id": user_id, "amount": amount}
                    ).scalar()
                    logging.info(f"Credit used for user {user_id}. Amount: {amount}, Remaining credits: {result}")
                    return result is not None
        except Exception as e:
            logging.error(f"Error using credit: {str(e)}", exc_info=True)
            return False

    def add_credits(self, user_id: int, amount: int) -> bool:
        """Add credits to user account. Returns True if successful."""
        try:
            add_credits_sql = """
            UPDATE user_credits
            SET credits = credits + :amount,
            last_updated = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
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
        """Search importers by name, country, or product"""
        try:
            # Clean and prepare search terms
            search_term = query.strip().lower()
            logging.info(f"Starting search with term: '{search_term}'")

            search_sql = """
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
                    CASE 
                        WHEN LOWER(country) LIKE :search_term THEN 0
                        WHEN LOWER(name) LIKE :search_term THEN 1
                        ELSE 2 
                    END as match_type
                FROM importers
                WHERE 
                    LOWER(name) LIKE :search_term OR 
                    LOWER(country) LIKE :search_term OR 
                    LOWER(product) LIKE :search_term OR
                    LOWER(role) LIKE :search_term
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
            ORDER BY match_type, country, name
            LIMIT 10;
            """

            with self.engine.connect() as conn:
                # Log the actual SQL and parameters being used
                logging.info(f"Executing search with parameters: {{'search_term': '%{search_term}%'}}")

                result = conn.execute(
                    text(search_sql), 
                    {"search_term": f"%{search_term}%"}
                ).fetchall()

                logging.info(f"Search found {len(result)} results for query: '{query}'")

                # Convert result to list of dicts with proper boolean conversion for wa_available
                formatted_results = []
                for row in result:
                    importer_dict = {
                        'name': row.name,
                        'country': row.country,
                        'contact': row.contact,
                        'website': row.website or '',
                        'email': row.email or '',
                        'wa_available': row.wa_available,  # Already a boolean from the SQL CASE
                        'hs_code': row.hs_code,  # Pass the full product field
                        'product_description': row.product_description or ''
                    }
                    logging.debug(f"Formatted result: {importer_dict}")
                    formatted_results.append(importer_dict)

                return formatted_results

        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []
    
    def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
            # Calculate credit cost for this contact
            credit_cost = self.calculate_credit_cost(importer)
            logging.info(f"Calculated credit cost for contact: {credit_cost}")

            # First check credits
            credits = self.get_user_credits(user_id)
            logging.info(f"Checking credits for user {user_id}. Current credits: {credits}")

            if credits < credit_cost:
                logging.warning(f"User {user_id} has insufficient credits ({credits}) to save contact (cost: {credit_cost})")
                return False

            save_sql = """
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
            with self.engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text(save_sql),
                        {
                            "user_id": user_id,
                            "name": importer['name'],
                            "country": importer['country'],
                            "phone": importer['contact'],
                            "email": importer['email'],
                            "website": importer['website'],
                            "wa_available": importer['wa_available'],
                            "hs_code": importer.get('product', ''),
                            "product_description": importer.get('product_description', '')
                        }
                    )

                    if result.rowcount > 0:
                        # Only use credits if the contact was actually saved
                        if self.use_credit(user_id, credit_cost):
                            logging.info(f"Successfully saved contact and used {credit_cost} credits")
                            return True
                        else:
                            # Rollback if we couldn't use the credits
                            conn.rollback()
                            logging.error("Failed to use credits, rolling back contact save")
                            return False

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
            INSERT INTO user_stats (user_id, command, usage_count)
            VALUES (:user_id, :command, 1)
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