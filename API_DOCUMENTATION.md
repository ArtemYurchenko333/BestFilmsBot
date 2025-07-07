# Telegram Movie Recommendation Bot - API Documentation

## Overview

This is a Telegram bot that provides personalized movie recommendations using Google's Gemini AI. The bot guides users through a conversation flow to select movie preferences (genre, year range, keywords) and generates top-3 movie recommendations based on their criteria.

## Table of Contents

1. [Configuration & Setup](#configuration--setup)
2. [Dependencies](#dependencies)
3. [Database Functions](#database-functions)
4. [Core Bot Functions](#core-bot-functions)
5. [Handler Functions](#handler-functions)
6. [Utility Functions](#utility-functions)
7. [Usage Examples](#usage-examples)
8. [API Reference](#api-reference)

## Configuration & Setup

### Environment Variables

The application requires the following environment variables:

```bash
TELEGRAM_BOT_TOKEN3=your_telegram_bot_token
GEMINI_API_KEY3=your_gemini_api_key
DATABASE_URL3=your_postgresql_database_url
```

### Application States

The bot uses conversation states to manage user flow:

```python
SELECT_GENRES = 0    # User selects movie genre
SELECT_YEARS = 1     # User selects year range
ENTER_KEYWORDS = 2   # User enters keywords
```

### Supported Data

#### Movie Genres
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

#### Year Ranges
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

## Dependencies

```txt
python-telegram-bot==20.6
google-generativeai
psycopg2-binary
```

## Database Functions

### `get_db_connection()`

**Description**: Establishes a connection to the PostgreSQL database.

**Returns**: 
- `psycopg2.connection` object on success
- `None` on failure

**Example**:
```python
conn = get_db_connection()
if conn:
    # Use connection
    cursor = conn.cursor()
    # ... perform database operations
    conn.close()
```

### `create_tables_if_not_exists()`

**Description**: Creates the required database tables if they don't exist.

**Tables Created**:
- `users`: Stores user profile information
- `films`: Stores movie recommendation requests and responses

**Usage**:
```python
create_tables_if_not_exists()
```

**Table Schema**:

#### Users Table
```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    telegram_username VARCHAR(255),
    first_name VARCHAR(255), 
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Films Table  
```sql
CREATE TABLE films (
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
```

### `save_user_data(user_id, username, first, last)`

**Description**: Saves or updates user information in the database.

**Parameters**:
- `user_id` (int): Telegram user ID
- `username` (str): Telegram username
- `first` (str): User's first name
- `last` (str): User's last name

**Returns**: None

**Example**:
```python
await save_user_data(
    user_id=123456789,
    username="john_doe", 
    first="John",
    last="Doe"
)
```

### `save_film_request(user_id, genres, years, keywords, gemini_response, **kwargs)`

**Description**: Saves a movie recommendation request and response to the database.

**Parameters**:
- `user_id` (int): Telegram user ID
- `genres` (str): Selected genres (comma-separated)
- `years` (str): Selected year ranges (comma-separated)
- `keywords` (str): User-provided keywords
- `gemini_response` (str): AI-generated response text
- `film1` (str, optional): First recommended movie
- `film2` (str, optional): Second recommended movie
- `film3` (str, optional): Third recommended movie
- `username` (str, optional): Telegram username
- `first_name` (str, optional): User's first name
- `last_name` (str, optional): User's last name
- `country` (str, optional): User's country
- `city` (str, optional): User's city
- `phone` (str, optional): User's phone number

**Example**:
```python
await save_film_request(
    user_id=123456789,
    genres="Боевик, Триллер",
    years="2010-2020",
    keywords="супергерои, взрывы",
    gemini_response="1. Мстители...",
    film1="Мстители",
    film2="Железный человек", 
    film3="Темный рыцарь",
    username="john_doe",
    first_name="John",
    last_name="Doe"
)
```

## Core Bot Functions

### `extract_film_names(text)`

**Description**: Extracts movie titles from Gemini AI response text using regex pattern matching.

**Parameters**:
- `text` (str): AI response text containing numbered movie recommendations

**Returns**: 
- `list`: List of 3 movie titles [film1, film2, film3], with None for missing entries

**Pattern**: Matches numbered lists like "1. Movie Title" or "1. Название фильма: Movie Title"

**Example**:
```python
response_text = """
1. Мстители: Финал
2. Название фильма: Железный человек
3. Темный рыцарь
"""

films = extract_film_names(response_text)
# Result: ["Мстители: Финал", "Железный человек", "Темный рыцарь"]
```

## Handler Functions

### `start(update, context)`

**Description**: Entry point handler that initiates the movie recommendation conversation.

**Parameters**:
- `update` (telegram.Update): Telegram update object
- `context` (telegram.ext.ContextTypes.DEFAULT_TYPE): Bot context

**Returns**: `SELECT_GENRES` state

**Functionality**:
- Saves user data to database
- Clears previous conversation data
- Displays genre selection keyboard
- Initializes user_data with empty lists

**Example Usage**:
```python
# User sends: /start
# Bot response: "Привет, @username! Выбери жанр:" + genre buttons
```

### `select_genres(update, context)`

**Description**: Handles genre selection and transitions to year selection.

**Parameters**:
- `update` (telegram.Update): Callback query with selected genre
- `context` (telegram.ext.ContextTypes.DEFAULT_TYPE): Bot context

**Returns**: `SELECT_YEARS` state

**Functionality**:
- Stores selected genre in context.user_data
- Displays year range selection keyboard
- Shows selected genre confirmation

**Example Flow**:
```python
# User clicks: "Боевик" button
# Bot stores: context.user_data['selected_genres'] = ["Боевик"]
# Bot response: "Вы выбрали жанр: Боевик. Теперь выбери годы:" + year buttons
```

### `select_years(update, context)`

**Description**: Handles year range selection and transitions to keyword input.

**Parameters**:
- `update` (telegram.Update): Callback query with selected year range
- `context` (telegram.ext.ContextTypes.DEFAULT_TYPE): Bot context

**Returns**: `ENTER_KEYWORDS` state

**Functionality**:
- Stores selected year range in context.user_data
- Displays keyword input prompt
- Shows selection summary

**Example Flow**:
```python
# User clicks: "10-е (2010-2020)" button  
# Bot stores: context.user_data['selected_years'] = ["10-е (2010-2020)"]
# Bot response: "Вы выбрали: Жанр: Боевик, Годы: 10-е (2010-2020). Введите ключевые слова:"
```

### `handle_keywords(update, context)`

**Description**: Processes user keywords and generates movie recommendations using Gemini AI.

**Parameters**:
- `update` (telegram.Update): Text message with keywords
- `context` (telegram.ext.ContextTypes.DEFAULT_TYPE): Bot context

**Returns**: `ConversationHandler.END`

**Functionality**:
- Collects user keywords
- Constructs prompt for Gemini AI
- Generates movie recommendations
- Extracts movie titles from response
- Saves request to database
- Offers restart option

**Example Flow**:
```python
# User sends: "супергерои, взрывы, экшн"
# Bot constructs prompt: "ТОП-3 фильмов в жанре Боевик, 2010-2020. По ключевым словам: 'супергерои, взрывы, экшн'..."
# Gemini generates response with 3 movie recommendations
# Bot sends response to user and saves to database
```

### Navigation Handlers

#### `back_to_genres(update, context)`
**Description**: Returns user to genre selection step.
**Returns**: `SELECT_GENRES` state

#### `back_to_years(update, context)`  
**Description**: Returns user to year selection step.
**Returns**: `SELECT_YEARS` state

#### `cancel(update, context)`
**Description**: Cancels current conversation and clears user data.
**Returns**: `ConversationHandler.END`

#### `unknown(update, context)`
**Description**: Handles unknown commands during conversation.

## Utility Functions

### `main()`

**Description**: Main application entry point that sets up and runs the bot.

**Functionality**:
- Creates database tables
- Builds Telegram application
- Configures conversation handler with states and callbacks
- Starts polling for updates

**Conversation Flow Configuration**:
```python
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
```

## Usage Examples

### Complete User Flow

1. **Start Conversation**:
   ```
   User: /start
   Bot: Привет, @username! Выбери жанр:
   [Боевик] [Комедия] [Драма] [Триллер] [Ужасы] [Фантастика]
   [Фэнтези] [Приключения] [Мелодрама] [Мультфильм] [Детектив] [Исторический] [Документальный]
   ```

2. **Genre Selection**:
   ```
   User: [clicks "Боевик"]
   Bot: Вы выбрали жанр: Боевик
        Теперь выбери годы:
   [00-е (2000-2009)] [10-е (2010-2020)] [20-е (2020-2029)] [⬅️ Назад]
   [30-е (1930-1939)] [40-е (1940-1949)] [50-е (1950-1959)]
   [60-е (1960-1969)] [70-е (1970-1979)] [80-е (1980-1989)] [90-е (1990-1999)]
   ```

3. **Year Selection**:
   ```
   User: [clicks "10-е (2010-2020)"]
   Bot: Вы выбрали:
        Жанр: Боевик
        Годы: 10-е (2010-2020)
        
        Введите ключевые слова:
   [⬅️ Назад]
   ```

4. **Keywords Input**:
   ```
   User: супергерои, взрывы, спецэффекты
   Bot: Ищу лучшие фильмы, подождите...
   
   ТОП-3 фильмов в жанре Боевик (2010-2020) по ключевым словам "супергерои, взрывы, спецэффекты":
   
   1. Мстители: Финал (2019)
   [Detailed description...]
   
   2. Мстители: Война бесконечности (2018)  
   [Detailed description...]
   
   3. Железный человек (2008)
   [Detailed description...]
   
   Хотите попробовать еще раз?
   [Начать новый поиск]
   ```

### Database Query Examples

**Get all requests by user**:
```sql
SELECT * FROM films WHERE user_id = 123456789 ORDER BY requested_at DESC;
```

**Get popular genres**:
```sql
SELECT genres, COUNT(*) as count FROM films GROUP BY genres ORDER BY count DESC;
```

**Get recent recommendations**:
```sql
SELECT film1, film2, film3, requested_at FROM films 
WHERE requested_at > NOW() - INTERVAL '7 days';
```

### Error Handling Examples

```python
# Database connection error
conn = get_db_connection()
if not conn:
    logger.error("Database connection failed")
    await update.message.reply_text("Временная ошибка. Попробуйте позже.")
    
# Gemini API error  
try:
    response = model.generate_content(prompt)
    text = response.text
except Exception as e:
    logger.error(f"Ошибка Gemini: {e}")
    await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
```

## API Reference

### Constants

| Constant | Type | Description |
|----------|------|-------------|
| `SELECT_GENRES` | int | Conversation state for genre selection (0) |
| `SELECT_YEARS` | int | Conversation state for year selection (1) |
| `ENTER_KEYWORDS` | int | Conversation state for keyword input (2) |
| `FILM_GENRES` | dict | Mapping of Russian genre names to English values |
| `FILM_YEAR_RANGES` | dict | Mapping of decade descriptions to year ranges |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN3` | Yes | Telegram Bot API token |
| `GEMINI_API_KEY3` | Yes | Google Gemini API key |
| `DATABASE_URL3` | Yes | PostgreSQL connection string |

### Callback Query Patterns

| Pattern | Handler | Description |
|---------|---------|-------------|
| `^genre_` | `select_genres` | Genre selection callbacks |
| `^year_` | `select_years` | Year range selection callbacks |
| `^back_to_genres$` | `back_to_genres` | Navigation back to genres |
| `^back_to_years$` | `back_to_years` | Navigation back to years |
| `^start_over$` | `start` | Restart conversation |

### Message Filters

| Filter | Handler | Description |
|--------|---------|-------------|
| `filters.TEXT & ~filters.COMMAND` | `handle_keywords` | Text messages for keywords |
| `filters.COMMAND` | `unknown` | Unknown commands fallback |

### Logging Configuration

```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
```

### Deployment

**Procfile**:
```
web: python main.py
```

**Required Python Version**: 3.7+

**Memory Requirements**: ~128MB RAM minimum

**Network Requirements**: 
- Outbound HTTPS access to api.telegram.org
- Outbound HTTPS access to generativelanguage.googleapis.com  
- Database connection (PostgreSQL)

This documentation covers all public APIs, functions, and components in the movie recommendation bot with comprehensive examples and usage instructions.