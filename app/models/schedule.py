# app/models/schedule.py
from app import db
from datetime import datetime

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
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
    teacher_name = db.Column(db.String(100), server_default='')
    auditory = db.Column(db.String(256), server_default='')

    # Метаданные
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_day_name(self):
        """Получить название дня недели"""
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        return days[self.weekday - 1] if 1 <= self.weekday <= 7 else ''

    def get_time_slot(self):
        """Получить временной слот занятия"""
        return f"{self.time_start} - {self.time_end}"

    def get_lesson_number(self):
        """Получить номер пары на основе времени начала"""
        time_slots = {
            "08:00": 1,
            "09:40": 2,
            "11:20": 3,
            "13:10": 4,
            "14:50": 5,
            "16:30": 6,
            "18:10": 7,
            "19:40": 8
        }
        return time_slots.get(self.time_start, 0)

    def __repr__(self):
        return f'<Schedule {self.group_name} {self.subject} {self.date}>'