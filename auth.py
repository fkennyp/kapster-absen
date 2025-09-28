from werkzeug.security import check_password_hash
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User
import random, string
from werkzeug.security import generate_password_hash
from flask_mail import Message
from flask import current_app

bp = Blueprint('auth', __name__)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username, is_active_user=True).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('attendance.my_attendance'))
        flash('Invalid credentials or inactive user.', 'danger')
    return render_template('login.html')


# Forgot password route
@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    sent = False
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(username=username, is_active_user=True, email=email).first()
        if user:
            # Email cocok, reset password dan kirim email
            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            subject = "Reset Password - Putera Barbershop"
            body = f"Halo {username},\n\nPassword baru Anda: {new_password}\n\nSilakan login dan segera ganti password Anda."
            msg = Message(
                subject=subject,
                sender=current_app.config.get('MAIL_USERNAME', 'noreply@example.com'),
                recipients=[email]
            )
            msg.body = body
            mail = current_app.extensions.get('mail')
            if mail is not None:
                try:
                    mail.send(msg)
                except Exception as e:
                    print(f"Gagal mengirim email: {e}")
        # Jika user tidak ditemukan, tidak reset password, hanya tampilkan notifikasi
        sent = True
        flash('Password baru telah dikirim ke email Anda.', 'info')
    return render_template('forgot_password.html', sent=sent)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not check_password_hash(current_user.password_hash, old_password):
            flash('Password lama salah.', 'danger')
        elif not new_password or len(new_password) < 6:
            flash('Password baru minimal 6 karakter.', 'danger')
        elif new_password != confirm_password:
            flash('Konfirmasi password tidak cocok.', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password berhasil diubah.', 'success')
            return redirect(url_for('auth.change_password'))
    return render_template('change_password.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('auth.login'))
