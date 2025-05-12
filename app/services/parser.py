import json
import codecs
from datetime import datetime
from typing import List, Dict, Any
from json.decoder import JSONDecodeError
import re


class TimetableParser:
    """
    Improved parser for processing JSON files with timetable data.
    Handles files in various encodings, different JSON formats,
    and provides robust error handling.
    """

    def __init__(self, show_empty_weeks: bool = False, skip_empty_fields: bool = True):
        self.show_empty_weeks = show_empty_weeks
        self.skip_empty_fields = skip_empty_fields
        # Словарь для замены проблемных символов
        self.char_replacements = {
            'с\\з': 'с/з', 'С\\З': 'С/З', '\\': '/', '\t': ' ', '\r': '', '\xa0': ' ',  # неразрывный пробел
            '—': '-',  # длинное тире на обычное
            '–': '-',  # среднее тире на обычное
        }
        self.processed_lessons = set()

    def get_lesson_key(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> str:
        """Creates a unique key for a lesson using multiple fields for better uniqueness."""
        date = self.parse_date(lesson['date'])
        time_start = lesson.get('time_start', '')
        subject = self.clean_string(lesson.get('subject', ''))
        lesson_type = self.clean_string(lesson.get('type', ''))
        subgroup = int(lesson.get('subgroup', 0))

        # Add teacher name to key if available
        teacher_name = ''
        teachers = lesson.get('teachers', [])
        if teachers and isinstance(teachers, list) and len(teachers) > 0:
            teacher_name = self.clean_string(teachers[0].get('teacher_name', ''))

        # Add auditory to key if available
        auditory = ''
        auditories = lesson.get('auditories', [])
        if auditories and isinstance(auditories, list) and len(auditories) > 0:
            auditory = self.clean_string(auditories[0].get('auditory_name', ''))

        # Create a more comprehensive key
        return f"{group_info['group_name']}_{date}_{time_start}_{subject}_{lesson_type}_{subgroup}_{teacher_name}_{auditory}"

    def clean_string(self, text: str) -> str:
        """
        Cleans a string by removing problematic characters and normalizing it.

        Args:
            text: The source string to clean

        Returns:
            Cleaned and normalized string
        """
        if not text:
            return ""

        # Apply replacements from the dictionary
        for old, new in self.char_replacements.items():
            text = text.replace(old, new)

        # Remove multiple spaces
        text = ' '.join(text.split())

        return text.strip()

    def parse_date(self, date_str: str) -> str:
        """
        Parses and validates a date string.

        Args:
            date_str: Date string in format "DD-MM-YYYY"

        Returns:
            Validated date string

        Raises:
            ValueError: If the date format is invalid
        """
        try:
            # Replace possible separators with hyphens
            date_str = date_str.replace('.', '-').replace('/', '-')

            # Parse date to check validity
            parsed_date = datetime.strptime(date_str, "%d-%m-%Y")

            # Return in standard format
            return parsed_date.strftime("%d-%m-%Y")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}")

    def validate_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> bool:
        """
        Validates required fields in a lesson and logs information about empty fields.

        Args:
            lesson: Dictionary with lesson data
            group_info: Information about the group

        Returns:
            bool: True if all required fields are present and valid, False otherwise
        """
        required_fields = {
            'subject': 'предмет',
            'type': 'тип занятия',
            'time_start': 'время начала',
            'time_end': 'время окончания',
            'date': 'дата'
        }

        # Check for missing required fields
        for field, name in required_fields.items():
            if field not in lesson:
                print(f"WARNING: Missing required field '{name}' in lesson")
                return False
            elif not lesson[field]:
                print(f"WARNING: Empty required field '{name}' in lesson")
                return False

        return True

    def process_lesson(self, lesson: Dict[str, Any], group_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes data for a single lesson.

        Args:
            lesson: Dictionary with lesson data
            group_info: Information about the group

        Returns:
            Dictionary with processed lesson data
        """
        # Process date at the beginning
        date_str = self.parse_date(lesson['date'])

        # Create a new dictionary with cleaned data
        processed_lesson = {
            'group_name': self.clean_string(group_info['group_name']),
            'course': int(group_info.get('course', 1)),
            'faculty': self.clean_string(group_info.get('faculty', '')),
            'subject': self.clean_string(lesson['subject']),
            'type': self.clean_string(lesson['type']),
            'subgroup': int(lesson.get('subgroup', 0)),
            'time_start': lesson['time_start'],
            'time_end': lesson['time_end'],
            'date': date_str,
            'weekday': self.get_weekday_from_date(date_str)  # Calculate day of week from date
        }

        # Process teachers
        teachers = lesson.get('teachers', [])
        if teachers and isinstance(teachers, list) and len(teachers) > 0:
            processed_lesson['teacher_name'] = self.clean_string(teachers[0].get('teacher_name', ''))
        else:
            processed_lesson['teacher_name'] = ''

        # Process auditoriums
        auditories = lesson.get('auditories', [])
        if auditories and isinstance(auditories, list) and len(auditories) > 0:
            processed_lesson['auditory'] = self.clean_string(auditories[0].get('auditory_name', ''))
        else:
            processed_lesson['auditory'] = ''

        return processed_lesson

    def parse_file(self, file) -> List[Dict[str, Any]]:
        """
        Parses a JSON file with timetable data.

        Args:
            file: File object to parse

        Returns:
            List of dictionaries with processed lesson data

        Raises:
            ValueError: If an error occurs during file processing
        """
        try:
            content = file.read()

            # Try different encodings
            for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'latin1']:
                try:
                    if isinstance(content, bytes):
                        decoded_content = content.decode(encoding)
                    else:
                        decoded_content = content
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not determine file encoding")

            # Clear set of processed lessons for a new file
            self.processed_lessons.clear()

            # Pre-process content
            for old, new in self.char_replacements.items():
                decoded_content = decoded_content.replace(old, new)

            # Initialize list for parsed lessons
            parsed_lessons = []

            # First, try to parse the entire content as a single JSON object
            try:
                data = json.loads(decoded_content)
                if isinstance(data, dict) and 'timetable' in data:
                    parsed_lessons.extend(self._process_timetable_data(data))
                elif isinstance(data, list):
                    # Handle array of timetable objects
                    for item in data:
                        if isinstance(item, dict) and 'timetable' in item:
                            parsed_lessons.extend(self._process_timetable_data(item))
            except JSONDecodeError:
                # If that fails, try to find JSON objects in the file
                parsed_lessons = self._extract_json_objects(decoded_content)

            if not parsed_lessons:
                raise ValueError("No timetable data could be extracted from the file")

            return parsed_lessons

        except Exception as e:
            raise ValueError(f"Error processing file: {str(e)}")

    def _process_timetable_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processes timetable data from a JSON object.

        Args:
            data: Dictionary with timetable data

        Returns:
            List of dictionaries with processed lesson data
        """
        result = []

        for week in data.get('timetable', []):
            week_number = week.get('week_number', 0)
            groups = week.get('groups', [])

            if not groups and not self.show_empty_weeks:
                continue

            for group in groups:
                for day in group.get('days', []):
                    for lesson in day.get('lessons', []):
                        try:
                            # Check for duplicate lessons
                            lesson_key = self.get_lesson_key(lesson, group)
                            if lesson_key in self.processed_lessons:
                                continue

                            # Validate lesson
                            if not self.validate_lesson(lesson, group):
                                continue

                            # Add to processed set
                            self.processed_lessons.add(lesson_key)

                            # Process lesson
                            processed_lesson = self.process_lesson(lesson, group)
                            processed_lesson['week_number'] = week_number
                            result.append(processed_lesson)
                        except ValueError as e:
                            print(f"WARNING: {str(e)}")
                            continue
                        except Exception as e:
                            print(f"ERROR processing lesson: {str(e)}")
                            continue

        return result

    def _extract_json_objects(self, content: str) -> List[Dict[str, Any]]:
        """
        Extracts and processes JSON objects from a string.

        Args:
            content: String containing JSON objects

        Returns:
            List of dictionaries with processed lesson data
        """
        result = []

        # Find all possible JSON objects
        start_pos = 0
        while True:
            # Find the start of a potential JSON object
            json_start = content.find('{', start_pos)
            if json_start == -1:
                break

            # Try to find a complete JSON object
            try:
                # Count brackets to find the corresponding closing brace
                bracket_count = 0
                for i in range(json_start, len(content)):
                    if content[i] == '{':
                        bracket_count += 1
                    elif content[i] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found a complete object, try to parse it
                            json_str = content[json_start:i + 1]
                            try:
                                data = json.loads(json_str)
                                if isinstance(data, dict) and 'timetable' in data:
                                    result.extend(self._process_timetable_data(data))
                            except JSONDecodeError:
                                pass  # Not a valid JSON object, continue searching

                            # Move past this object
                            start_pos = i + 1
                            break
                else:
                    # No matching closing brace found
                    break
            except Exception as e:
                print(f"WARNING: Error extracting JSON: {str(e)}")
                # Move to the next potential start
                start_pos = json_start + 1

        # Also try to find JSON arrays
        array_matches = re.finditer(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
        for match in array_matches:
            try:
                array_data = json.loads(match.group())
                for item in array_data:
                    if isinstance(item, dict) and 'timetable' in item:
                        result.extend(self._process_timetable_data(item))
            except JSONDecodeError:
                pass  # Not a valid JSON array
            except Exception as e:
                print(f"WARNING: Error processing JSON array: {str(e)}")

        return result

    def get_weekday_from_date(self, date_str: str) -> int:
        """
        Calculates the day of the week from a date.

        Args:
            date_str: Date string in format "DD-MM-YYYY"

        Returns:
            int: Day of week (1 - Monday, 7 - Sunday)
        """
        try:
            date_str = date_str.replace('.', '-').replace('/', '-')
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            # isoweekday() returns 1 for Monday and 7 for Sunday
            return date_obj.isoweekday()
        except ValueError as e:
            print(f"Error determining day of week for date {date_str}: {str(e)}")
            return 1