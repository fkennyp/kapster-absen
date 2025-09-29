from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Attendance, tznow, Transaction, TransactionItem, Service
from io import BytesIO
import pandas as pd
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill

bp = Blueprint('admin', __name__, url_prefix='/admin')


def require_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        abort(403)

# ====== Services Management =======
@bp.route('/services')
@login_required
def services_list():
    require_admin()
    services = Service.query.order_by(Service.name.asc()).all()
    return render_template('admin/services_list.html', services=services)

@bp.route('/services/new', methods=['GET', 'POST'])
@login_required
def service_create():
    require_admin()
    if request.method == 'POST':
        name = request.form['name'].strip()
        price = request.form.get('price', type=int)
        
        if not name:
            flash('Nama layanan wajib diisi.', 'danger')
        elif not price or price < 0:
            flash('Harga harus valid.', 'danger')
        else:
            service = Service(name=name, price=price)
            db.session.add(service)
            db.session.commit()
            flash('Layanan berhasil ditambahkan.', 'success')
            return redirect(url_for('admin.services_list'))
            
    return render_template('admin/service_form.html', service=None)

@bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def service_edit(service_id):
    require_admin()
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        price = request.form.get('price', type=int)
        
        if not name:
            flash('Nama layanan wajib diisi.', 'danger')
        elif not price or price < 0:
            flash('Harga harus valid.', 'danger')
        else:
            service.name = name
            service.price = price
            db.session.commit()
            flash('Layanan berhasil diperbarui.', 'success')
            return redirect(url_for('admin.services_list'))
            
    return render_template('admin/service_form.html', service=service)

@bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
def service_delete(service_id):
    require_admin()
    service = Service.query.get_or_404(service_id)
    
    # Cek apakah layanan masih digunakan di transaksi
    usage_count = TransactionItem.query.filter_by(service_id=service.id).count()
    if usage_count > 0:
        flash(f'Layanan tidak bisa dihapus karena masih digunakan di {usage_count} transaksi.', 'danger')
        return redirect(url_for('admin.services_list'))
        
    db.session.delete(service)
    db.session.commit()
    flash('Layanan berhasil dihapus.', 'success')
    return redirect(url_for('admin.services_list'))


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
        import re
        name = request.form['name'].strip()
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        role = request.form.get('role', 'kapster')
        # Validasi email regex
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            flash('Email tidak valid', 'danger')
            return render_template('user_form.html', user=None)
        u = User(name=name, username=username, email=email, role=role)
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
        import re
        u.name = request.form['name'].strip()
        u.username = request.form['username'].strip()
        email = request.form['email'].strip()
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            flash('Email tidak valid', 'danger')
            return render_template('user_form.html', user=u)
        # Cek email unik (tidak boleh sama dengan user lain)
        existing = User.query.filter(User.email == email, User.id != u.id).first()
        if existing:
            flash('Email telah terdaftar pada user lain.', 'danger')
            return render_template('user_form.html', user=u)
        u.email = email
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
    
@bp.route('/transactions/export.xlsx')
@login_required
def export_transactions_xlsx():
    """Export data transaksi ke Excel"""
    require_admin()

    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    q_user = request.args.get('user_id', type=int)

    # Build query
    query = Transaction.query.join(User, User.id == Transaction.user_id)

    # Apply date filters
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        from datetime import datetime, timedelta
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.created_at < end_date_obj)
        except ValueError:
            pass

    # Apply user filter
    if q_user:
        query = query.filter(Transaction.user_id == q_user)

    # Order by latest first
    transactions = query.order_by(Transaction.created_at.desc()).all()

    # Prepare data for Excel
    data = []
    for tx in transactions:
        # Get service details
        services = []
        for item in tx.items:
            services.append(f"{item.service.name} ({item.qty}x Rp {item.price_each:,})")
        
        services_str = ", ".join(services)
        
        data.append({
            'Invoice': tx.invoice_code or f"INV-{tx.created_at.strftime('%d/%m/%Y')}-{tx.invoice_seq or 'XXX'}",
            'Tanggal': tx.created_at.strftime('%Y-%m-%d %H:%M'),
            'Pelanggan': tx.customer_name,
            'Kapster': tx.user.name,
            'Layanan': services_str,
            'Total': tx.total,
            'Tipe Pembayaran': tx.payment_type.upper(),
            'Dibayar': tx.cash_given if tx.payment_type == 'cash' else tx.total,
            'Kembalian': tx.change_amount if tx.payment_type == 'cash' else 0,
            'Email Pelanggan': tx.customer_email or '',
            'Kunjungan Ke': tx.visit_number or 1
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Data Transaksi', index=False)
        
        # Format column widths
        worksheet = writer.sheets['Data Transaksi']
        worksheet.column_dimensions['A'].width = 20  # Invoice
        worksheet.column_dimensions['B'].width = 18  # Tanggal
        worksheet.column_dimensions['C'].width = 20  # Pelanggan
        worksheet.column_dimensions['D'].width = 15  # Kapster
        worksheet.column_dimensions['E'].width = 40  # Layanan
        worksheet.column_dimensions['F'].width = 15  # Total
        worksheet.column_dimensions['G'].width = 12  # Tipe Pembayaran
        worksheet.column_dimensions['H'].width = 15  # Dibayar
        worksheet.column_dimensions['I'].width = 12  # Kembalian
        worksheet.column_dimensions['J'].width = 25  # Email
        worksheet.column_dimensions['K'].width = 12  # Kunjungan
        
        # Format header style
        for cell in worksheet[1]:
            cell.font = openpyxl.styles.Font(bold=True)
            cell.fill = openpyxl.styles.PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    
    output.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"transaksi_export_{timestamp}.xlsx"
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )