from flask import Flask, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import db, User, Attendance, tznow
from config import Config
from auth import bp as auth_bp, login_manager
from attendance import bp as attendance_bp
from admin import bp as admin_bp
from reports import bp as reports_bp
from sales import bp as sales_bp
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # DB
    db.init_app(app)

    # Login
    login_manager.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    # For reverse proxy (nginx)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    @app.context_processor
    def inject_globals():
        return {'current_user': current_user}

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('attendance.my_attendance'))
        return redirect(url_for('auth.login'))

    @app.cli.command('bootstrap-admin')
    def bootstrap_admin():
        """Create initial admin if not exists (uses env variables)."""
        from flask import current_app
        with app.app_context():
            username = Config.ADMIN_USERNAME
            user = User.query.filter_by(username=username).first()
            if user:
                print("Admin already exists:", username)
                return
            u = User(name=Config.ADMIN_NAME, username=username, role='admin')
            u.set_password(Config.ADMIN_PASSWORD)
            db.session.add(u)
            db.session.commit()
            print("Admin created:", username)

    return app


app = create_app()
app.register_blueprint(sales_bp)