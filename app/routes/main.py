# app/routes/main.py
from datetime import datetime, timedelta

from flask import render_template, request, Blueprint, jsonify, make_response, send_file
from sqlalchemy.sql.expression import func
import re
from app import db
from app.config.settings import Settings
from app.models.schedule import Schedule
from app.models.user import User

main = Blueprint('main', __name__, static_folder='static')


@main.route('/')
def index():
    # Получаем данные из базы данных
    groups = db.session.query(Schedule.group_name).distinct().order_by(Schedule.group_name).all()
    teachers = db.session.query(Schedule.teacher_name).filter(Schedule.teacher_name != '').distinct().order_by(
        Schedule.teacher_name).all()
    rooms = db.session.query(Schedule.auditory).filter(Schedule.auditory != '').distinct().order_by(
        Schedule.auditory).all()

    groups = [group[0] for group in groups]
    teachers = [teacher[0] for teacher in teachers]
    rooms = [room[0] for room in rooms]

    # Определяем текущий семестр и неделю
    current_semester = Settings.get_current_semester()
    current_week = get_current_week()

    return render_template('index.html', groups=groups, teachers=teachers, rooms=rooms,
                           current_semester=current_semester, current_week=current_week)


# app/routes/main.py

@main.route('/yandex_63874f5319c0ae3b.html')
def yandex_verification():
    content = """
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        </head>
        <body>Verification: 63874f5319c0ae3b</body>
    </html>
    """
    response = make_response(content)
    response.headers['Content-Type'] = 'text/html'
    return response

@main.route('/manifest.json')
def manifest():
    return main.send_static_file('manifest.json')

@main.route('/service-worker.js')
def service_worker():
    response = make_response(main.send_static_file('service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@main.route('/timetable')
def schedule():
    schedule_type = request.args.get('type')
    value = request.args.get('value')

    # Определяем текущий семестр
    current_semester = Settings.get_current_semester()

    # Получаем семестр из параметров URL или используем текущий
    requested_semester = request.args.get('semester', current_semester, type=int)

    # Получаем все недели для запрошенного семестра
    weeks_data = db.session.query(
        Schedule.week_number,
        func.min(Schedule.date).label('start_date'),
        func.max(Schedule.date).label('end_date')
    ).filter_by(
        semester=requested_semester
    ).group_by(
        Schedule.week_number
    ).order_by(
        Schedule.week_number
    ).all()

    # Формируем список недель для выбранного семестра
    weeks = [week.week_number for week in weeks_data]

    # Определяем текущую/выбранную неделю
    current_week = None

    # Если неделя указана в URL, используем её
    if 'week' in request.args:
        current_week = int(request.args.get('week'))
    else:
        current_date = datetime.now().date()

        # Если смотрим текущий семестр, пытаемся найти текущую неделю
        if requested_semester == current_semester:
            for week in weeks_data:
                if week.start_date and week.end_date:
                    if week.start_date <= current_date <= week.end_date:
                        current_week = week.week_number
                        break

            # Если текущая дата не попадает ни в одну неделю,
            # находим ближайшую следующую неделю
            if not current_week and weeks_data:
                closest_future_week = None
                min_diff = timedelta.max

                for week in weeks_data:
                    if week.start_date:
                        diff = abs(week.start_date - current_date)
                        if diff < min_diff and week.start_date >= current_date:
                            min_diff = diff
                            closest_future_week = week.week_number

                if closest_future_week:
                    current_week = closest_future_week

        # Если неделя все еще не определена, берем первую доступную
        if not current_week and weeks:
            current_week = weeks[0]
        elif not current_week:
            current_week = 1

    # Получаем настройки семестров
    academic_settings = Settings.get_settings()['academic_year']
    semester_dates = {
        1: {
            'start': academic_settings['first_semester']['start'],
            'end': academic_settings['first_semester']['end']
        },
        2: {
            'start': academic_settings['second_semester']['start'],
            'end': academic_settings['second_semester']['end']
        }
    }

    today_weekday = datetime.now().isoweekday()
    settings = Settings.get_settings()

    return render_template(
        'timetable/index.html',
        current_semester=requested_semester,
        current_week=current_week,
        today_weekday=today_weekday,
        weeks=weeks,
        semester_dates=semester_dates,
        schedule_type=schedule_type,
        value=value,
        settings=settings,
        timedelta=timedelta
    )

@main.route('/api/schedule')
def get_schedule():
    schedule_type = request.args.get('type')
    value = request.args.get('value')
    semester = request.args.get('semester', type=int)
    week = request.args.get('week', type=int)

    if not all([schedule_type, value, semester, week]):
        return jsonify({'error': 'Missing required parameters'})

    try:
        # Получаем расписание
        schedule_filter = {
            'semester': semester,
            'week_number': week
        }

        if schedule_type == 'group':
            schedule_filter['group_name'] = value
        elif schedule_type == 'teacher':
            schedule_filter['teacher_name'] = value
        elif schedule_type == 'room':
            schedule_filter['auditory'] = value
        else:
            return jsonify({'error': 'Invalid schedule type'})

        schedule = Schedule.query.filter_by(**schedule_filter).all()

        # Рендерим HTML
        html = render_template(
            'timetable/schedule_table.html',
            schedule=schedule,
            schedule_type=schedule_type,
            value=value,
            timedelta=timedelta  # Передаем timedelta в шаблон
        )

        return jsonify({'html': html})

    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_current_week():
    """Определяет текущую неделю семестра"""
    try:
        settings = Settings.get_settings()
        current_semester = Settings.get_current_semester()
        today = datetime.now().date()

        # Получаем все недели текущего семестра
        weeks = db.session.query(
            Schedule.week_number,
            func.min(Schedule.date).label('start_date'),
            func.max(Schedule.date).label('end_date')
        ).filter_by(
            semester=current_semester
        ).group_by(
            Schedule.week_number
        ).order_by(
            Schedule.week_number
        ).all()

        if not weeks:
            return 1

        # Ищем текущую неделю по дате
        for week in weeks:
            if week.start_date and week.end_date:
                if week.start_date <= today <= week.end_date:
                    return week.week_number

        # Если текущая дата не попадает ни в одну неделю,
        # находим ближайшую следующую неделю
        closest_future_week = None
        min_diff = timedelta.max

        for week in weeks:
            if week.start_date:
                diff = abs(week.start_date - today)
                if diff < min_diff and week.start_date >= today:
                    min_diff = diff
                    closest_future_week = week.week_number

        if closest_future_week:
            return closest_future_week

        # Если не нашли подходящую неделю, возвращаем первую доступную
        return weeks[0].week_number if weeks else 1

    except Exception as e:
        print(f"Error determining current week: {e}")
        return 1


@main.route('/init_db_2025')
def create_admin():
    try:
        # Проверяем, существует ли уже админ
        existing_admin = User.query.filter_by(is_admin=True).first()
        if existing_admin:
            return "Администратор уже существует"

        # Создаем админа
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('Admin123!')

        db.session.add(admin)
        db.session.commit()

        return """
        <div style='text-align: center; padding: 20px;'>
            <h2 style='color: green;'>✅ Админ создан успешно</h2>
            <p>Логин: admin</p>
            <p>Пароль: Admin123!</p>
            <p style='color: red;'>Не забудьте сменить пароль при первом входе!</p>
        </div>
        """

    except Exception as e:
        return f"Ошибка: {str(e)}"


@main.route('/free-rooms')
def free_rooms():
    """Страница поиска свободных аудиторий"""
    buildings = Schedule.get_buildings()
    time_slots = Settings.get_settings().get('time_slots', [])
    current_semester = Settings.get_current_semester()

    # Получаем максимальное количество недель из всего расписания
    max_weeks = Schedule.get_max_weeks()  # Убираем параметр semester

    return render_template(
        'free_rooms.html',
        buildings=buildings,
        time_slots=time_slots,
        current_semester=current_semester,
        current_week=Schedule.get_week_by_date(datetime.now().date(), current_semester),
        current_day=datetime.now().isoweekday(),
        weeks_count=max_weeks
    )


@main.route('/free-rooms/data')
def free_rooms_data():
    semester = request.args.get('semester', Settings.get_current_semester(), type=int)
    week = request.args.get('week', type=int)
    day = request.args.get('day', type=int)
    building = request.args.get('building')
    lesson_number = request.args.get('lesson', type=int)

    if not all([week, day, lesson_number]):
        return jsonify([])

    # Получаем время пары
    time_slots = Settings.get_settings().get('time_slots', [])
    slot_time = next((slot['start'] for slot in time_slots if slot['number'] == lesson_number), None)
    if not slot_time:
        return jsonify([])

    # Сначала получаем все аудитории текущего семестра
    base_query = db.session.query(Schedule.auditory).distinct().filter(
        Schedule.semester == semester  # Добавляем фильтр по семестру
    )

    # Применяем фильтры в зависимости от корпуса
    if building == 'other':
        base_query = base_query.filter(
            ~Schedule.auditory.regexp_match(r'^(?:[1-9]|1[0-9]|2[0-5])\.'),
            Schedule.auditory != ''
        )
    elif building == '25':
        base_query = base_query.filter(Schedule.auditory.like('25.%'))
    else:
        base_query = base_query.filter(Schedule.auditory.like(f'{building}.%'))

    # Подзапрос для получения занятых аудиторий
    busy_rooms = db.session.query(Schedule.auditory).filter(
        Schedule.semester == semester,
        Schedule.week_number == week,
        Schedule.weekday == day,
        Schedule.time_start == slot_time
    )

    # Получаем свободные аудитории, исключая занятые
    free_rooms = base_query.filter(
        ~Schedule.auditory.in_(busy_rooms)
    ).order_by(Schedule.auditory).all()

    # Преобразуем результат
    free_rooms = [room[0] for room in free_rooms if room[0]]

    return jsonify(free_rooms)


@main.route('/free-rooms/room-details')
def room_details():
    """Получение детальной информации об аудитории на день"""
    semester = request.args.get('semester', type=int)
    week = request.args.get('week', type=int)
    day = request.args.get('day', type=int)
    room = request.args.get('room')

    if not all([semester, week, day, room]):
        return jsonify({'error': 'Missing parameters'}), 400

    # Получаем временные слоты
    time_slots = Settings.get_settings().get('time_slots', [])

    # Получаем расписание для конкретной аудитории
    lessons = Schedule.query.filter(
        Schedule.semester == semester,
        Schedule.week_number == week,
        Schedule.weekday == day,
        Schedule.auditory == room
    ).order_by(
        Schedule.time_start
    ).all()

    # Создаем словарь занятости по времени
    occupied_slots = {}
    for lesson in lessons:
        start_time = lesson.time_start
        if start_time not in occupied_slots:
            occupied_slots[start_time] = []

        occupied_slots[start_time].append({
            'subject': lesson.subject,
            'teacher': lesson.teacher_name,
            'group': lesson.group_name,
            'type': lesson.lesson_type
        })

    # Формируем полное расписание
    schedule = []
    for slot in time_slots:
        start_time = slot['start']
        schedule_item = {
            'number': slot['number'],
            'time': f"{slot['start']} - {slot['end']}",
            'is_occupied': start_time in occupied_slots
        }

        if start_time in occupied_slots:
            lessons_data = occupied_slots[start_time]
            groups = [lesson['group'] for lesson in lessons_data]

            # Берем данные первого занятия, так как предмет и преподаватель обычно одинаковые
            first_lesson = lessons_data[0]
            schedule_item.update({
                'subject': first_lesson['subject'],
                'teacher': first_lesson['teacher'],
                'type': first_lesson['type'],
                'groups': groups
            })

        schedule.append(schedule_item)

    return jsonify({
        'room': room,
        'schedule': schedule
    })