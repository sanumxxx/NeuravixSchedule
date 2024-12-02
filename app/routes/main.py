from flask import render_template, Blueprint, url_for, redirect
from flask_login import current_user
from app import db
from app.models.schedule import Schedule

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # Fetch the data from the database
    groups = db.session.query(Schedule.group_name).distinct().order_by(Schedule.group_name).all()
    teachers = db.session.query(Schedule.teacher_name).filter(Schedule.teacher_name != '').distinct().order_by(Schedule.teacher_name).all()
    rooms = db.session.query(Schedule.auditory).filter(Schedule.auditory != '').distinct().order_by(Schedule.auditory).all()

    # Convert the tuples to lists
    groups = [group[0] for group in groups]
    teachers = [teacher[0] for teacher in teachers]
    rooms = [room[0] for room in rooms]

    # Debugging output
    print("Groups:", groups)
    print("Teachers:", teachers)
    print("Rooms:", rooms)

    return render_template('index.html',
                           groups=groups,
                           teachers=teachers,
                           rooms=rooms)

@main.route('/timetable')
def schedule():
    return render_template('timetable/index.html')

