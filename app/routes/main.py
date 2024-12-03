# app/routes/main.py
from flask import render_template, request, Blueprint
from app import db
from app.models.schedule import Schedule
from app.config.settings import Settings
from datetime import datetime, timedelta
from sqlalchemy.sql.expression import func

main = Blueprint('main', __name__)
@main.route('/')
def index():
    # Получаем данные из базы данных
    groups = db.session.query(Schedule.group_name).distinct().order_by(Schedule.group_name).all()
    teachers = db.session.query(Schedule.teacher_name)\
        .filter(Schedule.teacher_name != '')\
        .distinct()\
        .order_by(Schedule.teacher_name).all()
    rooms = db.session.query(Schedule.auditory)\
        .filter(Schedule.auditory != '')\
        .distinct()\
        .order_by(Schedule.auditory).all()

    groups = [group[0] for group in groups]
    teachers = [teacher[0] for teacher in teachers]
    rooms = [room[0] for room in rooms]

    # Определяем текущий семестр и неделю
    current_semester = Settings.get_current_semester()
    current_week = get_current_week()

    return render_template('index.html',
                         groups=groups,
                         teachers=teachers,
                         rooms=rooms,
                         current_semester=current_semester,
                         current_week=current_week)


# app/routes/main.py

@main.route('/timetable')
def schedule():
    schedule_type = request.args.get('type')
    value = request.args.get('value')

    # Определяем текущий семестр и неделю
    current_semester = Settings.get_current_semester()
    current_date = datetime.now().date()

    # Получаем все недели для текущего семестра
    weeks_data = db.session.query(
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

    # Находим текущую неделю по дате
    current_week = 1  # значение по умолчанию
    for week in weeks_data:
        if week.start_date and week.end_date:
            if week.start_date <= current_date <= week.end_date:
                current_week = week.week_number
                break

    # Если текущая дата не попадает ни в одну неделю,
    # находим ближайшую следующую неделю
    if current_week == 1 and weeks_data:
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

    # Получаем список всех недель для отображения в селекте
    weeks = [week.week_number for week in weeks_data]

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

    # Если переданы параметры в URL, используем их
    if 'semester' in request.args:
        current_semester = int(request.args.get('semester'))
    if 'week' in request.args:
        current_week = int(request.args.get('week'))

    today_weekday = datetime.now().isoweekday() # 1-7 (пн-вс)

    settings = Settings.get_settings()

    return render_template('timetable/index.html',

                           current_semester=current_semester,
                           current_week=current_week,
                           today_weekday=today_weekday,
                           weeks=weeks,
                           semester_dates=semester_dates,
                           schedule_type=schedule_type,
                           value=value,
                           settings=settings)


def get_current_week():
    """Определяет текущую неделю семестра"""
    try:
        settings = Settings.get_settings()
        current_semester = Settings.get_current_semester()
        today = datetime.now().date()

        # Получаем даты начала семестра
        if current_semester == 1:
            semester_start = datetime.strptime(
                settings['academic_year']['first_semester']['start'],
                '%Y-%m-%d'
            ).date()
        else:
            semester_start = datetime.strptime(
                settings['academic_year']['second_semester']['start'],
                '%Y-%m-%d'
            ).date()

        # Вычисляем номер недели
        delta = today - semester_start
        current_week = (delta.days // 7) + 1

        # Проверяем существование недели в базе
        weeks = db.session.query(Schedule.week_number) \
            .filter_by(semester=current_semester) \
            .distinct() \
            .order_by(Schedule.week_number) \
            .all()
        weeks = [w[0] for w in weeks]

        if not weeks:
            return 1  # Если нет недель, возвращаем первую

        if current_week in weeks:
            return current_week
        else:
            # Находим ближайшую доступную неделю
            closest_week = min(weeks, key=lambda x: abs(x - current_week))
            return closest_week

    except Exception as e:
        print(f"Error determining current week: {e}")
        return 1  # В случае ошибки возвращаем первую неделю


