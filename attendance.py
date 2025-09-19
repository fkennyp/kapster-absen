from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Attendance, tznow


bp = Blueprint('attendance', __name__)


@bp.route('/attendance', methods=['GET'])
@login_required
def my_attendance():
    today = tznow().date()
    rec = Attendance.today_record_for(current_user.id)
    return render_template('attendance.html', today=today, rec=rec)


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