from typing import Dict, List, Optional
from db import MongoDB

class DataStore:
    def __init__(self):
        self.db = MongoDB.get_instance().get_database()
        self._user_stats = {}  # Keep this in memory for simplicity

    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name or products"""
        query = query.lower()
        return list(self.db.importers.find({
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'products': {'$regex': query, '$options': 'i'}}
            ]
        }))

    def get_importer(self, importer_id: int) -> Optional[Dict]:
        """Get importer by ID"""
        return self.db.importers.find_one({'id': importer_id})

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage"""
        if user_id not in self._user_stats:
            self._user_stats[user_id] = {'total_commands': 0, 'commands': {}}

        self._user_stats[user_id]['total_commands'] += 1
        if command not in self._user_stats[user_id]['commands']:
            self._user_stats[user_id]['commands'][command] = 0
        self._user_stats[user_id]['commands'][command] += 1

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        return self._user_stats.get(user_id, {'total_commands': 0, 'commands': {}})