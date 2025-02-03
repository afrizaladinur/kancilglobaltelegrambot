import logging
import ssl
from pymongo import MongoClient
from config import MONGODB_URI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_connection():
    try:
        logger.info("Attempting to connect to MongoDB...")
        logger.info(f"Using URI (masked): {MONGODB_URI.split('@')[1]}")

        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            w='majority',
            ssl=True,
            ssl_cert_reqs=ssl.CERT_NONE,
            connect=True
        )

        # Test the connection
        client.admin.command('ping')
        db = client.get_database()
        logger.info(f"Successfully connected to MongoDB. Database: {db.name}")

        # Test a simple operation
        collections = db.list_collection_names()
        logger.info(f"Available collections: {collections}")

        # Initialize with sample data if needed
        if 'importers' not in collections:
            logger.info("Importers collection not found, will be created automatically when data is inserted")

        return True

    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}", exc_info=True)
        return False

    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    success = test_connection()
    if not success:
        exit(1)