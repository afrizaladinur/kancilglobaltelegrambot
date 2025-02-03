import logging
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    uri = "mongodb+srv://kancilglobal:JgnNJe9KBegnH2vk@cluster0.23hro.mongodb.net/master_data"
    try:
        client = MongoClient(uri)
        # Test the connection
        client.admin.command('ping')
        db = client.get_database()
        logger.info(f"Successfully connected to MongoDB. Database: {db.name}")
        # Test a simple operation
        collections = db.list_collection_names()
        logger.info(f"Available collections: {collections}")
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    test_connection()
