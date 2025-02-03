import logging
from pymongo import MongoClient
from config import MONGODB_URI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def test_connection():
    """Test MongoDB connection with minimal configuration"""
    client = None
    try:
        logger.debug("Testing MongoDB connection...")

        if not MONGODB_URI:
            logger.error("MONGODB_URI environment variable is not set")
            return False

        # Mask sensitive information in logs
        masked_uri = MONGODB_URI.split('@')[1] if '@' in MONGODB_URI else 'local'
        logger.debug(f"Using MongoDB URI (masked): {masked_uri}")

        # Basic connection with minimal options
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=2000,  # Quick timeout for testing
            connectTimeoutMS=2000
        )

        # Simple ping test
        client.admin.command('ping')
        logger.info("MongoDB connection test successful!")

        return True

    except Exception as e:
        logger.error(f"MongoDB connection test failed: {str(e)}")
        return False

    finally:
        if client:
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    success = test_connection()
    if not success:
        exit(1)
