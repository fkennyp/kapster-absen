import re, os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, make_response, abort, current_app
from flask_login import login_required, current_user
from flask_mail import Message, Mail
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from models import db, Service, Transaction, TransactionItem, tznow, Attendance, Customer, DiscountRule
from config import Config
from datetime import timedelta, datetime
from functools import wraps 
from zoneinfo import ZoneInfo


bp = Blueprint('sales', __name__, url_prefix='/sales')

@bp.route('/phone-autocomplete')
@login_required
def phone_autocomplete():
    """Endpoint untuk autocomplete nomor HP dari transaksi yang pernah ada"""
    q = request.args.get('q', '').strip()
    # Ambil semua nomor HP unik dari tabel Customer, filter by q jika ada
    query = db.session.query(Customer.phone).filter(Customer.phone != None)
    if q:
        query = query.filter(Customer.phone.like(f"%{q}%"))
    phones = query.distinct().order_by(Customer.phone.asc()).limit(15).all()
    return {'phones': [p[0] for p in phones if p[0]]}
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Jakarta"))
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

def require_on_shift(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        # admin bebas akses
        if current_user.role != "kapster":
            return view(*args, **kwargs)

        today_local = datetime.now(TZ).date()
        att = Attendance.query.filter_by(user_id=current_user.id, date=today_local).first()

        if not att or not getattr(att, "check_in", None):
            flash("Kamu belum check-in. Silakan check-in dulu ya.", "warning")
            return redirect(url_for("attendance.check_in"))

        if getattr(att, "check_out", None):
            flash("Kamu sudah check-out, transaksi sudah ditutup.", "warning")
            return redirect(url_for("attendance.check_in"))

        return view(*args, **kwargs)
    return wrapper



@bp.route('/new', methods=['GET', 'POST'])
@require_on_shift
def new_sale():
    # --- VALIDASI ABSEN UNTUK KAPSTER ---
    if current_user.role == "kapster":
        today_local = datetime.now(TZ).date()
        att = Attendance.query.filter_by(user_id=current_user.id, date=today_local).first()

        # belum pernah check-in hari ini
        if not att or not att.check_in:
            flash("Kamu belum check-in, transaksi belum bisa dibuat.", "danger")
            # arahkan ke endpoint yang ADA: 'attendance.check_in'
            return redirect(url_for("attendance.my_attendance"))

        # sudah check-out → blok
        if att.check_out:
            flash("Kamu sudah check-out, transaksi tidak bisa dibuat lagi.", "danger")
            # boleh tetap arahkan ke halaman absen (check-in page) biar user paham konteks
            return redirect(url_for("attendance.my_attendance"))
    # --- /VALIDASI ---
    
    services = Service.query.filter_by(is_active=True).order_by(Service.name.asc()).all()
    # Ambil diskon aktif (periode valid & is_active)
    today = tznow().date()
    discounts = DiscountRule.query.filter(
        DiscountRule.is_active == True,
        DiscountRule.start_date <= today,
        DiscountRule.end_date >= today
    ).order_by(DiscountRule.name.asc()).all()

    customer_phone = None
    customer_name = None


    if request.method == 'POST':
        # --- ambil input ---
        ids = request.form.getlist('service_id')
        qtys = request.form.getlist('qty')
        pay_type = (request.form.get('payment_type') or 'cash').lower()
        cash_given_raw = request.form.get('cash_given')  # boleh kosong untuk non-cash
        discount_id = request.form.get('discount')
        discount_type = 'none'
        discount_val = 0
        discount_name = None
        if discount_id:
            rule = DiscountRule.query.filter_by(id=discount_id).first()
            if rule:
                discount_type = rule.discount_type
                discount_val = rule.value
                discount_name = rule.name
        customer_name = (request.form.get('customer_name') or '').strip()
        customer_email = request.form.get('customer_email') or None
        customer_phone = (request.form.get('customer_phone') or '').strip()
        barber_name = Config.BARBER_NAME

        # --- validasi 1: nama wajib ---
        if not customer_name:
            flash('Nama pelanggan harus diisi.', 'danger')
            return render_template('sale_new.html', services=services, discounts=discounts), 400

        # --- validasi email kalau diisi ---
        if customer_email and not EMAIL_RE.fullmatch(customer_email):
            flash("Format email customer tidak valid.", "danger")
            return render_template('sale_new.html', services=services, discounts=discounts), 400


        # --- bangun item & hitung subtotal ---
        items = []
        subtotal = 0
        for sid, q in zip(ids, qtys):
            try:
                q = int(q or 0)
            except ValueError:
                q = 0
            if q <= 0:
                continue
            svc = Service.query.get(int(sid))
            if not svc or not svc.is_active:
                continue
            line_total = svc.price * q
            subtotal += line_total
            items.append((svc, q, svc.price, line_total))

        # --- ambil diskon (nominal/persen) ---
        if discount_type == 'persen':
            discount = int(subtotal * discount_val / 100)
        elif discount_type == 'nominal':
            discount = discount_val
        else:
            discount = 0
        if discount < 0:
            discount = 0
        if discount > subtotal:
            discount = subtotal

        total = subtotal - discount

        # --- validasi 2: harus ada minimal 1 layanan ---

        if subtotal == 0 or not items:
            flash('Pilih minimal 1 layanan dengan qty > 0.', 'danger')
            return render_template('sale_new.html', services=services, discounts=discounts), 400

        # --- validasi 3: kalau cash, nominal >= total ---
        cash_val = None
        change = 0
        if pay_type == 'cash':
            try:
                cash_val = int(cash_given_raw or '0')
            except ValueError:
                cash_val = 0

            if cash_val <= 0 or cash_val < total:
                flash('Jumlah yang dibayarkan masih kurang dari total setelah diskon.', 'danger')
                return render_template('sale_new.html', services=services, discounts=discounts), 400

            change = cash_val - total
        else:
            cash_val = None
            change = 0

        # --- buat kode invoice ---
        now_local = tznow()  # sudah timezone-aware sesuai Config
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)

        # cari urutan terakhir hari ini lalu +1
        max_seq = db.session.query(db.func.max(Transaction.invoice_seq)).filter(
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end
        ).scalar()

        next_seq = (max_seq or 0) + 1
        invoice_code = f"INV-{now_local.strftime('%d/%m/%Y')}-{next_seq:03d}"

        # --- resolve CUSTOMER ---
        cust = None
        if customer_phone:
            cust = Customer.query.filter_by(phone=customer_phone).first()
        elif customer_name:
            # fallback by name jika phone kosong (boleh ada duplikat nama; kita ambil yang pertama)
            cust = Customer.query.filter_by(name=customer_name).first()

        if not cust:
            # create baru
            cust = Customer(
                name=customer_name or "(Tanpa Nama)",
                phone=customer_phone if customer_phone else None,
                created_at=tznow(),
                updated_at=tznow(),
            )
            db.session.add(cust)
            db.session.flush()  # dapatkan cust.id

        # hitung visit_number: jumlah transaksi sebelumnya + 1
        prev_count = db.session.query(db.func.count(Transaction.id))\
            .filter(Transaction.customer_id == cust.id).scalar() or 0
        visit_number = prev_count + 1
        cust.touch()  # update updated_at

    # --- simpan transaksi ---
        tx = Transaction(
            user_id=current_user.id,
            barber_name=barber_name,
            customer_name=customer_name,
            customer_email=customer_email,
            payment_type=pay_type,
            total=total,
            discount=discount,
            discount_name=discount_name,
            cash_given=cash_val,
            change_amount=change,
            created_at=tznow(),
            invoice_seq=next_seq,
            invoice_code=invoice_code,
            customer_id=cust.id,
            customer_phone=cust.phone,
            visit_number=visit_number,
        )
        db.session.add(tx)
        db.session.flush()  # dapatkan tx.id

        for svc, q, price_each, line_total in items:
            db.session.add(TransactionItem(
                transaction_id=tx.id,
                service_id=svc.id,
                qty=q,
                price_each=price_each,
                line_total=line_total
            ))

        db.session.commit()

    if request.method == 'POST':
        flash(f"Transaksi #{tx.id} berhasil dibuat.", "success")
        pdf_url = url_for('sales.receipt_pdf', tx_id=tx.id)
        return render_template(
            'sales/after_create.html',
            pdf_url=url_for('sales.receipt_pdf', tx_id=tx.id),
            redirect_url=url_for('sales.new_sale'),
            tx_id=tx.id
        )
    # GET render form
    return render_template('sale_new.html', services=services, discounts=discounts)


@bp.route('/receipt/<int:tx_id>.pdf')
@login_required
def receipt_pdf(tx_id):
    # --- ambil transaksi & auth ---
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.role != 'admin' and current_user.id != tx.user_id:
        abort(403)

    # --- nama file pakai nomor invoice (sanitize) ---
    inv = tx.invoice_code or f"INV-{tx.id}"
    safe_inv = re.sub(r'[^A-Za-z0-9._-]+', '-', inv)

    # --- pilih lebar roll ---
    try:
        width_mm = int(request.args.get('w', 80))
        width_mm = 58 if width_mm == 58 else 80
    except Exception:
        width_mm = 80
    page_w = width_mm * mm

    # --- hitung tinggi halaman & render PDF ---
    header_lines = 5 + (1 if tx.customer_name else 0)
    item_lines   = max(1, len(tx.items))
    total_lines  = 1 + (2 if (tx.payment_type == 'cash' and tx.cash_given is not None) else 0)
    footer_lines = 1

    line_h = 5 * mm
    top_margin = 6 * mm
    bottom_margin = 8 * mm
    est_h = top_margin + (header_lines + item_lines + total_lines + footer_lines) * line_h + bottom_margin
    page_h = max(est_h, 120 * mm)

    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=(page_w, page_h))

    x_l = 5 * mm
    x_r = page_w - 5 * mm
    y   = page_h - 8 * mm

    def draw(txt, sz=9, bold=False, x=None):
        nonlocal y
        p.setFont("Helvetica-Bold" if bold else "Helvetica", sz)
        p.drawString(x if x is not None else x_l, y, str(txt))
        y -= line_h

    def draw_r(txt, sz=9, bold=False, xr=None):
        nonlocal y
        p.setFont("Helvetica-Bold" if bold else "Helvetica", sz)
        p.drawRightString(xr if xr is not None else x_r, y, str(txt))
        y -= line_h

    # --- header ---
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(page_w/2, y, tx.barber_name or Config.BARBER_NAME); y -= line_h
    p.setFont("Helvetica", 9)

    code = tx.invoice_code or ("INV-" + tx.created_at.strftime("%d/%m/%Y") + "-XXX")
    draw(f"Invoice : {code}")
    draw(f"Tanggal : {tx.created_at.strftime('%d-%m-%Y %H:%M:%S')}")
    draw(f"Kapster : {tx.user.name}")
    if tx.customer_name:
        draw(f"Pelanggan : {tx.customer_name}")
    if getattr(tx, "visit_number", None):
        draw(f"Kunjungan ke : {tx.visit_number}")
    draw(f"Pembayaran : {tx.payment_type.upper()}")
    p.line(x_l, y, x_r, y); y -= line_h


    # --- items ---
    p.setFont("Helvetica-Bold", 9)
    p.drawString(x_l, y, "Layanan")
    p.drawRightString(x_r, y, "Subtotal"); y -= line_h
    p.setFont("Helvetica", 9)
    for it in tx.items:
        name = (it.service.name or "")[:24] if width_mm == 58 else (it.service.name or "")[:32]
        p.drawString(x_l, y, f"{name}")
        p.drawRightString(x_r, y, f"{it.qty}×{it.price_each:,}  =  {it.line_total:,}")
        y -= line_h

    p.line(x_l, y, x_r, y); y -= line_h

    subtotal = (tx.total or 0) + (tx.discount or 0)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_l, y, "Subtotal")
    p.drawRightString(x_r, y, f"Rp {subtotal:,}"); y -= line_h
    if (tx.discount or 0) > 0:
        p.setFont("Helvetica-Bold", 10)
        if getattr(tx, 'discount_name', None):
            p.drawString(x_l, y, f"Diskon ({tx.discount_name})")
        else:
            p.drawString(x_l, y, "Diskon")
        p.drawRightString(x_r, y, f"-Rp {tx.discount:,}"); y -= line_h
    p.setFont("Helvetica-Bold", 10)
    p.drawString(x_l, y, "TOTAL")
    p.drawRightString(x_r, y, f"Rp {tx.total:,}"); y -= line_h

    if tx.payment_type == 'cash' and tx.cash_given is not None:
        p.setFont("Helvetica", 9)
        p.drawString(x_l, y, "Dibayar")
        p.drawRightString(x_r, y, f"Rp {tx.cash_given:,}"); y -= line_h
        p.drawString(x_l, y, "Kembalian")
        p.drawRightString(x_r, y, f"Rp {tx.change_amount:,}"); y -= line_h

    y -= (line_h / 2)
    p.setFont("Helvetica", 8)
    p.drawCentredString(page_w/2, y, "Terima kasih"); y -= line_h

    p.showPage()
    p.save()
    buf.seek(0)
    pdf_data = buf.getvalue()  # untuk email; tidak mengubah posisi pointer

    if tx.customer_email:
        msg = Message(
            subject=f"Invoice {tx.invoice_code} - Putera Barbershop",
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[tx.customer_email]
        )
        msg.body = (
            f"Halo {tx.customer_name},\n\n"
            f"Terima kasih sudah berkunjung ke Putera Barbershop.\n"
            f"Berikut kami lampirkan invoice {tx.invoice_code}."
        )
        msg.attach(f"{tx.invoice_code}.pdf", "application/pdf", pdf_data)
        mail = current_app.extensions.get("mail")
        if mail is not None:
            mail.send(msg)

    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_inv}.pdf",
        max_age=0,
    )

    
@bp.route('/customer-visits')
@login_required
def customer_visits():
    """Endpoint untuk mendapatkan jumlah kunjungan customer berdasarkan nomor HP"""
    phone = request.args.get('phone', '').strip()
    print(f"[DEBUG] /customer-visits called with phone: '{phone}'")
    if not phone:
        print("[DEBUG] No phone provided, returning 0 visits")
        return {'visits': 0}
    try:
        prev_count = db.session.query(db.func.count(Transaction.id))\
            .filter(Transaction.customer_phone == phone).scalar() or 0
        print(f"[DEBUG] Found {prev_count} visits for phone '{phone}'")
        return {'visits': prev_count}
    except Exception as e:
        print(f"[ERROR] Error in customer_visits: {e}")
        return {'visits': 0}