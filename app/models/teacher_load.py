# app/models/teacher_load.py
from app import db
from datetime import datetime


class TeacherLoad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    group_name = db.Column(db.String(20), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    lesson_type = db.Column(db.String(20), nullable=False)
    hours = db.Column(db.Integer, nullable=False)  # количество академических часов
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def calculate_load(cls, schedule_items):
        """Вычисляет нагрузку на основе записей расписания"""
        load_data = {}
        for item in schedule_items:
            key = (item.teacher_name, item.subject, item.group_name,
                   item.week_number, item.lesson_type)
            if key not in load_data:
                load_data[key] = 2  # 2 академических часа за пару
            else:
                load_data[key] += 2

        return load_data

    @classmethod
    def generate_report(cls, teacher_name, start_date, end_date):
        """Генерирует отчет по нагрузке преподавателя"""
        loads = cls.query.filter(
            cls.teacher_name == teacher_name,
            cls.date_start >= start_date,
            cls.date_end <= end_date
        ).all()

        report = {
            'teacher': teacher_name,
            'period': {'start': start_date, 'end': end_date},
            'total_hours': 0,
            'by_type': {
                'lectures': 0,
                'practice': 0,
                'laboratory': 0
            },
            'by_subject': {},
            'by_week': {}
        }

        for load in loads:
            report['total_hours'] += load.hours

            # По типу занятий
            if load.lesson_type == 'lecture':
                report['by_type']['lectures'] += load.hours
            elif load.lesson_type == 'practice':
                report['by_type']['practice'] += load.hours
            elif load.lesson_type == 'laboratory':
                report['by_type']['laboratory'] += load.hours

            # По предметам
            if load.subject not in report['by_subject']:
                report['by_subject'][load.subject] = {
                    'total': 0,
                    'groups': set(),
                    'by_type': {'lectures': 0, 'practice': 0, 'laboratory': 0}
                }
            report['by_subject'][load.subject]['total'] += load.hours
            report['by_subject'][load.subject]['groups'].add(load.group_name)
            report['by_subject'][load.subject]['by_type'][load.lesson_type] += load.hours

            # По неделям
            if load.week_number not in report['by_week']:
                report['by_week'][load.week_number] = {
                    'total': 0,
                    'by_type': {'lectures': 0, 'practice': 0, 'laboratory': 0}
                }
            report['by_week'][load.week_number]['total'] += load.hours
            report['by_week'][load.week_number]['by_type'][load.lesson_type] += load.hours

        return report