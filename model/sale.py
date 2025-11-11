from app import db
from datetime import datetime


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    customer_id = db.Column(db.Integer, index=True)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    paid = db.Column(db.Numeric(12, 2), nullable=False)
    remark = db.Column(db.String(255))

