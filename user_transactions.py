from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import Transaction, User, db

bp = Blueprint('user_transactions', __name__, url_prefix='/my-transactions')

@bp.route('/', methods=['GET'])
@login_required
def my_transactions():
    # Hanya tampilkan transaksi milik user yang sedang login
    page = request.args.get('page', 1, type=int)
    per_page = 20
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import os
    TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Jakarta"))

    query = Transaction.query.filter(Transaction.user_id == current_user.id)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= start_dt)
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Tambahkan 1 hari agar end_date inklusif
            from datetime import timedelta
            end_dt = end_dt + timedelta(days=1)
            query = query.filter(Transaction.created_at < end_dt)
        except Exception:
            pass
    query = query.order_by(Transaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    txs = pagination.items

    # Hitung total transaksi sesuai filter
    total_query = Transaction.query.filter(Transaction.user_id == current_user.id)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            total_query = total_query.filter(Transaction.created_at >= start_dt)
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            from datetime import timedelta
            end_dt = end_dt + timedelta(days=1)
            total_query = total_query.filter(Transaction.created_at < end_dt)
        except Exception:
            pass
    total_filtered = total_query.with_entities(db.func.sum(Transaction.total)).scalar() or 0

    return render_template('user_transactions.html', txs=txs, pagination=pagination, total_filtered=total_filtered, start_date=start_date, end_date=end_date)
