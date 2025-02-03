from typing import Dict, List, Optional
from models import Importer, UserStats
from app import app, db
from sqlalchemy import or_

class DataStore:
    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name or products"""
        with app.app_context():
            query = f"%{query.lower()}%"
            importers = Importer.query.filter(
                or_(
                    Importer.name.ilike(query),
                    Importer.products.any(lambda x: x.ilike(query))
                )
            ).all()

            return [{
                'id': imp.id,
                'name': imp.name,
                'country': imp.country,
                'products': imp.products,
                'contact': imp.contact
            } for imp in importers]

    def get_importer(self, importer_id: int) -> Optional[Dict]:
        """Get importer by ID"""
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

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage"""
        with app.app_context():
            user_stats = UserStats.query.filter_by(user_id=user_id).first()
            if not user_stats:
                user_stats = UserStats(user_id=user_id, command_counts={})
                db.session.add(user_stats)

            user_stats.total_commands += 1
            if command not in user_stats.command_counts:
                user_stats.command_counts[command] = 0
            user_stats.command_counts[command] += 1

            db.session.commit()

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        with app.app_context():
            user_stats = UserStats.query.filter_by(user_id=user_id).first()
            if not user_stats:
                return {'total_commands': 0, 'commands': {}}

            return {
                'total_commands': user_stats.total_commands,
                'commands': user_stats.command_counts
            }