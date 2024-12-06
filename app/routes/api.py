# app/routes/api.py

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import func

from app import db
from app.models.schedule import Schedule
from ..config.settings import Settings

api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/weeks')
def get_weeks():
    """Получение списка недель для выбранного семестра"""
    try:
        semester = request.args.get('semester', type=int)
        if not semester:
            return jsonify({'error': 'Не указан семестр'}), 400

        weeks = db.session.query(Schedule.week_number).filter_by(semester=semester).distinct().order_by(
            Schedule.week_number).all()

        return jsonify([week[0] for week in weeks])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/current-semester')
def get_current_semester():
    """Получение текущего семестра на основе даты"""
    try:
        current_semester = Settings.get_current_semester()
        return jsonify({'semester': current_semester})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/schedule')
def get_schedule():
    """Получение расписания с фильтрацией по различным параметрам"""
    try:
        # Получаем параметры запроса
        semester = request.args.get('semester', type=int)
        week = request.args.get('week', type=int)
        schedule_type = request.args.get('type')
        value = request.args.get('value')

        print(f"Debug - Received params: semester={semester}, week={week}, type={schedule_type}, value={value}")

        # Проверяем наличие всех необходимых параметров
        if not all([semester, week, schedule_type, value]):
            return jsonify({'error': 'Не все параметры указаны'}), 400

        try:
            # Базовый запрос
            query = Schedule.query.filter_by(semester=semester, week_number=week)

            # Применяем фильтр в зависимости от типа расписания
            if schedule_type == 'group':
                query = query.filter_by(group_name=value)
            elif schedule_type == 'teacher':
                query = query.filter_by(teacher_name=value)
            elif schedule_type == 'room':
                query = query.filter_by(auditory=value)
            else:
                return jsonify({'error': 'Неверный тип расписания'}), 400

            # Получаем расписание, сортируем по дням и парам
            schedule_items = query.order_by(Schedule.weekday, Schedule.time_start).all()

            # Формируем данные для ответа
            schedule_data = []
            for item in schedule_items:
                try:
                    schedule_data.append({'id': item.id, 'weekday': item.weekday, 'day_name': item.get_day_name(),
                        'lesson_number': item.get_lesson_number(), 'time_slot': item.get_time_slot(),
                        'subject': item.subject, 'teacher_name': item.teacher_name, 'auditory': item.auditory,
                        'group_name': item.group_name, 'lesson_type': item.lesson_type,
                        'date': item.date.strftime('%d.%m.%Y') if item.date else None})
                except Exception as e:
                    print(f"Debug - Error processing schedule item: {e}")
                    continue

            # Генерируем HTML с помощью шаблона
            html = render_template('timetable/schedule_table.html', schedule=schedule_items,
                schedule_type=schedule_type, value=value)

            return jsonify({'success': True, 'html': html, 'data': schedule_data})

        except Exception as e:
            print(f"Debug - Error processing query: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        print(f"Debug - Error in get_schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/schedule/days')
def get_schedule_days():
    """Получение списка дней с занятиями"""
    try:
        semester = request.args.get('semester', type=int)
        week = request.args.get('week', type=int)

        if not all([semester, week]):
            return jsonify({'error': 'Не указан семестр или неделя'}), 400

        days = db.session.query(Schedule.day_number, func.count(Schedule.id).label('lessons_count')).filter_by(
            semester=semester, week_number=week).group_by(Schedule.day_number).order_by(Schedule.day_number).all()

        return jsonify([{'day_number': day.day_number, 'lessons_count': day.lessons_count} for day in days])

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/search/groups')
def search_groups():
    """Поиск групп по частичному совпадению"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        groups = db.session.query(Schedule.group_name).filter(
            Schedule.group_name.ilike(f'%{query}%')).distinct().order_by(Schedule.group_name).limit(10).all()

        return jsonify([group[0] for group in groups])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/search/teachers')
def search_teachers():
    """Поиск преподавателей по частичному совпадению"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        teachers = db.session.query(Schedule.teacher_name).filter(Schedule.teacher_name.ilike(f'%{query}%')).filter(
            Schedule.teacher_name != '').distinct().order_by(Schedule.teacher_name).limit(10).all()

        return jsonify([teacher[0] for teacher in teachers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/search/rooms')
def search_rooms():
    """Поиск аудиторий по частичному совпадению"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        rooms = db.session.query(Schedule.auditory).filter(Schedule.auditory.ilike(f'%{query}%')).filter(
            Schedule.auditory != '').distinct().order_by(Schedule.auditory).limit(10).all()

        return jsonify([room[0] for room in rooms])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
