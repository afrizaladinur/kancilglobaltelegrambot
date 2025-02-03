from typing import Dict, List, Optional
import logging
import os
from sqlalchemy import create_engine, text

class DataStore:
    def __init__(self):
        self.engine = create_engine(os.environ.get('DATABASE_URL'))
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

            # Create user_stats table with command_name as VARCHAR
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

            # Create user_credits table
            create_user_credits_sql = """
            CREATE TABLE IF NOT EXISTS user_credits (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                credits INTEGER DEFAULT 3,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            with self.engine.connect() as conn:
                conn.execute(text(create_saved_contacts_sql))
                conn.execute(text(create_user_stats_sql))
                conn.execute(text(create_user_credits_sql))
                conn.commit()
        except Exception as e:
            logging.error(f"Error creating tables: {str(e)}", exc_info=True)

    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name, country, or HS code products"""
        try:
            # Split the query into terms and remove empty strings
            search_terms = [term.strip() for term in query.split() if term.strip()]
            logging.info(f"Starting search with terms: {search_terms}")

            # Build dynamic WHERE clause for each term
            where_conditions = []
            params = {}
            for i, term in enumerate(search_terms):
                param_name = f"term_{i}"
                where_conditions.append(f"""(
                    name ILIKE :{param_name} OR 
                    country ILIKE :{param_name} OR 
                    product ILIKE :{param_name}
                )""")
                params[param_name] = f"%{term}%"

            # Combine conditions with AND
            where_clause = " AND ".join(where_conditions)
            
            search_sql = f"""
            SELECT name, country, phone, website, email_1, email_2, wa_availability,
                   CASE 
                       WHEN product LIKE 'WW %' THEN SUBSTRING(product, 4)
                       ELSE product 
                   END as product
            FROM importers
            WHERE {where_clause}
            ORDER BY 
                CASE WHEN wa_availability = 'Available' THEN 1 ELSE 2 END,
                CASE WHEN email_1 IS NOT NULL OR email_2 IS NOT NULL THEN 1 ELSE 2 END
            LIMIT 5;
            """

            with self.engine.connect() as conn:
                result = conn.execute(text(search_sql), params).fetchall()

                return [
                    {
                        'name': row.name,
                        'country': row.country,
                        'contact': row.phone,
                        'website': row.website,
                        'email': row.email_1 or row.email_2,
                        'wa_available': row.wa_availability == 'Available',
                        'product': row.product
                    }
                    for row in result
                ]
        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []
    
    def use_credit(self, user_id: int) -> bool:
        """Use one credit for the user. Returns True if successful."""
        try:
            use_credit_sql = """
            UPDATE user_credits
            SET credits = credits - 1,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = :user_id AND credits > 0
            RETURNING credits;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text(use_credit_sql),
                        {"user_id": user_id}
                    ).scalar()
                    logging.info(f"Credit used for user {user_id}. Remaining credits: {result}")
                    return result is not None
        except Exception as e:
            logging.error(f"Error using credit: {str(e)}", exc_info=True)
            return False

    def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
            # First check credits
            credits = self.get_user_credits(user_id)
            logging.info(f"Checking credits for user {user_id}. Current credits: {credits}")

            if credits <= 0:
                logging.warning(f"User {user_id} has insufficient credits ({credits}) to save contact")
                return False

            save_sql = """
            INSERT INTO saved_contacts (
                user_id, importer_name, country, phone, email, 
                website, wa_availability
            ) VALUES (
                :user_id, :name, :country, :phone, :email,
                :website, :wa_available
            )
            ON CONFLICT (user_id, importer_name) DO NOTHING;
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
                            "wa_available": importer['wa_available']
                        }
                    )
                    logging.info(f"Contact save attempt for user {user_id}: {result.rowcount} rows affected")
                    return result.rowcount > 0
        except Exception as e:
            logging.error(f"Error saving contact: {str(e)}", exc_info=True)
            return False

    def get_saved_contacts(self, user_id: int) -> List[Dict]:
        """Get saved contacts for a user"""
        try:
            get_saved_sql = """
            SELECT importer_name, country, phone, email, website, 
                   wa_availability, saved_at
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
                        'saved_at': row.saved_at.strftime("%Y-%m-%d %H:%M")
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
    
    def get_user_credits(self, user_id: int) -> int:
        """Get remaining credits for a user"""
        try:
            check_credits_sql = """
            INSERT INTO user_credits (user_id, credits)
            VALUES (:user_id, 3)
            ON CONFLICT (user_id) DO UPDATE 
            SET credits = CASE 
                WHEN user_credits.credits IS NULL THEN 3 
                ELSE user_credits.credits 
            END,
            last_updated = CASE 
                WHEN user_credits.credits IS NULL THEN CURRENT_TIMESTAMP 
                ELSE user_credits.last_updated 
            END
            RETURNING credits;
            """

            with self.engine.connect() as conn:
                result = conn.execute(
                    text(check_credits_sql),
                    {"user_id": user_id}
                ).scalar()
                logging.info(f"User {user_id} credits: {result}")
                return result or 0
        except Exception as e:
            logging.error(f"Error getting user credits: {str(e)}", exc_info=True)
            return 0

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
                    return result is not None
        except Exception as e:
            logging.error(f"Error adding credits: {str(e)}", exc_info=True)
            return False