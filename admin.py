from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Attendance, tznow

bp = Blueprint('admin', __name__, url_prefix='/admin')


def require_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        from flask import abort
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
    # Summary: total users, active today, missing today
    total_users = User.query.filter_by(is_active_user=True).count()
    activity_today = Attendance.query.filter(Attendance.date == today, Attendance.check_in.isnot(None)).count()
    missing_today = total_users - activity_today
    latest = Attendance.query.order_by(Attendance.id.desc()).limit(10).all()
    return render_template('dashboard.html', total_users=total_users, activity_today=activity_today, missing_today=missing_today, latest=latest, today=today)