from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class user(db.model):
    __tablename__ = 'users'
    user_id = db.colomn(db.Integer, primary_key=True)  
    name = db.colomn(db.String(100), nullable=False)
    email = db.colomn(db.String(100), unique=True, nullable=False)
    password_hash = db.colomn(db.String(255), nullable=False)

    created_at = db.colomn(db.DateTime, server_default=db.func.now())
