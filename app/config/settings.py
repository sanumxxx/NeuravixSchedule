# app/config/settings.py

import json
import os
from datetime import datetime


class Settings:
    @classmethod
    def get_database_url(cls):
        settings = cls.load_settings()
        db_type = settings['database']['type']
        host = settings['database']['host']
        port = settings['database']['port']
        name = settings['database']['name']
        user = settings['database']['user']
        password = settings['database']['password']

        # Поддержка только MySQL
        if db_type == 'mysql':
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"

        raise ValueError("Unsupported database type specified. Please set 'type' to 'mysql' in settings.json.")

    @classmethod
    def get_current_semester(cls):
        settings = cls.load_settings()
        today = datetime.now().date()

        try:
            first_start = datetime.strptime(settings['academic_year']['first_semester']['start'], '%Y-%m-%d').date()
            first_end = datetime.strptime(settings['academic_year']['first_semester']['end'], '%Y-%m-%d').date()
            second_start = datetime.strptime(settings['academic_year']['second_semester']['start'], '%Y-%m-%d').date()
            second_end = datetime.strptime(settings['academic_year']['second_semester']['end'], '%Y-%m-%d').date()

            if first_start <= today <= first_end:
                return 1
            elif second_start <= today <= second_end:
                return 2

        except (ValueError, KeyError):
            pass

        return 1  # По умолчанию возвращаем первый семестр

    @classmethod
    def load_settings(cls):
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            # Значения по умолчанию
            default_settings = {
                "database": {
                    "type": "sqlite",
                    "name": "schedule.db"
                },
                "academic_year": {"first_semester": {"start": "2023-09-01", "end": "2023-12-31"},
                                  "second_semester": {"start": "2024-01-09", "end": "2024-05-31"}}}

            # Создаем файл с настройками по умолчанию
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=4)

            return default_settings

        except Exception as e:
            print(f"Error loading settings: {e}")
            raise

    @classmethod
    def save_settings(cls, new_settings):
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(new_settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
            raise

    @classmethod
    def get_settings(cls):
        return cls.load_settings()
