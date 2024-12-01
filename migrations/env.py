from logging.config import fileConfig
import logging
from flask import current_app

from alembic import context

config = context.config

if config.config_file_name is not None:
    # Только если файл конфигурации существует
    try:
        fileConfig(config.config_file_name)
    except KeyError:
        # Если возникает ошибка с форматтерами, создаем базовую конфигурацию
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('alembic.env')

# Получаем метаданные из приложения
target_metadata = current_app.extensions['migrate'].db.metadata

# Остальные настройки
config.set_main_option(
    'sqlalchemy.url',
    str(current_app.extensions['migrate'].db.engine.url).replace('%', '%%')
)

def run_migrations_offline():
    """Запуск миграций в 'офлайн' режиме"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, 
        target_metadata=target_metadata, 
        literal_binds=True, 
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Запуск миграций в 'онлайн' режиме"""
    connectable = current_app.extensions['migrate'].db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()