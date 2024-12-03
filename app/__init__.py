# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from .config.settings import Settings
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

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

    csp = {
        'default-src': ['\'self\''],
        'script-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            '\'unsafe-eval\'',  # Для некоторых внешних скриптов
            'cdnjs.cloudflare.com',
            'cdn.tailwindcss.com',
            'cdn.jsdelivr.net'
        ],
        'style-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'cdn.jsdelivr.net',
            'fonts.googleapis.com'
        ],
        'img-src': [
            '\'self\'',
            'data:',
            '*'
        ],
        'font-src': [
            '\'self\'',
            'fonts.gstatic.com'
        ],
        'connect-src': [
            '\'self\'',
            'cdn.jsdelivr.net'
        ]
    }

    Talisman(app, content_security_policy=csp, force_https=False)

    # Загружаем настройки
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.get_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

    app.register_blueprint(main)
    app.register_blueprint(admin)
    app.register_blueprint(auth)
    app.register_blueprint(api)

    # Создание всех таблиц базы данных
    with app.app_context():
        db.create_all()

    return app