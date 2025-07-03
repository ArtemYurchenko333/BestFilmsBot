import os
import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from telegram.error import BadRequest # Импортируем BadRequest для обработки ошибок
import google.generativeai as genai
from telegram.helpers import escape_markdown

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Переменные для состояний разговора ---
SELECT_GENRES, SELECT_YEARS, ENTER_KEYWORDS = range(3)

# --- Переменные окружения ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Проверка наличия всех необходимых переменных окружения
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не установлен.")
    exit(1)
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY не установлен.")
    exit(1)
if not DATABASE_URL:
    logger.error("DATABASE_URL не установлен.")
    exit(1)

# --- Инициализация Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-flash')

# --- Списки для жанров и годов (можно расширить) ---
FILM_GENRES = {
    "Боевик": "action", "Комедия": "comedy", "Драма": "drama",
    "Триллер": "thriller", "Ужасы": "horror", "Фантастика": "sci-fi",
    "Фэнтези": "fantasy", "Приключения": "adventure", "Мелодрама": "romance",
    "Мультфильм": "animation", "Детектив": "mystery", "Исторический": "historical",
    "Документальный": "documentary"
}

FILM_YEAR_RANGES = {
    "00-е (2000-2009)": "2000-2009",
    "10-е (2010-2020)": "2010-2020",
    "20-е (2020-2029)": "2020-2029",
    "30-е (1930-1939)": "1930-1939",
    "40-е (1940-1949)": "1940-1949",
    "50-е (1950-1959)": "1950-1959",
    "60-е (1960-1969)": "1960-1969",
    "70-е (1970-1979)": "1970-1979",
    "80-е (1980-1989)": "1980-1989",
    "90-е (1990-1999)": "1990-1999"
}


# --- Функции для работы с базой данных ---
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Успешно подключено к базе данных PostgreSQL.")
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        return None

def create_tables_if_not_exists():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users2 (
                    id BIGINT PRIMARY KEY,
                    telegram_username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    phone_number VARCHAR(20),
                    city VARCHAR(255),
                    country VARCHAR(255),
                    ip_address VARCHAR(45),
                    email VARCHAR(255),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS films (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    telegram_username VARCHAR(255),
                    user_first_name VARCHAR(255),
                    user_last_name VARCHAR(255),
                    user_country VARCHAR(255),
                    user_city VARCHAR(255),
                    user_phone_number VARCHAR(20),
                    genres TEXT NOT NULL,
                    years TEXT NOT NULL,
                    keywords TEXT,
                    gemini_response TEXT NOT NULL,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users2(id)
                );
            """)
            conn.commit()
            logger.info("Таблицы users2 и films проверены/созданы.")
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}")
        finally:
            if conn:
                conn.close()

async def save_user_data(user_id: int, username: str, first_name: str, last_name: str):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT id FROM users2 WHERE id = %s", (user_id,))
            if cursor.fetchone() is None:
                # Если пользователя нет, вставляем нового
                cursor.execute(
                    """
                    INSERT INTO users2 (id, telegram_username, first_name, last_name)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (user_id, username, first_name, last_name)
                )
                logger.info(f"Новый пользователь {user_id} сохранен в БД.")
            else:
                logger.info(f"Пользователь {user_id} уже существует в БД.")
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при сохранении/обновлении пользователя {user_id}: {e}")
        finally:
            if conn:
                conn.close()

async def save_film_request(user_id: int, username: str, first_name: str, last_name: str,
                             genres: str, years: str, keywords: str, gemini_response: str):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Заглушки для полей, которые не запрашиваются в боте, но есть в таблице films
            country = ""
            city = ""
            phone_number = ""

            cursor.execute(
                """
                INSERT INTO films (user_id, telegram_username, user_first_name, user_last_name,
                                   user_country, user_city, user_phone_number,
                                   genres, years, keywords, gemini_response)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (user_id, username, first_name, last_name, country, city, phone_number,
                 genres, years, keywords, gemini_response)
            )
            conn.commit()
            logger.info(f"Запрос на фильм для пользователя {user_id} успешно сохранен в БД.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении запроса на фильм в базу данных: {e}")
        finally:
            if conn:
                conn.close()

# --- Функции-обработчики команд и сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await save_user_data(user.id, user.username, user.first_name, user.last_name)

    # Сбрасываем предыдущие выборы пользователя
    context.user_data.clear()
    context.user_data['selected_genres'] = [] # Теперь будет хранить только один жанр
    context.user_data['selected_years'] = []

    keyboard = []
    for genre_name in FILM_GENRES.keys():
        keyboard.append([InlineKeyboardButton(genre_name, callback_data=f"genre_{genre_name}")])
    # Кнопка "Подтвердить выбор жанров" удалена

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Я бот для подбора фильмов. "
        "Пожалуйста, выберите один жанр:"
    , reply_markup=reply_markup)
    logger.info(f"Пользователь {user.id} начал поиск фильмов. Отправлено меню жанров.")
    return SELECT_GENRES

async def select_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("genre_"):
        genre = query.data.replace("genre_", "")
        context.user_data['selected_genres'] = [genre] # Теперь всегда один жанр
        logger.info(f"Пользователь {user_id} выбрал жанр: {genre}. Текущие жанры: {context.user_data['selected_genres']}")

        # Сразу переходим к выбору годов
        keyboard = []
        for year_range_name in FILM_YEAR_RANGES.keys():
            keyboard.append([InlineKeyboardButton(year_range_name, callback_data=f"year_{year_range_name}")])
        keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                f"Отлично! Вы выбрали жанр: *{genre}*\n\n" # Указываем выбранный жанр
                "Теперь выберите года выпуска (можно выбрать несколько):",
                parse_mode='Markdown', # Включаем Markdown для выделения
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_genres: {e}. Возможно, сообщение уже изменено или устарело.")
            await query.message.reply_text(
                f"Отлично! Вы выбрали жанр: *{genre}*\n\n"
                "Теперь выберите года выпуска (можно выбрать несколько):",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        return SELECT_YEARS # Переходим к следующему состоянию

    # Если вдруг пришел какой-то другой колбэк, который не начинается с "genre_"
    return SELECT_GENRES


async def select_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("year_"):
        year_range_name = query.data.replace("year_", "")
        selected_years = context.user_data.get('selected_years', [])

        if year_range_name in selected_years:
            selected_years.remove(year_range_name)
            message_text = f"Года '{year_range_name}' удалены. "
        else:
            selected_years.append(year_range_name)
            message_text = f"Года '{year_range_name}' добавлены. "

        context.user_data['selected_years'] = selected_years
        logger.info(f"Пользователь {user_id} выбрал года: {year_range_name}. Текущие года: {selected_years}")

        # Обновляем клавиатуру для отображения выбранных годов
        keyboard = []
        for yr_name in FILM_YEAR_RANGES.keys():
            emoji = "✅ " if yr_name in selected_years else ""
            keyboard.append([InlineKeyboardButton(f"{emoji}{yr_name}", callback_data=f"year_{yr_name}")])
        keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                f"Выберите года выпуска (можно выбрать несколько):\n"
                f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}\n"
                f"{message_text}",
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_years (year_): {e}. Возможно, сообщение уже изменено или устарело.")
            await query.message.reply_text(
                f"Выберите года выпуска (можно выбрать несколько):\n"
                f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}\n"
                f"{message_text}",
                reply_markup=reply_markup
            )
        return SELECT_YEARS

    elif query.data == "confirm_years":
        selected_years = context.user_data.get('selected_years', [])
        if not selected_years:
            await query.answer("Пожалуйста, выберите хотя бы один диапазон годов.", show_alert=True)
            return SELECT_YEARS
        
        context.user_data['selected_years'] = selected_years
        logger.info(f"Пользователь {user_id} подтвердил выбор годов: {selected_years}")
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад к годам", callback_data="back_to_years")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантастика с неожиданным концом'):",
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_years (confirm_years): {e}. Возможно, сообщение уже изменено или устарело.")
            await query.message.reply_text(
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантастика с неожиданным концом'):",
                reply_markup=reply_markup
            )
        return ENTER_KEYWORDS

    return SELECT_YEARS


async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = user.id
    keywords = update.message.text
    context.user_data['keywords'] = keywords
    logger.info(f"Пользователь {user_id} ввел ключевые слова: '{keywords}'")

    selected_genres = context.user_data.get('selected_genres', [])
    selected_years = context.user_data.get('selected_years', [])

    if not selected_genres or not selected_years:
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните сначала с /start.")
        return ConversationHandler.END

    await update.message.reply_text("Отлично! Ищу лучшие фильмы по вашему запросу. Это может занять немного времени...")

    # Формируем промпт для Gemini
    genres_str = ", ".join(selected_genres)
    years_str = ", ".join([FILM_YEAR_RANGES[yr] for yr in selected_years])

    prompt_text = (
        f"Предложи ТОП-3 лучших фильма в жанрах: {genres_str}, "
        f"выпущенных в годах: {years_str}. "
        f"Ориентируйся на следующие ключевые слова/описание: '{keywords}'. "
        "Для каждого фильма укажи: Название, Год выпуска, Жанр(ы), Краткое описание (1-2 предложения). "
        "Форматируй ответ так, чтобы его было легко читать. Только лучшие фильмы по этому запросу."
    )

    gemini_response_text = ""
    try:
        response = model.generate_content(
            prompt_text,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        gemini_response_text = response.text
        await update.message.reply_text(gemini_response_text)

        # Сохраняем данные в базу данных
        await save_film_request(
            user_id,
            user.username,
            user.first_name,
            user.last_name,
            genres_str,
            years_str,
            keywords,
            gemini_response_text
        )

    except Exception as e:
        logger.error(f"Ошибка при обращении к Gemini API: {e}")
        await update.message.reply_text(
            "Извини, произошла ошибка при получении информации о фильмах. Попробуй еще раз позже."
        )

    # Предлагаем начать заново
    keyboard = [[InlineKeyboardButton("Начать новый поиск", callback_data="start_over")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Надеюсь, вам что-то подойдет!", reply_markup=reply_markup)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает текущий разговор."""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил разговор.")
    await update.message.reply_text(
        'Поиск отменен. Если хочешь начать сначала, используй команду /start.'
    )
    # Очищаем данные пользователя в контексте
    context.user_data.clear()
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на неизвестные команды/сообщения."""
    await update.message.reply_text("Извини, я не понял эту команду. Попробуй /start, чтобы начать поиск фильмов.")


# --- Обработчики кнопок "Назад" ---
async def back_to_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    # Сбрасываем выбранные года, если пользователь возвращается к жанрам
    context.user_data['selected_years'] = []

    keyboard = []
    # Теперь нет "Подтвердить выбор жанров"
    # selected_genres = context.user_data.get('selected_genres', []) # Не используем для отображения галочки, т.к. жанр только один и он уже выбран
    for genre_name in FILM_GENRES.keys():
        # Если нужно показать "выбранный" жанр после возвращения
        is_selected = context.user_data.get('selected_genres') and context.user_data['selected_genres'][0] == genre_name
        emoji = "✅ " if is_selected else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{genre_name}", callback_data=f"genre_{genre_name}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(
            f"Пожалуйста, выберите один жанр:"
            # f"Выбрано: {', '.join(selected_genres) if selected_genres else 'ничего'}", # Эта строка не нужна
            , reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_genres: {e}. Возможно, сообщение уже изменено или устарело.")
        await query.message.reply_text(
            f"Пожалуйста, выберите один жанр:"
            , reply_markup=reply_markup
        )
    logger.info(f"Пользователь {query.from_user.id} вернулся к выбору жанров.")
    return SELECT_GENRES


async def back_to_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Сбрасываем ключевые слова, если пользователь возвращается к годам
    context.user_data['keywords'] = None
    
    keyboard = []
    selected_years = context.user_data.get('selected_years', [])
    for year_range_name in FILM_YEAR_RANGES.keys():
        emoji = "✅ " if year_range_name in selected_years else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{year_range_name}", callback_data=f"year_{year_range_name}")])
    keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(
            f"Выберите года выпуска (можно выбрать несколько):\n"
            f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}",
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_years: {e}. Возможно, сообщение уже изменено или устарело.")
        await query.message.reply_text(
            f"Выберите года выпуска (можно выбрать несколько):\n"
            f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}",
            reply_markup=reply_markup
        )
    logger.info(f"Пользователь {query.from_user.id} вернулся к выбору годов.")
    return SELECT_YEARS


# --- Основная функция для запуска бота ---
def main() -> None:
    """Запускает бота."""
    create_tables_if_not_exists()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_GENRES: [
                CallbackQueryHandler(select_genres, pattern=r"^genre_") # Изменено для обработки только выбора жанра
            ],
            SELECT_YEARS: [
                CallbackQueryHandler(select_years, pattern=r"^(year_|confirm_years)$"),
                CallbackQueryHandler(back_to_genres, pattern="^back_to_genres$")
            ],
            ENTER_KEYWORDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keywords),
                CallbackQueryHandler(back_to_years, pattern="^back_to_years$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.COMMAND | filters.TEXT, unknown)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(start, pattern="^start_over$"))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Бот запущен. Ожидание сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
