
import os

# Required environment variables
required_vars = [
    'TELEGRAM_TOKEN',
    'FLASK_SECRET_KEY',
    'DATABASE_URL',
    'PGDATABASE',
    'PGHOST',
    'PGPORT',
    'PGUSER',
    'PGPASSWORD'
]

# Check for missing environment variables
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
TELEGRAM_DEV_TOKEN = os.environ.get('TELEGRAM_TOKEN_DEV')
IS_DEVELOPMENT = os.environ.get('ENVIRONMENT', 'production') == 'development'
BOT_TOKEN = TELEGRAM_DEV_TOKEN if (IS_DEVELOPMENT and TELEGRAM_DEV_TOKEN) else TELEGRAM_TOKEN

# Database Configuration
DATABASE_URL = os.environ['DATABASE_URL']
PGDATABASE = os.environ['PGDATABASE']
PGHOST = os.environ['PGHOST']
PGPORT = os.environ['PGPORT']
PGUSER = os.environ['PGUSER']
PGPASSWORD = os.environ['PGPASSWORD']

# Flask Configuration
FLASK_SECRET_KEY = os.environ['FLASK_SECRET_KEY']

# Rate Limiting
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS = 10
