from app import db


class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    location = db.Column(db.String(255), nullable=False)
    logo = db.Column(db.String(255))
    phone = db.Column(db.String(64))
