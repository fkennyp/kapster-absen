import csv
from io import StringIO
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import and_
from models import db, Attendance, User

bp = Blueprint('reports', __name__, url_prefix='/reports')

@bp.route('/')
@login_required
def report_view():
    # HANYA user kapster (opsional: yang aktif saja)
    users = (
        User.query
        .filter(User.role == 'kapster')
        .filter(User.is_active_user.is_(True))
        .order_by(User.name.asc())
        .all()
    )

    start = request.args.get('start')
    end = request.args.get('end')
    user_id = request.args.get('user_id', type=int)

    # Join ke User dan batasi HANYA kapster
    q = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .filter(User.role == 'kapster')
    )
    if start:
        q = q.filter(Attendance.date >= start)
    if end:
        q = q.filter(Attendance.date <= end)
    if user_id:
        q = q.filter(Attendance.user_id == user_id)

    q = q.order_by(Attendance.date.desc(), Attendance.user_id.asc())
    rows = q.all()

    return render_template('reports.html', users=users, rows=rows, start=start, end=end, user_id=user_id)

@bp.route('/export.csv')
@login_required
def export_csv():
    start = request.args.get('start')
    end = request.args.get('end')
    user_id = request.args.get('user_id', type=int)

    q = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .filter(User.role == 'kapster')
        .order_by(Attendance.date.asc(), Attendance.user_id.asc())
    )
    if start:
        q = q.filter(Attendance.date >= start)
    if end:
        q = q.filter(Attendance.date <= end)
    if user_id:
        q = q.filter(Attendance.user_id == user_id)

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['date','user_id','name','check_in','check_out','notes'])
    for r in q.all():
        cw.writerow([r.date, r.user_id, r.user.name, r.check_in, r.check_out, r.notes or ''])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=attendance.csv'})
