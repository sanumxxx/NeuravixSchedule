from app import create_app, db
from app.models.user import User

# Создаем экземпляр приложения
app = create_app()

# Создаем контекст приложения
with app.app_context():
    # Создаем нового пользователя-администратора
    admin = User(username='admin',  # Имя пользователя для входа
        email='admin@example.com',  # Email администратора
        is_admin=True  # Устанавливаем права администратора
    )

    # Устанавливаем пароль (он будет автоматически захеширован)
    admin.set_password('111')  # Замените на желаемый пароль

    # Добавляем пользователя в сессию базы данных
    db.session.add(admin)

    # Сохраняем изменения в базе данных
    db.session.commit()

    # Проверяем, что пользователь создан
    created_admin = User.query.filter_by(username='admin').first()
    if created_admin:
        print("Администратор успешно создан!")
        print(f"Имя пользователя: {created_admin.username}")
        print(f"Email: {created_admin.email}")
        print(f"Является администратором: {created_admin.is_admin}")
