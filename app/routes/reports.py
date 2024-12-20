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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    try:
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

        if not teachers or not semester:
            return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

        # Получаем все данные для преподавателей одним запросом
        all_reports = ReportService.get_multiple_teachers_load(semester, teachers)

        # Функция для генерации одного Excel-файла
        def generate_excel_for_teacher(teacher, faculty=None):
            try:
                teacher_report = all_reports[teacher]
                if faculty:
                    # Фильтруем по факультету
                    filtered_subjects = {
                        subj: data for subj, data in teacher_report['subjects'].items()
                        if any(g['faculty'] == faculty for g in data['groups'].values())
                    }
                    filtered_report = {
                        'teacher_name': teacher_report['teacher_name'],
                        'semester': teacher_report['semester'],
                        'subjects': filtered_subjects
                    }
                    excel_file = ReportService.export_teacher_load_excel_from_report(filtered_report)
                else:
                    excel_file = ReportService.export_teacher_load_excel_from_report(teacher_report)

                filename = f'Нагрузка_{teacher}_{semester}сем.xlsx'
                return filename, excel_file.getvalue()
            except Exception as e:
                print(f"Ошибка при обработке преподавателя {teacher}: {str(e)}")
                error_wb = Workbook()
                error_ws = error_wb.active
                error_ws['A1'] = f"Ошибка при создании отчета для {teacher}: {str(e)}"
                error_file = BytesIO()
                error_wb.save(error_file)
                return f'Ошибка_{teacher}_{semester}сем.xlsx', error_file.getvalue()

        memory_file = BytesIO()

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as main_zip:
            if sort_by_faculty:
                # Сортируем преподавателей по факультетам
                faculties = {}
                for teacher in teachers:
                    teacher_report = all_reports.get(teacher)
                    if not teacher_report:
                        continue
                    teacher_faculties = set()
                    for subj, subj_data in teacher_report['subjects'].items():
                        for grp_data in subj_data['groups'].values():
                            teacher_faculties.add(grp_data['faculty'])

                    for faculty in teacher_faculties:
                        faculties.setdefault(faculty, []).append(teacher)

                # Обработка по факультетам с помощью пула потоков
                for faculty, faculty_teachers in faculties.items():
                    faculty_zip = BytesIO()
                    with zipfile.ZipFile(faculty_zip, 'w', zipfile.ZIP_DEFLATED) as sub_zip:
                        # Используем ThreadPoolExecutor для параллельной генерации
                        with ThreadPoolExecutor(max_workers=4) as executor:
                            futures = [executor.submit(generate_excel_for_teacher, t, faculty) for t in
                                       faculty_teachers]

                            for future in as_completed(futures):
                                fname, fdata = future.result()
                                sub_zip.writestr(fname, fdata)

                    faculty_zip.seek(0)
                    main_zip.writestr(f'{faculty}.zip', faculty_zip.getvalue())
            else:
                # Обработка всех преподавателей в один архив без сортировки по факультетам
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [executor.submit(generate_excel_for_teacher, t) for t in teachers]

                    for future in as_completed(futures):
                        fname, fdata = future.result()
                        main_zip.writestr(fname, fdata)

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


@reports.route('/reports/teacher-load/export-list')
def export_teacher_load_list():
    """Экспорт расписания преподавателей в формате списка"""
    try:
        export_type = request.args.get('type')
        semester = request.args.get('semester', type=int)
        teachers = json.loads(request.args.get('teachers', '[]'))
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not all([teachers, semester, start_date, end_date]):
            return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

        if export_type == 'zip':
            memory_file = BytesIO()
            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for teacher in teachers:
                    excel_file = ReportService.generate_schedule_list(teacher, start_date, end_date)
                    filename = f'Расписание_{teacher}_{start_date}_{end_date}.xlsx'
                    filename = filename.encode('utf-8').decode('latin-1')
                    zf.writestr(filename, excel_file.getvalue())

            memory_file.seek(0)
            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'Расписание_преподавателей_{start_date}_{end_date}.zip'
            )
        else:
            # If only one teacher or single file requested
            teacher = teachers[0] if len(teachers) == 1 else teachers[0]  # Take first teacher if multiple selected
            excel_file = ReportService.generate_schedule_list(teacher, start_date, end_date)

            filename = f'Расписание_{teacher}_{start_date}_{end_date}.xlsx'
            filename = filename.encode('utf-8').decode('latin-1')

            return send_file(
                excel_file,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )

    except Exception as e:
        print(f"Ошибка экспорта: {str(e)}")
        return jsonify({'error': str(e)}), 500

    @reports.errorhandler(Exception)
    def handle_error(error):
        """Обработчик ошибок для роутов отчетов"""
        print(f"Error in reports route: {str(error)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(error)}), 500
        flash(f'Произошла ошибка: {str(error)}', 'error')
        return redirect(url_for('reports.index'))

    # Также добавим логирование ошибок
    import logging
    logger = logging.getLogger(__name__)

    def log_error(error):
        """Логирование ошибок с дополнительной информацией"""
        logger.error(f"""
        Error occurred:
        Type: {type(error).__name__}
        Message: {str(error)}
        Route: {request.url}
        Method: {request.method}
        Args: {dict(request.args)}
        Data: {request.get_data(as_text=True)}
        """)







