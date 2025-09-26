#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример выгрузки данных из 1С в Google Sheets
Поддерживает два способа подключения к 1С:
1. Через OData (веб-сервис)
2. Через COM-объект (Windows)
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from requests.auth import HTTPBasicAuth
import gspread
from google.oauth2.service_account import Credentials

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OneCConnector:
    """Класс для подключения к 1С"""
    
    def __init__(self, connection_type: str = "odata"):
        self.connection_type = connection_type
        self.connection = None
        
    def connect_odata(self, base_url: str, username: str, password: str, database: str):
        """
        Подключение к 1С через OData
        
        Args:
            base_url: Базовый URL сервера 1С (например: http://server:port/base_name)
            username: Имя пользователя
            password: Пароль
            database: Название базы данных
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.database = database
        
        # Проверка подключения
        try:
            response = requests.get(
                f"{self.base_url}/odata/standard.odata/$metadata",
                auth=self.auth,
                timeout=30
            )
            response.raise_for_status()
            logger.info("Успешное подключение к 1С через OData")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к 1С через OData: {e}")
            return False
    
    def connect_com(self):
        """
        Подключение к 1С через COM-объект (только Windows)
        """
        try:
            import win32com.client
            self.connection = win32com.client.Dispatch("V83.COMConnector")
            logger.info("Успешное подключение к 1С через COM")
            return True
        except ImportError:
            logger.error("COM-подключение доступно только на Windows с установленным pywin32")
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к 1С через COM: {e}")
            return False
    
    def get_data_odata(self, entity_name: str, filters: Optional[Dict] = None, 
                      select_fields: Optional[List[str]] = None) -> List[Dict]:
        """
        Получение данных через OData
        
        Args:
            entity_name: Название сущности (справочник, документ и т.д.)
            filters: Фильтры для запроса
            select_fields: Поля для выборки
            
        Returns:
            Список записей
        """
        if self.connection_type != "odata":
            raise ValueError("Метод доступен только для OData подключения")
            
        url = f"{self.base_url}/odata/standard.odata/{entity_name}"
        params = {}
        
        # Добавляем поля для выборки
        if select_fields:
            params['$select'] = ','.join(select_fields)
            
        # Добавляем фильтры
        if filters:
            filter_conditions = []
            for field, value in filters.items():
                if isinstance(value, str):
                    filter_conditions.append(f"{field} eq '{value}'")
                else:
                    filter_conditions.append(f"{field} eq {value}")
            if filter_conditions:
                params['$filter'] = ' and '.join(filter_conditions)
        
        # Добавляем формат JSON
        params['$format'] = 'json'
        
        try:
            response = requests.get(url, auth=self.auth, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            records = data.get('value', [])
            
            logger.info(f"Получено {len(records)} записей из {entity_name}")
            return records
            
        except Exception as e:
            logger.error(f"Ошибка получения данных из {entity_name}: {e}")
            return []
    
    def execute_query_com(self, connection_string: str, query: str) -> List[Dict]:
        """
        Выполнение запроса через COM-объект
        
        Args:
            connection_string: Строка подключения к базе 1С
            query: Текст запроса на языке запросов 1С
            
        Returns:
            Результат запроса
        """
        if self.connection_type != "com" or not self.connection:
            raise ValueError("COM подключение не инициализировано")
            
        try:
            # Подключение к базе
            infobase = self.connection.Connect(connection_string)
            
            # Создание и выполнение запроса
            query_obj = infobase.NewObject("Query")
            query_obj.Text = query
            result = query_obj.Execute()
            
            # Преобразование результата в список словарей
            records = []
            selection = result.Choose()
            while selection.Next():
                record = {}
                for i in range(result.Columns.Count()):
                    column_name = result.Columns.Get(i).Name
                    record[column_name] = selection.Get(column_name)
                records.append(record)
            
            logger.info(f"Получено {len(records)} записей через COM")
            return records
            
        except Exception as e:
            logger.error(f"Ошибка выполнения COM запроса: {e}")
            return []


class GoogleSheetsUploader:
    """Класс для работы с Google Sheets"""
    
    def __init__(self, credentials_file: str):
        """
        Инициализация подключения к Google Sheets
        
        Args:
            credentials_file: Путь к файлу с учетными данными сервисного аккаунта
        """
        self.credentials_file = credentials_file
        self.client = None
        self._connect()
    
    def _connect(self):
        """Подключение к Google Sheets API"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=scope
            )
            self.client = gspread.authorize(credentials)
            logger.info("Успешное подключение к Google Sheets API")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets API: {e}")
            raise
    
    def create_or_open_sheet(self, sheet_name: str, worksheet_name: str = "Лист1") -> gspread.Worksheet:
        """
        Создание или открытие таблицы
        
        Args:
            sheet_name: Название таблицы
            worksheet_name: Название листа
            
        Returns:
            Объект листа
        """
        try:
            # Попытка открыть существующую таблицу
            spreadsheet = self.client.open(sheet_name)
            logger.info(f"Открыта существующая таблица: {sheet_name}")
        except gspread.SpreadsheetNotFound:
            # Создание новой таблицы
            spreadsheet = self.client.create(sheet_name)
            logger.info(f"Создана новая таблица: {sheet_name}")
        
        # Получение или создание листа
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        
        return worksheet
    
    def upload_data(self, worksheet: gspread.Worksheet, data: List[Dict], 
                   clear_sheet: bool = True) -> bool:
        """
        Загрузка данных в лист
        
        Args:
            worksheet: Объект листа
            data: Данные для загрузки
            clear_sheet: Очистить лист перед загрузкой
            
        Returns:
            True если успешно, False если ошибка
        """
        if not data:
            logger.warning("Нет данных для загрузки")
            return False
        
        try:
            # Очистка листа
            if clear_sheet:
                worksheet.clear()
            
            # Получение заголовков из первой записи
            headers = list(data[0].keys())
            
            # Подготовка данных для загрузки
            values = [headers]  # Заголовки
            for record in data:
                row = []
                for header in headers:
                    value = record.get(header, '')
                    # Преобразование значений для Google Sheets
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif value is None:
                        value = ''
                    row.append(str(value))
                values.append(row)
            
            # Загрузка данных
            worksheet.update('A1', values)
            
            logger.info(f"Загружено {len(data)} записей в лист {worksheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return False


class OneCToGoogleSheetsExporter:
    """Основной класс для экспорта данных из 1С в Google Sheets"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        Инициализация экспортера
        
        Args:
            config_file: Путь к файлу конфигурации
        """
        self.config = self._load_config(config_file)
        self.onec_connector = OneCConnector(self.config.get('connection_type', 'odata'))
        self.sheets_uploader = GoogleSheetsUploader(self.config['google_credentials_file'])
    
    def _load_config(self, config_file: str) -> Dict:
        """Загрузка конфигурации из файла"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл конфигурации {config_file} не найден")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка в файле конфигурации: {e}")
            raise
    
    def export_odata_entity(self, entity_name: str, sheet_name: str, 
                           worksheet_name: str = "Данные", 
                           filters: Optional[Dict] = None,
                           select_fields: Optional[List[str]] = None):
        """
        Экспорт сущности 1С через OData в Google Sheets
        
        Args:
            entity_name: Название сущности в 1С
            sheet_name: Название таблицы Google Sheets
            worksheet_name: Название листа
            filters: Фильтры для данных
            select_fields: Поля для выборки
        """
        logger.info(f"Начало экспорта {entity_name} в {sheet_name}")
        
        # Подключение к 1С
        if not self.onec_connector.connect_odata(
            self.config['onec_odata_url'],
            self.config['onec_username'],
            self.config['onec_password'],
            self.config['onec_database']
        ):
            return False
        
        # Получение данных из 1С
        data = self.onec_connector.get_data_odata(entity_name, filters, select_fields)
        
        if not data:
            logger.warning("Нет данных для экспорта")
            return False
        
        # Создание/открытие листа Google Sheets
        worksheet = self.sheets_uploader.create_or_open_sheet(sheet_name, worksheet_name)
        
        # Загрузка данных
        success = self.sheets_uploader.upload_data(worksheet, data)
        
        if success:
            logger.info(f"Экспорт {entity_name} завершен успешно")
        else:
            logger.error(f"Ошибка при экспорте {entity_name}")
        
        return success
    
    def export_com_query(self, query: str, sheet_name: str, 
                        worksheet_name: str = "Данные"):
        """
        Экспорт результата запроса 1С через COM в Google Sheets
        
        Args:
            query: Текст запроса на языке запросов 1С
            sheet_name: Название таблицы Google Sheets
            worksheet_name: Название листа
        """
        logger.info(f"Начало экспорта запроса в {sheet_name}")
        
        # Подключение к 1С через COM
        if not self.onec_connector.connect_com():
            return False
        
        # Выполнение запроса
        data = self.onec_connector.execute_query_com(
            self.config['onec_com_connection_string'],
            query
        )
        
        if not data:
            logger.warning("Нет данных для экспорта")
            return False
        
        # Создание/открытие листа Google Sheets
        worksheet = self.sheets_uploader.create_or_open_sheet(sheet_name, worksheet_name)
        
        # Загрузка данных
        success = self.sheets_uploader.upload_data(worksheet, data)
        
        if success:
            logger.info("Экспорт запроса завершен успешно")
        else:
            logger.error("Ошибка при экспорте запроса")
        
        return success


def main():
    """Пример использования"""
    try:
        # Создание экспортера
        exporter = OneCToGoogleSheetsExporter()
        
        # Пример 1: Экспорт справочника "Номенклатура" через OData
        exporter.export_odata_entity(
            entity_name="Catalog_Номенклатура",
            sheet_name="Номенклатура из 1С",
            select_fields=["Ref_Key", "Description", "Артикул", "ЕдиницаИзмерения"]
        )
        
        # Пример 2: Экспорт документов "Реализация товаров и услуг" с фильтром по дате
        exporter.export_odata_entity(
            entity_name="Document_РеализацияТоваровУслуг",
            sheet_name="Продажи за месяц",
            filters={"Date": "2024-01-01T00:00:00"},
            select_fields=["Ref_Key", "Date", "Number", "Контрагент", "СуммаДокумента"]
        )
        
        # Пример 3: Экспорт произвольного запроса через COM (только для Windows)
        query = """
        ВЫБРАТЬ
            Номенклатура.Наименование КАК Товар,
            СУММА(ПродажиОбороты.Количество) КАК КоличествоПродано,
            СУММА(ПродажиОбороты.Сумма) КАК СуммаПродаж
        ИЗ
            РегистрНакопления.Продажи.Обороты КАК ПродажиОбороты
            ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Номенклатура КАК Номенклатура
            ПО ПродажиОбороты.Номенклатура = Номенклатура.Ссылка
        СГРУППИРОВАТЬ ПО
            Номенклатура.Наименование
        УПОРЯДОЧИТЬ ПО
            СуммаПродаж УБЫВ
        """
        
        # exporter.export_com_query(query, "Отчет по продажам")
        
    except Exception as e:
        logger.error(f"Ошибка в основной функции: {e}")


if __name__ == "__main__":
    main()