import os

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'your_telegram_token_here')

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DB = os.getenv('MONGODB_DB', 'importers_db')
if not MONGODB_URI.startswith('mongodb+srv://') and not MONGODB_URI.startswith('mongodb://'):
    MONGODB_URI = f'mongodb://{MONGODB_URI}'

# Rate Limiting
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS = 10

# Sample Importer Data (Initial data for MongoDB)
SAMPLE_IMPORTERS = [
    {
        "id": 1,
        "name": "PT Import Jaya",
        "country": "Indonesia",
        "products": ["Electronics", "Gadgets"],
        "contact": "contact@importjaya.com"
    },
    {
        "id": 2,
        "name": "Global Trade Indonesia",
        "country": "Indonesia",
        "products": ["Textiles", "Raw Materials"],
        "contact": "info@globaltrade.id"
    }
]