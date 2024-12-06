from datetime import datetime
from typing import List, Dict, Tuple

from app import db
from app.models.schedule import Schedule


class ScheduleService:
    @staticmethod
    def save_schedule(lessons: List[Dict], semester: int) -> Tuple[int, int, List[str]]:
        added = 0
        duplicates = []

        print(f"Начало сохранения для семестра {semester}")
        print(f"Всего занятий к обработке: {len(lessons)}")

        # Используем новую сессию для гарантированного сохранения
        session = db.session

        try:
            for lesson_data in lessons:
                try:
                    date = datetime.strptime(lesson_data['date'], '%d-%m-%Y').date()

                    # Создаем новое занятие
                    new_lesson = Schedule(semester=semester, week_number=lesson_data['week_number'],
                        group_name=lesson_data['group_name'], course=lesson_data['course'],
                        faculty=lesson_data['faculty'], subject=lesson_data['subject'],
                        lesson_type=lesson_data.get('type', ''), subgroup=lesson_data.get('subgroup', 0), date=date,
                        time_start=lesson_data['time_start'], time_end=lesson_data['time_end'],
                        weekday=lesson_data['weekday'], teacher_name=lesson_data.get('teacher_name', ''),
                        auditory=lesson_data.get('auditory', ''))
                    session.add(new_lesson)
                    added += 1

                except Exception as e:
                    print(f"Ошибка при обработке занятия: {str(e)}")
                    continue

            # Явно сохраняем изменения
            print(f"Попытка сохранения в БД. Всего добавлено: {added}")
            session.commit()
            print("Изменения успешно сохранены в БД")

            return added, 0, []

        except Exception as e:
            print(f"Ошибка при сохранении в БД: {str(e)}")
            session.rollback()
            raise

    @staticmethod
    def check_conflicts(lessons: List[Dict], semester: int) -> Dict:
        """Проверяет конфликты новых занятий с существующими в базе данных"""
        if not lessons:
            return None

        # Получаем непустые недели из новых занятий
        week_numbers = set()
        for lesson in lessons:
            week_numbers.add(lesson['week_number'])

        # Проверяем каждую неделю на наличие в базе данных для указанного семестра
        conflicting_weeks = []
        for week_number in week_numbers:
            existing = Schedule.query.filter_by(semester=semester, week_number=week_number).first()
            if existing:
                conflicting_weeks.append(week_number)

        if conflicting_weeks:
            return {'conflicting_weeks': sorted(conflicting_weeks), 'week_number': conflicting_weeks[0]}

        return None

    @staticmethod
    def delete_week(week_number: int, semester: int) -> None:
        """Удаляет все занятия указанной недели определенного семестра"""
        try:
            Schedule.query.filter_by(semester=semester, week_number=week_number).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Ошибка при удалении недели {week_number} семестра {semester}: {str(e)}")

    @staticmethod
    def merge_schedules(new_lessons: List[Dict], week_number: int, semester: int) -> None:
        existing_lessons = Schedule.query.filter_by(semester=semester, week_number=week_number).all()

        for new_lesson_data in new_lessons:
            if new_lesson_data['week_number'] == week_number:
                date = datetime.strptime(new_lesson_data['date'], '%d-%m-%Y').date()

                existing_lesson = next((lesson for lesson in existing_lessons if lesson.group_name == new_lesson_data[
                    'group_name'] and lesson.date == date and lesson.time_start == new_lesson_data[
                                            'time_start'] and lesson.subject == new_lesson_data[
                                            'subject'] and lesson.subgroup == new_lesson_data.get('subgroup', 0)), None)

                if existing_lesson:
                    # Обновляем существующее занятие
                    existing_lesson.teacher_name = new_lesson_data.get('teacher_name', existing_lesson.teacher_name)
                    existing_lesson.auditory = new_lesson_data.get('auditory', existing_lesson.auditory)
                else:
                    # Создаем новое занятие
                    new_lesson = Schedule(semester=semester, week_number=new_lesson_data['week_number'],
                                          group_name=new_lesson_data['group_name'], course=new_lesson_data['course'],
                                          faculty=new_lesson_data['faculty'], subject=new_lesson_data['subject'],
                                          lesson_type=new_lesson_data.get('type', ''),
                                          subgroup=new_lesson_data.get('subgroup', 0), date=date,
                                          time_start=new_lesson_data['time_start'],
                                          time_end=new_lesson_data['time_end'], weekday=new_lesson_data['weekday'],
                                          teacher_name=new_lesson_data.get('teacher_name', ''),
                                          auditory=new_lesson_data.get('auditory', ''))
                    db.session.add(new_lesson)

        db.session.commit()

    @staticmethod
    def replace_week(new_lessons: List[Dict], week_number: int, semester: int) -> Tuple[int, int, List[str]]:
        """Заменяет все занятия недели новыми"""
        try:
            # Сначала удаляем все занятия этой недели для указанного семестра
            ScheduleService.delete_week(week_number, semester)
            # Затем сохраняем новые занятия с указанием семестра
            return ScheduleService.save_schedule(new_lessons, semester)
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при замене недели {week_number} семестра {semester}: {str(e)}")
            raise
