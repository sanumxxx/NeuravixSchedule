import subprocess
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
import os
from waitress import serve
from app import create_app  # Импортируем create_app вместо app

# Загружаем переменные из .flaskenv
load_dotenv('.flaskenv')


def run_server():
    # Создаем приложение
    app = create_app()

    while True:
        try:
            print(f"[{datetime.now()}] Starting Flask application with Waitress...")

            # Запускаем через waitress
            serve(
                app,
                host='0.0.0.0',
                port=5000,
                threads=4,
                asyncore_use_poll=True,
                channel_timeout=300
            )

        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            sys.exit(0)

        except Exception as e:
            print(f"[{datetime.now()}] Unexpected error: {str(e)}")
            print("Restarting in 5 seconds...")
            time.sleep(5)
            continue


if __name__ == "__main__":
    print("Starting Flask application with Waitress...")
    print(f"FLASK_APP: {os.getenv('FLASK_APP')}")
    print(f"FLASK_ENV: {os.getenv('FLASK_ENV')}")
    print(f"FLASK_DEBUG: {os.getenv('FLASK_DEBUG')}")
    run_server()