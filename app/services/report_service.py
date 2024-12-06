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
        """Получает нагрузку преподавателя с разбивкой по неделям и типам занятий"""
        query = Schedule.query.filter(Schedule.teacher_name == teacher_name, Schedule.semester == semester)

        if week_number:
            query = query.filter(Schedule.week_number == week_number)

        lessons = query.order_by(Schedule.week_number, Schedule.date).all()

        # Инициализируем структуру отчета с пустыми неделями
        report = {'teacher_name': teacher_name, 'semester': semester, 'total_hours': 0, 'subjects': {}, 'weeks': {
            i: {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0, 'total': 0,
                'dates': {'start': None, 'end': None}} for i in range(1, 19)}  # Инициализируем все 18 недель
        }

        for lesson in lessons:
            week_num = lesson.week_number
            subject = lesson.subject
            lesson_type = ReportService.LESSON_TYPES.get(lesson.lesson_type, 'other')
            group = lesson.group_name

            if subject not in report['subjects']:
                report['subjects'][subject] = {'groups': set(), 'total_hours': 0,
                    'by_type': {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0},
                    'by_week': {str(w): {'lecture': 0, 'practice': 0, 'laboratory': 0, 'other': 0} for w in
                        range(1, 19)}}

            # Обновляем часы
            hours = 2  # 1 пара = 2 академических часа
            report['weeks'][week_num][lesson_type] += hours
            report['weeks'][week_num]['total'] += hours
            report['total_hours'] += hours

            # Обновляем даты недели
            if not report['weeks'][week_num]['dates']['start'] or lesson.date < report['weeks'][week_num]['dates'][
                'start']:
                report['weeks'][week_num]['dates']['start'] = lesson.date
            if not report['weeks'][week_num]['dates']['end'] or lesson.date > report['weeks'][week_num]['dates']['end']:
                report['weeks'][week_num]['dates']['end'] = lesson.date

            # Обновляем информацию по предмету
            subject_data = report['subjects'][subject]
            subject_data['groups'].add(group)
            subject_data['total_hours'] += hours
            subject_data['by_type'][lesson_type] += hours
            subject_data['by_week'][str(week_num)][lesson_type] += hours

        return report

    @staticmethod
    def export_teacher_load_excel(teacher_name: str, semester: int) -> BytesIO:
        """
        Экспортирует нагрузку преподавателя в Excel файл
        Returns: BytesIO object containing the Excel file
        """
        try:
            report = ReportService.get_teacher_load(teacher_name, semester)

            wb = Workbook()
            ws = wb.active

            # Определяем стили один раз
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

            try:
                # Заголовок
                ws.merge_cells('A1:T1')
                header_cell = ws['A1']
                header_cell.value = f'Загруженность преподавателя: {teacher_name} ({semester} семестр)'
                header_cell.font = header_font
                header_cell.alignment = center_alignment
                header_cell.border = thick_border

                current_row = 2

                # Обработка предметов
                for subject, data in report['subjects'].items():
                    try:
                        ws.merge_cells(f'A{current_row}:T{current_row}')
                        subject_cell = ws[f'A{current_row}']
                        subject_cell.value = f'Предмет: {subject}'
                        subject_cell.font = header_font
                        subject_cell.border = thick_border
                        current_row += 1

                        # Обработка групп
                        for group in sorted(data['groups']):
                            try:
                                # Заголовок группы
                                group_cell = ws.cell(row=current_row, column=1, value=f'Группа: {group}')
                                group_cell.font = header_font
                                group_cell.border = thick_border

                                # Заголовки недель
                                for i in range(18):
                                    week_cell = ws.cell(row=current_row, column=i + 2, value=f'Неделя {i + 1}')
                                    week_cell.font = header_font
                                    week_cell.border = thick_border
                                    week_cell.alignment = center_alignment

                                # ИТОГО
                                total_header = ws.cell(row=current_row, column=20, value='ИТОГО')
                                total_header.font = header_font
                                total_header.border = thick_border
                                total_header.alignment = center_alignment

                                current_row += 1

                                # Строки с типами занятий
                                for lesson_type in ['Лекции', 'Практики', 'Лабораторные']:
                                    try:
                                        type_cell = ws.cell(row=current_row, column=1, value=lesson_type)
                                        type_cell.font = normal_font
                                        type_cell.border = thin_border

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

                                            cell = ws.cell(row=current_row, column=week + 1)
                                            cell.value = hours if hours > 0 else ''
                                            cell.font = normal_font
                                            cell.border = thin_border
                                            cell.alignment = center_alignment
                                            total += hours

                                        # Итого для типа занятий
                                        total_cell = ws.cell(row=current_row, column=20, value=total)
                                        total_cell.font = normal_font
                                        total_cell.border = thin_border
                                        total_cell.alignment = center_alignment

                                        current_row += 1
                                    except Exception as e:
                                        print(f"Error processing lesson type {lesson_type}: {str(e)}")
                                        continue

                                current_row += 1  # Пробел между группами
                            except Exception as e:
                                print(f"Error processing group {group}: {str(e)}")
                                continue

                        current_row += 1  # Пробел между предметами
                    except Exception as e:
                        print(f"Error processing subject {subject}: {str(e)}")
                        continue

                # Настройка ширины столбцов
                ws.column_dimensions['A'].width = 25
                for col_idx in range(18):
                    ws.column_dimensions[chr(ord('B') + col_idx)].width = 12
                ws.column_dimensions['T'].width = 12

                # Настройки печати
                ws.print_area = f'A1:T{current_row - 1}'
                ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = False
                ws.print_options.horizontalCentered = True
                ws.print_title_rows = '1:1'
                ws.oddHeader.left.text = f"Преподаватель: {teacher_name}"
                ws.oddHeader.center.text = f"{semester} семестр"
                ws.oddHeader.right.text = "&[Date]"
                ws.oddFooter.right.text = "Страница &[Page] из &[Pages]"

                # Сохраняем в BytesIO
                excel_file = BytesIO()
                wb.save(excel_file)
                excel_file.seek(0)

                return excel_file

            except Exception as e:
                print(f"Error while processing Excel file: {str(e)}")
                # Создаем простой файл с ошибкой
                ws.cell(row=1, column=1, value=f"Ошибка при создании отчета: {str(e)}")
                error_file = BytesIO()
                wb.save(error_file)
                error_file.seek(0)
                return error_file

        except Exception as e:
            print(f"Critical error in export_teacher_load_excel: {str(e)}")
            # Создаем новый файл с сообщением об ошибке
            error_wb = Workbook()
            error_ws = error_wb.active
            error_ws['A1'] = f"Критическая ошибка при создании отчета для {teacher_name}: {str(e)}"
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
