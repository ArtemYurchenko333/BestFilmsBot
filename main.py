import os
import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from telegram.error import BadRequest, TimedOut
import google.generativeai as genai
from telegram.helpers import escape_markdown
import re

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Переменные для состояний разговора ---
SELECT_GENRES, SELECT_YEARS, ENTER_KEYWORDS = range(3)

# --- Переменные окружения ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN3")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY3")
DATABASE_URL = os.getenv("DATABASE_URL3")

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
                CREATE TABLE IF NOT EXISTS users (
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
                    genres TEXT NOT NULL,
                    years TEXT NOT NULL,
                    keywords TEXT,
                    film1 VARCHAR(255),
                    film2 VARCHAR(255),
                    film3 VARCHAR(255),
                    gemini_response TEXT NOT NULL,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_city VARCHAR(255),
                    user_phone_number VARCHAR(20),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)
            conn.commit()
            logger.info("Таблицы users и films проверены/созданы.")
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
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO users (id, telegram_username, first_name, last_name)
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

async def save_film_request(user_id: int, genres: str, years: str, keywords: str, gemini_response: str,
                            film1_name: str = None, film2_name: str = None, film3_name: str = None,
                            username: str = None, first_name: str = None, last_name: str = None,
                            country: str = "", city: str = "", phone_number: str = ""):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO films (
                    user_id, telegram_username, user_first_name, user_last_name, user_country,
                    genres, years, keywords, gemini_response,
                    film1, film2, film3,
                    requested_at,
                    user_city, user_phone_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, DEFAULT, %s, %s);
                """,
                (user_id, username, first_name, last_name, country,
                 genres, years, keywords, gemini_response,
                 film1_name, film2_name, film3_name,
                 city, phone_number)
            )
            conn.commit()
            logger.info(f"Запрос на фильм для пользователя {user_id} успешно сохранен в БД с названиями фильмов.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении запроса на фильм в базу данных: {e}")
        finally:
            if conn:
                conn.close()

# --- Вспомогательная функция для парсинга названий фильмов ---
def extract_film_names(gemini_response_text: str) -> list:
    """
    Парсит ответ Gemini для извлечения названий фильмов.
    Возвращает список из 3х названий фильмов (None, если фильм не найден).
    """
    film_names = [None, None, None]
    
    pattern = r'^\s*(\d+)\.\s*(?:Название фильма:\s*)?([^:.]+)'
    matches = re.findall(pattern, gemini_response_text, re.MULTILINE)

    for num_str, name_candidate in matches:
        num = int(num_str)
        if 1 <= num <= 3:
            cleaned_name = re.sub(r'[,.]\s*$', '', name_candidate).strip()
            film_names[num - 1] = cleaned_name
            logger.info(f"Парсинг: найден фильм {num}: '{cleaned_name}'")
    
    while len(film_names) < 3:
        film_names.append(None)

    logger.info(f"Извлеченные названия фильмов: {film_names}")
    return film_names


# --- Функции-обработчики команд и сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await save_user_data(user.id, user.username, user.first_name, user.last_name)

    context.user_data.clear()
    context.user_data['selected_genres'] = []
    context.user_data['selected_years'] = []

    keyboard = []
    for genre_name in FILM_GENRES.keys():
        keyboard.append([InlineKeyboardButton(genre_name, callback_data=f"genre_{genre_name}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Если это callback_query (т.е. нажата кнопка "Начать новый поиск")
        if update.callback_query:
            # Отвечаем на callback_query, чтобы убрать "часики" с кнопки
            await update.callback_query.answer("Начинаем новый поиск...")
            
            # Попытаемся отредактировать исходное сообщение, чтобы убрать кнопки
            try:
                await update.callback_query.message.edit_reply_markup(reply_markup=None)
            except BadRequest as e:
                logger.warning(f"Не удалось отредактировать reply_markup в start для callback_query: {e}")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при редактировании reply_markup: {e}")
            
            # Отправляем новое сообщение в тот же чат
            await update.callback_query.message.reply_html(
                f"Привет, {user.mention_html()}! Я бот для подбора фильмов. "
                "Пожалуйста, выберите один жанр:"
                , reply_markup=reply_markup
            )
        # Если это текстовое сообщение (например, команда /start)
        elif update.message:
            await update.message.reply_html(
                f"Привет, {user.mention_html()}! Я бот для подбора фильмов. "
                "Пожалуйста, выберите один жанр:"
                , reply_markup=reply_markup
            )
        else:
            logger.error("Функция start вызвана без update.message или update.callback_query.")
            # Если ни message, ни callback_query нет, пытаемся отправить сообщение через effective_chat
            if update.effective_chat:
                await update.effective_chat.send_message(
                    f"Привет, {user.mention_html()}! Я бот для подбора фильмов. "
                    "Пожалуйста, выберите один жанр:"
                    , reply_markup=reply_markup, parse_mode='HTML'
                )

    except BadRequest as e:
        logger.error(f"Ошибка BadRequest при отправке стартового сообщения в start: {e}")
        # В случае BadRequest, попробуем отправить просто новое сообщение, если возможно.
        if update.effective_chat:
            await update.effective_chat.send_message(
                f"Привет, {user.mention_html()}! Я бот для подбора фильмов. "
                "Пожалуйста, выберите один жанр:"
                , reply_markup=reply_markup, parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при отправке стартового сообщения в start: {e}")
        if update.effective_chat:
            await update.effective_chat.send_message("Извините, произошла непредвиденная ошибка. Пожалуйста, попробуйте команду /start еще раз.")


    logger.info(f"Пользователь {user.id} начал поиск фильмов. Отправлено меню жанров.")
    return SELECT_GENRES

async def select_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("genre_"):
        genre = query.data.replace("genre_", "")
        context.user_data['selected_genres'] = [genre]
        logger.info(f"Пользователь {user_id} выбрал жанр: {genre}. Текущие жанры: {context.user_data['selected_genres']}")

        keyboard = []
        for year_range_name in FILM_YEAR_RANGES.keys():
            keyboard.append([InlineKeyboardButton(year_range_name, callback_data=f"year_{year_range_name}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            # Попытаемся отредактировать сообщение
            await query.edit_message_text(
                f"Отлично! Вы выбрали жанр: *{genre}*\n\n"
                "Теперь выберите один диапазон годов выпуска:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_genres: {e}. Возможно, сообщение уже изменено, устарело, или текст не изменился.")
            # Если не удалось отредактировать, отправляем новое сообщение
            await query.message.reply_text(
                f"Отлично! Вы выбрали жанр: *{genre}*\n\n"
                "Теперь выберите один диапазон годов выпуска:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except TimedOut as e:
            logger.error(f"Timeout при редактировании сообщения в select_genres: {e}")
            await query.message.reply_text(
                f"Извините, произошла задержка. Вы выбрали жанр: *{genre}*\n\n"
                "Теперь выберите один диапазон годов выпуска:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в select_genres: {e}")
            await query.message.reply_text("Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return SELECT_YEARS

    return SELECT_GENRES


async def select_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("year_"):
        year_range_name = query.data.replace("year_", "")
        context.user_data['selected_years'] = [year_range_name]
        logger.info(f"Пользователь {user_id} выбрал года: {year_range_name}. Текущие года: {context.user_data['selected_years']}")

        selected_genre = context.user_data['selected_genres'][0] if context.user_data['selected_genres'] else "не выбран"

        keyboard = [[InlineKeyboardButton("⬅️ Назад к годам", callback_data="back_to_years")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                f"Вы выбрали:\n"
                f"Жанр: *{selected_genre}*\n"
                f"Года: *{year_range_name}*\n\n"
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантастика с неожиданным концом'):",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_years: {e}. Возможно, сообщение уже изменено, устарело, или текст не изменился.")
            await query.message.reply_text(
                f"Вы выбрали:\n"
                f"Жанр: *{selected_genre}*\n"
                f"Года: *{year_range_name}*\n\n"
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантафика с неожиданным концом'):",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except TimedOut as e:
            logger.error(f"Timeout при редактировании сообщения в select_years: {e}")
            await query.message.reply_text(
                f"Извините, произошла задержка. Вы выбрали:\n"
                f"Жанр: *{selected_genre}*\n"
                f"Года: *{year_range_name}*\n\n"
                "Теперь введите ключевые слова для поиска:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в select_years: {e}")
            await query.message.reply_text("Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.")
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

    genres_str = ", ".join(selected_genres)
    years_str = ", ".join([FILM_YEAR_RANGES[yr] for yr in selected_years])

    prompt_text = (
        f"Предложи ТОП-3 лучших фильма в жанрах: {genres_str}, "
        f"выпущенных в годах: {years_str}. "
        f"Ориентируйся на следующие ключевые слова/описание: '{keywords}'. "
        "Для каждого фильма укажи: Название, Год выпуска, Жанр(ы), Краткое описание (1-2 предложения). "
        "Форматируй ответ как нумерованный список, например:\n"
        "1. Название фильма 1: Год, Жанр. Краткое описание.\n"
        "2. Название фильма 2: Год, Жанр. Краткое описание.\n"
        "3. Название фильма 3: Год, Жанр. Краткое описание.\n"
        "Только лучшие фильмы по этому запросу."
    )

    gemini_response_text = ""
    film_names = [None, None, None]
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

        film_names = extract_film_names(gemini_response_text)
        
        await save_film_request(
            user_id=user.id,
            genres=genres_str,
            years=years_str,
            keywords=keywords,
            gemini_response=gemini_response_text,
            film1_name=film_names[0],
            film2_name=film_names[1],
            film3_name=film_names[2],
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            country=context.user_data.get('user_country', ''),
            city=context.user_data.get('user_city', ''),
            phone_number=context.user_data.get('user_phone_number', '')
        )

    except Exception as e:
        logger.error(f"Ошибка при обращении к Gemini API или обработке ответа: {e}")
        await update.message.reply_text(
            "Извини, произошла ошибка при получении информации о фильмах. Попробуй еще раз позже."
        )

    keyboard = [[InlineKeyboardButton("Начать новый поиск", callback_data="start_over")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Надеюсь, вам что-то подойдет!", reply_markup=reply_markup)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил разговор.")
    await update.message.reply_text(
        'Поиск отменен. Если хочешь начать сначала, используй команду /start.'
    )
    context.user_data.clear()
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Извини, я не понял эту команду. Попробуй /start, чтобы начать поиск фильмов.")


async def back_to_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    context.user_data['selected_years'] = []

    keyboard = []
    for genre_name in FILM_GENRES.keys():
        is_selected = context.user_data.get('selected_genres') and context.user_data['selected_genres'][0] == genre_name
        emoji = "✅ " if is_selected else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{genre_name}", callback_data=f"genre_{genre_name}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(
            f"Пожалуйста, выберите один жанр:",
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_genres: {e}. Возможно, сообщение уже изменено, устарело, или текст не изменился.")
        await query.message.reply_text(
            f"Пожалуйста, выберите один жанр:",
            reply_markup=reply_markup
        )
    except TimedOut as e:
        logger.error(f"Timeout при редактировании сообщения в back_to_genres: {e}")
        await query.message.reply_text(
            "Извините, произошла задержка. Пожалуйста, выберите один жанр:"
            , reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в back_to_genres: {e}")
        await query.message.reply_text("Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.")
    logger.info(f"Пользователь {query.from_user.id} вернулся к выбору жанров.")
    return SELECT_GENRES


async def back_to_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data['keywords'] = None
    
    keyboard = []
    for year_range_name in FILM_YEAR_RANGES.keys():
        is_selected = context.user_data.get('selected_years') and context.user_data['selected_years'][0] == year_range_name
        emoji = "✅ " if is_selected else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{year_range_name}", callback_data=f"year_{year_range_name}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(
            f"Теперь выберите один диапазон годов выпуска:",
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_years: {e}. Возможно, сообщение уже изменено, устарело, или текст не изменился.")
        await query.message.reply_text(
            f"Теперь выберите один диапазон годов выпуска:",
            reply_markup=reply_markup
        )
    except TimedOut as e:
        logger.error(f"Timeout при редактировании сообщения в back_to_years: {e}")
        await query.message.reply_text(
            "Извините, произошла задержка. Теперь выберите один диапазон годов выпуска:"
            , reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в back_to_years: {e}")
        await query.message.reply_text("Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.")
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
                CallbackQueryHandler(select_genres, pattern=r"^genre_")
            ],
            SELECT_YEARS: [
                CallbackQueryHandler(select_years, pattern=r"^year_"),
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
