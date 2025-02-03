import logging
import certifi
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import MONGODB_URI, MONGODB_DB

class MongoDB:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if MongoDB._instance is not None:
            raise Exception("MongoDB instance already exists!")

        try:
            logging.info("Attempting to connect to MongoDB")

            # Parse the URI to get the database name if specified
            parsed_uri = urlparse(MONGODB_URI)
            path_parts = parsed_uri.path.strip('/').split('/')
            db_name = path_parts[0] if path_parts else MONGODB_DB

            # Initialize MongoDB client with minimal configuration
            # Let pymongo handle the URI parsing
            self.client = MongoClient(
                MONGODB_URI,
                tlsCAFile=certifi.where()
            )

            # Test connection explicitly
            self.client.admin.command('ping')
            logging.info("Successfully connected to MongoDB")

            # Use the database name from URI or config
            self.db = self.client[db_name]
            logging.info(f"Using database: {db_name}")
            self._init_collections()

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logging.error(f"Could not connect to MongoDB: {e}")
            raise
        except Exception as e:
            logging.error(f"Error initializing MongoDB: {e}")
            raise

    def _init_collections(self):
        """Initialize collections and insert sample data if empty"""
        try:
            collections = self.db.list_collection_names()
            if 'importers' not in collections:
                logging.info("Creating importers collection")
                self.db.create_collection('importers')
                from config import SAMPLE_IMPORTERS
                if SAMPLE_IMPORTERS:
                    self.db.importers.insert_many(SAMPLE_IMPORTERS)
                    logging.info(f"Inserted {len(SAMPLE_IMPORTERS)} sample importers")
        except Exception as e:
            logging.error(f"Error initializing collections: {e}")
            raise

    def get_database(self):
        return self.db