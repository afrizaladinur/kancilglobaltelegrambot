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
            DROP TABLE IF EXISTS user_stats;
            CREATE TABLE user_stats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                command VARCHAR(50) NOT NULL,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, command)
            );
            """
            with self.engine.connect() as conn:
                conn.execute(text(create_saved_contacts_sql))
                conn.execute(text(create_user_stats_sql))
                conn.commit()
        except Exception as e:
            logging.error(f"Error creating tables: {str(e)}", exc_info=True)

    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name, country, or products"""
        try:
            logging.info(f"Starting search with query: '{query}'")
            search_sql = """
            SELECT name, country, phone, website, email_1, email_2, wa_availability
            FROM importers
            WHERE name ILIKE :query 
               OR country ILIKE :query
            ORDER BY 
                CASE WHEN wa_availability = 'Available' THEN 1 ELSE 2 END,
                CASE WHEN email_1 IS NOT NULL OR email_2 IS NOT NULL THEN 1 ELSE 2 END
            LIMIT 5;
            """
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(search_sql), 
                    {"query": f"%{query}%"}
                ).fetchall()

                return [
                    {
                        'name': row.name,
                        'country': row.country,
                        'contact': row.phone,
                        'website': row.website,
                        'email': row.email_1 or row.email_2,
                        'wa_available': row.wa_availability == 'Available'
                    }
                    for row in result
                ]
        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []

    def save_contact(self, user_id: int, importer: Dict) -> bool:
        """Save an importer contact for a user"""
        try:
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