# app/services/report_service.py
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func, distinct
from app import db
from app.models.schedule import Schedule
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from io import BytesIO
from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from io import BytesIO


class ReportService:
    # Маппинг типов занятий
    LESSON_TYPES = {
        'л.': 'lecture',
        'пр.': 'practice',
        'лаб.': 'laboratory',
        'лекция': 'lecture',
        'практика': 'practice',
        'лабораторная': 'laboratory'
    }

    @staticmethod
    def get_teacher_load(teacher_name: str, semester: int, week_number: int = None) -> Dict:
        """Получает нагрузку преподавателя с разбивкой по неделям и типам занятий"""
        query = Schedule.query.filter(
            Schedule.teacher_name == teacher_name,
            Schedule.semester == semester
        )

        if week_number:
            query = query.filter(Schedule.week_number == week_number)

        lessons = query.order_by(
            Schedule.week_number,
            Schedule.date
        ).all()

        # Инициализируем структуру отчета с пустыми неделями
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
                'dates': {'start': None, 'end': None}
            } for i in range(1, 19)}  # Инициализируем все 18 недель
        }

        for lesson in lessons:
            week_num = lesson.week_number
            subject = lesson.subject
            lesson_type = ReportService.LESSON_TYPES.get(lesson.lesson_type, 'other')
            group = lesson.group_name

            if subject not in report['subjects']:
                report['subjects'][subject] = {
                    'groups': set(),
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
                        'other': 0
                    } for w in range(1, 19)}
                }

            # Обновляем часы
            hours = 2  # 1 пара = 2 академических часа
            report['weeks'][week_num][lesson_type] += hours
            report['weeks'][week_num]['total'] += hours
            report['total_hours'] += hours

            # Обновляем даты недели
            if not report['weeks'][week_num]['dates']['start'] or \
                    lesson.date < report['weeks'][week_num]['dates']['start']:
                report['weeks'][week_num]['dates']['start'] = lesson.date
            if not report['weeks'][week_num]['dates']['end'] or \
                    lesson.date > report['weeks'][week_num]['dates']['end']:
                report['weeks'][week_num]['dates']['end'] = lesson.date

            # Обновляем информацию по предмету
            subject_data = report['subjects'][subject]
            subject_data['groups'].add(group)
            subject_data['total_hours'] += hours
            subject_data['by_type'][lesson_type] += hours
            subject_data['by_week'][str(week_num)][lesson_type] += hours

        return report

    @staticmethod
    def export_teacher_load_excel(teacher_name: str, semester: int):
        try:
            report = ReportService.get_teacher_load(teacher_name, semester)

            wb = Workbook()
            ws = wb.active

            # Стили
            header_font = Font(name='Times New Roman', bold=True)
            normal_font = Font(name='Times New Roman')
            thick_border = Border(
                left=Side(style='medium'),
                right=Side(style='medium'),
                top=Side(style='medium'),
                bottom=Side(style='medium')
            )
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            center_alignment = Alignment(horizontal='center', vertical='center')

            # Заголовок
            ws.merge_cells('A1:T1')
            cell = ws['A1']
            cell.value = f'Загруженность преподавателя: {teacher_name} ({semester} семестр)'  # Добавили семестр
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = thick_border

            current_row = 2

            # Для каждого предмета
            for subject, data in report['subjects'].items():
                # Название предмета
                subj_cell = ws.cell(row=current_row, column=1, value=f'Предмет: {subject}')
                ws.merge_cells(f'A{current_row}:T{current_row}')
                subj_cell.font = header_font
                subj_cell.border = thick_border
                current_row += 1

                # Для каждой группы
                for group in sorted(data['groups']):
                    # Заголовок группы и недели
                    ws.cell(row=current_row, column=1, value=f'Группа: {group}')

                    # Заголовки недель
                    for i in range(18):
                        col = chr(ord('A') + i + 1)
                        cell = ws.cell(row=current_row, column=i + 2)
                        cell.value = f'Неделя {i + 1}'
                        cell.font = header_font
                        cell.border = thick_border
                        cell.alignment = center_alignment

                    # ИТОГО
                    itogo_cell = ws.cell(row=current_row, column=20)
                    itogo_cell.value = 'ИТОГО'
                    itogo_cell.font = header_font
                    itogo_cell.border = thick_border
                    itogo_cell.alignment = center_alignment

                    # Стили для заголовка группы
                    group_cell = ws.cell(row=current_row, column=1)
                    group_cell.font = header_font
                    group_cell.border = thick_border

                    current_row += 1

                    # Данные занятий
                    for lesson_type in ['Лекции', 'Практики', 'Лабораторные']:
                        row = current_row

                        # Тип занятия
                        type_cell = ws.cell(row=row, column=1, value=lesson_type)
                        type_cell.font = normal_font
                        type_cell.border = thin_border

                        # Данные по неделям
                        total = 0
                        for week in range(1, 19):
                            hours = 0
                            if str(week) in data.get('by_week', {}):
                                if lesson_type == 'Лекции':
                                    hours = data['by_week'][str(week)].get('lecture', 0)
                                elif lesson_type == 'Практики':
                                    hours = data['by_week'][str(week)].get('practice', 0)
                                elif lesson_type == 'Лабораторные':
                                    hours = data['by_week'][str(week)].get('laboratory', 0)

                            cell = ws.cell(row=row, column=week + 1)
                            cell.value = hours if hours > 0 else ''
                            cell.font = normal_font
                            cell.border = thin_border
                            cell.alignment = center_alignment
                            total += hours

                        # Итого для типа
                        total_cell = ws.cell(row=row, column=20, value=total)
                        total_cell.font = normal_font
                        total_cell.border = thin_border
                        total_cell.alignment = center_alignment

                        current_row += 1

                    current_row += 1  # Пробел между группами

                current_row += 1  # Пробел между предметами

            # Настройка ширины столбцов
            ws.column_dimensions['A'].width = 25
            for i in range(18):
                col = chr(ord('B') + i)
                ws.column_dimensions[col].width = 12
            ws.column_dimensions['T'].width = 12

            excel_file = BytesIO()
            wb.save(excel_file)
            excel_file.seek(0)

            return excel_file

        except Exception as e:
            print(f"Excel generation error: {str(e)}")
            raise

    @staticmethod
    def get_teachers_total_load(semester: int) -> List[Dict]:
        """Получает общую нагрузку всех преподавателей за семестр"""
        # Оптимизируем запрос для больших данных
        load_data = db.session.query(
            Schedule.teacher_name,
            func.count(Schedule.id).label('lessons_count'),
            func.count(distinct(Schedule.subject)).label('subjects_count'),
            func.count(distinct(Schedule.week_number)).label('weeks_count')
        ).filter(
            Schedule.semester == semester,
            Schedule.teacher_name != ''
        ).group_by(
            Schedule.teacher_name
        ).all()

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