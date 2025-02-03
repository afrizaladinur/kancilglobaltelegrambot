import os

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# PostgreSQL Configuration is handled via DATABASE_URL environment variable

# Rate Limiting
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS = 10

# Sample Importer Data (Initial data for PostgreSQL)
SAMPLE_IMPORTERS = [
    {
        "name": "PT Import Jaya",
        "country": "Indonesia",
        "products": ["Electronics", "Gadgets"],
        "contact": "contact@importjaya.com"
    },
    {
        "name": "Global Trade Indonesia",
        "country": "Indonesia",
        "products": ["Textiles", "Raw Materials"],
        "contact": "info@globaltrade.id"
    }
]