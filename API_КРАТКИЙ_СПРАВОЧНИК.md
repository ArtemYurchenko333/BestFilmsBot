# 📚 API Краткий справочник - Телеграм-бот рекомендации фильмов

> Быстрое руководство по основным функциям и API для разработчиков

## 🔧 Основные функции

### 🗄️ База данных

```python
# Подключение к БД
conn = get_db_connection()
if conn:
    cursor = conn.cursor()
    # выполнить операции
    conn.close()

# Сохранение пользователя
await save_user_data(
    user_id=123456789,
    username="ivan_petrov",
    first="Иван", 
    last="Петров"
)

# Сохранение запроса рекомендации
await save_film_request(
    user_id=123456789,
    genres="Боевик",
    years="2010-2020", 
    keywords="супергерои",
    gemini_response="1. Мстители...",
    film1="Мстители",
    film2="Железный человек",
    film3="Темный рыцарь"
)
```

### 🤖 Обработчики состояний

```python
# Точка входа
async def start(update, context) -> int:
    # Сохраняет пользователя, показывает жанры
    return SELECT_GENRES

# Выбор жанра  
async def select_genres(update, context) -> int:
    # Сохраняет жанр, показывает годы
    return SELECT_YEARS

# Выбор года
async def select_years(update, context) -> int:
    # Сохраняет год, запрашивает ключевые слова
    return ENTER_KEYWORDS

# Обработка ключевых слов + ИИ
async def handle_keywords(update, context) -> int:
    # Генерирует рекомендации через Gemini
    return ConversationHandler.END
```

### 🧠 Обработка ИИ

```python
# Извлечение названий фильмов из ответа Gemini
response_text = """
1. Мстители: Финал
2. Железный человек  
3. Темный рыцарь
"""
films = extract_film_names(response_text)
# Результат: ["Мстители: Финал", "Железный человек", "Темный рыцарь"]
```

## 📊 Константы и конфигурация

### Состояния разговора
```python
SELECT_GENRES = 0    # Выбор жанра
SELECT_YEARS = 1     # Выбор года
ENTER_KEYWORDS = 2   # Ввод ключевых слов
```

### Поддерживаемые жанры
```python
FILM_GENRES = {
    "Боевик": "action",
    "Комедия": "comedy", 
    "Драма": "drama",
    "Триллер": "thriller",
    "Ужасы": "horror",
    "Фантастика": "sci-fi",
    "Фэнтези": "fantasy",
    "Приключения": "adventure",
    "Мелодрама": "romance",
    "Мультфильм": "animation",
    "Детектив": "mystery",
    "Исторический": "historical",
    "Документальный": "documentary"
}
```

### Временные периоды
```python
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
```

## 🔄 Callback паттерны

| Паттерн | Функция | Описание |
|---------|---------|----------|
| `^genre_` | `select_genres` | Выбор жанра |
| `^year_` | `select_years` | Выбор года |
| `^back_to_genres$` | `back_to_genres` | Назад к жанрам |
| `^back_to_years$` | `back_to_years` | Назад к годам |
| `^start_over$` | `start` | Перезапуск |

## 🗃️ Схема базы данных

### Таблица users
```sql
id BIGINT PRIMARY KEY
telegram_username VARCHAR(255)
first_name VARCHAR(255)
last_name VARCHAR(255)
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### Таблица films
```sql
id SERIAL PRIMARY KEY
user_id BIGINT NOT NULL (FK → users.id)
genres TEXT NOT NULL
years TEXT NOT NULL  
keywords TEXT
film1 VARCHAR(255)
film2 VARCHAR(255)
film3 VARCHAR(255)
gemini_response TEXT NOT NULL
requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

## 🚀 Быстрые примеры

### Получение всех запросов пользователя
```sql
SELECT * FROM films 
WHERE user_id = 123456789 
ORDER BY requested_at DESC;
```

### Популярные жанры
```sql
SELECT genres, COUNT(*) as count 
FROM films 
GROUP BY genres 
ORDER BY count DESC;
```

### Недавние рекомендации
```sql
SELECT film1, film2, film3, requested_at 
FROM films 
WHERE requested_at > NOW() - INTERVAL '7 days';
```

## ⚙️ Переменные окружения

```bash
TELEGRAM_BOT_TOKEN3=ваш_токен_бота
GEMINI_API_KEY3=ваш_ключ_gemini
DATABASE_URL3=postgresql://user:pass@host:port/db
```

## 🔧 Конфигурация ConversationHandler

```python
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^start_over$")
    ],
    states={
        SELECT_GENRES: [
            CallbackQueryHandler(select_genres, pattern="^genre_")
        ],
        SELECT_YEARS: [
            CallbackQueryHandler(select_years, pattern="^year_"),
            CallbackQueryHandler(back_to_genres, pattern="^back_to_genres$")
        ],
        ENTER_KEYWORDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keywords),
            CallbackQueryHandler(back_to_years, pattern="^back_to_years$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel), 
        MessageHandler(filters.COMMAND, unknown)
    ]
)
```

## 🛠️ Регулярные выражения

### Извлечение названий фильмов
```python
pattern = r'^\s*(\d+)\.\s*(?:Название фильма:\s*)?([^:.]+)'
# Поддерживает форматы:
# "1. Название фильма"
# "2. Название фильма: Дополнительная информация"
```

## 🔍 Полезные SQL запросы

### Статистика по пользователям
```sql
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as total_requests FROM films;
SELECT COUNT(DISTINCT user_id) as active_users FROM films;
```

### Анализ запросов
```sql
-- Самые частые ключевые слова
SELECT keywords, COUNT(*) FROM films 
WHERE keywords IS NOT NULL 
GROUP BY keywords 
ORDER BY COUNT(*) DESC LIMIT 10;

-- Активность по дням
SELECT DATE(requested_at) as date, COUNT(*) as requests
FROM films 
GROUP BY DATE(requested_at) 
ORDER BY date DESC;
```

## 🚨 Обработка ошибок

### Типичные проверки
```python
# Проверка подключения к БД
conn = get_db_connection()
if not conn:
    logger.error("Database connection failed")
    return

# Проверка переменных окружения
if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, DATABASE_URL]):
    logger.error("Environment variables missing")
    exit(1)

# Обработка ошибок Gemini API
try:
    response = model.generate_content(prompt)
    text = response.text
except Exception as e:
    logger.error(f"Gemini API error: {e}")
    await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
```

---

📖 **Полная документация**: [ДОКУМЕНТАЦИЯ_API.md](ДОКУМЕНТАЦИЯ_API.md)  
🔧 **Техническое руководство**: [РУКОВОДСТВО_РАЗРАБОТЧИКА.md](РУКОВОДСТВО_РАЗРАБОТЧИКА.md)  
🏠 **Главная**: [README.md](README.md)