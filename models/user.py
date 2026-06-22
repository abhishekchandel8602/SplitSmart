<<<<<<< Updated upstream
from flask_sqlalchemy import SQLAlchemy
=======
from models import db
from werkzeug.security import check_password_hash, generate_password_hash
>>>>>>> Stashed changes

db = SQLAlchemy()

class user(db.model):
    __tablename__ = 'users'
    user_id = db.colomn(db.Integer, primary_key=True)  
    name = db.colomn(db.String(100), nullable=False)
    email = db.colomn(db.String(100), unique=True, nullable=False)
    password_hash = db.colomn(db.String(255), nullable=False)

<<<<<<< Updated upstream
    created_at = db.colomn(db.DateTime, server_default=db.func.now())
=======
    user_id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(db.String(20), unique=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    owned_groups = db.relationship(
        "Group",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    verification_codes = db.relationship(
        "VerificationCode",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class VerificationCode(db.Model):
    __tablename__ = "verification_codes"

    verification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(30), nullable=False, default="registration")
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="verification_codes")

    def set_code(self, code):
        self.code_hash = generate_password_hash(code)

    def check_code(self, code):
        return check_password_hash(self.code_hash, code)
>>>>>>> Stashed changes
