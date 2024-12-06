# app/forms/timetable.py

from flask_wtf import FlaskForm
from wtforms import MultipleFileField, SelectField, BooleanField
from wtforms.validators import DataRequired


class TimetableUploadForm(FlaskForm):
    timetable_files = MultipleFileField('JSON файлы расписания', validators=[DataRequired()])
    semester = SelectField('Семестр', choices=[(1, '1 семестр'), (2, '2 семестр')], coerce=int,
                           validators=[DataRequired()])
    show_empty_weeks = BooleanField('Отображать пустые недели')
    skip_errors = BooleanField('Пропускать ошибки при загрузке')
