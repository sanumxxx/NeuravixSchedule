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

    def __init__(self, show_empty_weeks: bool = False,  skip_empty_fields: bool = True):
        self.show_empty_weeks = show_empty_weeks
        self.skip_empty_fields = skip_empty_fields
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

    def validate_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> None:
        """
        Проверяет обязательные поля урока и логирует информацию о пустых полях.

        Args:
            lesson: Словарь с данными урока
            group_info: Информация о группе

        Raises:
            ValueError: Только если отсутствуют критически важные поля
        """
        required_fields = {
            'subject': 'предмет',
            'type': 'тип занятия',
            'time_start': 'время начала',
            'time_end': 'время окончания',
            'date': 'дата'
        }

        missing_fields = []
        empty_fields = []

        # Проверяем только критически важные поля
        for field, name in required_fields.items():
            if field not in lesson:
                missing_fields.append(name)
            elif not lesson[field]:
                empty_fields.append(name)

        # Проверяем и логируем информацию о дополнительных полях
        teachers = lesson.get('teachers', [])
        auditories = lesson.get('auditories', [])

        if not teachers or not teachers[0].get('teacher_name'):
            print(f"\nИнформация: отсутствует преподаватель")
            print(f"Группа: {group_info.get('group_name')}")
            print(f"Предмет: {lesson.get('subject')}")
            print(f"Дата: {lesson.get('date')}")
            print(f"Время: {lesson.get('time_start')} - {lesson.get('time_end')}")

        if not auditories or not auditories[0].get('auditory_name'):
            print(f"\nИнформация: отсутствует аудитория")
            print(f"Группа: {group_info.get('group_name')}")
            print(f"Предмет: {lesson.get('subject')}")
            print(f"Дата: {lesson.get('date')}")
            print(f"Время: {lesson.get('time_start')} - {lesson.get('time_end')}")

        # Выбрасываем ошибку только если отсутствуют критически важные поля
        if missing_fields or empty_fields:
            error_msg = f"Проблема с занятием для группы {group_info.get('group_name', 'UNKNOWN')}\n"
            error_msg += f"Предмет: {lesson.get('subject', 'НЕ УКАЗАН')}\n"
            error_msg += f"Дата: {lesson.get('date', 'НЕ УКАЗАНА')}\n"
            error_msg += f"Время: {lesson.get('time_start', 'НЕ УКАЗАНО')} - {lesson.get('time_end', 'НЕ УКАЗАНО')}\n"

            if missing_fields:
                error_msg += f"Отсутствующие поля: {', '.join(missing_fields)}\n"
            if empty_fields:
                error_msg += f"Пустые обязательные поля: {', '.join(empty_fields)}\n"

            raise ValueError(error_msg)

    def process_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает данные одного занятия.
        """
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
        try:
            content = file.read()

            # Декодирование содержимого
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

            # Предварительная обработка содержимого
            for old, new in self.char_replacements.items():
                decoded_content = decoded_content.replace(old, new)

            # Находим все объекты JSON в файле
            parsed_lessons = []
            start_pos = 0

            while True:
                try:
                    # Ищем начало следующего JSON объекта
                    json_start = decoded_content.find('{', start_pos)
                    if json_start == -1:
                        break

                    # Считаем фигурные скобки для определения конца объекта
                    brackets = 0
                    pos = json_start

                    while pos < len(decoded_content):
                        if decoded_content[pos] == '{':
                            brackets += 1
                        elif decoded_content[pos] == '}':
                            brackets -= 1
                            if brackets == 0:
                                # Нашли конец объекта
                                json_str = decoded_content[json_start:pos + 1]
                                try:
                                    data = json.loads(json_str)
                                    if isinstance(data, dict) and 'timetable' in data:
                                        # Обработка расписания
                                        for week in data['timetable']:
                                            week_number = week.get('week_number', 0)
                                            groups = week.get('groups', [])

                                            if not groups and not self.show_empty_weeks:
                                                continue

                                            for group in groups:
                                                for day in group.get('days', []):
                                                    for lesson in day.get('lessons', []):
                                                        try:
                                                            # Проверяем валидность занятия
                                                            self.validate_lesson(lesson, group)
                                                            # Если всё в порядке, обрабатываем его
                                                            processed_lesson = self.process_lesson(lesson, group)
                                                            processed_lesson['week_number'] = week_number
                                                            parsed_lessons.append(processed_lesson)
                                                        except ValueError as e:
                                                            print(f"\nПРЕДУПРЕЖДЕНИЕ: {str(e)}")
                                                            continue
                                except json.JSONDecodeError:
                                    print(f"Предупреждение: пропущен некорректный JSON объект")

                                start_pos = pos + 1
                                break
                        pos += 1

                    if brackets != 0:
                        # Если скобки не сбалансированы, прерываем обработку
                        break

                except Exception as e:
                    print(f"Предупреждение: ошибка при обработке части файла: {str(e)}")
                    break

            if not parsed_lessons:
                raise ValueError("Не удалось извлечь данные расписания из файла")

            return parsed_lessons

        except Exception as e:
            raise ValueError(f"Ошибка при обработке файла: {str(e)}")