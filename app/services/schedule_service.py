from typing import List, Dict, Tuple
from app import db
from app.models.schedule import Schedule
from datetime import datetime


class ScheduleService:
    @staticmethod
    def save_schedule(lessons: List[Dict]) -> Tuple[int, int]:
        """
        Сохраняет расписание в базу данных.

        Args:
            lessons: Список занятий для сохранения

        Returns:
            Tuple[int, int]: кортеж, где первое число - количество добавленных занятий,
                            второе число - количество обновленных занятий
        """
        added = 0
        updated = 0

        for lesson_data in lessons:
            # Конвертируем строку даты в объект datetime
            date = datetime.strptime(lesson_data['date'], '%d-%m-%Y').date()

            # Проверяем существование занятия
            existing_lesson = Schedule.query.filter_by(
                group_name=lesson_data['group_name'],
                date=date,
                time_start=lesson_data['time_start'],
                subject=lesson_data['subject']
            ).first()

            if existing_lesson:
                # Обновляем существующее занятие
                for key, value in lesson_data.items():
                    if key == 'date':
                        continue  # Дата уже обработана
                    if key == 'type':
                        setattr(existing_lesson, 'lesson_type', value)
                    else:
                        setattr(existing_lesson, key, value)
                updated += 1
            else:
                # Создаем новое занятие
                new_lesson = Schedule(
                    group_name=lesson_data['group_name'],
                    course=lesson_data['course'],
                    faculty=lesson_data['faculty'],
                    subject=lesson_data['subject'],
                    lesson_type=lesson_data.get('type', ''),
                    subgroup=lesson_data.get('subgroup', 0),
                    date=date,
                    time_start=lesson_data['time_start'],
                    time_end=lesson_data['time_end'],
                    weekday=lesson_data['weekday'],
                    teacher_name=lesson_data.get('teacher_name', ''),
                    auditory=lesson_data.get('auditory', '')
                )
                db.session.add(new_lesson)
                added += 1

        # Сохраняем все изменения
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Ошибка при сохранении в базу данных: {str(e)}")

        return added, updated