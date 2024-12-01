import json
import codecs
from datetime import datetime
from typing import List, Dict, Any
from json.decoder import JSONDecodeError


class TimetableParser:
    """
    Парсер для обработки JSON-файлов с расписанием.
    Обрабатывает файлы в кодировке CP1251, учитывает различные форматы данных
    и обеспечивает надежную обработку ошибок.
    """

    def __init__(self, show_empty_weeks: bool = False):
        self.show_empty_weeks = show_empty_weeks
        # Словарь для замены проблемных символов
        self.char_replacements = {
            'с\\з': 'с/з',
            'С\\З': 'С/З',
            '\\': '/',
            '\t': ' ',
            '\r': '',
            '\xa0': ' ',  # неразрывный пробел
            '—': '-',  # длинное тире на обычное
            '–': '-',  # среднее тире на обычное
        }

    def clean_string(self, text: str) -> str:
        """
        Очищает строку от проблемных символов и нормализует её.

        Args:
            text: Исходная строка для очистки

        Returns:
            Очищенная и нормализованная строка
        """
        if not text:
            return ""

        # Применяем замены из словаря
        for old, new in self.char_replacements.items():
            text = text.replace(old, new)

        # Удаляем множественные пробелы
        text = ' '.join(text.split())

        return text.strip()

    def parse_date(self, date_str: str) -> str:
        """
        Парсит и валидирует строку даты.

        Args:
            date_str: Строка даты в формате "DD-MM-YYYY"

        Returns:
            Валидированная строка даты

        Raises:
            ValueError: Если формат даты неверный
        """
        try:
            # Заменяем возможные разделители на дефис
            date_str = date_str.replace('.', '-').replace('/', '-')

            # Парсим дату для проверки валидности
            parsed_date = datetime.strptime(date_str, "%d-%m-%Y")

            # Возвращаем в стандартном формате
            return parsed_date.strftime("%d-%m-%Y")
        except ValueError:
            raise ValueError(f"Неверный формат даты: {date_str}")

    def validate_lesson(self, lesson: Dict[str, Any]) -> None:
        """
        Проверяет обязательные поля урока.

        Args:
            lesson: Словарь с данными урока

        Raises:
            ValueError: Если отсутствуют обязательные поля
        """
        required_fields = {
            'subject': 'предмет',
            'type': 'тип занятия',
            'time_start': 'время начала',
            'time_end': 'время окончания',
            'date': 'дата'
        }

        for field, name in required_fields.items():
            if field not in lesson:
                raise ValueError(f"Отсутствует обязательное поле '{name}'")
            if not lesson[field]:
                raise ValueError(f"Поле '{name}' не может быть пустым")

    def process_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает данные одного занятия.

        Args:
            lesson: Словарь с данными занятия
            group_info: Информация о группе

        Returns:
            Обработанный словарь с данными занятия
        """
        # Проверяем обязательные поля
        self.validate_lesson(lesson)

        # Создаем новый словарь с очищенными данными
        processed_lesson = {
            'group_name': self.clean_string(group_info['group_name']),
            'course': int(group_info.get('course', 1)),
            'faculty': self.clean_string(group_info.get('faculty', '')),
            'subject': self.clean_string(lesson['subject']),
            'type': self.clean_string(lesson['type']),
            'subgroup': int(lesson.get('subgroup', 0)),
            'time_start': lesson['time_start'],
            'time_end': lesson['time_end'],
            'date': self.parse_date(lesson['date']),
            'weekday': int(lesson.get('weekday', 1))
        }

        # Обработка преподавателей
        teachers = lesson.get('teachers', [])
        if teachers:
            processed_lesson['teacher_name'] = self.clean_string(
                teachers[0].get('teacher_name', '')
            )
        else:
            processed_lesson['teacher_name'] = ''

        # Обработка аудиторий
        auditories = lesson.get('auditories', [])
        if auditories:
            processed_lesson['auditory'] = self.clean_string(
                auditories[0].get('auditory_name', '')
            )
        else:
            processed_lesson['auditory'] = ''

        return processed_lesson

    def parse_file(self, file) -> List[Dict[str, Any]]:
        """
        Парсит файл расписания с предварительной обработкой проблемных символов.

        Args:
            file: Файловый объект для парсинга

        Returns:
            Список обработанных занятий

        Raises:
            ValueError: При ошибках парсинга или валидации
        """
        try:
            # Читаем содержимое файла
            content = file.read()

            # Пробуем декодировать в разных кодировках
            for encoding in ['cp1251', 'utf-8', 'utf-8-sig']:
                try:
                    if isinstance(content, bytes):
                        decoded_content = content.decode(encoding)
                    else:
                        decoded_content = content
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Не удалось определить кодировку файла")

            # Предварительная обработка проблемных символов
            # Заменяем проблемные последовательности до парсинга JSON
            processed_content = decoded_content

            # Заменяем проблемные последовательности с обратным слешем
            replacements = {
                'с\\з': 'с/з',
                'С\\З': 'С/з',
                '\\з': '/з',
                '\\З': '/З'
            }

            for old, new in replacements.items():
                processed_content = processed_content.replace(old, new)

            try:
                # Теперь пытаемся разобрать предварительно обработанный JSON
                data = json.loads(processed_content)
            except JSONDecodeError as e:
                # Если всё еще есть ошибка, показываем подробную информацию
                line_number = e.lineno
                column = e.colno
                lines = processed_content.splitlines()
                error_line = lines[line_number - 1] if line_number <= len(lines) else "Строка не найдена"
                # Показываем контекст - несколько строк до и после ошибки
                context = '\n'.join(lines[max(0, line_number - 3):min(len(lines), line_number + 2)])

                raise ValueError(
                    f"Ошибка JSON в строке {line_number}, позиция {column}:\n"
                    f"Контекст ошибки:\n{context}\n"
                    f"Описание ошибки: {str(e)}"
                )

            # Остальная часть обработки данных
            if not isinstance(data, list):
                raise ValueError("JSON должен начинаться с массива")

            parsed_lessons = []

            for schedule in data:
                timetable = schedule.get('timetable', [])

                for week in timetable:
                    groups = week.get('groups', [])
                    if not groups and not self.show_empty_weeks:
                        continue

                    for group in groups:
                        for day in group.get('days', []):
                            for lesson in day.get('lessons', []):
                                try:
                                    processed_lesson = self.process_lesson(lesson, group)
                                    parsed_lessons.append(processed_lesson)
                                except ValueError as e:
                                    raise ValueError(
                                        f"Ошибка в занятии группы "
                                        f"{group.get('group_name', 'UNKNOWN')}: {str(e)}"
                                    )

            return parsed_lessons

        except Exception as e:
            # Добавляем контекст ко всем необработанным ошибкам
            raise ValueError(f"Ошибка при обработке файла: {str(e)}")