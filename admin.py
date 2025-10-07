

# All imports at the top
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Attendance, tznow, Transaction, TransactionItem, Service, Customer, DiscountRule
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta, date

import openpyxl
from openpyxl.styles import Font, PatternFill

bp = Blueprint('admin', __name__, url_prefix='/admin')
def require_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        abort(403)

# ====== User Delete =======
@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def user_delete(user_id):
    u = User.query.get_or_404(user_id)
    if u.role == 'admin':
        flash('Tidak bisa menghapus user admin.', 'danger')
        return redirect(url_for('admin.users'))
    # Cek relasi attendance
    attendance_count = Attendance.query.filter_by(user_id=u.id).count()
    if attendance_count > 0:
        flash('Tidak bisa menghapus user karena masih ada data absensi terkait.', 'danger')
        return redirect(url_for('admin.users'))
    db.session.delete(u)
    db.session.commit()
    flash('User berhasil dihapus.', 'success')
    return redirect(url_for('admin.users'))



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


@bp.route('/transactions/<int:transaction_id>')
@login_required
def transaction_view(transaction_id):
    require_admin()
    transaction = Transaction.query.get_or_404(transaction_id)
    users = User.query.filter_by(role='kapster', is_active_user=True).all()
    return render_template('admin/transaction_form.html', 
                         transaction=transaction,
                         users=users,
                         edit_mode=False)

@bp.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def transaction_edit(transaction_id):
    require_admin()
    transaction = Transaction.query.get_or_404(transaction_id)
    
    if request.method == 'POST':
        # Update basic transaction info
        transaction.customer_name = request.form['customer_name'].strip()
        transaction.barber_name = request.form['barber_name']
        transaction.payment_type = request.form['payment_type']
        
        if transaction.payment_type == 'cash':
            cash_given = request.form.get('cash_given', type=int)
            if cash_given and cash_given >= transaction.total:
                transaction.cash_given = cash_given
                transaction.change_amount = cash_given - transaction.total
            else:
                flash('Jumlah uang yang diterima harus lebih besar atau sama dengan total transaksi.', 'danger')
                return redirect(url_for('admin.transaction_edit', transaction_id=transaction_id))
        
        db.session.commit()
        flash('Transaksi berhasil diperbarui.', 'success')
        return redirect(url_for('admin.transactions_list'))
        
    users = User.query.filter_by(role='kapster', is_active_user=True).all()
    return render_template('admin/transaction_form.html', 
                         transaction=transaction,
                         users=users,
                         edit_mode=True)

@bp.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
@login_required
def transaction_delete(transaction_id):
    require_admin()
    try:
        Transaction.delete(transaction_id)
        flash('Transaksi berhasil dihapus.', 'success')
    except Exception as e:
        flash('Gagal menghapus transaksi.', 'danger')
    
    return redirect(url_for('admin.transactions_list'))

@bp.before_request
def enforce_admin():
    # Jangan blokir endpoint autocomplete customer untuk kapster
    if request.endpoint and request.endpoint.startswith('admin.'):
        # Izinkan kapster akses /admin/customers?q=...
        if request.endpoint == 'admin.customers_list' and request.args.get('q') and current_user.role == 'kapster':
            return
        require_admin()


@bp.route('/users')
@login_required
def users():
    q = User.query.order_by(User.role.desc(), User.name.asc()).all()
    return render_template('admin/users.html', users=q)


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
            return render_template('admin/user_form.html', user=None)
        # Cek email unik (tidak boleh sama dengan user lain)
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email telah terdaftar pada user lain.', 'danger')
            return render_template('admin/user_form.html', user=None)
        u = User(name=name, username=username, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('User created', 'success')
        return redirect(url_for('admin.users'))
    else:
        return render_template('admin/user_form.html', user=None)


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
            return render_template('admin/user_form.html', user=u)
        # Cek email unik (tidak boleh sama dengan user lain)
        existing = User.query.filter(User.email == email, User.id != u.id).first()
        if existing:
            flash('Email telah terdaftar pada user lain.', 'danger')
            return render_template('admin/user_form.html', user=u)
        u.email = email
        role = request.form.get('role', 'kapster')
        u.role = role
        if request.form.get('password'):
            u.set_password(request.form['password'])
        u.is_active_user = request.form.get('is_active_user') == 'on'
        db.session.commit()
        flash('User updated', 'success')
        return redirect(url_for('admin.users'))
    else:
        return render_template('admin/user_form.html', user=u)


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

    # Check if date filters are applied
    has_date_filter = bool(start_date or end_date)
    
    # If no date filter, set empty results
    if not has_date_filter:
        query = query.filter(Transaction.id < 0)  # Force empty result
        total_query = total_query.filter(Transaction.id < 0)
    else:
        # Apply date filters
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(Transaction.created_at >= start_date_obj)
                total_query = total_query.filter(Transaction.created_at >= start_date_obj)
            except ValueError:
                flash('Format tanggal mulai tidak valid.', 'danger')

        if end_date:
            try:
                # Add 1 day to include the end date fully
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Transaction.created_at < end_date_obj)
                total_query = total_query.filter(Transaction.created_at < end_date_obj)
            except ValueError:
                flash('Format tanggal akhir tidak valid.', 'danger')

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
        transactions=txs,
        users=users,
        pagination=pagination,
        total_amount=total_amount
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
        subtotal = (tx.total or 0) + (tx.discount or 0)
        data.append({
            'Invoice': tx.invoice_code or f"INV-{tx.created_at.strftime('%d/%m/%Y')}-{tx.invoice_seq or 'XXX'}",
            'Tanggal': tx.created_at.strftime('%Y-%m-%d %H:%M'),
            'Pelanggan': tx.customer_name,
            'Kapster': tx.user.name,
            'Layanan': services_str,
            'Subtotal': subtotal,
            'Diskon': tx.discount or 0,
            'Total Setelah Diskon': tx.total or 0,
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
        worksheet.column_dimensions['F'].width = 15  # Subtotal
        worksheet.column_dimensions['G'].width = 12  # Diskon
        worksheet.column_dimensions['H'].width = 18  # Total Setelah Diskon
        worksheet.column_dimensions['I'].width = 12  # Tipe Pembayaran
        worksheet.column_dimensions['J'].width = 15  # Dibayar
        worksheet.column_dimensions['K'].width = 12  # Kembalian
        worksheet.column_dimensions['L'].width = 25  # Email
        worksheet.column_dimensions['M'].width = 12  # Kunjungan
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


# ====== Customer Management =======
@bp.route('/customers', methods=['GET'])
@login_required
def customers_list():
    # Only return JSON if ?q= is present (for autocomplete)
    if request.args.get('q'):
        # Izinkan admin dan kapster untuk query autocomplete
        if not (current_user.role == 'admin' or current_user.role == 'kapster'):
            return {'error': 'Forbidden'}, 403
        q = request.args.get('q', '').strip()
        query = Customer.query
        if q:
            query = query.filter(Customer.phone.like(f"%{q}%") | Customer.name.like(f"%{q}%"))
        customers = query.order_by(Customer.name).limit(15).all()
        return {'customers': [ {'name': c.name, 'phone': c.phone} for c in customers if c.phone ]}
    # Otherwise, always render the normal HTML page
    require_admin()
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('admin/customers_list.html', customers=customers)

@bp.route('/customers/new', methods=['GET', 'POST'])
@login_required
def customer_create():
    require_admin()
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip() or None

        if not name:
            flash('Nama pelanggan wajib diisi.', 'danger')
        else:
            from sqlalchemy.exc import IntegrityError
            try:
                Customer.create(name=name, phone=phone)
                flash('Data pelanggan berhasil ditambahkan.', 'success')
                return redirect(url_for('admin.customers_list'))
            except IntegrityError as e:
                from models import db
                db.session.rollback()
                flash('Nomor telepon sudah terdaftar untuk pelanggan lain.', 'danger')
            except Exception as e:
                from models import db
                db.session.rollback()
                flash('Terjadi kesalahan. Silakan coba lagi.', 'danger')

    return render_template('admin/customer_form.html', customer=None)

@bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def customer_edit(customer_id):
    require_admin()
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip() or None
        
        if not name:
            flash('Nama pelanggan wajib diisi.', 'danger')
        else:
            try:
                Customer.update(id=customer_id, name=name, phone=phone)
                flash('Data pelanggan berhasil diperbarui.', 'success')
                return redirect(url_for('admin.customers_list'))
            except Exception as e:
                if 'uq_customers_phone' in str(e):
                    flash('Nomor telepon sudah terdaftar untuk pelanggan lain.', 'danger')
                else:
                    flash('Terjadi kesalahan. Silakan coba lagi.', 'danger')
            
    return render_template('admin/customer_form.html', customer=customer)

@bp.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def customer_delete(customer_id):
    require_admin()
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if customer has any transactions
    transaction_count = Transaction.query.filter_by(customer_id=customer.id).count()
    if transaction_count > 0:
        flash(f'Pelanggan tidak dapat dihapus karena memiliki {transaction_count} transaksi.', 'danger')
        return redirect(url_for('admin.customers_list'))
        
    try:
        Customer.delete(id=customer_id)
        flash('Data pelanggan berhasil dihapus.', 'success')
    except Exception as e:
        flash('Terjadi kesalahan saat menghapus data.', 'danger')
        
    return redirect(url_for('admin.customers_list'))

# ====== DISCOUNT RULES MANAGEMENT =======
@bp.route('/discounts')
@login_required
def discounts_list():
    require_admin()
    rules = DiscountRule.query.order_by(DiscountRule.start_date.desc()).all()
    return render_template('admin/discounts_list.html', rules=rules)

@bp.route('/discounts/new', methods=['GET', 'POST'])
@login_required
def discount_create():
    require_admin()
    if request.method == 'POST':
        name = request.form['name'].strip()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        discount_type = request.form['discount_type']
        value = int(request.form['value'])
        is_active = request.form.get('is_active') == 'on'
        rule = DiscountRule(
            name=name,
            start_date=start_date,
            end_date=end_date,
            discount_type=discount_type,
            value=value,
            is_active=is_active,
            created_at=date.today(),
            updated_at=date.today()
        )
        db.session.add(rule)
        db.session.commit()
        flash('Diskon berhasil ditambahkan.', 'success')
        return redirect(url_for('admin.discounts_list'))
    return render_template('admin/discount_form.html', rule=None)

@bp.route('/discounts/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def discount_edit(rule_id):
    require_admin()
    rule = DiscountRule.query.get_or_404(rule_id)
    if request.method == 'POST':
        rule.name = request.form['name'].strip()
        rule.start_date = request.form['start_date']
        rule.end_date = request.form['end_date']
        rule.discount_type = request.form['discount_type']
        rule.value = int(request.form['value'])
        rule.is_active = request.form.get('is_active') == 'on'
        rule.updated_at = date.today()
        db.session.commit()
        flash('Diskon berhasil diperbarui.', 'success')
        return redirect(url_for('admin.discounts_list'))
    return render_template('admin/discount_form.html', rule=rule)

@bp.route('/discounts/<int:rule_id>/delete', methods=['POST'])
@login_required
def discount_delete(rule_id):
    require_admin()
    rule = DiscountRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Diskon berhasil dihapus.', 'success')
    return redirect(url_for('admin.discounts_list'))