from typing import Dict, List, Optional
import logging
from models import Importer, UserStats
from app import app, db
from sqlalchemy import or_, func, text

class DataStore:
    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name or products"""
        try:
            with app.app_context():
                query = query.lower()
                logging.info(f"Searching with query: '{query}'")

                # Create an SQL expression using array operators
                importers = Importer.query.filter(
                    or_(
                        func.lower(Importer.name).like(f"%{query}%"),
                        # Convert products array to lowercase and check if any element contains the query
                        text("EXISTS (SELECT 1 FROM unnest(products) product WHERE lower(product) LIKE :query)").params(query=f"%{query}%")
                    )
                ).all()

                logging.info(f"Found {len(importers)} results for query '{query}'")

                results = [{
                    'id': imp.id,
                    'name': imp.name,
                    'country': imp.country,
                    'products': imp.products,
                    'contact': imp.contact
                } for imp in importers]

                logging.debug(f"Search results: {results}")
                return results

        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []

    def get_importer(self, importer_id: int) -> Optional[Dict]:
        """Get importer by ID"""
        try:
            with app.app_context():
                importer = Importer.query.get(importer_id)
                if importer:
                    return {
                        'id': importer.id,
                        'name': importer.name,
                        'country': importer.country,
                        'products': importer.products,
                        'contact': importer.contact
                    }
                return None
        except Exception as e:
            logging.error(f"Error getting importer: {str(e)}", exc_info=True)
            return None

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage"""
        try:
            with app.app_context():
                user_stats = UserStats.query.filter_by(user_id=user_id).first()
                if not user_stats:
                    user_stats = UserStats(
                        user_id=user_id,
                        command_counts={},
                        total_commands=0
                    )
                    db.session.add(user_stats)

                user_stats.total_commands += 1
                if command not in user_stats.command_counts:
                    user_stats.command_counts[command] = 0
                user_stats.command_counts[command] += 1

                db.session.commit()
                logging.info(f"Command tracked for user {user_id}: {command}")
        except Exception as e:
            logging.error(f"Error tracking command: {str(e)}", exc_info=True)
            db.session.rollback()

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        try:
            with app.app_context():
                user_stats = UserStats.query.filter_by(user_id=user_id).first()
                if not user_stats:
                    return {'total_commands': 0, 'commands': {}}

                return {
                    'total_commands': user_stats.total_commands,
                    'commands': user_stats.command_counts
                }
        except Exception as e:
            logging.error(f"Error getting user stats: {str(e)}", exc_info=True)
            return {'total_commands': 0, 'commands': {}}