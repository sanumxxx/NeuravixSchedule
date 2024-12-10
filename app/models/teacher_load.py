# app/models/teacher_load.py
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from sqlalchemy import text
from app import db


class TeacherLoad(db.Model):
    """Model for tracking teacher workload including classes, exams and tests"""

    __tablename__ = 'teacher_loads'

    # Primary fields
    id = db.Column(db.Integer, primary_key=True)
    teacher_name = db.Column(db.String(100), nullable=False, index=True)
    subject = db.Column(db.String(256), nullable=False)
    group_name = db.Column(db.String(20), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    lesson_type = db.Column(db.String(20), nullable=False)
    hours = db.Column(db.Integer, nullable=False)  # количество академических часов
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # New fields for exam tracking
    exam_type = db.Column(db.String(20))  # тип контроля: экзамен/зачет/etc
    is_exam = db.Column(db.Boolean, default=False)  # флаг для быстрой фильтрации экзаменов

    # Constants
    EXAM_TYPES = {
        'экзамен': 'Э',  # Exam
        'зач': 'З',  # Pass/fail test
        'зчО': 'ЗО'  # Graded test
    }

    LESSON_TYPES = {
        'л.': 'lecture',
        'пр.': 'practice',
        'лаб.': 'laboratory',
        'лекция': 'lecture',
        'практика': 'practice',
        'лабораторная': 'laboratory',
        'экзамен': 'exam',
        'зач': 'test',
        'зчО': 'graded_test'
    }

    def __init__(self, **kwargs):
        super(TeacherLoad, self).__init__(**kwargs)
        if self.exam_type in self.EXAM_TYPES:
            self.is_exam = True

    def __repr__(self):
        return f'<TeacherLoad {self.teacher_name} - {self.subject} ({self.lesson_type})>'

    @classmethod
    def calculate_load(cls, schedule_items: List) -> Dict[Tuple, int]:
        """
        Вычисляет нагрузку на основе записей расписания

        Args:
            schedule_items: Список записей расписания

        Returns:
            Dict: Словарь с ключом (teacher, subject, group, week, type) и значением часов
        """
        load_data = {}
        for item in schedule_items:
            key = (
                item.teacher_name,
                item.subject,
                item.group_name,
                item.week_number,
                item.lesson_type
            )

            # For regular classes, add 2 academic hours per class
            if item.lesson_type not in cls.EXAM_TYPES:
                if key not in load_data:
                    load_data[key] = 2
                else:
                    load_data[key] += 2
            # For exams, just mark them without adding hours
            else:
                load_data[key] = 0

        return load_data

    @classmethod
    def generate_report(cls, teacher_name: str, start_date: datetime, end_date: datetime) -> Dict:
        """
        Генерирует отчет по нагрузке преподавателя

        Args:
            teacher_name: ФИО преподавателя
            start_date: Начальная дата периода
            end_date: Конечная дата периода

        Returns:
            Dict: Отчет с детализацией нагрузки
        """
        loads = cls.query.filter(
            cls.teacher_name == teacher_name,
            cls.date_start >= start_date,
            cls.date_end <= end_date
        ).order_by(cls.week_number, cls.date_start).all()

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
            # Skip adding hours for exam entries
            if load.exam_type:
                continue

            report['total_hours'] += load.hours

            # Группировка по типу занятий
            if load.lesson_type in cls.LESSON_TYPES:
                lesson_type = cls.LESSON_TYPES[load.lesson_type]
                if lesson_type in ['lecture', 'practice', 'laboratory']:
                    report['by_type'][f'{lesson_type}s'] += load.hours

            # Группировка по предметам
            if load.subject not in report['by_subject']:
                report['by_subject'][load.subject] = {
                    'total': 0,
                    'groups': set(),
                    'by_type': {
                        'lectures': 0,
                        'practice': 0,
                        'laboratory': 0
                    }
                }

            subject_data = report['by_subject'][load.subject]
            subject_data['total'] += load.hours
            subject_data['groups'].add(load.group_name)

            if lesson_type in ['lecture', 'practice', 'laboratory']:
                subject_data['by_type'][f'{lesson_type}s'] += load.hours

            # Группировка по неделям
            if load.week_number not in report['by_week']:
                report['by_week'][load.week_number] = {
                    'total': 0,
                    'by_type': {
                        'lectures': 0,
                        'practice': 0,
                        'laboratory': 0
                    },
                    'exams': []  # List to store exam information
                }

            week_data = report['by_week'][load.week_number]
            week_data['total'] += load.hours

            if lesson_type in ['lecture', 'practice', 'laboratory']:
                week_data['by_type'][f'{lesson_type}s'] += load.hours

            # Add exam information if this is an exam entry
            if load.exam_type:
                week_data['exams'].append({
                    'type': cls.EXAM_TYPES.get(load.exam_type, 'Э'),
                    'subject': load.subject,
                    'group': load.group_name
                })

        return report

    @classmethod
    def get_teacher_subjects(cls, teacher_name: str, semester: Optional[int] = None) -> List[str]:
        """
        Получает список предметов преподавателя за семестр

        Args:
            teacher_name: ФИО преподавателя
            semester: Номер семестра (опционально)

        Returns:
            List[str]: Список названий предметов
        """
        query = cls.query.with_entities(cls.subject).distinct()
        query = query.filter(cls.teacher_name == teacher_name)

        if semester:
            # Assuming you have a semester field or can derive it from dates
            query = query.filter(text("semester = :sem")).params(sem=semester)

        return [row[0] for row in query.all()]

    @classmethod
    def get_weekly_hours(cls, teacher_name: str, subject: str, group: str) -> Dict[int, Dict]:
        """
        Получает почасовую нагрузку по неделям для конкретного предмета и группы

        Args:
            teacher_name: ФИО преподавателя
            subject: Название предмета
            group: Название группы

        Returns:
            Dict[int, Dict]: Словарь {номер_недели: {тип_занятия: часы}}
        """
        loads = cls.query.filter(
            cls.teacher_name == teacher_name,
            cls.subject == subject,
            cls.group_name == group
        ).order_by(cls.week_number).all()

        weekly_hours = {}
        for load in loads:
            week = load.week_number
            if week not in weekly_hours:
                weekly_hours[week] = {
                    'lecture': 0,
                    'practice': 0,
                    'laboratory': 0,
                    'exam_info': None
                }

            # Handle exam types
            if load.exam_type:
                exam_symbol = cls.EXAM_TYPES.get(load.exam_type, 'Э')
                regular_hours = sum(weekly_hours[week].values()) - (1 if weekly_hours[week]['exam_info'] else 0)
                weekly_hours[week]['exam_info'] = f"{exam_symbol}/{regular_hours}" if regular_hours > 0 else exam_symbol
            else:
                lesson_type = cls.LESSON_TYPES.get(load.lesson_type)
                if lesson_type in ['lecture', 'practice', 'laboratory']:
                    weekly_hours[week][lesson_type] += load.hours

        return weekly_hours