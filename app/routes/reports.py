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


from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from app.services.report_service import ReportService
from app.config.settings import Settings
import io
from io import BytesIO
import zipfile
import json
from openpyxl.cell.cell import MergedCell
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from copy import copy

reports = Blueprint('reports', __name__)


@reports.route('/reports')
def index():
    """Главная страница отчетов"""
    return render_template('reports/index.html')


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
    """Экспорт нагрузки одного преподавателя"""
    teacher_name = request.args.get('teacher')
    semester = request.args.get('semester', type=int)

    if not teacher_name or not semester:
        return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

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
        print(f"Ошибка экспорта: {str(e)}")
        return jsonify({'error': str(e)}), 500


@reports.route('/reports/teacher-load/export-multiple', methods=['GET', 'POST'])
def export_multiple_teachers():
    """Экспорт данных для нескольких преподавателей"""
    try:
        # Получаем параметры в зависимости от метода запроса
        if request.method == 'POST':
            data = request.get_json()
            export_type = data.get('type')
            semester = data.get('semester')
            teachers = data.get('teachers', [])
        else:
            export_type = request.args.get('type')
            semester = request.args.get('semester', type=int)
            teachers = json.loads(request.args.get('teachers', '[]'))

        # Проверяем обязательные параметры
        if not teachers or not semester:
            return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

        # Экспорт в один файл Excel
        if export_type == 'single':
            try:
                wb = Workbook()
                # Удаляем дефолтный лист
                if 'Sheet' in wb.sheetnames:
                    wb.remove(wb.get_sheet_by_name('Sheet'))

                # Обрабатываем каждого преподавателя
                for teacher in teachers:
                    try:
                        # Создаем безопасное имя листа (макс. 31 символ)
                        safe_name = str(teacher)[:31]
                        # Заменяем недопустимые символы
                        for char in ['/', '\\', '?', '*', ':', '[', ']']:
                            safe_name = safe_name.replace(char, '_')

                        # Создаем новый лист
                        ws = wb.create_sheet(title=safe_name)

                        # Получаем данные преподавателя из сервиса
                        temp_file = ReportService.export_teacher_load_excel(teacher, semester)
                        temp_wb = load_workbook(temp_file)
                        temp_ws = temp_wb.active

                        # Копируем все данные и стили из временного файла
                        for row in temp_ws.rows:
                            for cell in row:
                                if isinstance(cell, MergedCell):
                                    continue
                                # Копируем значение и стили
                                new_cell = ws.cell(row=cell.row, column=cell.column,
                                                   value=cell.value)
                                if cell.has_style:
                                    new_cell.font = copy(cell.font)
                                    new_cell.border = copy(cell.border)
                                    new_cell.fill = copy(cell.fill)
                                    new_cell.alignment = copy(cell.alignment)

                        # Копируем настройки листа
                        ws.print_area = temp_ws.print_area
                        ws.page_setup = copy(temp_ws.page_setup)
                        ws.print_options = copy(temp_ws.print_options)

                        # Копируем размеры столбцов
                        for column in temp_ws.column_dimensions:
                            ws.column_dimensions[column] = copy(temp_ws.column_dimensions[column])

                        # Копируем объединенные ячейки
                        for merged_range in temp_ws.merged_cells.ranges:
                            ws.merge_cells(str(merged_range))

                    except Exception as e:
                        print(f"Ошибка при обработке преподавателя {teacher}: {str(e)}")
                        # Создаем лист с ошибкой для этого преподавателя
                        error_ws = wb.create_sheet(title=f"Ошибка_{safe_name}")
                        error_ws['A1'] = f"Ошибка при обработке данных преподавателя {teacher}: {str(e)}"
                        continue

                # Сохраняем итоговый файл
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
                print(f"Ошибка при создании общего Excel файла: {str(e)}")
                return jsonify({'error': str(e)}), 500

        # Экспорт в ZIP архив
        else:
            try:
                memory_file = BytesIO()
                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for teacher in teachers:
                        try:
                            excel_file = ReportService.export_teacher_load_excel(teacher, semester)

                            # Создаем безопасное имя файла
                            safe_name = str(teacher)
                            for char in ['/', '\\', '?', '*', ':', '[', ']']:
                                safe_name = safe_name.replace(char, '_')

                            filename = f'Нагрузка_{safe_name}_{semester}сем.xlsx'
                            zf.writestr(filename, excel_file.getvalue())
                        except Exception as e:
                            print(f"Ошибка при добавлении файла преподавателя {teacher} в ZIP: {str(e)}")
                            # Создаем файл с ошибкой для этого преподавателя
                            error_wb = Workbook()
                            error_ws = error_wb.active
                            error_ws['A1'] = f"Ошибка при создании отчета для {teacher}: {str(e)}"
                            error_file = BytesIO()
                            error_wb.save(error_file)
                            zf.writestr(f'Ошибка_Нагрузка_{safe_name}_{semester}сем.xlsx',
                                        error_file.getvalue())
                            continue

                memory_file.seek(0)
                return send_file(
                    memory_file,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f'Нагрузка_преподавателей_{semester}сем.zip'
                )

            except Exception as e:
                print(f"Ошибка при создании ZIP файла: {str(e)}")
                return jsonify({'error': str(e)}), 500

    except Exception as e:
        print(f"Общая ошибка экспорта: {str(e)}")
        return jsonify({'error': str(e)}), 500





