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
    query = Transaction.query.filter(Transaction.user_id == current_user.id)
    query = query.order_by(Transaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    txs = pagination.items

    # Hitung total transaksi hari ini
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import os
    TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Jakarta"))
    today = datetime.now(TZ).date()
    total_today = (
        Transaction.query
        .filter(Transaction.user_id == current_user.id)
        .filter(Transaction.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=TZ))
        .filter(Transaction.created_at < datetime.combine(today, datetime.max.time(), tzinfo=TZ))
        .with_entities(db.func.sum(Transaction.total)).scalar() or 0
    )

    return render_template('user_transactions.html', txs=txs, pagination=pagination, total_today=total_today)
