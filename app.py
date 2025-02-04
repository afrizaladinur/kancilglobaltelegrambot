import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
# setup a secret key, required by sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"

# configure the database with proper SSL and connection handling
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,  # recycle connections every 5 minutes
    "pool_timeout": 20,   # wait up to 20 seconds for a connection

@app.route('/admin/users')
def view_users():
    with db.engine.connect() as conn:
        # Get user credits
        credits = conn.execute(text("""
            SELECT user_id, credits, last_updated 
            FROM user_credits
            ORDER BY last_updated DESC
        """)).fetchall()
        
        # Get user stats
        stats = conn.execute(text("""
            SELECT user_id, command, usage_count, last_used
            FROM user_stats
            ORDER BY last_used DESC
        """)).fetchall()
        
        return jsonify({
            'users_credits': [dict(row) for row in credits],
            'users_stats': [dict(row) for row in stats]
        })

    "pool_pre_ping": True,  # enable connection health checks
    "pool_size": 5,       # maintain up to 5 connections
    "max_overflow": 10,   # allow up to 10 extra connections
    "connect_args": {
        "sslmode": "require",  # require SSL
        "connect_timeout": 10  # connection timeout in seconds
    }
}

# initialize the app with the extension
db.init_app(app)

@app.route('/')
def index():
    return jsonify({"status": "ok", "message": "Server is running"})

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401

    db.create_all()

    # Import sample data if no importers exist
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