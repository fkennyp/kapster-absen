from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Attendance, tznow, Transaction

bp = Blueprint('admin', __name__, url_prefix='/admin')


def require_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        abort(403)


@bp.before_request
def enforce_admin():
    if request.endpoint and request.endpoint.startswith('admin.'):
        require_admin()


@bp.route('/users')
@login_required
def users():
    q = User.query.order_by(User.role.desc(), User.name.asc()).all()
    return render_template('users.html', users=q)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
def user_create():
    if request.method == 'POST':
        name = request.form['name'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role', 'kapster')
        u = User(name=name, username=username, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('User created', 'success')
        return redirect(url_for('admin.users'))
    return render_template('user_form.html', user=None)


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    u = User.query.get_or_404(user_id)
    if request.method == 'POST':
        u.name = request.form['name'].strip()
        u.username = request.form['username'].strip()
        role = request.form.get('role', 'kapster')
        u.role = role
        if request.form.get('password'):
            u.set_password(request.form['password'])
        u.is_active_user = request.form.get('is_active_user') == 'on'
        db.session.commit()
        flash('User updated', 'success')
        return redirect(url_for('admin.users'))
    return render_template('user_form.html', user=u)


@bp.route('/dashboard')
@login_required
def admin_dashboard():
    today = tznow().date()
    
    # Hitung tanggal 2 minggu yang lalu
    from datetime import timedelta
    two_weeks_ago = today - timedelta(days=14)

    # Hanya kapster aktif
    total_users = User.query.filter_by(is_active_user=True, role='kapster').count()

    # Checked-in hari ini oleh kapster aktif
    activity_today = (
        db.session.query(Attendance.id)
        .join(User, Attendance.user_id == User.id)
        .filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            User.role == 'kapster',
            User.is_active_user.is_(True),
        )
        .count()
    )

    missing_today = max(total_users - activity_today, 0)

    # Tampilkan log attendance kapster saja (2 minggu terakhir)
    latest = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .filter(
            User.role == 'kapster',
            Attendance.date >= two_weeks_ago
        )
        .order_by(Attendance.date.desc(), Attendance.id.desc())
        .limit(50)  # Limit lebih banyak karena rentang waktu lebih panjang
        .all()
    )

    return render_template(
        'dashboard.html',
        total_users=total_users,
        activity_today=activity_today,
        missing_today=missing_today,
        latest=latest,
        today=today
    )

@bp.route('/transactions')
@login_required
def transactions_list():
    require_admin()

    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    q_user = request.args.get('user_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Build query
    query = Transaction.query.join(User, User.id == Transaction.user_id)

    # Query untuk total (tanpa pagination)
    total_query = Transaction.query

    # Apply date filters
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
        total_query = total_query.filter(Transaction.created_at >= start_date)
    if end_date:
        # Add 1 day to include the end date fully
        from datetime import datetime, timedelta
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.created_at < end_date_obj)
            total_query = total_query.filter(Transaction.created_at < end_date_obj)
        except ValueError:
            # Handle invalid date format
            pass

    # Apply user filter
    if q_user:
        query = query.filter(Transaction.user_id == q_user)
        total_query = total_query.filter(Transaction.user_id == q_user)

    # Order by latest first
    query = query.order_by(Transaction.created_at.desc())

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    txs = pagination.items

    # Hitung total transaksi
    total_amount = total_query.with_entities(db.func.sum(Transaction.total)).scalar() or 0
    total_count = total_query.count()

    # Get active kapsters for filter dropdown
    users = User.query.filter_by(role='kapster', is_active_user=True).order_by(User.name.asc()).all()

    return render_template(
        'admin/transactions_list.html',
        txs=txs,
        users=users,
        pagination=pagination,
        total_amount=total_amount,
        total_count=total_count
    )