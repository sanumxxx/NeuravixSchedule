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

    def __init__(self, show_empty_weeks: bool = False, skip_empty_fields: bool = True):
        self.show_empty_weeks = show_empty_weeks
        self.skip_empty_fields = skip_empty_fields
        # Словарь для замены проблемных символов
        self.char_replacements = {'с\\з': 'с/з', 'С\\З': 'С/З', '\\': '/', '\t': ' ', '\r': '', '\xa0': ' ',
            # неразрывный пробел
            '—': '-',  # длинное тире на обычное
            '–': '-',  # среднее тире на обычное
        }
        self.processed_lessons = set()

    def get_lesson_key(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> str:
        """Создает уникальный ключ для занятия."""
        """Создает уникальный ключ для занятия."""
        date = self.parse_date(lesson['date'])
        subgroup = int(lesson.get('subgroup', 0))
        return f"{group_info['group_name']}_{date}_{lesson['time_start']}_{lesson['subject']}_{lesson['type']}_{subgroup}"

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
        required_fields = {'subject': 'предмет', 'type': 'тип занятия', 'time_start': 'время начала',
            'time_end': 'время окончания', 'date': 'дата'}

        missing_fields = []
        empty_fields = []

        # Проверяем только критически важные поля
        for field, name in required_fields.items():
            if field not in lesson:
                missing_fields.append(name)
            elif not lesson[field]:
                empty_fields.append(name)




    def process_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает данные одного занятия.
        """
        # Обрабатываем дату в начале
        date_str = self.parse_date(lesson['date'])

        # Создаем новый словарь с очищенными данными
        processed_lesson = {'group_name': self.clean_string(group_info['group_name']),
            'course': int(group_info.get('course', 1)), 'faculty': self.clean_string(group_info.get('faculty', '')),
            'subject': self.clean_string(lesson['subject']), 'type': self.clean_string(lesson['type']),
            'subgroup': int(lesson.get('subgroup', 0)), 'time_start': lesson['time_start'],
            'time_end': lesson['time_end'], 'date': date_str, 'weekday': self.get_weekday_from_date(date_str)
            # Вычисляем день недели из даты
        }

        # Обработка преподавателей
        teachers = lesson.get('teachers', [])
        if teachers:
            processed_lesson['teacher_name'] = self.clean_string(teachers[0].get('teacher_name', ''))
        else:
            processed_lesson['teacher_name'] = ''

        # Обработка аудиторий
        auditories = lesson.get('auditories', [])
        if auditories:
            processed_lesson['auditory'] = self.clean_string(auditories[0].get('auditory_name', ''))
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
            # Очищаем множество обработанных занятий для нового файла
            self.processed_lessons.clear()
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
                                                            lesson_key = self.get_lesson_key(lesson, group)
                                                            if lesson_key in self.processed_lessons:
                                                                continue  # Пропускаем дубликат
                                                            self.processed_lessons.add(lesson_key)
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

    def get_weekday_from_date(self, date_str: str) -> int:
        """
        Вычисляет номер дня недели из даты.

        Args:
            date_str: Строка даты в формате DD-MM-YYYY

        Returns:
            int: Номер дня недели (1 - понедельник, 7 - воскресенье)
        """
        try:
            date_str = date_str.replace('.', '-').replace('/', '-')
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            # isoweekday() возвращает 1 для понедельника и 7 для воскресенья
            return date_obj.isoweekday()
        except ValueError as e:
            print(f"Ошибка при определении дня недели для даты {date_str}: {str(e)}")
            return 1
