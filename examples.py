#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Примеры использования для выгрузки данных из 1С в Google Sheets
"""

from main import OneCToGoogleSheetsExporter
import logging

logging.basicConfig(level=logging.INFO)

def example_nomenclature_export():
    """Пример экспорта справочника номенклатуры"""
    exporter = OneCToGoogleSheetsExporter()
    
    # Экспорт всей номенклатуры
    exporter.export_odata_entity(
        entity_name="Catalog_Номенклатура",
        sheet_name="Справочник номенклатуры",
        worksheet_name="Все товары",
        select_fields=[
            "Ref_Key", 
            "Description", 
            "Артикул", 
            "ЕдиницаИзмерения_Key",
            "Группа_Key"
        ]
    )

def example_sales_export():
    """Пример экспорта документов продаж с фильтрами"""
    exporter = OneCToGoogleSheetsExporter()
    
    # Экспорт продаж за текущий месяц
    exporter.export_odata_entity(
        entity_name="Document_РеализацияТоваровУслуг",
        sheet_name="Продажи 2024",
        worksheet_name="Январь",
        filters={
            "Date": "2024-01-01T00:00:00"  # Фильтр по дате
        },
        select_fields=[
            "Ref_Key",
            "Date", 
            "Number",
            "Контрагент_Key",
            "СуммаДокумента",
            "Валюта_Key",
            "Ответственный_Key"
        ]
    )

def example_counterparties_export():
    """Пример экспорта справочника контрагентов"""
    exporter = OneCToGoogleSheetsExporter()
    
    exporter.export_odata_entity(
        entity_name="Catalog_Контрагенты",
        sheet_name="База контрагентов",
        worksheet_name="Все контрагенты",
        select_fields=[
            "Ref_Key",
            "Description",
            "ИНН",
            "КПП", 
            "ЮридическийАдрес",
            "ФактическийАдрес",
            "Телефон",
            "Email"
        ]
    )

def example_inventory_balances():
    """Пример экспорта остатков товаров"""
    exporter = OneCToGoogleSheetsExporter()
    
    exporter.export_odata_entity(
        entity_name="AccumulationRegister_ТоварныеЗапасы_Balance",
        sheet_name="Остатки товаров",
        worksheet_name="Текущие остатки",
        select_fields=[
            "Номенклатура_Key",
            "Склад_Key",
            "КоличествоBalance",
            "СтоимостьBalance"
        ]
    )

def example_com_custom_query():
    """Пример выполнения произвольного запроса через COM (Windows)"""
    exporter = OneCToGoogleSheetsExporter()
    
    # Запрос топ-10 товаров по продажам
    query = """
    ВЫБРАТЬ ПЕРВЫЕ 10
        Номенклатура.Наименование КАК Товар,
        Номенклатура.Артикул КАК Артикул,
        СУММА(ПродажиОбороты.Количество) КАК КоличествоПродано,
        СУММА(ПродажиОбороты.Сумма) КАК СуммаПродаж,
        СРЕДНЕЕ(ПродажиОбороты.Сумма / ПродажиОбороты.Количество) КАК СредняяЦена
    ИЗ
        РегистрНакопления.Продажи.Обороты(
            &НачалоПериода,
            &КонецПериода,
            ,
            ) КАК ПродажиОбороты
        ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Номенклатура КАК Номенклатура
        ПО ПродажиОбороты.Номенклатура = Номенклатура.Ссылка
    ГДЕ
        ПродажиОбороты.Количество > 0
    СГРУППИРОВАТЬ ПО
        Номенклатура.Наименование,
        Номенклатура.Артикул
    УПОРЯДОЧИТЬ ПО
        СуммаПродаж УБЫВ
    """
    
    exporter.export_com_query(
        query=query,
        sheet_name="ТОП товары по продажам",
        worksheet_name="ТОП-10"
    )

def example_batch_export():
    """Пример пакетной выгрузки нескольких справочников"""
    exporter = OneCToGoogleSheetsExporter()
    
    # Список справочников для выгрузки
    catalogs = [
        {
            "entity": "Catalog_Номенклатура",
            "sheet": "Справочники 1С",
            "worksheet": "Номенклатура",
            "fields": ["Ref_Key", "Description", "Артикул", "ЕдиницаИзмерения_Key"]
        },
        {
            "entity": "Catalog_Контрагенты", 
            "sheet": "Справочники 1С",
            "worksheet": "Контрагенты",
            "fields": ["Ref_Key", "Description", "ИНН", "КПП"]
        },
        {
            "entity": "Catalog_Склады",
            "sheet": "Справочники 1С", 
            "worksheet": "Склады",
            "fields": ["Ref_Key", "Description", "Ответственный_Key"]
        },
        {
            "entity": "Catalog_ЕдиницыИзмерения",
            "sheet": "Справочники 1С",
            "worksheet": "Единицы измерения", 
            "fields": ["Ref_Key", "Description", "Код"]
        }
    ]
    
    # Выгрузка всех справочников
    for catalog in catalogs:
        print(f"Выгружаем {catalog['entity']}...")
        exporter.export_odata_entity(
            entity_name=catalog["entity"],
            sheet_name=catalog["sheet"],
            worksheet_name=catalog["worksheet"],
            select_fields=catalog["fields"]
        )

if __name__ == "__main__":
    print("Выберите пример для запуска:")
    print("1. Экспорт номенклатуры")
    print("2. Экспорт продаж")
    print("3. Экспорт контрагентов")
    print("4. Экспорт остатков")
    print("5. Произвольный запрос (COM)")
    print("6. Пакетная выгрузка")
    
    choice = input("Введите номер примера (1-6): ")
    
    if choice == "1":
        example_nomenclature_export()
    elif choice == "2":
        example_sales_export()
    elif choice == "3":
        example_counterparties_export()
    elif choice == "4":
        example_inventory_balances()
    elif choice == "5":
        example_com_custom_query()
    elif choice == "6":
        example_batch_export()
    else:
        print("Неверный выбор!")