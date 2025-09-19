from datetime import datetime, date
import pytz
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

db = SQLAlchemy()

def tznow():
    tz = pytz.timezone(Config.TIMEZONE)
    return datetime.now(tz)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='kapster')  # 'admin' or 'kapster'
    is_active_user = db.Column(db.Boolean, default=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    user = db.relationship('User', backref='attendances')

    @staticmethod
    def today_record_for(user_id: int):
        today = tznow().date()
        return Attendance.query.filter_by(user_id=user_id, date=today).first()

    @staticmethod
    def ensure_today(user_id: int):
        rec = Attendance.today_record_for(user_id)
        if not rec:
            rec = Attendance(user_id=user_id, date=tznow().date())
        return rec