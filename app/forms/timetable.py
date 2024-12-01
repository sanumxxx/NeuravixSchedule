from flask_wtf import FlaskForm
from flask_wtf.file import FileField, MultipleFileField
from wtforms import BooleanField

class TimetableUploadForm(FlaskForm):
    timetable_files = MultipleFileField('JSON файлы расписания')
    show_empty_weeks = BooleanField('Отображать пустые недели')
    skip_errors = BooleanField('Пропускать ошибки при загрузке')