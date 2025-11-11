
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change this to a secure value
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# model
import model

# routes
import routes
from routes.reports import reports_bp   
app.register_blueprint(reports_bp)

if __name__ == '__main__':
    app.run()
