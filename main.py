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
if not TELEGRAM_BOT_TOKEN: [cite: 1]
    logger.error("TELEGRAM_BOT_TOKEN не установлен.") [cite: 1]
    exit(1) [cite: 1]
if not GEMINI_API_KEY: [cite: 1]
    logger.error("GEMINI_API_KEY не установлен.") [cite: 1]
    exit(1) [cite: 2]
if not DATABASE_URL: [cite: 2]
    logger.error("DATABASE_URL не установлен.") [cite: 2]
    exit(1) [cite: 2]

# --- Инициализация Gemini API ---
genai.configure(api_key=GEMINI_API_KEY) [cite: 2]
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
    "40-е (1940-1949)": "1940-1949", [cite: 3]
    "50-е (1950-1959)": "1950-1959", [cite: 3]
    "60-е (1960-1969)": "1960-1969", [cite: 3]
    "70-е (1970-1979)": "1970-1979", [cite: 3]
    "80-е (1980-1989)": "1980-1989", [cite: 3]
    "90-е (1990-1999)": "1990-1999" [cite: 3]
}


# --- Функции для работы с базой данных ---
def get_db_connection(): [cite: 3]
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Успешно подключено к базе данных PostgreSQL.") [cite: 3]
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}") [cite: 4]
        return None

def create_tables_if_not_exists():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users2 (
                    id BIGINT PRIMARY KEY, [cite: 5]
                    telegram_username VARCHAR(255), [cite: 5]
                    first_name VARCHAR(255), [cite: 5]
                    last_name VARCHAR(255), [cite: 5]
                    phone_number VARCHAR(20), [cite: 5]
                    city VARCHAR(255), [cite: 6]
                    country VARCHAR(255), [cite: 6]
                    ip_address VARCHAR(45), [cite: 6]
                    email VARCHAR(255), [cite: 6]
                    description TEXT, [cite: 7]
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS films (
                    id SERIAL PRIMARY KEY, [cite: 8]
                    user_id BIGINT NOT NULL, [cite: 8]
                    telegram_username VARCHAR(255), [cite: 8]
                    user_first_name VARCHAR(255), [cite: 8]
                    user_last_name VARCHAR(255), [cite: 9]
                    user_country VARCHAR(255), [cite: 9]
                    user_city VARCHAR(255), [cite: 9]
                    user_phone_number VARCHAR(20), [cite: 9]
                    genres TEXT NOT NULL, [cite: 10]
                    years TEXT NOT NULL, [cite: 10]
                    keywords TEXT, [cite: 10]
                    gemini_response TEXT NOT NULL, [cite: 10]
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, [cite: 10]
                    FOREIGN KEY (user_id) REFERENCES users2(id) [cite: 11]
                );
            """) [cite: 12]
            conn.commit() [cite: 12]
            logger.info("Таблицы users2 и films проверены/созданы.") [cite: 12]
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}") [cite: 12]
        finally:
            if conn:
                conn.close()

async def save_user_data(user_id: int, username: str, first_name: str, last_name: str): [cite: 13]
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT id FROM users2 WHERE id = %s", (user_id,)) [cite: 13]
            if cursor.fetchone() is None: [cite: 13]
                # Если пользователя нет, вставляем нового
                cursor.execute(
                    """
                    INSERT INTO users2 (id, telegram_username, first_name, last_name)
                    VALUES (%s, %s, %s, %s);
                    """, [cite: 15]
                    (user_id, username, first_name, last_name) [cite: 15]
                )
                logger.info(f"Новый пользователь {user_id} сохранен в БД.") [cite: 15]
            else:
                logger.info(f"Пользователь {user_id} уже существует в БД.") [cite: 16]
            conn.commit() [cite: 16]
        except Exception as e:
            logger.error(f"Ошибка при сохранении/обновлении пользователя {user_id}: {e}") [cite: 16]
        finally:
            if conn:
                conn.close() [cite: 17]

async def save_film_request(user_id: int, username: str, first_name: str, last_name: str,
                             genres: str, years: str, keywords: str, gemini_response: str):
    conn = get_db_connection()
    if conn:
        try: [cite: 18]
            cursor = conn.cursor() [cite: 18]
            # Заглушки для полей, которые не запрашиваются в боте, но есть в таблице films
            country = ""
            city = ""
            phone_number = ""

            cursor.execute(
                """
                INSERT INTO films (user_id, telegram_username, user_first_name, user_last_name,
                                   user_country, user_city, user_phone_number,
                                   genres, years, keywords, gemini_response) [cite: 20]
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, [cite: 21]
                (user_id, username, first_name, last_name, country, city, phone_number,
                 genres, years, keywords, gemini_response) [cite: 21]
            )
            conn.commit() [cite: 21]
            logger.info(f"Запрос на фильм для пользователя {user_id} успешно сохранен в БД.") [cite: 21]
        except Exception as e: [cite: 22]
            logger.error(f"Ошибка при сохранении запроса на фильм в базу данных: {e}") [cite: 22]
        finally:
            if conn:
                conn.close() [cite: 22]

# --- Функции-обработчики команд и сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await save_user_data(user.id, user.username, user.first_name, user.last_name) [cite: 22]

    # Сбрасываем предыдущие выборы пользователя
    context.user_data.clear() [cite: 23]
    context.user_data['selected_genres'] = [] [cite: 23]
    context.user_data['selected_years'] = [] [cite: 23]

    keyboard = []
    for genre_name in FILM_GENRES.keys():
        keyboard.append([InlineKeyboardButton(genre_name, callback_data=f"genre_{genre_name}")])
    keyboard.append([InlineKeyboardButton("Подтвердить выбор жанров", callback_data="confirm_genres")]) [cite: 23]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Я бот для подбора фильмов. " [cite: 24]
        "Пожалуйста, выберите от 1 до 3 жанров:"
    , reply_markup=reply_markup) [cite: 24]
    logger.info(f"Пользователь {user.id} начал поиск фильмов. Отправлено меню жанров.") [cite: 24]
    return SELECT_GENRES [cite: 24]

async def select_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("genre_"):
        genre = query.data.replace("genre_", "")
        selected_genres = context.user_data.get('selected_genres', [])

        if genre in selected_genres: [cite: 25]
            selected_genres.remove(genre) [cite: 25]
            message_text = f"Жанр '{genre}' удален. " [cite: 26]
        else:
            if len(selected_genres) < 3:
                selected_genres.append(genre) [cite: 27]
                message_text = f"Жанр '{genre}' добавлен. " [cite: 27]
            else:
                await query.answer("Вы можете выбрать не более 3 жанров.", show_alert=True) [cite: 27]
                message_text = "Выбрано 3 жанра. " [cite: 28]

        context.user_data['selected_genres'] = selected_genres [cite: 28]
        logger.info(f"Пользователь {user_id} выбрал жанр: {genre}. Текущие жанры: {selected_genres}") [cite: 28]

        # Обновляем клавиатуру, чтобы показать выбранные/невыбранные жанры
        keyboard = []
        for g_name in FILM_GENRES.keys():
            emoji = "✅ " if g_name in selected_genres else ""
            keyboard.append([InlineKeyboardButton(f"{emoji}{g_name}", callback_data=f"genre_{g_name}")])
        keyboard.append([InlineKeyboardButton("Подтвердить выбор жанров", callback_data="confirm_genres")]) [cite: 29]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try: # <--- Добавляем блок try-except здесь
            await query.edit_message_text(
                f"Выберите от 1 до 3 жанров:\n"
                f"Выбрано: {', '.join(selected_genres) if selected_genres else 'ничего'}\n"
                f"{message_text}",
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_genres (genre_): {e}. Возможно, сообщение уже изменено или устарело.")
            # Можно отправить новое сообщение вместо редактирования, если ошибка критична
            # или просто проигнорировать, так как await query.answer() уже был вызван
            await query.message.reply_text(
                f"Выберите от 1 до 3 жанров:\n"
                f"Выбрано: {', '.join(selected_genres) if selected_genres else 'ничего'}\n"
                f"{message_text}",
                reply_markup=reply_markup
            )
        
        return SELECT_GENRES [cite: 30]

    elif query.data == "confirm_genres":
        selected_genres = context.user_data.get('selected_genres', [])
        if not selected_genres:
            await query.answer("Пожалуйста, выберите хотя бы один жанр.", show_alert=True) [cite: 31]
            return SELECT_GENRES
        
        context.user_data['selected_genres'] = selected_genres [cite: 31]
        logger.info(f"Пользователь {user_id} подтвердил выбор жанров: {selected_genres}") [cite: 31]

        keyboard = []
        for year_range_name in FILM_YEAR_RANGES.keys():
            keyboard.append([InlineKeyboardButton(year_range_name, callback_data=f"year_{year_range_name}")])
        keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")]) [cite: 31]
        keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")]) [cite: 31]

        reply_markup = InlineKeyboardMarkup(keyboard)
        try: # <--- Добавляем блок try-except здесь
            await query.edit_message_text(
                "Отлично! Теперь выберите года выпуска (можно выбрать несколько):", [cite: 32]
                reply_markup=reply_markup
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_genres (confirm_genres): {e}. Возможно, сообщение уже изменено или устарело.")
            await query.message.reply_text(
                "Отлично! Теперь выберите года выпуска (можно выбрать несколько):",
                reply_markup=reply_markup
            )

        return SELECT_YEARS [cite: 32]

    return SELECT_GENRES


async def select_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("year_"):
        year_range_name = query.data.replace("year_", "")
        selected_years = context.user_data.get('selected_years', [])

        if year_range_name in selected_years: [cite: 33]
            selected_years.remove(year_range_name) [cite: 33]
            message_text = f"Года '{year_range_name}' удалены. " [cite: 34]
        else:
            selected_years.append(year_range_name) [cite: 34]
            message_text = f"Года '{year_range_name}' добавлены. " [cite: 35]

        context.user_data['selected_years'] = selected_years [cite: 35]
        logger.info(f"Пользователь {user_id} выбрал года: {year_range_name}. Текущие года: {selected_years}") [cite: 35]

        # Обновляем клавиатуру для отображения выбранных годов
        keyboard = []
        for yr_name in FILM_YEAR_RANGES.keys():
            emoji = "✅ " if yr_name in selected_years else ""
            keyboard.append([InlineKeyboardButton(f"{emoji}{yr_name}", callback_data=f"year_{yr_name}")])
        keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")]) [cite: 36]
        keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")]) [cite: 36]

        reply_markup = InlineKeyboardMarkup(keyboard)
        try: # <--- Добавляем блок try-except здесь
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
        return SELECT_YEARS [cite: 37]

    elif query.data == "confirm_years":
        selected_years = context.user_data.get('selected_years', [])
        if not selected_years:
            await query.answer("Пожалуйста, выберите хотя бы один диапазон годов.", show_alert=True) [cite: 37]
            return SELECT_YEARS
        
        context.user_data['selected_years'] = selected_years [cite: 37]
        logger.info(f"Пользователь {user_id} подтвердил выбор годов: {selected_years}") [cite: 38]
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад к годам", callback_data="back_to_years")]] [cite: 38]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try: # <--- Добавляем блок try-except здесь
            await query.edit_message_text(
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантастика с неожиданным концом'):",
                reply_markup=reply_markup [cite: 39]
            )
        except BadRequest as e:
            logger.warning(f"Ошибка при редактировании сообщения в select_years (confirm_years): {e}. Возможно, сообщение уже изменено или устарело.")
            await query.message.reply_text(
                "Наконец, введите ключевые слова, название фильма или описание того, что вы ищете (например, 'французский фильм про космос', 'комедия с Джимом Керри', 'научная фантастика с неожиданным концом'):",
                reply_markup=reply_markup
            )
        return ENTER_KEYWORDS [cite: 39]

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
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните сначала с /start.") [cite: 40]
        return ConversationHandler.END

    await update.message.reply_text("Отлично! Ищу лучшие фильмы по вашему запросу. Это может занять немного времени...")

    # Формируем промпт для Gemini
    genres_str = ", ".join(selected_genres)
    years_str = ", ".join([FILM_YEAR_RANGES[yr] for yr in selected_years])

    prompt_text = (
        f"Предложи ТОП-3 лучших фильма в жанрах: {genres_str}, "
        f"выпущенных в годах: {years_str}. "
        f"Ориентируйся на следующие ключевые слова/описание: '{keywords}'. " [cite: 41]
        "Для каждого фильма укажи: Название, Год выпуска, Жанр(ы), Краткое описание (1-2 предложения). "
        "Форматируй ответ так, чтобы его было легко читать. Только лучшие фильмы по этому запросу."
    )

    gemini_response_text = ""
    try:
        response = model.generate_content(
            prompt_text,
            safety_settings=[ [cite: 41]
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, [cite: 42]
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, [cite: 42]
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, [cite: 42]
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}, [cite: 42]
            ]
        )
        gemini_response_text = response.text [cite: 43]
        await update.message.reply_text(gemini_response_text) [cite: 43]

        # Сохраняем данные в базу данных
        await save_film_request(
            user_id,
            user.username,
            user.first_name,
            user.last_name,
            genres_str,
            years_str, [cite: 44]
            keywords, [cite: 44]
            gemini_response_text [cite: 44]
        )

    except Exception as e: [cite: 44]
        logger.error(f"Ошибка при обращении к Gemini API: {e}") [cite: 45]
        await update.message.reply_text(
            "Извини, произошла ошибка при получении информации о фильмах. Попробуй еще раз позже." [cite: 45]
        )

    # Предлагаем начать заново
    keyboard = [[InlineKeyboardButton("Начать новый поиск", callback_data="start_over")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Надеюсь, вам что-то подойдет!", reply_markup=reply_markup) [cite: 45]

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает текущий разговор."""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил разговор.") [cite: 46]
    await update.message.reply_text(
        'Поиск отменен. Если хочешь начать сначала, используй команду /start.' [cite: 46]
    )
    # Очищаем данные пользователя в контексте
    context.user_data.clear() [cite: 46]
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на неизвестные команды/сообщения."""
    await update.message.reply_text("Извини, я не понял эту команду. Попробуй /start, чтобы начать поиск фильмов.") [cite: 47]


# --- Обработчики кнопок "Назад" ---
async def back_to_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    # Сбрасываем выбранные года, если пользователь возвращается к жанрам
    context.user_data['selected_years'] = [] [cite: 47]

    keyboard = []
    selected_genres = context.user_data.get('selected_genres', []) [cite: 47]
    for genre_name in FILM_GENRES.keys():
        emoji = "✅ " if genre_name in selected_genres else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{genre_name}", callback_data=f"genre_{genre_name}")])
    keyboard.append([InlineKeyboardButton("Подтвердить выбор жанров", callback_data="confirm_genres")]) [cite: 48]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try: # <--- Добавляем блок try-except здесь
        await query.edit_message_text(
            f"Выберите от 1 до 3 жанров:\n"
            f"Выбрано: {', '.join(selected_genres) if selected_genres else 'ничего'}",
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_genres: {e}. Возможно, сообщение уже изменено или устарело.")
        await query.message.reply_text(
            f"Выберите от 1 до 3 жанров:\n"
            f"Выбрано: {', '.join(selected_genres) if selected_genres else 'ничего'}",
            reply_markup=reply_markup
        )
    logger.info(f"Пользователь {query.from_user.id} вернулся к выбору жанров.") [cite: 48]
    return SELECT_GENRES [cite: 48]


async def back_to_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Сбрасываем ключевые слова, если пользователь возвращается к годам
    context.user_data['keywords'] = None [cite: 49]
    
    keyboard = []
    selected_years = context.user_data.get('selected_years', []) [cite: 49]
    for year_range_name in FILM_YEAR_RANGES.keys():
        emoji = "✅ " if year_range_name in selected_years else ""
        keyboard.append([InlineKeyboardButton(f"{emoji}{year_range_name}", callback_data=f"year_{year_range_name}")])
    keyboard.append([InlineKeyboardButton("Подтвердить выбор годов", callback_data="confirm_years")]) [cite: 49]
    keyboard.append([InlineKeyboardButton("⬅️ Назад к жанрам", callback_data="back_to_genres")]) [cite: 49]

    reply_markup = InlineKeyboardMarkup(keyboard)
    try: # <--- Добавляем блок try-except здесь
        await query.edit_message_text(
            f"Выберите года выпуска (можно выбрать несколько):\n"
            f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}", [cite: 50]
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.warning(f"Ошибка при редактировании сообщения в back_to_years: {e}. Возможно, сообщение уже изменено или устарело.")
        await query.message.reply_text(
            f"Выберите года выпуска (можно выбрать несколько):\n"
            f"Выбрано: {', '.join(selected_years) if selected_years else 'ничего'}",
            reply_markup=reply_markup
        )
    logger.info(f"Пользователь {query.from_user.id} вернулся к выбору годов.") [cite: 50]
    return SELECT_YEARS [cite: 50]


# --- Основная функция для запуска бота ---
def main() -> None:
    """Запускает бота."""
    create_tables_if_not_exists()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)], [cite: 50]
        states={
            SELECT_GENRES: [ [cite: 51]
                CallbackQueryHandler(select_genres, pattern=r"^(genre_|confirm_genres)$"), [cite: 51]
                CallbackQueryHandler(back_to_genres, pattern="^back_to_genres$") [cite: 51]
            ],
            SELECT_YEARS: [ [cite: 52]
                CallbackQueryHandler(select_years, pattern=r"^(year_|confirm_years)$"), [cite: 52]
                CallbackQueryHandler(back_to_genres, pattern="^back_to_genres$") [cite: 52]
            ],
            ENTER_KEYWORDS: [ [cite: 52]
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keywords), [cite: 52]
                CallbackQueryHandler(back_to_years, pattern="^back_to_years$") [cite: 52]
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.COMMAND | filters.TEXT, unknown)], [cite: 53]
    )

    application.add_handler(conv_handler) [cite: 53]
    application.add_handler(CallbackQueryHandler(start, pattern="^start_over$")) [cite: 53]
    application.add_handler(MessageHandler(filters.COMMAND, unknown)) [cite: 53]

    logger.info("Бот запущен. Ожидание сообщений...") [cite: 53]
    application.run_polling(allowed_updates=Update.ALL_TYPES) [cite: 53]

if __name__ == "__main__":
    main()
