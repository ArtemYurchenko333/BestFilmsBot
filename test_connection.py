#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки подключения к Google Sheets API
Запустите этот файл для проверки правильности настройки API
"""

import gspread
from google.oauth2.service_account import Credentials
import json
import os

def test_google_sheets_connection():
    """Тестирование подключения к Google Sheets API"""
    
    print("🔄 Проверка подключения к Google Sheets API...")
    
    # Проверка наличия файла с ключами
    credentials_file = 'google_service_account.json'
    if not os.path.exists(credentials_file):
        print(f"❌ Файл {credentials_file} не найден!")
        print("📝 Убедитесь, что:")
        print("   1. Вы скачали JSON ключ из Google Cloud Console")
        print("   2. Переименовали его в 'google_service_account.json'")
        print("   3. Поместили в папку с этим скриптом")
        return False
    
    try:
        # Проверка корректности JSON файла
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
            client_email = creds_data.get('client_email', 'НЕ НАЙДЕН')
            project_id = creds_data.get('project_id', 'НЕ НАЙДЕН')
        
        print(f"📧 Email сервисного аккаунта: {client_email}")
        print(f"🏗️  ID проекта: {project_id}")
        
        # Настройка авторизации
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(
            credentials_file, scopes=scope
        )
        client = gspread.authorize(credentials)
        
        print("✅ Авторизация прошла успешно!")
        
        # Создание тестовой таблицы
        sheet_name = "Test API Connection"
        print(f"📊 Создание тестовой таблицы '{sheet_name}'...")
        
        sheet = client.create(sheet_name)
        worksheet = sheet.get_worksheet(0)
        
        # Добавление тестовых данных
        test_data = [
            ['Тест', 'Статус', 'Время'],
            ['Подключение к API', 'Успешно', '2024-01-01 12:00:00'],
            ['Создание таблицы', 'Успешно', '2024-01-01 12:01:00'],
            ['Запись данных', 'Успешно', '2024-01-01 12:02:00']
        ]
        
        worksheet.update('A1', test_data)
        
        print("✅ Тестовые данные записаны!")
        print(f"🔗 Ссылка на таблицу: {sheet.url}")
        print("\n📋 Что делать дальше:")
        print("   1. Откройте ссылку выше в браузере")
        print("   2. Убедитесь, что видите тестовые данные")
        print("   3. Если всё работает - можете использовать основной код!")
        print(f"   4. Не забудьте поделиться доступом с: {client_email}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Файл {credentials_file} не найден!")
        return False
        
    except json.JSONDecodeError:
        print(f"❌ Файл {credentials_file} содержит некорректный JSON!")
        return False
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n🔧 Возможные причины:")
        print("   1. Не включен Google Sheets API в Google Cloud Console")
        print("   2. Не включен Google Drive API в Google Cloud Console")
        print("   3. Неправильный файл с ключами")
        print("   4. Проблемы с интернет-соединением")
        return False

def test_existing_sheet_access():
    """Тестирование доступа к существующей таблице"""
    
    sheet_name = input("\n📝 Введите название существующей таблицы для тестирования (или нажмите Enter для пропуска): ").strip()
    
    if not sheet_name:
        print("⏭️  Тестирование существующей таблицы пропущено")
        return
    
    try:
        credentials_file = 'google_service_account.json'
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(
            credentials_file, scopes=scope
        )
        client = gspread.authorize(credentials)
        
        # Попытка открыть существующую таблицу
        sheet = client.open(sheet_name)
        worksheet = sheet.get_worksheet(0)
        
        # Попытка записи тестовых данных
        worksheet.update('A1', 'Тест доступа к существующей таблице')
        
        print(f"✅ Доступ к таблице '{sheet_name}' работает!")
        print(f"🔗 Ссылка: {sheet.url}")
        
    except gspread.SpreadsheetNotFound:
        print(f"❌ Таблица '{sheet_name}' не найдена!")
        print("   Убедитесь, что:")
        print("   1. Название таблицы указано точно")
        print("   2. Таблица существует в вашем Google Drive")
        print("   3. Сервисному аккаунту предоставлен доступ к таблице")
        
    except gspread.exceptions.APIError as e:
        print(f"❌ Ошибка доступа к таблице: {e}")
        print("   Возможно, у сервисного аккаунта нет прав на редактирование")
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

if __name__ == "__main__":
    print("🚀 Тестирование подключения к Google Sheets API")
    print("=" * 50)
    
    # Проверка зависимостей
    try:
        import gspread
        import google.oauth2.service_account
        print("✅ Все необходимые библиотеки установлены")
    except ImportError as e:
        print(f"❌ Отсутствуют библиотеки: {e}")
        print("📦 Установите зависимости: pip install gspread google-auth")
        exit(1)
    
    # Основное тестирование
    if test_google_sheets_connection():
        print("\n" + "=" * 50)
        test_existing_sheet_access()
        print("\n🎉 Тестирование завершено!")
    else:
        print("\n❌ Тестирование не пройдено. Проверьте настройки API.")