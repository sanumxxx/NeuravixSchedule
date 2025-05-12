import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота, который вы получите от @BotFather
TOKEN = "6897033821:AAE80aF2-Kvn3dF8CSHH_PPMDoyulJMiLoo"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот для создания расписания с кнопками.\n\n"
        "Чтобы создать расписание, отправьте мне команду:\n"
        "/schedule номер_недели\n\n"
        "Например: /schedule 29"
    )


# Функция для создания кнопок в два столбца
def create_two_column_buttons(text):
    lines = text.strip().split('\n')
    keyboard = []
    current_row = []

    for line in lines:
        if "|" not in line:
            continue

        parts = line.split("|", 1)
        button_text = parts[0].strip()
        button_url = parts[1].strip()

        # Проверяем, что URL начинается с http:// или https://
        if not (button_url.startswith("http://") or button_url.startswith("https://")):
            button_url = "https://" + button_url

        # Создаем кнопку
        button = InlineKeyboardButton(text=button_text, url=button_url)

        # Добавляем кнопку в текущий ряд
        current_row.append(button)

        # Если в текущем ряду уже 2 кнопки, добавляем ряд в клавиатуру и создаем новый
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []

    # Если остались кнопки в последнем ряду, добавляем его
    if current_row:
        keyboard.append(current_row)

    return keyboard


# Обработчик команды /schedule
async def create_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "Пожалуйста, укажите номер недели.\n"
            "Например: /schedule 29"
        )
        return

    week_number = context.args[0]

    # Создаем заголовок сообщения
    header = f"СЕМЕСТР 2\n\nНЕДЕЛЯ {week_number} ВЫГРУЖЕНА\n\nОтправляю расписание для преподавателей на {week_number} НЕДЕЛИ.\n____________________________________________________"

    # Список преподавателей с URL, где неделя заменена на нужную
    teachers_data = [
        f"Бездитный А.А. | https://kafit.ru/timetable?type=teacher&value=%D0%91%D0%B5%D0%B7%D0%B4%D0%B8%D1%82%D0%BD%D1%8B%D0%B9+%D0%90.%D0%90.&semester=2&week={week_number}",
        f"Белокопытов А.В. | https://kafit.ru/timetable?type=teacher&value=%D0%91%D0%B5%D0%BB%D0%BE%D0%BA%D0%BE%D0%BF%D1%8B%D1%82%D0%BE%D0%B2+%D0%90.%D0%92.&semester=2&week={week_number}",
        f"Береговой А.В. | https://kafit.ru/timetable?type=teacher&value=%D0%91%D0%B5%D1%80%D0%B5%D0%B3%D0%BE%D0%B2%D0%BE%D0%B9+%D0%90.%D0%92.&semester=2&week={week_number}",
        f"Береговой1 А.В. | https://kafit.ru/timetable?type=teacher&value=%D0%91%D0%B5%D1%80%D0%B5%D0%B3%D0%BE%D0%B2%D0%BE%D0%B91+%D0%90.%D0%92.&semester=2&week={week_number}",
        f"Букреев Д.А. | https://kafit.ru/timetable?type=teacher&value=%D0%91%D1%83%D0%BA%D1%80%D0%B5%D0%B5%D0%B2+%D0%94.%D0%90.&semester=2&week={week_number}",
        f"Вакансия_26931 (каф.4) | https://kafit.ru/timetable?type=teacher&value=%D0%92%D0%B0%D0%BA%D0%B0%D0%BD%D1%81%D0%B8%D1%8F_26931+%28%D0%BA%D0%B0%D1%84.4%29&semester=2&week={week_number}",
        f"Вакансия_27025 (каф.4) | https://kafit.ru/timetable?type=teacher&value=%D0%92%D0%B0%D0%BA%D0%B0%D0%BD%D1%81%D0%B8%D1%8F_27025+%28%D0%BA%D0%B0%D1%84.4%29&semester=2&week={week_number}",
        f"Дяченко А.С. | https://kafit.ru/timetable?type=teacher&value=Дяченко+А.С.&semester=2&week={week_number}",
        f"Еремеев В.С. | https://kafit.ru/timetable?type=teacher&value=%D0%95%D1%80%D0%B5%D0%BC%D0%B5%D0%B5%D0%B2+%D0%92.%D0%A1.&semester=2&week={week_number}",
        f"Караев А.И. | https://kafit.ru/timetable?type=teacher&value=%D0%9A%D0%B0%D1%80%D0%B0%D0%B5%D0%B2+%D0%90.%D0%98.&semester=2&week={week_number}",
        f"Лебедев В.А. | https://kafit.ru/timetable?type=teacher&value=%D0%9B%D0%B5%D0%B1%D0%B5%D0%B4%D0%B5%D0%B2+%D0%92.%D0%90.&semester=2&week={week_number}",
        f"Луцкий Е.А. | https://kafit.ru/timetable?type=teacher&value=%D0%9B%D1%83%D1%86%D0%BA%D0%B8%D0%B9+%D0%95.%D0%90.&semester=2&week={week_number}",
        f"Милько Д.А. | https://kafit.ru/timetable?type=teacher&value=%D0%9C%D0%B8%D0%BB%D1%8C%D0%BA%D0%BE+%D0%94.%D0%90.&semester=2&week={week_number}",
        f"Мовчан В.Ф. | https://kafit.ru/timetable?type=teacher&value=%D0%9C%D0%BE%D0%B2%D1%87%D0%B0%D0%BD+%D0%92.%D0%A4.&semester=2&week={week_number}",
        f"Мозговенко А.А. | https://kafit.ru/timetable?type=teacher&value=%D0%9C%D0%BE%D0%B7%D0%B3%D0%BE%D0%B2%D0%B5%D0%BD%D0%BA%D0%BE+%D0%90.%D0%90.&semester=2&week={week_number}",
        f"Найдыш А.В. | https://kafit.ru/timetable?type=teacher&value=%D0%9D%D0%B0%D0%B9%D0%B4%D1%8B%D1%88+%D0%90.%D0%92.&semester=2&week={week_number}",
        f"Окулова Е.А. | https://kafit.ru/timetable?type=teacher&value=%D0%9E%D0%BA%D1%83%D0%BB%D0%BE%D0%B2%D0%B0+%D0%95.%D0%90.&semester=2&week={week_number}",
        f"Олейник Н.П. | https://kafit.ru/timetable?type=teacher&value=%D0%9E%D0%BB%D0%B5%D0%B9%D0%BD%D0%B8%D0%BA+%D0%9D.%D0%9F.&semester=2&week={week_number}",
        f"Покуса Т.В. | https://kafit.ru/timetable?type=teacher&value=%D0%9F%D0%BE%D0%BA%D1%83%D1%81%D0%B0+%D0%A2.%D0%92.&semester=2&week={week_number}",
        f"Саньков С.М. | https://kafit.ru/timetable?type=teacher&value=%D0%A1%D0%B0%D0%BD%D1%8C%D0%BA%D0%BE%D0%B2+%D0%A1.%D0%9C.&semester=2&week={week_number}",
        f"Строкань О.В. | https://kafit.ru/timetable?type=teacher&value=%D0%A1%D1%82%D1%80%D0%BE%D0%BA%D0%B0%D0%BD%D1%8C+%D0%9E.%D0%92.&semester=2&week={week_number}",
        f"Ступницкий В.С. | https://kafit.ru/timetable?type=teacher&value=%D0%A1%D1%82%D1%83%D0%BF%D0%BD%D0%B8%D1%86%D0%BA%D0%B8%D0%B9+%D0%92.%D0%A1.&semester=2&week={week_number}",
        f"Трусова И.С. | https://kafit.ru/timetable?type=teacher&value=%D0%A2%D1%80%D1%83%D1%81%D0%BE%D0%B2%D0%B0+%D0%98.%D0%A1.&semester=2&week={week_number}",
        f"Трусов Е.А. | https://kafit.ru/timetable?type=teacher&value=%D0%A2%D1%80%D1%83%D1%81%D0%BE%D0%B2+%D0%95.%D0%90.&semester=2&week={week_number}"
    ]

    # Создаем кнопки из данных преподавателей
    teachers_data_str = "\n".join(teachers_data)
    keyboard = create_two_column_buttons(teachers_data_str)

    if not keyboard:
        await update.message.reply_text("Ошибка создания кнопок.")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с заголовком и кнопками
    await update.message.reply_text(
        header,
        reply_markup=reply_markup
    )


# Обработчик текстовых сообщений
async def process_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = update.message.text

    # Проверяем, может быть это запрос на создание расписания с номером недели
    week_match = re.match(r'^\s*(\d+)\s*$', message_text)
    if week_match:
        week_number = week_match.group(1)
        context.args = [week_number]
        await create_schedule(update, context)
        return

    # Если это не запрос на создание расписания, объясняем как пользоваться ботом
    await update.message.reply_text(
        "Чтобы создать расписание, отправьте мне команду /schedule с номером недели.\n"
        "Например: /schedule 29\n\n"
        "Или просто отправьте номер недели."
    )


# Функция для запуска бота
def main() -> None:
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", create_schedule))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_buttons))

    # Запускаем бота
    print("Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()