from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.models.user import User
from app import db
from functools import wraps
from app.services.parser import TimetableParser
from app.forms.timetable import TimetableUploadForm
from app.services.schedule_service import ScheduleService

admin = Blueprint('admin', __name__, url_prefix='/admin')


# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен. Требуются права администратора.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function


@admin.route('/')
@login_required
@admin_required
def index():
    """Главная страница административной панели"""
    return render_template('admin/index.html')


@admin.route('/users')
@login_required
@admin_required
def users():
    """Страница управления пользователями"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@admin.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Создание нового пользователя через модальное окно"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = 'is_admin' in request.form
        is_editor = 'is_editor' in request.form
        is_headDepartment = 'is_headDepartment' in request.form

        # Проверяем существование пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'error')
            return redirect(url_for('admin.users'))

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('admin.users'))

        try:
            # Создаем нового пользователя
            user = User(
                username=username,
                email=email,
                is_admin=is_admin,
                is_editor=is_editor,
                is_headDepartment=is_headDepartment
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Пользователь успешно создан', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при создании пользователя', 'error')

        return redirect(url_for('admin.users'))


@admin.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    """
    Маршрут для редактирования существующего пользователя.
    Получает id пользователя и обрабатывает как GET-запросы для отображения формы,
    так и POST-запросы для сохранения изменений.
    """
    user = User.query.get_or_404(id)

    # Защита от редактирования последнего администратора
    if user.is_admin and User.query.filter_by(is_admin=True).count() == 1:
        is_last_admin = True
    else:
        is_last_admin = False

    if request.method == 'POST':
        # Получаем данные из формы
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('password')

        # Проверяем, не занято ли имя пользователя другим пользователем
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != id:
            flash('Пользователь с таким именем уже существует', 'error')
            return redirect(url_for('admin.edit_user', id=id))

        # Обновляем данные пользователя
        user.username = username
        user.email = email

        # Обновляем пароль только если он был предоставлен
        if new_password:
            user.set_password(new_password)

        # Обновляем роли, но защищаем от удаления последнего администратора
        if not is_last_admin:
            user.is_admin = 'is_admin' in request.form
        user.is_editor = 'is_editor' in request.form
        user.is_headDepartment = 'is_headDepartment' in request.form

        try:
            db.session.commit()
            flash('Пользователь успешно обновлен', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при обновлении пользователя', 'error')

    return render_template('admin/edit_user.html', user=user, is_last_admin=is_last_admin)


@admin.route('/timetable', methods=['GET'])
@login_required
@admin_required
def timetable():
    form = TimetableUploadForm()
    return render_template('admin/timetable.html', form=form)


@admin.route('/timetable/upload', methods=['POST'])
@login_required
@admin_required
def upload_timetable():
    """
    Обработчик загрузки файлов расписания.
    Принимает файлы JSON, обрабатывает их и сохраняет в базу данных.
    """
    if 'timetable_files' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Файлы не выбраны'
        })

    files = request.files.getlist('timetable_files')
    show_empty_weeks = request.form.get('show_empty_weeks') == 'on'
    skip_errors = request.form.get('skip_errors') == 'on'

    parser = TimetableParser(show_empty_weeks=show_empty_weeks)
    schedule_service = ScheduleService()

    total_processed = 0
    total_added = 0
    total_updated = 0
    errors = []

    try:
        for file in files:
            try:
                # Для каждого файла пытаемся его обработать
                current_file = f"Обработка файла: {file.filename}"
                print(current_file)

                # Парсим файл и получаем список занятий
                lessons = parser.parse_file(file)
                print(f"Найдено занятий: {len(lessons)}")

                # Сохраняем занятия в базу данных
                added, updated = schedule_service.save_schedule(lessons)
                total_added += added
                total_updated += updated
                total_processed += 1

            except Exception as e:
                error_message = f"Ошибка в файле {file.filename}: {str(e)}"
                print(error_message)
                errors.append(error_message)
                if not skip_errors:
                    return jsonify({
                        'success': False,
                        'error': error_message
                    })

        # Формируем сообщение об успешной загрузке
        success_message = (
            f"Загрузка завершена успешно!\n"
            f"Обработано файлов: {total_processed}\n"
            f"Добавлено новых занятий: {total_added}\n"
            f"Обновлено существующих: {total_updated}"
        )

        if errors:
            success_message += f"\n\nФайлы с ошибками ({len(errors)}):\n"
            success_message += "\n".join(errors)

        return jsonify({
            'success': True,
            'message': success_message,
            'redirect': url_for('admin.timetable')
        })

    except Exception as e:
        error_message = f"Неожиданная ошибка при обработке файлов: {str(e)}"
        print(error_message)
        return jsonify({
            'success': False,
            'error': error_message
        })