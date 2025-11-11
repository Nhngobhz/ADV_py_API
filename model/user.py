from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(128), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    profile = db.Column(db.String(255))
