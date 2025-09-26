import pandas as pd
from io import BytesIO
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

@bp.route('/export.xlsx')
@login_required
def export_xlsx():
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

    # Convert to DataFrame
    data = []
    for r in q.all():
        data.append({
            'Tanggal': r.date.strftime('%Y-%m-%d'),
            'ID User': r.user_id,
            'Nama': r.user.name,
            'Check In': r.check_in.strftime('%H:%M:%S') if r.check_in else '',
            'Check Out': r.check_out.strftime('%H:%M:%S') if r.check_out else '',
            'Catatan': r.notes or ''
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Check-in Reports', index=False)
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=checkin_reports.xlsx'}
    )