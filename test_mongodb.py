import logging
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
        logger.info(f"Using URI (masked): {MONGODB_URI.split('@')[1] if '@' in MONGODB_URI else 'local'}")

        # Minimal connection configuration
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # Short timeout for quick testing
            connectTimeoutMS=5000,
            retryWrites=True
        )

        # Test the connection without creating data
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")

        # Just list database names without creating anything
        db_names = client.list_database_names()
        logger.info(f"Available databases: {db_names}")

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