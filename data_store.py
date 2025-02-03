from typing import Dict, List, Optional
import logging
from mongo_client import MongoDBClient

class DataStore:
    def __init__(self):
        self.mongo_client = MongoDBClient()
        logging.info("DataStore initialized with MongoDB client")

    def search_importers(self, query: str) -> List[Dict]:
        """Search importers by name or products"""
        try:
            logging.info(f"Starting search with query: '{query}'")
            return self.mongo_client.search_importers(query)
        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}", exc_info=True)
            return []

    def get_importer(self, importer_id: int) -> Optional[Dict]:
        """Get importer by ID"""
        try:
            importer = self.mongo_client.importers_collection.find_one({"_id": importer_id})
            if importer:
                return {
                    'id': importer['_id'],
                    'name': importer['name'],
                    'country': importer['country'],
                    'products': importer['products'],
                    'contact': importer['contact']
                }
            return None
        except Exception as e:
            logging.error(f"Error getting importer: {str(e)}", exc_info=True)
            return None

    def track_user_command(self, user_id: int, command: str):
        """Track user command usage"""
        try:
            self.mongo_client.track_user_command(user_id, command)
            logging.info(f"Command tracked for user {user_id}: {command}")
        except Exception as e:
            logging.error(f"Error tracking command: {str(e)}", exc_info=True)

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        try:
            return self.mongo_client.get_user_stats(user_id)
        except Exception as e:
            logging.error(f"Error getting user stats: {str(e)}", exc_info=True)
            return {'total_commands': 0, 'commands': {}}