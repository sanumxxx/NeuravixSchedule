from flask import render_template, Blueprint, url_for, redirect
from flask_login import current_user


main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/timetable')
def schedule():
    return render_template('timetable/index.html')

