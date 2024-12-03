# app/routes/main.py
from flask import render_template, request, Blueprint
from app import db
from app.models.schedule import Schedule
from app.config.settings import Settings

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

    return render_template('index.html',
                         groups=groups,
                         teachers=teachers,
                         rooms=rooms)


# app/routes/main.py

@main.route('/timetable')
def schedule():
    schedule_type = request.args.get('type')
    value = request.args.get('value')

    # Получаем текущий семестр из настроек
    current_semester = Settings.get_current_semester()

    # Получаем все доступные недели для текущего семестра
    weeks = db.session.query(Schedule.week_number) \
        .filter_by(semester=current_semester) \
        .distinct() \
        .order_by(Schedule.week_number) \
        .all()
    weeks = [week[0] for week in weeks]

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

    return render_template('timetable/index.html',
                           current_semester=current_semester,
                           weeks=weeks,
                           semester_dates=semester_dates,
                           schedule_type=schedule_type,
                           value=value)