from app import db
from datetime import datetime

class Importer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(50))
    website = db.Column(db.Text)
    email_1 = db.Column(db.String(255))
    email_2 = db.Column(db.String(255))
    product = db.Column(db.String(50))
    wa_availability = db.Column(db.String(50))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    command = db.Column(db.String(50), nullable=False)
    usage_count = db.Column(db.Integer, default=1)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)

class UserCredit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('credits >= 0', name='credits_non_negative'),
    )

class SavedContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    importer_name = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(100))
    contact = db.Column(db.String(50))
    email = db.Column(db.String(255))
    website = db.Column(db.Text)
    wa_availability = db.Column(db.Boolean)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'importer_name', name='uix_user_importer'),
    )