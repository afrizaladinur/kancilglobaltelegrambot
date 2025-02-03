import logging
from typing import List, Dict, Any
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from config import MONGODB_URI, SAMPLE_IMPORTERS
import time
import ssl

class MongoDBClient:
    def __init__(self):
        self._client: MongoClient = None
        self._db: Database = None
        self._max_retries = 3
        self._retry_delay = 2  # seconds
        self.connect()

    def connect(self) -> None:
        """Connect to MongoDB with retry logic"""
        retries = 0
        last_error = None

        while retries < self._max_retries:
            try:
                logging.info("Attempting to connect to MongoDB...")
                # Create MongoClient with the complete URI and options
                self._client = MongoClient(
                    MONGODB_URI,
                    serverSelectionTimeoutMS=5000,
                    retryWrites=True,
                    w='majority',
                    ssl=True,
                    ssl_cert_reqs=ssl.CERT_NONE,
                    connect=True
                )
                # Test the connection
                self._client.admin.command('ping')
                # Get database from the URI
                self._db = self._client.get_database()
                logging.info(f"Successfully connected to MongoDB database: {self._db.name}")

                # Initialize with sample data if collection is empty
                if self._db.importers.count_documents({}) == 0:
                    self._db.importers.insert_many(SAMPLE_IMPORTERS)
                    logging.info("Initialized MongoDB with sample importers data")
                return

            except Exception as e:
                last_error = e
                logging.warning(f"Connection attempt {retries + 1} failed: {str(e)}")
                retries += 1
                if retries < self._max_retries:
                    time.sleep(self._retry_delay)

        logging.error(f"Failed to connect to MongoDB after {self._max_retries} attempts. Last error: {str(last_error)}")
        raise Exception(f"Failed to connect to MongoDB: {str(last_error)}")

    @property
    def importers_collection(self) -> Collection:
        """Get importers collection"""
        return self._db.importers

    def search_importers(self, query: str) -> List[Dict[str, Any]]:
        """Search importers by name or products"""
        try:
            # Case-insensitive search across multiple fields
            search_query = {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"products": {"$regex": query, "$options": "i"}},
                    {"country": {"$regex": query, "$options": "i"}}
                ]
            }
            return list(self.importers_collection.find(search_query))
        except Exception as e:
            logging.error(f"Error searching importers: {str(e)}")
            return []

    def track_user_command(self, user_id: int, command: str) -> None:
        """Track user command usage"""
        try:
            self._db.user_stats.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "total_commands": 1,
                        f"commands.{command}": 1
                    }
                },
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error tracking user command: {str(e)}")

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user command statistics"""
        try:
            stats = self._db.user_stats.find_one({"user_id": user_id})
            if not stats:
                return {"total_commands": 0, "commands": {}}
            return {
                "total_commands": stats.get("total_commands", 0),
                "commands": stats.get("commands", {})
            }
        except Exception as e:
            logging.error(f"Error getting user stats: {str(e)}")
            return {"total_commands": 0, "commands": {}}

    def close(self) -> None:
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            logging.info("MongoDB connection closed")