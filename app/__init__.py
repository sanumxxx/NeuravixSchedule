from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    from .routes.main import main
    app.register_blueprint(main)
    from .routes.auth import auth
    app.register_blueprint(auth)
    from .routes.admin import admin
    app.register_blueprint(admin)
    app.config['SECRET_KEY'] = 'sanumxxx'

    # Здесь указываем данные для подключения к PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:111@localhost:5432/timetable'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    from app.models.user import User
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Указываем, куда перенаправлять для входа
    login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    from app.models.user import User


    return app
