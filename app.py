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
# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
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