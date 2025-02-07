import os
import logging
from flask import Flask, request, Response, jsonify
from telegram import Update
from sqlalchemy.orm import DeclarativeBase
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import json

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_timeout": 20,
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10,
    "connect_args": {
        "sslmode": "require",
        "connect_timeout": 30
    }
}

db.init_app(app)
bot = None  # Will be set from main.py

@app.route('/')
def index():
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/webhook', methods=['POST'])
async def webhook():
    if request.method == "POST":
        try:
            if not bot or not bot.application:
                logging.error("Bot not initialized")
                return Response('Bot not initialized', status=500)

            update = Update.de_json(request.get_json(), bot.application.bot)
            if update is None:
                logging.error("Invalid update received")
                return Response('Invalid update', status=400)

            await bot.application.process_update(update)
            return Response('ok', status=200)
        except Exception as e:
            logging.error(f"Webhook error: {str(e)}", exc_info=True)
            return Response(f'Error: {str(e)}', status=500)
    return Response(status=403)

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "bot_initialized": bot is not None,
        "database_connected": db.engine.pool.checkedout() >= 0
    })

with app.app_context():
    import models
    db.create_all()

    # Load sample data if needed
    if not models.Importer.query.first():
        from config import SAMPLE_IMPORTERS
        try:
            for importer_data in SAMPLE_IMPORTERS:
                importer = models.Importer(
                    name=importer_data['name'],
                    country=importer_data['country'],
                    product=importer_data['products'],
                    contact=importer_data['contact']
                )
                db.session.add(importer)
            db.session.commit()
            logging.info("Sample data loaded successfully")
        except Exception as e:
            logging.error(f"Error loading sample data: {e}")
            db.session.rollback()