import os
import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler, CallbackQueryHandler
)
from telegram.error import BadRequest
import google.generativeai as genai
from telegram.helpers import escape_markdown
import re

# --- Логирование ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Состояния ---
SELECT_GENRES, SELECT_YEARS, ENTER_KEYWORDS = range(3)

# --- Переменные окружения ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN3")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY3")
DATABASE_URL = os.getenv("DATABASE_URL3")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY or not DATABASE_URL:
    logger.error("Одна или несколько переменных окружения не установлены.")
    exit(1)

# --- Настройка Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
# model = genai.GenerativeModel('models/gemini-1.5-flash')
model = genai.GenerativeModel('models/gemini-2.0-flash')

# --- Справочники ---
FILM_GENRES = {
    "Боевик": "action", "Комедия": "comedy", "Драма": "drama",
    "Триллер": "thriller", "Ужасы": "horror", "Фантастика": "sci-fi",
    "Фэнтези": "fantasy", "Приключения": "adventure", "Мелодрама": "romance",
    "Мультфильм": "animation", "Детектив": "mystery", "Исторический": "historical",
    "Документальный": "documentary"
}

FILM_YEAR_RANGES = {
    "00-е (2000-2009)": "2000-2009", "10-е (2010-2020)": "2010-2020", "20-е (2020-2029)": "2020-2029",
    "30-е (1930-1939)": "1930-1939", "40-е (1940-1949)": "1940-1949", "50-е (1950-1959)": "1950-1959",
    "60-е (1960-1969)": "1960-1969", "70-е (1970-1979)": "1970-1979", "80-е (1980-1989)": "1980-1989",
    "90-е (1990-1999)": "1990-1999"
}

# --- DB ---
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Ошибка подключения к базе: {e}")
        return None

def create_tables_if_not_exists():
    conn = get_db_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY, telegram_username VARCHAR(255),
                first_name VARCHAR(255), last_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS films (
                id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
                telegram_username VARCHAR(255), user_first_name VARCHAR(255), user_last_name VARCHAR(255),
                user_country VARCHAR(255), genres TEXT NOT NULL, years TEXT NOT NULL, keywords TEXT,
                film1 VARCHAR(255), film2 VARCHAR(255), film3 VARCHAR(255), gemini_response TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_city VARCHAR(255), user_phone_number VARCHAR(20),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
    finally:
        conn.close()

async def save_user_data(user_id, username, first, last):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO users (id, telegram_username, first_name, last_name)
                VALUES (%s, %s, %s, %s);
            """, (user_id, username, first, last))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
    finally:
        conn.close()

async def save_film_request(user_id, genres, years, keywords, gemini_response,
                            film1=None, film2=None, film3=None,
                            username=None, first_name=None, last_name=None,
                            country="", city="", phone=""):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO films (
                user_id, telegram_username, user_first_name, user_last_name, user_country,
                genres, years, keywords, gemini_response,
                film1, film2, film3,
                user_city, user_phone_number
            )
            VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s);
        """, (user_id, username, first_name, last_name, country,
              genres, years, keywords, gemini_response,
              film1, film2, film3, city, phone))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения фильма: {e}")
    finally:
        conn.close()

# --- Парсинг Gemini ---
def extract_film_names(text):
    pattern = r'^\s*(\d+)\.\s*(?:Название фильма:\s*)?([^:.]+)'
    matches = re.findall(pattern, text, re.MULTILINE)
    result = [None, None, None]
    for num_str, title in matches:
        num = int(num_str)
        if 1 <= num <= 3:
            result[num-1] = re.sub(r'[,.]\s*$', '', title).strip()
    return result

# --- Хендлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await save_user_data(user.id, user.username, user.first_name, user.last_name)
    context.user_data.clear()
    context.user_data['selected_genres'] = []
    context.user_data['selected_years'] = []

    keyboard = [[InlineKeyboardButton(genre, callback_data=f"genre_{genre}")]
                for genre in FILM_GENRES.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer("Начинаем заново...")
        try:
            await update.callback_query.message.edit_reply_markup(reply_markup=None)
        except BadRequest:
            pass

    await update.effective_message.reply_html(
        f"Привет, {user.mention_html()}! Выбери жанр:", reply_markup=reply_markup)
    return SELECT_GENRES

async def select_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    genre = query.data.replace("genre_", "")
    context.user_data['selected_genres'] = [genre]

    keyboard = [[InlineKeyboardButton(year, callback_data=f"year_{year}")]
                for year in FILM_YEAR_RANGES]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_genres")])
    await query.edit_message_text(f"Вы выбрали жанр: *{genre}*\n\nТеперь выбери годы:",
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_YEARS

async def select_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    year = query.data.replace("year_", "")
    context.user_data['selected_years'] = [year]
    genre = context.user_data['selected_genres'][0]

    await query.edit_message_text(
        f"Вы выбрали:\nЖанр: *{genre}*\nГоды: *{year}*\n\nВведите ключевые слова:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_years")]])
    )
    return ENTER_KEYWORDS

async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    keywords = update.message.text
    genres = ", ".join(context.user_data['selected_genres'])
    years = ", ".join([FILM_YEAR_RANGES[y] for y in context.user_data['selected_years']])

    await update.message.reply_text("Ищу лучшие фильмы, подождите...")
    prompt = f"ТОП-3 фильмов в жанре {genres}, {years}. По ключевым словам: '{keywords}'..."
    try:
        response = model.generate_content(prompt)
        text = response.text
        films = extract_film_names(text)
        await update.message.reply_text(text)
        await save_film_request(user.id, genres, years, keywords, text,
                                films[0], films[1], films[2], user.username,
                                user.first_name, user.last_name)
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

    await update.message.reply_text("Хотите попробовать еще раз?", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Начать новый поиск", callback_data="start_over")]
    ]))
    return ConversationHandler.END

async def back_to_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await start(update, context)

async def back_to_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await select_genres(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Поиск отменен. Используйте /start для начала.")
    context.user_data.clear()
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Используйте /start")

def main():
    create_tables_if_not_exists()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^start_over$")
        ],
        states={
            SELECT_GENRES: [CallbackQueryHandler(select_genres, pattern="^genre_")],
            SELECT_YEARS: [
                CallbackQueryHandler(select_years, pattern="^year_"),
                CallbackQueryHandler(back_to_genres, pattern="^back_to_genres$")
            ],
            ENTER_KEYWORDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keywords),
                CallbackQueryHandler(back_to_years, pattern="^back_to_years$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.COMMAND, unknown)]
    )

    app.add_handler(conv_handler)
    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
