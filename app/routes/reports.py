# app/routes/reports.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from app.services.report_service import ReportService
from app.config.settings import Settings
import io
from io import BytesIO
import zipfile
import json
from openpyxl.cell.cell import MergedCell
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from io import BytesIO

reports = Blueprint('reports', __name__)


@reports.route('/reports')
def index():
    """Главная страница отчетов"""
    return render_template('reports/index.html')


@reports.route('/reports/teacher-load/export-multiple', methods=['GET', 'POST'])
def export_multiple_teachers():
    try:
        if request.method == 'POST':
            data = request.get_json()
            export_type = data.get('type')
            semester = data.get('semester')
            teachers = data.get('teachers', [])
        else:
            export_type = request.args.get('type')
            semester = request.args.get('semester', type=int)
            teachers = json.loads(request.args.get('teachers', '[]'))

        if not teachers or not semester:
            print("Missing required parameters")
            return jsonify({'error': 'Missing required parameters'}), 400

        if export_type == 'single':
            try:
                wb = Workbook()

                # Определяем стили
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

                for i, teacher in enumerate(teachers):
                    if i == 0:
                        ws = wb.active
                        ws.title = teacher[:31]
                    else:
                        ws = wb.create_sheet(title=teacher[:31])

                    report = ReportService.get_teacher_load(teacher, semester)

                    # Заголовок
                    ws.merge_cells('A1:T1')
                    ws['A1'] = f'Загруженность преподавателя: {teacher} ({semester} семестр)'
                    ws['A1'].font = header_font
                    ws['A1'].alignment = center_alignment
                    ws['A1'].border = thick_border

                    current_row = 2

                    # Для каждого предмета
                    for subject, data in report['subjects'].items():
                        ws.merge_cells(f'A{current_row}:T{current_row}')
                        ws[f'A{current_row}'] = f'Предмет: {subject}'
                        ws[f'A{current_row}'].font = header_font
                        ws[f'A{current_row}'].border = thick_border
                        current_row += 1

                        # Для каждой группы
                        for group in sorted(data['groups']):
                            # Заголовок группы и недели
                            group_cell = ws.cell(row=current_row, column=1, value=f'Группа: {group}')
                            group_cell.font = header_font
                            group_cell.border = thick_border

                            # Заголовки недель
                            for i in range(18):
                                col = chr(ord('B') + i)
                                week_cell = ws.cell(row=current_row, column=i + 2, value=f'Неделя {i + 1}')
                                week_cell.font = header_font
                                week_cell.border = thick_border
                                week_cell.alignment = center_alignment

                            # ИТОГО
                            itogo_cell = ws.cell(row=current_row, column=20, value='ИТОГО')
                            itogo_cell.font = header_font
                            itogo_cell.border = thick_border
                            itogo_cell.alignment = center_alignment

                            current_row += 1

                            # Данные по типам занятий
                            for lesson_type in ['Лекции', 'Практики', 'Лабораторные']:
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

                                    cell = ws.cell(row=current_row, column=week + 1, value=hours if hours > 0 else '')
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

                            current_row += 1  # Пробел между группами

                        current_row += 1  # Пробел между предметами

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
                    ws.oddHeader.left.text = f"Преподаватель: {teacher}"
                    ws.oddHeader.center.text = f"{semester} семестр"
                    ws.oddHeader.right.text = "&[Date]"
                    ws.oddFooter.right.text = "Страница &[Page] из &[Pages]"

                output = BytesIO()
                wb.save(output)
                output.seek(0)

                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'Нагрузка_преподавателей_{semester}сем.xlsx'
                )
            except Exception as e:
                print(f"Error creating Excel file: {str(e)}")
                raise

        else:
            try:
                memory_file = BytesIO()
                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for teacher in teachers:
                        excel_file = ReportService.export_teacher_load_excel(teacher, semester)
                        zf.writestr(
                            f'Нагрузка_{teacher}_{semester}сем.xlsx',
                            excel_file.getvalue()
                        )

                memory_file.seek(0)
                return send_file(
                    memory_file,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f'Нагрузка_преподавателей_{semester}сем.zip'
                )
            except Exception as e:
                print(f"Error creating ZIP file: {str(e)}")
                raise

    except Exception as e:
        print(f"Multiple export error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@reports.route('/reports/teacher-load')
def teacher_load():
    """Отчет по нагрузке преподавателя"""
    teacher_name = request.args.get('teacher')
    semester = request.args.get('semester', Settings.get_current_semester(), type=int)
    week = request.args.get('week', type=int)

    if not teacher_name:
        # Показываем список всех преподавателей с их общей нагрузкой
        teachers_load = ReportService.get_teachers_total_load(semester)
        return render_template('reports/teachers_list.html',
                               teachers_load=teachers_load,
                               semester=semester)

    report = ReportService.get_teacher_load(teacher_name, semester, week)
    return render_template('reports/teacher_load.html', report=report)


@reports.route('/reports/teacher-load/export')
def export_teacher_load():
    teacher_name = request.args.get('teacher')
    semester = request.args.get('semester', type=int)

    if not teacher_name or not semester:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        excel_file = ReportService.export_teacher_load_excel(teacher_name, semester)

        filename = f'Нагрузка_{teacher_name}_{semester}сем.xlsx'
        filename = filename.encode('utf-8').decode('latin-1')

        response = make_response(excel_file.getvalue())
        response.headers.update({
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': len(excel_file.getvalue())
        })

        return response

    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500