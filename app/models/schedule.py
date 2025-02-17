# app/models/schedule.py
from datetime import datetime

from app import db
from ..config.settings import Settings
from sqlalchemy import func
import re


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
        """Возвращает временной интервал пары в формате 'HH:MM - HH:MM'"""
        try:
            # Конвертируем строку времени в объект времени
            if isinstance(self.time_start, str):
                lesson_time = self.time_start
            else:
                lesson_time = self.time_start.strftime('%H:%M')

            # Получаем настройки временных слотов
            settings = Settings.get_settings()
            time_slots = settings.get('time_slots', [])

            # Ищем подходящий временной слот
            for slot in time_slots:
                if slot['start'] == lesson_time:
                    return f"{slot['start']} - {slot['end']}"

            # Если слот не найден, возвращаем исходные значения
            if isinstance(self.time_end, str):
                return f"{self.time_start} - {self.time_end}"
            else:
                return f"{self.time_start.strftime('%H:%M')} - {self.time_end.strftime('%H:%M')}"

        except Exception as e:
            print(f"Error in get_time_slot: {e}")
            if isinstance(self.time_end, str):
                return f"{self.time_start} - {self.time_end}"
            else:
                return f"{self.time_start.strftime('%H:%M')} - {self.time_end.strftime('%H:%M')}"

    def get_lesson_number(self):
        """Определяет номер пары на основе времени начала занятия и настроек расписания звонков"""
        try:
            # Конвертируем строку времени в объект времени
            if isinstance(self.time_start, str):
                lesson_time = self.time_start
            else:
                lesson_time = self.time_start.strftime('%H:%M')

            # Получаем настройки временных слотов
            settings = Settings.get_settings()
            time_slots = settings.get('time_slots', [])

            # Ищем подходящий временной слот
            for slot in time_slots:
                if slot['start'] == lesson_time:
                    return slot['number']

            # Если точное совпадение не найдено, пытаемся найти ближайший слот
            for slot in time_slots:
                slot_time = datetime.strptime(slot['start'], '%H:%M').time()
                lesson_datetime = datetime.strptime(lesson_time, '%H:%M').time()

                # Допускаем небольшую погрешность (например, 5 минут)
                if abs((datetime.combine(datetime.today(), slot_time) - datetime.combine(datetime.today(),
                                                                                         lesson_datetime)).total_seconds()) <= 300:
                    return slot['number']

            # Если подходящий слот не найден, возвращаем номер по умолчанию
            return 0

        except Exception as e:
            print(f"Error in get_lesson_number: {e}")
            return 0

    def __repr__(self):
        return f'<Schedule {self.group_name} {self.subject} {self.date}>'

    @classmethod
    def get_max_weeks(cls):
        """Получить максимальное количество недель в расписании по всем семестрам"""
        result = db.session.query(func.max(Schedule.week)).scalar()
        return result or 60  # Если в расписании нет данных, возвращаем максимум 52 недели

    @staticmethod
    def get_week_by_date(date, semester):
        """Получает номер недели по дате"""
        week_data = db.session.query(Schedule.week_number,
                                     func.min(Schedule.date).label('start_date'),
                                     func.max(Schedule.date).label('end_date')) \
            .filter_by(semester=semester) \
            .group_by(Schedule.week_number) \
            .order_by(Schedule.week_number) \
            .all()

        # Ищем подходящую неделю
        for week in week_data:
            if week.start_date <= date <= week.end_date:
                return week.week_number

        # Если не нашли точное совпадение, ищем ближайшую
        if week_data:
            closest_week = min(week_data,
                               key=lambda w: abs((w.start_date - date).days))
            return closest_week.week_number

        return 1

    # В модель Schedule добавим метод:
    @staticmethod
    def get_available_semesters():
        """Получает список всех семестров из базы данных"""
        semesters = db.session.query(Schedule.semester) \
            .distinct() \
            .order_by(Schedule.semester) \
            .all()
        return [s[0] for s in semesters]

    @classmethod
    def get_buildings(cls):
        """Получение списка всех корпусов"""
        rooms = cls.query.filter(cls.auditory != '') \
            .with_entities(cls.auditory) \
            .distinct() \
            .all()

        buildings = {'regular': set(), 'remote': set(), 'other': set()}

        for room in rooms:
            if not room[0]:
                continue
            match = re.match(r'^(\d+)\.', room[0])
            if match:
                building_num = int(match.group(1))
                if building_num == 25:
                    buildings['remote'].add('25')
                elif 1 <= building_num <= 24:
                    buildings['regular'].add(str(building_num))
                else:
                    buildings['other'].add(room[0])
            else:
                buildings['other'].add(room[0])

        return {
            'regular': sorted(buildings['regular'], key=int),
            'remote': list(buildings['remote']),
            'other': bool(buildings['other'])  # Просто флаг наличия других аудиторий
        }
