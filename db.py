import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import MONGODB_URI, MONGODB_DB, SAMPLE_IMPORTERS

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
            # Configure MongoDB client with proper SSL settings
            self.client = MongoClient(
                MONGODB_URI,
                tlsAllowInvalidCertificates=True,  # Replace ssl_cert_reqs
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            self.db = self.client[MONGODB_DB]
            self._init_collections()
            # Test connection
            self.client.server_info()
            logging.info("MongoDB connection initialized successfully")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logging.error(f"Could not connect to MongoDB: {e}")
            raise

    def _init_collections(self):
        """Initialize collections and insert sample data if empty"""
        try:
            if 'importers' not in self.db.list_collection_names():
                self.db.create_collection('importers')
                if SAMPLE_IMPORTERS:
                    self.db.importers.insert_many(SAMPLE_IMPORTERS)
                    logging.info(f"Inserted {len(SAMPLE_IMPORTERS)} sample importers")
        except Exception as e:
            logging.error(f"Error initializing collections: {e}")
            raise

    def get_database(self):
        return self.db