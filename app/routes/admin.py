from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.models.user import User
from app import db
from functools import wraps
from app.services.parser import TimetableParser
from app.forms.timetable import TimetableUploadForm
from app.services.schedule_service import ScheduleService
from app.models.schedule import Schedule
from sqlalchemy import func
from app.services.parser import TimetableParser as parser
import psycopg2
from app.config.settings import Settings
from datetime import datetime

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


@admin.route('/timetable/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_timetable():
    if request.method == 'GET':
        return render_template('admin/upload_timetable.html')

    if 'timetable_files' not in request.files:
        return jsonify({'success': False, 'error': 'Файлы не выбраны'})

    semester = request.form.get('semester')
    if not semester:
        return jsonify({'success': False, 'error': 'Семестр не выбран'})

    try:
        semester = int(semester)
        if semester not in [1, 2]:
            return jsonify({'success': False, 'error': 'Некорректный номер семестра'})
    except ValueError:
        return jsonify({'success': False, 'error': 'Некорректный формат семестра'})

    files = request.files.getlist('timetable_files')
    show_empty_weeks = request.form.get('show_empty_weeks') == 'on'
    skip_errors = request.form.get('skip_errors') == 'on'
    conflict_action = request.form.get('conflict_action')

    total_processed = 0
    total_added = 0
    all_errors = []

    try:
        # Собираем все занятия из всех файлов
        all_lessons = []
        for file in files:
            try:
                print(f"\nОбработка файла: {file.filename}")
                parser = TimetableParser(show_empty_weeks=show_empty_weeks)
                lessons = parser.parse_file(file)
                # Добавляем семестр к каждому занятию
                for lesson in lessons:
                    lesson['semester'] = semester
                all_lessons.extend(lessons)
                total_processed += 1
            except Exception as e:
                error_message = f"Ошибка в файле {file.filename}: {str(e)}"
                if not skip_errors:
                    return jsonify({'success': False, 'error': error_message})
                all_errors.append(error_message)

        if not all_lessons:
            return jsonify({'success': False, 'error': 'Нет данных для загрузки'})

        # Если это первичная загрузка файлов (нет действия с конфликтом)
        if not conflict_action:
            conflicts = ScheduleService.check_conflicts(all_lessons, semester)
            if conflicts:
                return jsonify({
                    'success': False,
                    'conflicts': conflicts
                })

            # Если конфликтов нет, сохраняем все занятия
            added, _, _ = ScheduleService.save_schedule(all_lessons, semester)
            total_added = added
        else:
            # Обрабатываем конфликты
            if conflict_action == 'replace':
                # Получаем номера недель из занятий
                week_numbers = {lesson['week_number'] for lesson in all_lessons if lesson['week_number']}
                for week_number in week_numbers:
                    ScheduleService.delete_week(week_number, semester)
                # Сохраняем новые занятия
                added, _, _ = ScheduleService.save_schedule(all_lessons, semester)
                total_added = added

            elif conflict_action == 'merge':
                week_numbers = {lesson['week_number'] for lesson in all_lessons if lesson['week_number']}
                for week_number in week_numbers:
                    week_lessons = [l for l in all_lessons if l['week_number'] == week_number]
                    ScheduleService.merge_schedules(week_lessons, week_number, semester)
                total_added = len(all_lessons)

            elif conflict_action == 'skip':
                # Получаем существующие недели
                existing_weeks = {week[0] for week in
                                db.session.query(Schedule.week_number)
                                .filter_by(semester=semester)
                                .all()}
                # Фильтруем неконфликтные занятия
                non_conflicting_lessons = [
                    lesson for lesson in all_lessons
                    if lesson['week_number'] not in existing_weeks
                ]
                if non_conflicting_lessons:
                    added, _, _ = ScheduleService.save_schedule(non_conflicting_lessons, semester)
                    total_added = added

        summary = (
            f"Загрузка завершена!\n"
            f"Обработано файлов: {total_processed}\n"
            f"Всего добавлено занятий: {total_added}"
        )

        if all_errors:
            summary += f"\nОшибок: {len(all_errors)}"

        return jsonify({
            'success': True,
            'message': summary,
            'errors': all_errors if all_errors else None
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Неожиданная ошибка: {str(e)}'
        })


@admin.route('/timetable/weeks', methods=['GET'])
@login_required
@admin_required
def get_loaded_weeks():
    try:
        weeks_data = db.session.query(
            Schedule.week_number,
            func.min(Schedule.date).label('start_date'),
            func.max(Schedule.date).label('end_date'),
            func.count(Schedule.id).label('lessons_count')
        ).group_by(Schedule.week_number).order_by(Schedule.week_number).all()

        loaded_weeks = [{
            'week_number': week.week_number,
            'start_date': week.start_date.strftime('%d.%m.%Y') if week.start_date else 'Нет данных',
            'end_date': week.end_date.strftime('%d.%m.%Y') if week.end_date else 'Нет данных',
            'lessons_count': week.lessons_count
        } for week in weeks_data]

        return jsonify(loaded_weeks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin.route('/timetable/week/<int:week_number>', methods=['DELETE'])
@login_required
@admin_required
def delete_week(week_number):
    try:
        # Проверяем CSRF-токен
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Invalid request'}), 400

        semester = request.args.get('semester')
        if not semester:
            return jsonify({'success': False, 'error': 'Семестр не указан'}), 400

        semester = int(semester)
        if semester not in [1, 2]:
            return jsonify({'success': False, 'error': 'Некорректный номер семестра'}), 400

        deleted_count = Schedule.query.filter_by(
            semester=semester,
            week_number=week_number
        ).delete()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Неделя {week_number} семестра {semester} успешно удалена (удалено {deleted_count} занятий)'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Ошибка при удалении недели: {str(e)}'
        }), 500


@admin.route('/timetable/weeks/list', methods=['GET'])
@login_required
@admin_required
def list_weeks():
    try:
        # Получаем список всех недель сгруппированных по семестрам
        loaded_weeks = db.session.query(
            Schedule.semester,
            Schedule.week_number,
            func.min(Schedule.date).label('start_date'),
            func.max(Schedule.date).label('end_date'),
            func.count(Schedule.id).label('lessons_count')
        ).group_by(
            Schedule.semester,
            Schedule.week_number
        ).order_by(
            Schedule.semester,
            Schedule.week_number
        ).all()

        weeks = [{
            'semester': week.semester,
            'week_number': week.week_number,
            'start_date': week.start_date.strftime('%d.%m.%Y') if week.start_date else 'Нет данных',
            'end_date': week.end_date.strftime('%d.%m.%Y') if week.end_date else 'Нет данных',
            'lessons_count': week.lessons_count
        } for week in loaded_weeks]

        return jsonify(weeks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin.route('/timetable/resolve-conflict', methods=['POST'])
@login_required
@admin_required
def resolve_conflict():
    data = request.get_json()
    if not data or 'weekNumber' not in data or 'action' not in data:
        return jsonify({'success': False, 'error': 'Неверные параметры'})

    week_number = data['weekNumber']
    action = data['action']

    try:
        if action == 'skip':
            return jsonify({
                'success': True,
                'message': 'Неделя пропущена'
            })

        elif action == 'replace':
            # Удаляем старые занятия
            Schedule.query.filter_by(week_number=week_number).delete()
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Неделя заменена'
            })

        elif action == 'merge':
            # В этом случае просто позволяем добавить новые занятия
            return jsonify({
                'success': True,
                'message': 'Недели объединены'
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Неизвестное действие'
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@admin.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_settings():
    if request.method == 'POST':
        try:
            new_settings = {
                "database": {
                    "host": request.form.get('db_host'),
                    "port": request.form.get('db_port'),
                    "name": request.form.get('db_name'),
                    "user": request.form.get('db_user'),
                    "password": request.form.get('db_password')
                },
                "academic_year": {
                    "first_semester": {
                        "start": request.form.get('first_semester_start'),
                        "end": request.form.get('first_semester_end')
                    },
                    "second_semester": {
                        "start": request.form.get('second_semester_start'),
                        "end": request.form.get('second_semester_end')
                    }
                }
            }

            # Validate dates
            try:
                for semester in ['first_semester', 'second_semester']:
                    datetime.strptime(new_settings['academic_year'][semester]['start'], '%Y-%m-%d')
                    datetime.strptime(new_settings['academic_year'][semester]['end'], '%Y-%m-%d')
            except ValueError:
                flash('Неверный формат даты. Используйте формат YYYY-MM-DD', 'error')
                return redirect(url_for('admin.manage_settings'))

            # Use save_settings instead of update_settings
            Settings.save_settings(new_settings)
            flash('Настройки успешно сохранены', 'success')

        except Exception as e:
            flash(f'Ошибка при сохранении настроек: {str(e)}', 'error')

        return redirect(url_for('admin.manage_settings'))

    current_settings = Settings.get_settings()
    return render_template('admin/settings.html', settings=current_settings)


@admin.route('/settings/academic', methods=['GET', 'POST'])
@login_required
@admin_required
def academic_settings():
    if request.method == 'POST':
        try:
            # Получаем все значения из формы
            slot_numbers = request.form.getlist('slot_numbers[]')
            slot_starts = request.form.getlist('slot_starts[]')
            slot_ends = request.form.getlist('slot_ends[]')

            # Формируем список временных слотов
            time_slots = []
            for i in range(len(slot_numbers)):
                time_slots.append({
                    "number": int(slot_numbers[i]),
                    "start": slot_starts[i],
                    "end": slot_ends[i]
                })

            # Сортируем слоты по номеру
            time_slots.sort(key=lambda x: x["number"])

            new_settings = {
                "academic_year": {
                    "first_semester": {
                        "start": request.form.get('first_semester_start'),
                        "end": request.form.get('first_semester_end')
                    },
                    "second_semester": {
                        "start": request.form.get('second_semester_start'),
                        "end": request.form.get('second_semester_end')
                    }
                },
                "time_slots": time_slots
            }

            # Обновляем настройки
            current_settings = Settings.get_settings()
            current_settings.update({
                "academic_year": new_settings["academic_year"],
                "time_slots": new_settings["time_slots"]
            })
            Settings.save_settings(current_settings)

            flash('Настройки учебного процесса успешно сохранены', 'success')
        except Exception as e:
            flash(f'Ошибка при сохранении настроек: {str(e)}', 'error')

        return redirect(url_for('admin.academic_settings'))

    return render_template('admin/academic_settings.html', settings=Settings.get_settings())


@admin.route('/settings/appearance', methods=['GET', 'POST'])
@login_required
@admin_required
def appearance_settings():
    if request.method == 'POST':
        try:
            minimal_style = 'minimal_style' in request.form
            mobile_view = 'mobile_view' in request.form

            new_settings = {
                "appearance": {
                    "timetable_colors": {
                        "л.": request.form.get('color_lecture'),
                        "лаб.": request.form.get('color_lab'),
                        "пр.": request.form.get('color_practice')
                    },
                    "minimal_style": minimal_style,
                    "mobile_view": mobile_view
                }
            }

            # Обновляем настройки
            current_settings = Settings.get_settings()
            # Удаляем старые настройки цветов, если они есть
            current_settings.pop('timetable_colors', None)
            # Обновляем настройки appearance
            if 'appearance' not in current_settings:
                current_settings['appearance'] = {}
            current_settings['appearance'].update(new_settings['appearance'])
            Settings.save_settings(current_settings)

            flash('Настройки оформления успешно сохранены', 'success')
        except Exception as e:
            flash(f'Ошибка при сохранении настроек: {str(e)}', 'error')

        return redirect(url_for('admin.appearance_settings'))

    return render_template(
        'admin/appearance_settings.html',
        settings=Settings.get_settings()
    )


@admin.route('/settings/database', methods=['GET', 'POST'])
@login_required
@admin_required
def database_settings():
    if request.method == 'POST':
        try:
            new_settings = {
                "database": {
                    "host": request.form.get('db_host'),
                    "port": request.form.get('db_port'),
                    "name": request.form.get('db_name'),
                    "user": request.form.get('db_user'),
                    "password": request.form.get('db_password')
                }
            }

            # Обновляем только настройки базы данных
            current_settings = Settings.get_settings()
            current_settings.update(new_settings)
            Settings.save_settings(current_settings)

            flash('Настройки базы данных успешно сохранены', 'success')
        except Exception as e:
            flash(f'Ошибка при сохранении настроек: {str(e)}', 'error')

        return redirect(url_for('admin.database_settings'))

    return render_template('admin/database_settings.html', settings=Settings.get_settings())

