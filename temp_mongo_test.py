import logging
from pymongo import MongoClient
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_mongo_connection():
    """Test MongoDB connection without saving any data"""
    client = None
    try:
        uri = os.environ.get('MONGODB_URI')
        if not uri:
            logger.error("MONGODB_URI not set in environment")
            return False
            
        # Only show non-sensitive part of URI in logs
        masked_uri = uri.split('@')[-1] if '@' in uri else 'localhost'
        logger.info(f"Testing connection to: {masked_uri}")
        
        # Minimal connection test
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return True
        
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        return False
        
    finally:
        if client:
            client.close()
            logger.info("Connection closed")

if __name__ == "__main__":
    test_mongo_connection()
