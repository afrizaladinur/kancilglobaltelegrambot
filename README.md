
# Telegram Export-Import Directory Bot

A Telegram bot that helps users find and manage export-import contacts with credit-based access.

## Features

- 🔍 Search importers by category and product
- 📁 Save and manage contacts
- 💳 Credit system for accessing contacts
- 🌐 WhatsApp integration for direct contact
- 📊 User statistics tracking
- 💰 Built-in payment processing

## Environment Variables

Required environment variables:
- `TELEGRAM_TOKEN`: Your Telegram bot token
- `DATABASE_URL`: PostgreSQL database URL 

## Project Structure

```
├── bot.py           # Bot initialization and core setup
├── handlers.py      # Command and callback handlers
├── messages.py      # Message templates and formatting
├── data_store.py    # Database operations
├── rate_limiter.py  # Request rate limiting
└── main.py         # Application entry point
```

## Commands

- `/start` - Show main menu
- `/saved` - View saved contacts
- `/credits` - Check credit balance
- `/help` - Show help information

## Running the Bot

1. Set required environment variables
2. Run `python main.py`

## Credit System

- New users get 10 free credits
- Contact costs:
  - 3 credits: Full contact with WhatsApp
  - 2 credits: Full contact without WhatsApp
  - 1 credit: Basic contact information
