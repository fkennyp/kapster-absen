from datetime import datetime, date
import pytz
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from sqlalchemy.orm import relationship

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
    
class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), unique=True)  # boleh NULL, tapi kalau isi harus unik
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    def touch(self):
        self.updated_at = tznow()


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    barber_name = db.Column(db.String(120))
    customer_name = db.Column(db.String(120))
    customer_email = db.Column(db.String(120), nullable=True)
    payment_type = db.Column(db.String(20), nullable=False)
    total = db.Column(db.Integer, nullable=False)
    cash_given = db.Column(db.Integer)
    change_amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False)

    invoice_seq = db.Column(db.Integer)          # urutan per-hari (1,2,3..)
    invoice_code = db.Column(db.String(50))      # tampilan: INV-DD/MM/YYYY-###
    
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    visit_number = db.Column(db.Integer)  # freeze "kunjungan ke-X" pada saat transaksi
    
    user = relationship('User')
    items = relationship('TransactionItem', backref='transaction', cascade='all, delete-orphan')
    customer = relationship('Customer', lazy='joined')


class TransactionItem(db.Model):
    __tablename__ = 'transaction_items'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    price_each = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Integer, nullable=False)

    service = relationship('Service')