from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Attendance, tznow


bp = Blueprint('attendance', __name__)


@bp.route('/attendance', methods=['GET'])
@login_required
def my_attendance():
    import locale
    from datetime import datetime
    today = tznow().date()
    rec = Attendance.today_record_for(current_user.id)

    # Set locale to Indonesian for month names (if available)
    try:
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'id_ID')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '')  # fallback ke default


    # Format tanggal cross-platform (Windows tidak support %-d)
    def format_tanggal(dt, with_time=False):
        if not dt:
            return None
        try:
            if with_time:
                # Coba format Linux/Mac
                return dt.strftime('%-d %B %Y %H:%M:%S')
            else:
                return dt.strftime('%-d %B %Y')
        except ValueError:
            try:
                if with_time:
                    # Format Windows
                    return dt.strftime('%#d %B %Y %H:%M:%S')
                else:
                    return dt.strftime('%#d %B %Y')
            except Exception:
                # Fallback
                return dt.strftime('%d %B %Y %H:%M:%S') if with_time else dt.strftime('%d %B %Y')

    today_id = format_tanggal(today)
    check_in_id = format_tanggal(rec.check_in, with_time=True) if rec and rec.check_in else None
    check_out_id = format_tanggal(rec.check_out, with_time=True) if rec and rec.check_out else None

    return render_template('attendance.html', today=today, rec=rec, today_id=today_id, check_in_id=check_in_id, check_out_id=check_out_id)


@bp.route('/attendance/check-in', methods=['POST'])
@login_required
def check_in():
    rec = Attendance.ensure_today(current_user.id)
    if rec.check_in:
        flash('You already checked in today.', 'warning')
        return redirect(url_for('attendance.my_attendance'))
    rec.check_in = tznow()
    rec.notes = request.form.get('notes') or rec.notes
    db.session.add(rec)
    db.session.commit()
    flash('Checked in. Have a great shift!', 'success')
    return redirect(url_for('attendance.my_attendance'))


@bp.route('/attendance/check-out', methods=['POST'])
@login_required
def check_out():
    rec = Attendance.ensure_today(current_user.id)
    if not rec.check_in:
        flash('You have not checked in yet.', 'danger')
        return redirect(url_for('attendance.my_attendance'))
    if rec.check_out:
        flash('You already checked out today.', 'warning')
        return redirect(url_for('attendance.my_attendance'))
    rec.check_out = tznow()
    rec.notes = request.form.get('notes') or rec.notes
    db.session.add(rec)
    db.session.commit()
    flash('Checked out. Good job!', 'success')
    return redirect(url_for('attendance.my_attendance'))