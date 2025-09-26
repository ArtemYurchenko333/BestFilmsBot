# Пошаговая настройка Google Sheets API и Google Drive API

## Визуальная инструкция с подробными шагами

### 🚀 Шаг 1: Создание проекта в Google Cloud Console

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Войдите в свой Google аккаунт, если еще не вошли
3. В верхней части экрана найдите выпадающий список с названием текущего проекта
4. Нажмите на него и выберите **"NEW PROJECT"** (Новый проект)
5. В форме создания проекта:
   - **Project name**: введите "1C-GoogleSheets-Integration"
   - **Organization**: оставьте как есть (если есть)
   - **Location**: оставьте как есть
6. Нажмите кнопку **"CREATE"** (Создать)
7. Дождитесь создания проекта (может занять несколько секунд)

---

### 📚 Шаг 2: Включение необходимых API

#### 2.1 Переход к библиотеке API
1. В левом боковом меню найдите раздел **"APIs & Services"**
2. Нажмите на **"Library"** (Библиотека)

#### 2.2 Включение Google Sheets API
1. В строке поиска введите: `Google Sheets API`
2. Нажмите на первый результат "Google Sheets API"
3. На открывшейся странице нажмите синюю кнопку **"ENABLE"** (Включить)
4. Дождитесь активации API (появится зеленая галочка)

#### 2.3 Включение Google Drive API
1. Вернитесь к библиотеке API (нажмите "Library" в левом меню)
2. В строке поиска введите: `Google Drive API`
3. Нажмите на первый результат "Google Drive API"
4. На открывшейся странице нажмите синюю кнопку **"ENABLE"** (Включить)
5. Дождитесь активации API

---

### 🔐 Шаг 3: Создание сервисного аккаунта

1. В левом меню выберите **"APIs & Services"** → **"Credentials"** (Учетные данные)
2. В верхней части страницы нажмите **"+ CREATE CREDENTIALS"**
3. В выпадающем меню выберите **"Service account"** (Сервисный аккаунт)

#### 3.1 Заполнение информации о сервисном аккаунте
1. **Service account name**: `1c-sheets-exporter`
2. **Service account ID**: автоматически заполнится как `1c-sheets-exporter`
3. **Description**: `Сервисный аккаунт для экспорта данных из 1С в Google Sheets`
4. Нажмите **"CREATE AND CONTINUE"**

#### 3.2 Настройка ролей (опционально)
1. В поле **"Select a role"** можете выбрать **"Editor"** или пропустить этот шаг
2. Нажмите **"CONTINUE"**

#### 3.3 Доступ пользователей (пропускаем)
1. Оставьте поля пустыми
2. Нажмите **"DONE"**

---

### 🔑 Шаг 4: Создание ключа доступа

1. В списке сервисных аккаунтов найдите созданный `1c-sheets-exporter`
2. Нажмите на email адрес аккаунта (например: `1c-sheets-exporter@your-project.iam.gserviceaccount.com`)
3. Перейдите на вкладку **"KEYS"** (Ключи)
4. Нажмите **"ADD KEY"** → **"Create new key"**
5. Выберите формат **"JSON"**
6. Нажмите **"CREATE"**

**Результат:** На ваш компьютер автоматически загрузится JSON файл с ключами доступа.

---

### 📁 Шаг 5: Настройка файла ключей

1. Найдите загруженный JSON файл (обычно в папке "Загрузки")
2. Переименуйте его в `google_service_account.json`
3. Переместите файл в папку с вашим проектом (туда же, где лежит `main.py`)

---

### 📊 Шаг 6: Предоставление доступа к Google Sheets

#### 6.1 Получение email сервисного аккаунта
1. Откройте файл `google_service_account.json` в текстовом редакторе
2. Найдите строку с `"client_email"`
3. Скопируйте email адрес (например: `1c-sheets-exporter@your-project-12345.iam.gserviceaccount.com`)

#### 6.2 Предоставление доступа к существующим таблицам
1. Откройте Google Sheets в браузере
2. Откройте таблицу, в которую хотите экспортировать данные
3. Нажмите кнопку **"Поделиться"** (Share) в правом верхнем углу
4. В поле "Добавить пользователей и группы" вставьте скопированный email
5. В выпадающем списке прав выберите **"Редактор"** (Editor)
6. **ВАЖНО:** Снимите галочку "Уведомить пользователей" (чтобы не отправлять email роботу)
7. Нажмите **"Отправить"**

---

### ✅ Проверка настройки

Создайте простой тестовый файл для проверки:

```python
# test_connection.py
import gspread
from google.oauth2.service_account import Credentials

try:
    # Настройка авторизации
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = Credentials.from_service_account_file(
        'google_service_account.json', scopes=scope
    )
    client = gspread.authorize(credentials)
    
    # Создание тестовой таблицы
    sheet = client.create("Test API Connection")
    worksheet = sheet.get_worksheet(0)
    worksheet.update('A1', 'Тест подключения успешен!')
    
    print("✅ Подключение к Google Sheets API работает!")
    print(f"Создана тестовая таблица: {sheet.url}")
    
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
```

Запустите тест:
```bash
pip install gspread google-auth
python test_connection.py
```

---

### 🔧 Возможные проблемы и решения

#### Проблема: "The caller does not have permission"
**Решение:** Убедитесь, что включили Google Drive API и Google Sheets API

#### Проблема: "Insufficient Permission"
**Решение:** Проверьте, что предоставили сервисному аккаунту права "Редактор" на таблицу

#### Проблема: "File not found: google_service_account.json"
**Решение:** Убедитесь, что JSON файл находится в той же папке, что и скрипт

#### Проблема: API не включается
**Решение:** Убедитесь, что выбран правильный проект в Google Cloud Console

---

### 📋 Чек-лист готовности

- [ ] Создан проект в Google Cloud Console
- [ ] Включен Google Sheets API
- [ ] Включен Google Drive API  
- [ ] Создан сервисный аккаунт
- [ ] Создан и загружен JSON ключ
- [ ] Файл переименован в `google_service_account.json`
- [ ] Email сервисного аккаунта добавлен в Google Sheets с правами "Редактор"
- [ ] Тестовое подключение работает

После выполнения всех шагов вы сможете использовать код для экспорта данных из 1С в Google Sheets!