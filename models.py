from init_db import db
from datetime import datetime

class Importer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    products = db.Column(db.ARRAY(db.String), nullable=False)
    contact = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    total_commands = db.Column(db.Integer, default=0)
    command_counts = db.Column(db.JSON, default=dict)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)