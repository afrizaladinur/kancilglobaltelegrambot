from typing import Dict, List, Optional
import logging
import os
from sqlalchemy import create_engine, text

class DataStore:
    def __init__(self):
        self.engine = create_engine(os.environ.get('DATABASE_URL'))
        logging.info("DataStore initialized with PostgreSQL")

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

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage in PostgreSQL"""
        try:
            # First, ensure the user_stats table exists
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS user_stats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                command VARCHAR(50) NOT NULL,
                count INTEGER DEFAULT 1,
                UNIQUE(user_id, command)
            );
            """
            update_sql = """
            INSERT INTO user_stats (user_id, command, count)
            VALUES (:user_id, :command, 1)
            ON CONFLICT (user_id, command)
            DO UPDATE SET count = user_stats.count + 1;
            """

            with self.engine.connect() as conn:
                with conn.begin():
                    conn.execute(text(create_table_sql))
                    conn.execute(text(update_sql), {"user_id": user_id, "command": command})

            logging.info(f"Command tracked for user {user_id}: {command}")
        except Exception as e:
            logging.error(f"Error tracking command: {str(e)}", exc_info=True)

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics from PostgreSQL"""
        try:
            stats_sql = """
            SELECT command, count
            FROM user_stats
            WHERE user_id = :user_id;
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(stats_sql), {"user_id": user_id}).fetchall()
                commands = {row.command: row.count for row in result}
                total = sum(commands.values())
                return {
                    'total_commands': total,
                    'commands': commands
                }
        except Exception as e:
            logging.error(f"Error getting user stats: {str(e)}", exc_info=True)
            return {'total_commands': 0, 'commands': {}}