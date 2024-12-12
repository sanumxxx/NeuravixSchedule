from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

from .config.settings import Settings

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
# Импортируем модель User здесь для избежания циклических импортов
from app.models.user import User


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)

    csp = {'default-src': ['\'self\''],
           'script-src': ['\'self\'', '\'unsafe-inline\'', '\'unsafe-eval\'',
                          'cdnjs.cloudflare.com', 'cdn.tailwindcss.com', 'cdn.jsdelivr.net'],
           'style-src': ['\'self\'', '\'unsafe-inline\'', 'cdn.jsdelivr.net', 'fonts.googleapis.com'],
           'img-src': ['\'self\'', 'data:', '*'],
           'font-src': ['\'self\'', 'fonts.gstatic.com'],
           'connect-src': ['\'self\'', 'cdn.jsdelivr.net']}

    @app.context_processor
    def utility_processor():
        def get_settings():
            from app.config.settings import Settings
            return Settings.get_settings()

        def get_lesson_color(lesson_type):
            settings = get_settings()
            return settings.get('appearance', {}).get('timetable_colors', {}).get(lesson_type, '#2C3E50')

        return dict(get_settings=get_settings, get_lesson_color=get_lesson_color)

    Talisman(app, content_security_policy=csp, force_https=False)

    # Загружаем настройки
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.get_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }
    app.config['SECRET_KEY'] = 'your-secret-key'  # Замените на реальный секретный ключ

    # Инициализация расширений
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Регистрация blueprints
    from app.routes.main import main
    from app.routes.admin import admin
    from app.routes.auth import auth
    from app.routes.api import api
    from app.routes.reports import reports
    app.register_blueprint(reports)

    app.register_blueprint(main)
    app.register_blueprint(admin)
    app.register_blueprint(auth)
    app.register_blueprint(api)

    # Обработка исключений при подключении к базе данных
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"Ошибка при подключении к базе данных: {e}")
            # Вы можете создать пользовательскую страницу для отображения ошибок
            @app.route('/')
            def db_error():
                return render_template('errors/db_error.html', error=e), 500

    return app
