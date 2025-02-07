import os
from flask import Flask, request, Response
from telegram import Update
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

@app.route('/admin/users')
def view_users():
    with db.engine.connect() as conn:
        credits = conn.execute(text("""
            SELECT user_id, credits, last_updated 
            FROM user_credits
            ORDER BY last_updated DESC
        """)).fetchall()

        stats = conn.execute(text("""
            SELECT user_id, command, usage_count, last_used
            FROM user_stats
            ORDER BY last_used DESC
        """)).fetchall()

        return jsonify({
            'users_credits': [dict(row) for row in credits],
            'users_stats': [dict(row) for row in stats]
        })

@app.route('/webhook', methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(), bot.application.bot if bot else None)
        await bot.application.process_update(update) # Assuming bot.application.process_update exists in your TelegramBot class
        return Response('ok', status=200)
    return Response(status=403)

with app.app_context():
    import models
    db.create_all()

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
            print("Sample data loaded successfully")
        except Exception as e:
            print(f"Error loading sample data: {e}")
            db.session.rollback()