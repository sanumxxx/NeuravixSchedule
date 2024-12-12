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
from app import db
from app.models.schedule import Schedule

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
    """Экспорт данных для нескольких преподавателей с учетом факультетов"""
    try:
        # Получаем параметры в зависимости от метода запроса
        if request.method == 'POST':
            data = request.get_json()
            export_type = data.get('type')
            semester = data.get('semester')
            teachers = data.get('teachers', [])
            sort_by_faculty = data.get('sort_by_faculty', '0') == '1'
        else:
            export_type = request.args.get('type')
            semester = request.args.get('semester', type=int)
            teachers = json.loads(request.args.get('teachers', '[]'))
            sort_by_faculty = request.args.get('sort_by_faculty', '0') == '1'

        # Проверяем обязательные параметры
        if not teachers or not semester:
            return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as main_zip:
            if sort_by_faculty:
                # Сортируем преподавателей по факультетам
                faculties = {}
                for teacher in teachers:
                    # Получаем факультеты преподавателя из базы данных
                    teacher_faculties = db.session.query(Schedule.faculty.distinct()).filter(
                        Schedule.teacher_name == teacher, Schedule.semester == semester).all()

                    for faculty in teacher_faculties:
                        faculties.setdefault(faculty[0], []).append(teacher)

                # Создаем ZIP-архивы для каждого факультета
                for faculty, faculty_teachers in faculties.items():
                    faculty_zip = BytesIO()
                    with zipfile.ZipFile(faculty_zip, 'w', zipfile.ZIP_DEFLATED) as sub_zip:
                        for teacher in faculty_teachers:
                            try:
                                # Экспортируем только занятия по конкретному факультету
                                report = ReportService.get_teacher_load(teacher, semester)
                                filtered_subjects = {
                                    subj: data for subj, data in report['subjects'].items()
                                    if any(group['faculty'] == faculty for group in data['groups'].values())
                                }
                                report['subjects'] = filtered_subjects

                                excel_file = ReportService.export_teacher_load_excel_from_report(report)
                                filename = f'Нагрузка_{teacher}_{semester}сем.xlsx'
                                sub_zip.writestr(filename, excel_file.getvalue())
                            except Exception as e:
                                print(f"Ошибка при обработке преподавателя {teacher}: {str(e)}")
                                error_wb = Workbook()
                                error_ws = error_wb.active
                                error_ws['A1'] = f"Ошибка при создании отчета для {teacher}: {str(e)}"
                                error_file = BytesIO()
                                error_wb.save(error_file)
                                sub_zip.writestr(f'Ошибка_{teacher}_{semester}сем.xlsx', error_file.getvalue())

                    faculty_zip.seek(0)
                    main_zip.writestr(f'{faculty}.zip', faculty_zip.getvalue())
            else:
                # Экспорт всех преподавателей в один ZIP
                for teacher in teachers:
                    try:
                        excel_file = ReportService.export_teacher_load_excel(teacher, semester)
                        filename = f'Нагрузка_{teacher}_{semester}сем.xlsx'
                        main_zip.writestr(filename, excel_file.getvalue())
                    except Exception as e:
                        print(f"Ошибка при обработке преподавателя {teacher}: {str(e)}")
                        error_wb = Workbook()
                        error_ws = error_wb.active
                        error_ws['A1'] = f"Ошибка при создании отчета для {teacher}: {str(e)}"
                        error_file = BytesIO()
                        error_wb.save(error_file)
                        main_zip.writestr(f'Ошибка_{teacher}_{semester}сем.xlsx', error_file.getvalue())

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'Нагрузка_преподавателей_{semester}сем.zip'
        )
    except Exception as e:
        print(f"Ошибка экспорта: {str(e)}")
        return jsonify({'error': str(e)}), 500






