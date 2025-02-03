import os
from flask import Flask
from init_db import db

app = Flask(__name__)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Initialize database
db.init_app(app)

# Import models after db initialization
with app.app_context():
    from models import Importer, UserStats

    # Create tables
    db.create_all()

    # Import sample data if no importers exist
    if not Importer.query.first():
        from config import SAMPLE_IMPORTERS
        try:
            for importer_data in SAMPLE_IMPORTERS:
                importer = Importer(
                    name=importer_data['name'],
                    country=importer_data['country'],
                    products=importer_data['products'],
                    contact=importer_data['contact']
                )
                db.session.add(importer)
            db.session.commit()
            print("Sample data loaded successfully")
        except Exception as e:
            print(f"Error loading sample data: {e}")
            db.session.rollback()