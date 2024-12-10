# app/services/report_service.py
from io import BytesIO
from typing import Dict, List
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from sqlalchemy import func, distinct

from app import db
from app.models.schedule import Schedule


class ReportService:
    # Маппинг типов занятий
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

    # Маппинг отображения экзаменов
    EXAM_DISPLAY = {
        'экзамен': 'Э',
        'зач.': 'З',
        'зчО.': 'ЗО'
    }

    @staticmethod
    def get_teacher_load(teacher_name: str, semester: int, week_number: int = None) -> Dict:
        """Generates a teacher load report for a given teacher and semester."""

        # Query the database for schedule entries
        query = Schedule.query.filter(Schedule.teacher_name == teacher_name, Schedule.semester == semester)
        if week_number:
            query = query.filter(Schedule.week_number == week_number)
        lessons = query.order_by(Schedule.week_number, Schedule.date).all()

        # Initialize the report dictionary
        report = {
            'teacher_name': teacher_name,
            'semester': semester,
            'total_hours': 0,
            'subjects': {},
            'weeks': {i: {
                'lecture': 0,
                'practice': 0,
                'laboratory': 0,
                'other': 0,
                'total': 0,
                'dates': {'start': None, 'end': None},
                'exam_info': None
            } for i in range(1, 19)}
        }

        # First pass: identify exam weeks and their types
        exam_weeks = {}  # {(subject, group, week): exam_type}
        for lesson in lessons:
            if lesson.lesson_type in ReportService.EXAM_DISPLAY:
                key = (lesson.subject, lesson.group_name, lesson.week_number)
                exam_weeks[key] = ReportService.EXAM_DISPLAY[lesson.lesson_type]

        # Process lessons
        for lesson in lessons:
            week_num = lesson.week_number
            subject = lesson.subject
            group = lesson.group_name
            original_type = lesson.lesson_type
            lesson_type = ReportService.LESSON_TYPES.get(original_type, 'other')
            hours = 2  # Default hours per lesson

            # Initialize subject if not exists
            if subject not in report['subjects']:
                report['subjects'][subject] = {
                    'groups': {},
                    'total_hours': 0,
                    'by_type': {
                        'lecture': 0,
                        'practice': 0,
                        'laboratory': 0,
                        'other': 0,
                        'exam': []
                    }
                }

            # Initialize group if not exists
            if group not in report['subjects'][subject]['groups']:
                report['subjects'][subject]['groups'][group] = {
                    'total_hours': 0,
                    'by_type': {
                        'lecture': 0,
                        'practice': 0,
                        'laboratory': 0,
                        'other': 0
                    },
                    'by_week': {str(w): {
                        'lecture': 0,
                        'practice': 0,
                        'laboratory': 0,
                        'other': 0,
                        'exam_type': None,
                        'hours': {}  # Changed to dict to store hours per type
                    } for w in range(1, 19)}
                }

            group_data = report['subjects'][subject]['groups'][group]
            week_data = group_data['by_week'][str(week_num)]

            # Check if this is an exam week
            exam_key = (subject, group, week_num)
            if exam_key in exam_weeks:
                exam_symbol = exam_weeks[exam_key]
                week_data['exam_type'] = exam_symbol

            # Process lesson hours
            if lesson_type in ['lecture', 'practice', 'laboratory']:
                # Always add hours to the week data regardless of exam status
                week_data[lesson_type] += hours

                # For exam weeks, also store in the hours dictionary
                if exam_key in exam_weeks:
                    if lesson_type not in week_data['hours']:
                        week_data['hours'][lesson_type] = hours
                    else:
                        week_data['hours'][lesson_type] += hours

                # Add to group totals
                group_data['total_hours'] += hours
                group_data['by_type'][lesson_type] += hours

                # Add to subject totals
                report['subjects'][subject]['total_hours'] += hours
                report['subjects'][subject]['by_type'][lesson_type] += hours

            # Add exam information if this is an exam
            if original_type in ReportService.EXAM_DISPLAY and exam_key in exam_weeks:
                exam_info = {
                    'type': exam_symbol,
                    'week': week_num,
                    'group': group
                }
                if exam_info not in report['subjects'][subject]['by_type']['exam']:
                    report['subjects'][subject]['by_type']['exam'].append(exam_info)

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
                'thick': Border(
                    left=Side(style='medium'),
                    right=Side(style='medium'),
                    top=Side(style='medium'),
                    bottom=Side(style='medium')
                ),
                'thin': Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            }
            center = Alignment(horizontal='center', vertical='center')
            exam_fill = PatternFill(start_color='E6E6E6', end_color='E6E6E6', fill_type='solid')

            # Заголовок
            ws.merge_cells('A1:T1')
            header = ws['A1']
            header.value = f'Загруженность преподавателя: {teacher_name} ({semester} семестр)'
            header.font = header_font
            header.alignment = center
            header.border = borders['thick']

            current_row = 2

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
                    for lesson_type, label in [
                        ('lecture', 'Лекции'),
                        ('practice', 'Практики'),
                        ('laboratory', 'Лабораторные')
                    ]:
                        type_cell = ws.cell(row=current_row, column=1, value=label)
                        type_cell.font = normal_font
                        type_cell.border = borders['thin']

                        total = 0
                        for week in range(1, 19):
                            week_data = group_data['by_week'][str(week)]
                            cell = ws.cell(row=current_row, column=week + 1)

                            # Проверяем наличие экзамена/зачета
                            if week_data['exam_type']:
                                cell.value = week_data['exam_type']
                                cell.fill = exam_fill
                            else:
                                hours = week_data[lesson_type]
                                cell.value = hours if hours > 0 else ''
                                if hours > 0:
                                    total += hours

                            cell.font = normal_font
                            cell.border = borders['thin']
                            cell.alignment = center

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
        load_data = db.session.query(
            Schedule.teacher_name,
            func.count(Schedule.id).label('lessons_count'),
            func.count(distinct(Schedule.subject)).label('subjects_count'),
            func.count(distinct(Schedule.week_number)).label('weeks_count')
        ).filter(
            Schedule.semester == semester,
            Schedule.teacher_name != ''
        ).group_by(Schedule.teacher_name).all()

        result = []
        for data in load_data:
            hours = data.lessons_count * 2  # 1 пара = 2 академических часа
            result.append({
                'teacher_name': data.teacher_name,
                'total_hours': hours,
                'subjects_count': data.subjects_count,
                'weeks_count': data.weeks_count
            })

        return sorted(result, key=lambda x: x['total_hours'], reverse=True)