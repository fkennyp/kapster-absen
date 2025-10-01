from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from models import Transaction, User, db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

bp = Blueprint('user_transactions', __name__, url_prefix='/my-transactions')
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Jakarta"))

def apply_date_filters(query, start_date, end_date):
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= start_dt)
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.created_at < end_dt)
        except Exception:
            pass
    return query

def check_today_transactions_empty(user_id):
    today = datetime.now(TZ).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=TZ)
    today_end = datetime.combine(today, datetime.max.time(), tzinfo=TZ)
    count_today = (
        Transaction.query
        .filter(Transaction.user_id == user_id)
        .filter(Transaction.created_at >= today_start)
        .filter(Transaction.created_at <= today_end)
        .count()
    )
    return count_today == 0

@bp.route('/', methods=['GET'])
@login_required
def my_transactions():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Jika tidak ada filter tanggal, tampilkan tabel kosong
    if not start_date and not end_date:
        txs = []
        pagination = None
        total_filtered = 0
        is_today_empty = None  # Tidak perlu pesan hari ini
    else:
        # Query transaksi sesuai user dan filter tanggal
        query = Transaction.query.filter(Transaction.user_id == current_user.id)
        query = apply_date_filters(query, start_date, end_date)
        query = query.order_by(Transaction.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        txs = pagination.items

        # Hitung total transaksi yang difilter
        total_query = Transaction.query.filter(Transaction.user_id == current_user.id)
        total_query = apply_date_filters(total_query, start_date, end_date)
        total_filtered = total_query.with_entities(db.func.sum(Transaction.total)).scalar() or 0
        is_today_empty = None

    return render_template(
        'user_transactions.html',
        txs=txs,
        pagination=pagination,
        total_filtered=total_filtered,
        start_date=start_date,
        end_date=end_date,
        is_today_empty=is_today_empty
    )

@bp.route('/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):
    # Get transaction and verify it belongs to current user
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        abort(403)  # Forbidden if transaction doesn't belong to user
    
    return render_template('transaction_detail.html', transaction=transaction, is_admin=False)
