from app import db
from datetime import datetime


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Информация о группе
    group_name = db.Column(db.String(20), nullable=False)
    course = db.Column(db.Integer, nullable=False)
    faculty = db.Column(db.String(100))

    # Информация о занятии
    subject = db.Column(db.String(256), nullable=False)
    lesson_type = db.Column(db.String(20))  # тип занятия (лекция, практика и т.д.)
    subgroup = db.Column(db.Integer, default=0)

    # Время занятия
    date = db.Column(db.Date, nullable=False)
    time_start = db.Column(db.String(5), nullable=False)
    time_end = db.Column(db.String(5), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)

    # Место проведения и преподаватель
    teacher_name = db.Column(db.String(100))
    auditory = db.Column(db.String(256))

    # Метаданные
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Schedule {self.group_name} {self.subject} {self.date}>'