# app/services/report_service.py
from io import BytesIO
from typing import Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side
from sqlalchemy import func, distinct

from app import db
from app.models.schedule import Schedule


class ReportService:
    # Маппинг типов занятий
    LESSON_TYPES = {'л.': 'lecture', 'пр.': 'practice', 'лаб.': 'laboratory', 'лекция': 'lecture',
        'практика': 'practice', 'лабораторная': 'laboratory'}

    @staticmethod
    def get_teacher_load(teacher_name: str, semester: int, week_number: int = None) -> Dict:
        query = Schedule.query.filter(Schedule.teacher_name == teacher_name, Schedule.semester == semester)
        if week_number:
            query = query.filter(Schedule.week_number == week_number)
        lessons = query.order_by(Schedule.week_number, Schedule.date).all()

        report = {
            'teacher_name': teacher_name,
            'semester': semester,
            'total_hours': 0,
            'subjects': {},
            'weeks': {i: {
                'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0,
                'total': 0, 'dates': {'start': None, 'end': None}
            } for i in range(1, 19)}
        }

        # Для отслеживания уникальных лекций
        unique_lectures = {}

        for lesson in lessons:
            week_num = lesson.week_number
            subject = lesson.subject
            lesson_type = ReportService.LESSON_TYPES.get(lesson.lesson_type, 'other')
            group = lesson.group_name
            hours = 2

            # Инициализация структур
            if subject not in report['subjects']:
                report['subjects'][subject] = {
                    'groups': {},
                    'total_hours': 0,
                    'by_type': {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0}
                }

            if group not in report['subjects'][subject]['groups']:
                report['subjects'][subject]['groups'][group] = {
                    'total_hours': 0,
                    'by_type': {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0},
                    'by_week': {str(w): {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0}
                                for w in range(1, 19)}
                }

            # Обновление часов для группы
            group_data = report['subjects'][subject]['groups'][group]
            group_data['total_hours'] += hours
            group_data['by_type'][lesson_type] += hours
            group_data['by_week'][str(week_num)][lesson_type] += hours

            # Для лекций учитываем только уникальные пары
            if lesson_type == 'lecture':
                lecture_key = (week_num, subject, lesson.date)
                if lecture_key not in unique_lectures:
                    unique_lectures[lecture_key] = hours
                    report['subjects'][subject]['total_hours'] += hours
                    report['subjects'][subject]['by_type'][lesson_type] += hours
            else:
                report['subjects'][subject]['total_hours'] += hours
                report['subjects'][subject]['by_type'][lesson_type] += hours

            # Обновление дат недели
            week_dates = report['weeks'][week_num]['dates']
            if not week_dates['start'] or lesson.date < week_dates['start']:
                week_dates['start'] = lesson.date
            if not week_dates['end'] or lesson.date > week_dates['end']:
                week_dates['end'] = lesson.date

        # Подсчет общих часов
        for subject_data in report['subjects'].values():
            for lesson_type in ['practice', 'laboratory', 'other']:
                report['total_hours'] += subject_data['by_type'][lesson_type]

        # Добавляем уникальные лекционные часы
        report['total_hours'] += sum(unique_lectures.values())

        return report

    @staticmethod
    def export_teacher_load_excel(teacher_name: str, semester: int) -> BytesIO:
        try:
            report = ReportService.get_teacher_load(teacher_name, semester)
            wb = Workbook()
            ws = wb.active

            # Стили
            header_font = Font(name='Times New Roman', bold=True)
            normal_font = Font(name='Times New Roman')
            borders = {
                'thick': Border(left=Side(style='medium'), right=Side(style='medium'),
                                top=Side(style='medium'), bottom=Side(style='medium')),
                'thin': Border(left=Side(style='thin'), right=Side(style='thin'),
                               top=Side(style='thin'), bottom=Side(style='thin'))
            }
            center = Alignment(horizontal='center', vertical='center')

            # Заголовок
            ws.merge_cells('A1:T1')
            header = ws['A1']
            header.value = f'Загруженность преподавателя: {teacher_name} ({semester} семестр)'
            header.font = header_font
            header.alignment = center
            header.border = borders['thick']

            current_row = 2

            # Уникальные лекции для каждого предмета
            unique_lectures = {}

            for subject, data in report['subjects'].items():
                ws.merge_cells(f'A{current_row}:T{current_row}')
                subject_cell = ws[f'A{current_row}']
                subject_cell.value = f'Предмет: {subject}'
                subject_cell.font = header_font
                subject_cell.border = borders['thick']
                current_row += 1

                for group, group_data in data['groups'].items():
                    # Заголовок группы
                    group_cell = ws.cell(row=current_row, column=1, value=f'Группа: {group}')
                    group_cell.font = header_font
                    group_cell.border = borders['thick']

                    # Заголовки недель
                    for i in range(18):
                        week_cell = ws.cell(row=current_row, column=i + 2, value=f'Неделя {i + 1}')
                        week_cell.font = header_font
                        week_cell.border = borders['thick']
                        week_cell.alignment = center

                    total_header = ws.cell(row=current_row, column=20, value='ИТОГО')
                    total_header.font = header_font
                    total_header.border = borders['thick']
                    total_header.alignment = center
                    current_row += 1

                    # Типы занятий
                    for lesson_type, label in [('lecture', 'Лекции'), ('practice', 'Практики'),
                                               ('laboratory', 'Лабораторные')]:
                        type_cell = ws.cell(row=current_row, column=1, value=label)
                        type_cell.font = normal_font
                        type_cell.border = borders['thin']

                        total = 0
                        for week in range(1, 19):
                            hours = group_data['by_week'][str(week)][lesson_type]

                            # Для лекций отслеживаем уникальные пары
                            if lesson_type == 'lecture':
                                lecture_key = (week, subject)
                                if lecture_key not in unique_lectures:
                                    unique_lectures[lecture_key] = hours

                            cell = ws.cell(row=current_row, column=week + 1)
                            cell.value = hours if hours > 0 else ''
                            cell.font = normal_font
                            cell.border = borders['thin']
                            cell.alignment = center
                            total += hours

                        total_cell = ws.cell(row=current_row, column=20, value=total)
                        total_cell.font = normal_font
                        total_cell.border = borders['thin']
                        total_cell.alignment = center
                        current_row += 1

                    current_row += 1

                current_row += 1

            # Форматирование
            ws.column_dimensions['A'].width = 25
            for col_idx in range(18):
                ws.column_dimensions[chr(ord('B') + col_idx)].width = 12
            ws.column_dimensions['T'].width = 12

            # Настройки печати
            ws.print_area = f'A1:T{current_row - 1}'
            ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            ws.page_setup.fitToWidth = 1
            ws.print_options.horizontalCentered = True
            ws.print_title_rows = '1:1'

            excel_file = BytesIO()
            wb.save(excel_file)
            excel_file.seek(0)
            return excel_file

        except Exception as e:
            error_wb = Workbook()
            error_ws = error_wb.active
            error_ws['A1'] = f"Ошибка: {str(e)}"
            error_file = BytesIO()
            error_wb.save(error_file)
            error_file.seek(0)
            return error_file

    @staticmethod
    def get_teachers_total_load(semester: int) -> List[Dict]:
        """Получает общую нагрузку всех преподавателей за семестр"""
        # Оптимизируем запрос для больших данных
        load_data = db.session.query(Schedule.teacher_name, func.count(Schedule.id).label('lessons_count'),
            func.count(distinct(Schedule.subject)).label('subjects_count'),
            func.count(distinct(Schedule.week_number)).label('weeks_count')).filter(Schedule.semester == semester,
                                                                                    Schedule.teacher_name != '').group_by(
            Schedule.teacher_name).all()

        result = []
        for data in load_data:
            hours = data.lessons_count * 2  # 1 пара = 2 академических часа
            result.append(
                {'teacher_name': data.teacher_name, 'total_hours': hours, 'subjects_count': data.subjects_count,
                    'weeks_count': data.weeks_count})

        return sorted(result, key=lambda x: x['total_hours'], reverse=True)
