import os

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7639309068:AAHQItcXwh-i9MTWP58VYS9_syC7osIsFmo')

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://kancilglobal:JgnNJe9KBegnH2vk@cluster0.23hro.mongodb.net/master_data')
MONGODB_DB = 'master_data'

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