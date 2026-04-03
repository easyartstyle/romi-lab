import sys 
import pandas as pd 
import numpy as np 
import json 
import os 
from pathlib import Path 
import random 
import logging 
import shutil 
import urllib .request 
import urllib .error 
import urllib .parse 
from io import StringIO 
from datetime import datetime ,timedelta # <-- ДОАВЛЯЕМ timedelta
from PyQt6 .QtWidgets import *
from PyQt6 .QtWidgets import QFileDialog 
from PyQt6 .QtWidgets import QInputDialog 
from PyQt6 .QtGui import QAction 
from PyQt6 .QtCore import *
from PyQt6 .QtGui import *
import matplotlib .pyplot as plt 
from matplotlib .backends .backend_qt5agg import FigureCanvasQTAgg as FigureCanvas 

WORKSPACE_ROOT =Path (__file__ ).resolve ().parent 
if str (WORKSPACE_ROOT )not in sys .path :
    sys .path .insert (0 ,str (WORKSPACE_ROOT ))


try :
    from app_release import load_app_version ,load_release_config ,normalize_version ,is_newer_version 
except Exception :
    def load_app_version ():
        return "0.1.0"
    def load_release_config ():
        return {
        "app_name":"ROMI Lab",
        "publisher":"easyartstyle",
        "github_owner":"",
        "github_repo":"",
        "update_check_enabled":True ,
        "release_api_template":"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        "release_page_template":"https://github.com/{owner}/{repo}/releases/latest",
        }
    def normalize_version (value ):
        text =str (value or "").strip ()
        return text [1 :]if text.lower ().startswith ("v")else (text or "0.1.0")
    def is_newer_version (latest ,current ):
        def version_tuple (value ):
            parts =[]
            for part in normalize_version (value ).split ("."):
                digits ="".join (ch for ch in part if ch .isdigit ())
                parts .append (int (digits )if digits else 0 )
            return tuple (parts )
        return version_tuple (latest )>version_tuple (current )

try :
    from web .shared .analytics_core import (
    build_merged_dataframe_from_sources as shared_build_merged_dataframe_from_sources ,
    fill_missing_crm_dimensions_from_ads as shared_fill_missing_crm_dimensions_from_ads ,
    normalize_source_dataframe as shared_normalize_source_dataframe ,
    )
except Exception :
    shared_build_merged_dataframe_from_sources =None 
    shared_fill_missing_crm_dimensions_from_ads =None 
    shared_normalize_source_dataframe =None 

try :
    from web .shared .kpi_core import (
    build_kpi_dataframe_from_metrics as shared_build_kpi_dataframe_from_metrics ,
    calculate_kpi_metrics as shared_calculate_kpi_metrics ,
    format_kpi_values as shared_format_kpi_values ,
    )
except Exception :
    shared_build_kpi_dataframe_from_metrics =None 
    shared_calculate_kpi_metrics =None 
    shared_format_kpi_values =None 

class NumericTableWidgetItem (QTableWidgetItem ):
    """Кастомный элемент таблицы для правильной числовой сортировки"""
    def __init__ (self ,text ,numeric_value =None ):
        super ().__init__ (text )
        self .numeric_value =numeric_value 

    def __lt__ (self ,other ):
        try :
        # Получаем значения для сравнения
            val1 =self .numeric_value if self .numeric_value is not None else self ._extract_numeric (self .text ())
            val2 =other .numeric_value if hasattr (other ,'numeric_value')and other .numeric_value is not None else self ._extract_numeric (other .text ())

            # Если оба числа - сравниваем как числа
            if isinstance (val1 ,(int ,float ))and isinstance (val2 ,(int ,float )):
                return val1 <val2 
                # иначе сравниваем как строки
            return super ().__lt__ (other )
        except :
            return super ().__lt__ (other )

    def _extract_numeric (self ,text ):
        """Извлекает число из текста, удаляя пробелы и знаки"""
        if not text :
            return 0 
            # Убираем пробелы, знак %, заменяем запятую на точку
        cleaned =text .replace (' ','').replace ('%','').replace (',','.')
        try :
            return float (cleaned )
        except :
            return text 

class AnalyticsApp (QMainWindow ):
    def __init__ (self ):
        super ().__init__ ()

        # 1. КОНСТАНТЫ  ПУТ
        self .projects_dir =os .path .join (os .path .expanduser ("~"),"AnalyticsProjects")
        if not os .path .exists (self .projects_dir ):
            os .makedirs (self .projects_dir )

        self .projects_index_file =os .path .join (self .projects_dir ,"projects_index.json")
        self .plan_file =os .path .join (os .path .expanduser ("~"),"analytics_plan.json")
        self .project_backups_dir =os .path .join (self .projects_dir ,"_backups")
        if not os .path .exists (self .project_backups_dir ):
            os .makedirs (self .project_backups_dir )

        # 2. ИНИЦИАЛИЗАЦИЯ ВСЕХ ПЕРЕМЕННЫХ
        self .project_list =[]
        self .current_project =None 
        self .current_project_path =None 
        self .selected_project_name =None 
        self .current_client ="Клиент 1"
        self .dark_mode =False
        self .app_version =load_app_version ()
        self .release_config =load_release_config ()
        self .ads_file_path =None 
        self .crm_file_path =None 
        self .available_ads_platforms =["Яндекс.Директ","Google Ads","VK Ads","Telegram Ads"]
        self .available_crm_platforms =["AmoCRM","Bitrix24"]
        self .ads_connections ={}
        self .crm_connections ={}
        self .last_ads_sync_at =None 
        self .last_crm_sync_at =None 
        self .last_project_refresh_at =None 
        self .auto_refresh_mode ="Каждые 6 часов" 
        self .last_auto_refresh_slot_key =None 
        self .last_auto_refresh_error =None 

        # Виджеты-пустышки
        self .footer_table =None 
        self .table =None 
        self .hide_plan_checkbox =None 
        self .plan_budget_label =None 
        self .plan_leads_label =None 

        # Сортировка
        self .current_sort_col =-1 
        self .sort_order =Qt .SortOrder .AscendingOrder 
        self .sort_column =None 
        self .sort_ascending =True 

        # Данные и измерения
        self .dimension_raw_data ={}
        self .dimension_tables ={}
        self .dimension_data ={}
        self .dimension_sort_column ={}
        self .dimension_sort_ascending ={}
        self .dimension_metrics ={}

        self .ads_data =None 
        self .crm_data =None 
        self .plans_history ={}

        # 3. ПОДГОТОВКА ДЕФОЛТНОГО DATAFRAME
        self .data =pd .DataFrame ({
        "Дата":pd .date_range (start ="2026-03-01",periods =5 ,freq ="D"),
        "Расход":[35000 ,55000 ,65000 ,80000 ,90000 ],
        "Показы":[150000 ,220000 ,180000 ,90500 ,210000 ],
        "Клики":[1000 ,1100 ,1200 ,1300 ,1000 ],
        "Лиды":[50 ,65 ,70 ,55 ,60 ],
        "Продажи":[2 ,3 ,0 ,3 ,2 ],
        "Ср.чек":[65000 ,75000 ,62500 ,72800 ,71440 ]
        })

        # 4. НАСТРОЙКА ЛОГИРОВАНИЯ (ДО расчета метрик)
        self .setup_logging ()

        # 5. ПРИНУДИТЕЛЬНОЕ ПРЕОБРАЗОВАНИЕ ДАТ
        self .data =self ._convert_dates_to_datetime (self .data )

        # 6. РАСЧЕТ МЕТРИК (теперь self.log уже существует)
        self ._calculate_initial_metrics ()

        self .chart_data =self .data .copy ()
        self .filtered_data =self .data .copy ()
        self .original_data =self .data .copy ()

        # Словари для клиентомв и планов
        self .plan_data ={
        "period_from":None ,"period_to":None ,"source":"Все",
        "medium":"Все","budget":0 ,"leads":0 ,"cpl":0 
        }

        self .clients ={
        "Клиент 1":{
        "data":self .data .copy (),
        "plan_data":self .plan_data .copy ()
        }
        }

        # 7. ЗАГРУЗКА ВНЕШНИХ ДАННЫХ
        self .load_plan ()
        self .load_projects_index ()
        self .load_plans_history ()

        # 8. ИНИЦИАЛИЗАЦИЯ ИНТЕРФЕЙСА
        self .init_ui ()
        self ._apply_consistent_widget_styles ()
        if hasattr (self ,"refresh_connection_lists"):
            self .refresh_connection_lists ()

            # Настройка окна
        self .setWindowTitle (f"ROMI Lab {self .app_version }")
        self .setGeometry (100 ,100 ,1200 ,800 )

        # 9. ФИНАЛЬНОЕ ОБНОВЛЕНИЕ
        QTimer .singleShot (2500 ,self .check_for_updates_on_startup )

        if self .current_project :
            self .update_dashboard ()
            self ._refresh_display ()
            self ._ensure_datetime ()
        else :
            self ._set_empty_project_view ()

    def _calculate_initial_metrics (self ):
        """Вспомогательный метод для расчета первичных метрик"""
        df =self .data 

        # ===== ПРЕОБРАЗУЕМ ДАТУ В DATETIME =====
        if "Дата"in df .columns :
        # Выводим текущий тип
            self .log (f"Тип даты до преобразования: {df ['Дата'].dtype }")
            self .log (f"Примеры дат: {df ['Дата'].head ().tolist ()}")

            # Преобразуем
            df ["Дата"]=pd .to_datetime (df ["Дата"],errors ='coerce',dayfirst =True )

            # Выводим после преобразования
            self .log (f"Тип даты после преобразования: {df ['Дата'].dtype }")
            self .log (f"Примеры после: {df ['Дата'].head ().tolist ()}")

            # Удаляетм строки с некорректными датами
            before =len (df )
            df =df .dropna (subset =["Дата"])
            self .log (f"Удалено {before -len (df )} строк с некорректными датами")

        df ["CTR"]=(df ["Клики"]/df ["Показы"])*100 
        df ["CR1"]=(df ["Лиды"]/df ["Клики"])*100 
        df ["CPC"]=(df ["Расход"]/df ["Клики"]).round (0 ).fillna (0 ).astype (int )
        df ["CPL"]=(df ["Расход"]/df ["Лиды"]).round (0 ).replace ([float ('inf'),-float ('inf')],0 ).fillna (0 ).astype (int )
        df ["Выручка"]=(df ["Продажи"]*df ["Ср.чек"]).round (0 ).astype (int )
        df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).round (0 ).astype (int )

        df ["CR2"]=df .apply (lambda r :0 if r ["Лиды"]==0 else r ["Продажи"]/r ["Лиды"]*100 ,axis =1 )
        df ["ROMI"]=df .apply (lambda r :-100 if r ["Расход"]==0 else (r ["Выручка"]-r ["Расход"])/r ["Расход"]*100 ,axis =1 )

        for col in ["CTR","CR1","CR2","ROMI"]:
            df [col ]=df [col ].round (2 )

        column_order =["Дата","Расход","Показы","Клики","CPC","CTR","Лиды","CPL","CR1","Продажи","CR2","Ср.чек","Выручка","Маржа","ROMI"]
        self .data =df [column_order ]


    def _get_common_header_stylesheet (self ):
        """Возвращает единый объемный стиль заголовков таблиц для текущей темы."""
        if self .dark_mode :
            return """
                QHeaderView::section {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3c3c3c,
                        stop:1 #262626
                    );
                    color: #e0e0e0;
                    border: none;
                    border-right: 1px solid #3a3a3a;
                    border-bottom: 1px solid #3a3a3a;
                    padding: 5px 2px;
                    margin: 0px;
                    font-weight: bold;
                }
                QHeaderView::section:last {
                    border-right: none;
                }
                QHeaderView::section:hover {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #454545,
                        stop:1 #2d2d2d
                    );
                }
            """
        return """
                QHeaderView::section {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffffff,
                        stop:1 #ececec
                    );
                    color: #2c3e50;
                    border: none;
                    border-right: 1px solid #e0e0e0;
                    border-bottom: 1px solid #e0e0e0;
                    padding: 5px 2px;
                    margin: 0px;
                    font-weight: bold;
                }
                QHeaderView::section:last {
                    border-right: none;
                }
                QHeaderView::section:hover {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffffff,
                    stop:1 #e4e4e4
                );
            }
        """

    def _apply_header_style_to_table (self ,table ):
        """Применяет единый локальный стиль таблицы и заголовка."""
        if table is None :
            return 

        if self .dark_mode :
            table_style ="""
                QTableWidget {
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                    gridline-color: #3a3a3a;
                    color: #e0e0e0;
                }
                QHeaderView::section {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3c3c3c,
                        stop:1 #262626
                    );
                    color: #e0e0e0;
                    border: none;
                    border-right: 1px solid #3a3a3a;
                    border-bottom: 1px solid #3a3a3a;
                    padding: 0px;
                    margin: 0px;
                    font-weight: bold;
                }
                QHeaderView::section:last {
                    border-right: none;
                }
                QHeaderView::section:hover {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #454545,
                        stop:1 #2d2d2d
                    );
                }
            """
        else :
            table_style ="""
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    gridline-color: #e0e0e0;
                    color: #2c3e50;
                }
                QHeaderView::section {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffffff,
                        stop:1 #ececec
                    );
                    color: #2c3e50;
                    border: none;
                    border-right: 1px solid #e0e0e0;
                    border-bottom: 1px solid #e0e0e0;
                    padding: 0px;
                    margin: 0px;
                    font-weight: bold;
                }
                QHeaderView::section:last {
                    border-right: none;
                }
                QHeaderView::section:hover {
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffffff,
                        stop:1 #e4e4e4
                    );
                }
            """

        table .setStyleSheet (table_style )
        header =table .horizontalHeader ()
        header .setFixedHeight (35 )
        header .setDefaultAlignment (Qt .AlignmentFlag .AlignCenter )
        header .setHighlightSections (False )
        header .setSectionsMovable (False )
        header .setStretchLastSection (False )
        table .setShowGrid (True )
        table .setGridStyle (Qt .PenStyle .SolidLine )

    def _refresh_all_table_headers_geometry (self ):
        """Повторно применяет стиль и геометрию шапок после перестройки layout."""
        if hasattr (self ,"table")and self .table is not None :
            self ._apply_header_style_to_table (self .table )
            self .table .horizontalHeader ().setSectionResizeMode (QHeaderView .ResizeMode .Fixed )
            self .sync_all_table_columns_width ()
            self .table .setShowGrid (True )
            self .table .setGridStyle (Qt .PenStyle .SolidLine )
            self .table .horizontalHeader ().viewport ().update ()
            self .table .viewport ().update ()

        if hasattr (self ,"dimension_tables"):
            for table in self .dimension_tables .values ():
                if table is not None :
                    self ._apply_header_style_to_table (table )
                    table .horizontalHeader ().viewport ().update ()
                    table .viewport ().update ()

    def _set_empty_project_view (self ):
        """Переводит интерфейс в пустое состояние, если проект не выбран."""
        self .current_project =None 
        self .current_project_path =None 
        self .data =pd .DataFrame ()
        self .original_data =pd .DataFrame ()
        self .filtered_data =pd .DataFrame ()
        self .chart_data =pd .DataFrame ()
        self .filtered_source_data =pd .DataFrame ()
        self .ads_data =None 
        self .crm_data =None 
        self .ads_file_path =None 
        self .crm_file_path =None 
        self .ads_connections ={}
        self .crm_connections ={}
        self .last_ads_sync_at =None 
        self .last_crm_sync_at =None 
        self .last_project_refresh_at =None 
        if hasattr (self ,"refresh_connection_lists"):
            self .refresh_connection_lists ()
        self .refresh_data_loader_labels ()
        self .display_empty_table ()
        self ._clear_dimension_tabs ()
        self .update_chart ()
        self .update_plan_display ()
        if hasattr (self ,'active_project_label'):
            pass 

        self .update_project_status_labels ()

    def _clear_filter_widgets_state (self ):
        """Очищает виджеты фильтров без демо-значений."""
        if not hasattr (self ,"filters_widgets"):
            return 
        for filter_key ,widgets in self .filters_widgets .items ():
            if "list"in widgets and widgets ["list"]is not None :
                widgets ["list"].blockSignals (True )
                widgets ["list"].clear ()
                widgets ["list"].blockSignals (False )
            widgets ["items"]=[]
            if "button"in widgets and widgets ["button"]is not None :
                widgets ["button"].setText ("—")
            self .filter_states [filter_key ]={}

    def setup_table_header_style (self ):
        """Устанавливает единый стиль заголовков таблицы и отключает стандартную сортировку"""
        if not hasattr (self ,'table'):
            return 

        header =self .table .horizontalHeader ()
        self ._apply_header_style_to_table (self .table )

        # Устанавливае высоту заголовков
        # ВАЖНО: Отключаем стандартную сортировку
        self .table .setSortingEnabled (False )
        header .setSortIndicatorShown (False )

        # Подключаем свой метод сортировки по клику на заголовок
        # Сначала отключае предыдущие подключения, чтобы не было дублирования
        try :
            header .sectionClicked .disconnect ()
        except :
            pass 
        header .sectionClicked .connect (self .custom_sort )

        # Настройка растягивания
        header .setStretchLastSection (True )

    def refresh_plan_dimension_options (self ):
        """Обновляетт списки Источник/Тип во вкладке Плана из реальных данных."""
        if not hasattr (self ,"plan_source")or not hasattr (self ,"plan_medium"):
            return 

        source_values =["Все"]
        medium_values =["Все"]

        if hasattr (self ,"data")and self .data is not None and not self .data .empty :
            if "Источник"in self .data .columns :
                values =(
                self .data ["Источник"]
                .fillna ("Не указано")
                .astype (str )
                .str .strip ()
                )
                values =[v for v in values .unique ().tolist ()if v ]
                source_values .extend (sorted (v for v in values if v !="Все"))

            medium_column =None 
            if "Medium"in self .data .columns :
                medium_column ="Medium"
            elif "Тип"in self .data .columns :
                medium_column ="Тип"

            if medium_column :
                values =(
                self .data [medium_column ]
                .fillna ("Не указано")
                .astype (str )
                .str .strip ()
                .replace ("","Не указано")
                )
                values =[v for v in values .unique ().tolist ()if v ]
                normalized =[]
                for value in values :
                    normalized .append ("Не указано"if value in ["nan","None","(не указано)"]else value )
                medium_values .extend (sorted (set (v for v in normalized if v !="Все")))
            else :
                medium_values .append ("Не указано")

        for combo ,values in ((self .plan_source ,source_values ),(self .plan_medium ,medium_values )):
            current_text =combo .currentText ().strip ()
            combo .blockSignals (True )
            combo .clear ()
            combo .addItems (values )
            combo .blockSignals (False )
            combo .setEditText (current_text if current_text else "Все")

    def _apply_plan_form_card_style (self ):
        """Применяет согласованный стиль к карточке формы Планирования."""
        if not hasattr (self ,"plan_form_card"):
            return 

        if self .dark_mode :
            card_style ="""
                QLabel#planScreenTitle {
                    color: #f8fafc;
                    font-size: 20px;
                    font-weight: 800;
                    padding: 0 0 4px 0;
                }
                QFrame#planFormCard {
                    background-color: #202936;
                    border: 1px solid #334155;
                    border-radius: 16px;
                }
                QFrame#planFormCard QLineEdit,
                QFrame#planFormCard QComboBox,
                QFrame#planFormCard QDateEdit {
                    min-height: 42px;
                    max-height: 42px;
                    padding: 6px 12px;
                    border: 1px solid #475569;
                    border-radius: 10px;
                    background-color: #0f172a;
                    color: #f8fafc;
                }
                QFrame#planFormCard QComboBox::drop-down {
                    border: none;
                    width: 28px;
                    background: transparent;
                }
                QFrame#planFormCard QComboBox QAbstractItemView {
                    background-color: #0f172a;
                    color: #f8fafc;
                    selection-background-color: #1e293b;
                }
                QFrame#planFormDivider {
                    background-color: #334155;
                    border: none;
                }
                QLabel#planFormTitle {
                    color: #f8fafc;
                    font-size: 18px;
                    font-weight: 700;
                }
                QLabel#planFieldLabel {
                    font-weight: 600;
                    color: #cbd5e1;
                    background: transparent;
                    border: none;
                    padding: 0;
                }
                QLabel#planMutedLabel {
                    color: #94a3b8;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                    padding: 0;
                }
                QLabel#planCplValue {
                    color: #f8fafc;
                    font-weight: 700;
                    font-size: 16px;
                }
                QLabel#planCplSuffix {
                    color: #94a3b8;
                }
                QPushButton#planPrimaryButton {
                    background-color: #1f9d67;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planPrimaryButton:hover {
                    background-color: #22b573;
                }
                QPushButton#planDangerButton {
                    background-color: #c94b49;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planDangerButton:hover {
                    background-color: #db5a58;
                }
                QPushButton#planSecondaryButton {
                    background-color: #2b6cb0;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planSecondaryButton:hover {
                    background-color: #3182ce;
                }
            """
            summary_style ="""
                QGroupBox#planSummaryGroup {
                    border: 1px solid #334155;
                    border-radius: 12px;
                    margin-top: 12px;
                    padding-top: 16px;
                    background-color: #202936;
                }
                QGroupBox#planSummaryGroup::title {
                    subcontrol-origin: margin;
                    left: 14px;
                    padding: 0 6px;
                    color: #e2e8f0;
                    font-weight: 700;
                }
                QLabel#planSummaryValue {
                    color: #f8fafc;
                    font-weight: 600;
                    background-color: #243244;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px 12px;
                }
            """
        else :
            card_style ="""
                QLabel#planScreenTitle {
                    color: #1f2d3d;
                    font-size: 20px;
                    font-weight: 800;
                    padding: 0 0 4px 0;
                }
                QFrame#planFormCard {
                    background-color: #ffffff;
                    border: 1px solid #dbe3ea;
                    border-radius: 16px;
                }
                QFrame#planFormCard QLineEdit,
                QFrame#planFormCard QComboBox,
                QFrame#planFormCard QDateEdit {
                    min-height: 42px;
                    max-height: 42px;
                    padding: 6px 12px;
                    border: 1px solid #cfd7df;
                    border-radius: 10px;
                    background-color: #ffffff;
                    color: #1f2d3d;
                }
                QFrame#planFormCard QComboBox::drop-down {
                    border: none;
                    width: 28px;
                    background: transparent;
                }
                QFrame#planFormCard QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #1f2d3d;
                    selection-background-color: #e9eef3;
                }
                QFrame#planFormDivider {
                    background-color: #e2e8f0;
                    border: none;
                }
                QLabel#planFormTitle {
                    color: #1f2d3d;
                    font-size: 18px;
                    font-weight: 700;
                }
                QLabel#planFieldLabel {
                    font-weight: 600;
                    color: #334155;
                    background: transparent;
                    border: none;
                    padding: 0;
                }
                QLabel#planMutedLabel {
                    color: #64748b;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                    padding: 0;
                }
                QLabel#planCplValue {
                    color: #1f2d3d;
                    font-weight: 700;
                    font-size: 16px;
                }
                QLabel#planCplSuffix {
                    color: #64748b;
                }
                QPushButton#planPrimaryButton {
                    background-color: #1f9d67;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planPrimaryButton:hover {
                    background-color: #22b573;
                }
                QPushButton#planDangerButton {
                    background-color: #e15241;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planDangerButton:hover {
                    background-color: #f06555;
                }
                QPushButton#planSecondaryButton {
                    background-color: #2f80c1;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-weight: 700;
                }
                QPushButton#planSecondaryButton:hover {
                    background-color: #3b92d4;
                }
            """
            summary_style ="""
                QGroupBox#planSummaryGroup {
                    border: 1px solid #dbe3ea;
                    border-radius: 12px;
                    margin-top: 12px;
                    padding-top: 16px;
                    background-color: #fbfcfd;
                }
                QGroupBox#planSummaryGroup::title {
                    subcontrol-origin: margin;
                    left: 14px;
                    padding: 0 6px;
                    color: #1f2d3d;
                    font-weight: 700;
                }
                QLabel#planSummaryValue {
                    color: #1f2d3d;
                    font-weight: 600;
                    background-color: #ffffff;
                    border: 1px solid #dbe3ea;
                    border-radius: 8px;
                    padding: 8px 12px;
                }
            """

        self .plan_form_card .setStyleSheet (card_style )
        for child in self .plan_tab .findChildren (QGroupBox ):
            if child .objectName ()=="planSummaryGroup":
                child .setStyleSheet (summary_style )

    def setup_logging (self ):
        """Настраивает логирование в файл"""
        # Создает папку для логов
        log_dir =os .path .join (os .path .expanduser ("~"),"AnalyticsLogs")
        if not os .path .exists (log_dir ):
            os .makedirs (log_dir )

            # Создает имя файла с датой и времени
        log_filename =f"analytics_log_{datetime .now ().strftime ('%Y%m%d_%H%M%S')}.txt"
        self .log_file_path =os .path .join (log_dir ,log_filename )

        # Настраивает логгер
        self .logger =logging .getLogger ('ROMILab')
        self .logger .setLevel (logging .DEBUG )

        # Очищае старые обработчики
        for handler in self .logger .handlers [:]:
            self .logger .removeHandler (handler )

            # Файловый обработчик
        file_handler =logging .FileHandler (self .log_file_path ,encoding ='utf-8')
        file_handler .setLevel (logging .DEBUG )

        # Формат логов
        formatter =logging .Formatter ('%(asctime)s - %(levelname)s - %(message)s',datefmt ='%H:%M:%S')
        file_handler .setFormatter (formatter )

        self .logger .addHandler (file_handler )

        # Также добавляе вывод в консоль
        console_handler =logging .StreamHandler ()
        console_handler .setLevel (logging .INFO )
        console_handler .setFormatter (formatter )
        self .logger .addHandler (console_handler )

        # ===== СОЗДАЕМ МЕТОД log =====
        def log (message ,level ="info"):
            if level =="info":
                self .logger .info (message )
            elif level =="debug":
                self .logger .debug (message )
            elif level =="warning":
                self .logger .warning (message )
            elif level =="error":
                self .logger .error (message )
            elif level =="critical":
                self .logger .critical (message )
            print (message )

        self .log =log 

        self .logger .info ("=== ЛОГИРОВАНИЕ ЗАПУЩЕНО ===")
        self .logger .info (f"Файл лога: {self .log_file_path }")

    def generate_client_data (self ,client_name ):
        import random 
        random .seed (hash (client_name ))

        # Генерирует данные за 30 дней
        dates =pd .date_range (start ="2026-03-01",periods =30 ,freq ="D")
        data =pd .DataFrame ({
        "Дата":dates ,
        "Расход":[random .randint (20000 ,100000 )for _ in range (30 )],
        "Показы":[random .randint (80000 ,250000 )for _ in range (30 )],
        "Клики":[random .randint (800 ,1500 )for _ in range (30 )],
        "Лиды":[random .randint (40 ,80 )for _ in range (30 )],
        "Продажи":[random .randint (1 ,4 )for _ in range (30 )],
        "Ср.чек":[random .randint (50000 ,80000 )for _ in range (30 )]
        })

        # Рассчитывает метрики
        data ["CTR"]=(data ["Клики"]/data ["Показы"])*100 
        data ["CR1"]=(data ["Лиды"]/data ["Клики"])*100 
        data ["CPC"]=(data ["Расход"]/data ["Клики"]).round (0 ).astype (int )
        data ["CPL"]=(data ["Расход"]/data ["Лиды"]).round (0 ).astype (int )
        data ["Выручка"]=(data ["Продажи"]*data ["Ср.чек"]).round (0 ).astype (int )
        data ["Маржа"]=(data ["Выручка"]-data ["Расход"]).round (0 ).astype (int )
        data ["CR2"]=data .apply (lambda row :0 if row ["Продажи"]==0 else row ["Лиды"]/row ["Продажи"],axis =1 )
        data ["ROMI"]=data .apply (lambda row :-100 if row ["Расход"]==0 else (row ["Выручка"]-row ["Расход"])/row ["Расход"]*100 ,axis =1 )

        for col in ["CTR","CR1","CR2","ROMI"]:
            data [col ]=data [col ].round (2 )

        return data 

    def init_ui (self ):
    # Центральный виджет
        central_widget =QWidget ()
        self .setCentralWidget (central_widget )

        # ===== ОКОВАЯ ПАНЕЛЬ =====
        self .dock =QDockWidget ("Навигация",self )
        self .dock .setAllowedAreas (Qt .DockWidgetArea .LeftDockWidgetArea )
        self .dock .setFeatures (QDockWidget .DockWidgetFeature .NoDockWidgetFeatures )
        self .dock .setTitleBarWidget (QWidget ())
        self .dock .setMinimumWidth (300 )
        self .dock .setMaximumWidth (340 )
        # Виджет для содержимого боковой панели
        dock_widget =QWidget ()
        dock_layout =QVBoxLayout (dock_widget )
        dock_layout .setContentsMargins (12 ,12 ,12 ,12 )
        dock_layout .setSpacing (8 )

        # Заголовок
        title =QLabel ("Управление")
        title .setStyleSheet ("font-size: 14px; font-weight: bold; margin: 5px;")
        dock_layout .addWidget (title )
        self .active_project_label =QLabel ("Активный проект: —")
        self .active_project_label .setStyleSheet ("font-size: 12px; color: #6b7b8c; margin: 0 5px 8px 5px;")
        dock_layout .addWidget (self .active_project_label )
        self .project_status_label =QLabel ("Статус проекта: проект не выбран")
        self .project_status_label .setWordWrap (True )
        self .project_status_label .setStyleSheet ("font-size: 12px; color: #6b7b8c; margin: 0 5px 8px 5px;")
        dock_layout .addWidget (self .project_status_label )
        self .refresh_now_btn =QPushButton ("Обновить сейчас")
        self .refresh_now_btn .clicked .connect (self .refresh_project_now )
        dock_layout .addWidget (self .refresh_now_btn )

        # Список проектов
        dock_layout .addWidget (QLabel ("Проекты:"))
        self .project_list =QListWidget ()
        self .project_list .setMinimumHeight (120 )
        self .project_list .itemClicked .connect (self .on_project_selected )
        dock_layout .addWidget (self .project_list )
        self .update_project_list ()


        # Кнопки управления проектами
        btn_layout =QHBoxLayout ()
        self .new_project_btn =QPushButton ("Новый")
        self .new_project_btn .clicked .connect (self .new_project )
        self .load_selected_project_btn =QPushButton ("Загрузить")
        self .load_selected_project_btn .clicked .connect (self .load_selected_project )
        self .open_project_btn =QPushButton ("Открыть")
        self .open_project_btn .clicked .connect (self .open_project )
        self .delete_project_btn =QPushButton ("Удалить")
        self .delete_project_btn .clicked .connect (self .delete_project )
        btn_layout .addWidget (self .new_project_btn )
        btn_layout .addWidget (self .load_selected_project_btn )
        btn_layout .addWidget (self .open_project_btn )
        btn_layout .addWidget (self .delete_project_btn )
        dock_layout .addLayout (btn_layout )



        # Раздел подключений
        dock_layout .addWidget (QLabel ("Подключения:"))

        # Рекламные кабинеты
        self .ads_group =QGroupBox ("Рекламные кабинеты")
        ads_layout =QVBoxLayout ()
        self .ads_list =QListWidget ()
        self .ads_list .addItem ("Яндекс.Директ (не подключен)")
        self .ads_list .addItem ("Google Ads (не подключен)")
        self .ads_list .itemDoubleClicked .connect (self .edit_selected_ads_account )
        ads_layout .addWidget (self .ads_list )

        self .add_ads_btn =QPushButton ("+ Добавить кабинет")
        self .add_ads_btn .clicked .connect (self .add_ads_account )
        ads_layout .addWidget (self .add_ads_btn )
        self .ads_group .setLayout (ads_layout )
        dock_layout .addWidget (self .ads_group )

        # CRM
        self .crm_group =QGroupBox ("CRM")
        crm_layout =QVBoxLayout ()

        self .crm_list =QListWidget ()
        self .crm_list .addItem ("AmoCRM (не подключен)")
        self .crm_list .itemDoubleClicked .connect (self .edit_selected_crm_connection )
        crm_layout .addWidget (self .crm_list )

        self .add_crm_btn =QPushButton ("+ Подключить CRM")
        self .add_crm_btn .clicked .connect (self .add_crm )
        crm_layout .addWidget (self .add_crm_btn )

        self .crm_group .setLayout (crm_layout )
        dock_layout .addWidget (self .crm_group )

        self .data_loader_btn =QPushButton ("Загрузка данных")
        self .data_loader_btn .clicked .connect (self .open_data_loader_dialog )
        dock_layout .addWidget (self .data_loader_btn )
        self .data_status_label =QLabel ("Данные: проект пустой")
        self .data_status_label .setWordWrap (True )
        self .data_status_label .setStyleSheet ("font-size: 12px; color: #6b7b8c; margin: 0 5px 8px 5px;")
        dock_layout .addWidget (self .data_status_label )

        # Кнопка экспорта логов
        self .export_logs_btn =QPushButton ("📄 Экспорт логов")
        self .export_logs_btn .clicked .connect (self .export_logs )
        dock_layout .addWidget (self .export_logs_btn )

        # Кнопка открытия папки с логами
        self .open_logs_folder_btn =QPushButton ("📁 Папка с логами")
        self .open_logs_folder_btn .clicked .connect (self .open_logs_folder )
        dock_layout .addWidget (self .open_logs_folder_btn )
        if hasattr (self ,'export_logs_btn'):
            self .export_logs_btn .hide ()
        if hasattr (self ,'open_logs_folder_btn'):
            self .open_logs_folder_btn .hide ()
        dock_layout .addStretch ()

        self .dock .setWidget (dock_widget )
        self .addDockWidget (Qt .DockWidgetArea .LeftDockWidgetArea ,self .dock )

        # ===== МЕНЮ =====
        menubar =self .menuBar ()
        view_menu =menubar .addMenu ("Вид")
        toggle_action =QAction ("Показать/скрыть панель",self )
        toggle_action .triggered .connect (self .toggle_panel )
        view_menu .addAction (toggle_action )

        # ===== ОСНОВНОЙ LAYOUT =====
        help_menu =menubar .addMenu ("Справка")
        about_action =QAction ("О программе",self )
        about_action .triggered .connect (self .show_about_dialog )
        help_menu .addAction (about_action )
        check_updates_action =QAction ("Проверить обновления",self )
        check_updates_action .triggered .connect (lambda :self .check_for_updates_on_startup (True ))
        help_menu .addAction (check_updates_action )

        logs_menu =menubar .addMenu ("Логи")
        export_logs_action =QAction ("Экспорт логов",self )
        export_logs_action .triggered .connect (self .export_logs )
        logs_menu .addAction (export_logs_action )
        open_logs_folder_action =QAction ("Папка с логами",self )
        open_logs_folder_action .triggered .connect (self .open_logs_folder )
        logs_menu .addAction (open_logs_folder_action )
        export_menu =menubar .addMenu ("Экспорт")
        export_excel_action =QAction ("Текущий отчет в Xlsx",self )
        export_excel_action .triggered .connect (self .export_current_report_excel )
        export_menu .addAction (export_excel_action )
        export_csv_action =QAction ("Текущий отчет в CSV",self )
        export_csv_action .triggered .connect (self .export_current_report_csv )
        export_menu .addAction (export_csv_action )
        export_all_excel_action =QAction ("\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 Xlsx",self )
        export_all_excel_action .triggered .connect (self .export_all_reports_excel )
        export_menu .addAction (export_all_excel_action )
        export_all_csv_action =QAction ("\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 CSV",self )
        export_all_csv_action .triggered .connect (self .export_all_reports_csv )
        export_menu .addAction (export_all_csv_action )
        export_menu .setTitle ("\u042d\u043a\u0441\u043f\u043e\u0440\u0442")
        export_excel_action .setText ("\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043e\u0442\u0447\u0435\u0442 \u0432 Xlsx")
        export_csv_action .setText ("\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043e\u0442\u0447\u0435\u0442 \u0432 CSV")
        export_all_excel_action .setText ("\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 Xlsx")
        export_all_csv_action .setText ("\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 CSV")

        main_layout =QVBoxLayout ()
        central_widget .setLayout (main_layout )

        # Верхняя панель с периодом и клиентом
        top_layout =QHBoxLayout ()

        # Период
        period_layout =QHBoxLayout ()
        period_layout .addWidget (QLabel ("Период:"))
        period_layout .addWidget (QLabel ("с"))

        self .date_from =QDateEdit ()
        self .date_from .setDate (QDate (2026 ,3 ,1 ))
        self .date_from .setCalendarPopup (True )
        period_layout .addWidget (self .date_from )

        period_layout .addWidget (QLabel ("по"))

        self .date_to =QDateEdit ()
        self .date_to .setDate (QDate (2026 ,3 ,5 ))
        self .date_to .setCalendarPopup (True )
        period_layout .addWidget (self .date_to )

        self .apply_btn =QPushButton ("Применить")
        self .apply_btn .clicked .connect (self .update_dashboard )
        period_layout .addWidget (self .apply_btn )

        top_layout .addLayout (period_layout )
        top_layout .addStretch ()

        # Скрытый комбобокс оставляет только для совместимости со старой логикой
        self .client_combo =QComboBox ()
        if self .clients :
            self .client_combo .addItems (list (self .clients .keys ()))
            self .client_combo .setCurrentText (self .current_client )
        else :
            self .client_combo .addItem ("Клиент 1")
        self .client_combo .currentTextChanged .connect (self .change_client )
        self .client_combo .hide ()

        # Кнопка переключения темы
        self .theme_btn =QPushButton ("🌙 Темная тема")
        self .theme_btn .setFixedWidth (120 )
        self .theme_btn .clicked .connect (self .toggle_theme )
        top_layout .addWidget (self .theme_btn )

        main_layout .addLayout (top_layout )

        # ===== КАРТОЧКИ KPI =====
        self .kpi_layout =QHBoxLayout ()
        self .kpi_labels ={}

        kpi_list =["Расход","Клики","Лиды","CPL","CR1","Продажи","CR2","Ср.чек","Выручка","Маржа","ROMI"]

        for kpi in kpi_list :
            frame =QFrame ()
            frame .setFrameStyle (QFrame .Shape .StyledPanel )
            frame .setStyleSheet ("""
                QFrame {
                    border: 1px solid #d9e2ec;
                    border-radius: 10px;
                    padding: 10px;
                    background-color: #fbfcfd;
                }
                QLabel {
                    color: #2c3e50;
                }
            """)

            layout =QVBoxLayout ()
            frame .setLayout (layout )

            title =QLabel (kpi )
            title .setStyleSheet ("font-size: 13px; font-weight: bold; color: #6b7b8c; letter-spacing: 0.4px;")
            title .setAlignment (Qt .AlignmentFlag .AlignCenter )
            layout .addWidget (title )

            value =QLabel ("0")
            value .setStyleSheet ("font-size: 18px; font-weight: bold; color: #1f2d3d;")
            value .setAlignment (Qt .AlignmentFlag .AlignCenter )
            layout .addWidget (value )

            self .kpi_labels [kpi ]=value 
            self .kpi_layout .addWidget (frame )

        main_layout .addLayout (self .kpi_layout )

        # ===== ПАНЕЛЬ ФИЛЬТРОВ =====
        self .filters_layout =QGridLayout ()
        self .filters_layout .setAlignment (Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignTop )
        self .filters_layout .setHorizontalSpacing (8 )
        self .filters_layout .setVerticalSpacing (8 )
        self .filters_widgets ={}
        self .filter_popups ={}

        filters_names =["Source","Medium","Campaign","Gbid","Content","Term","Region","Device","Placement","Position","URL","Product"]
        filters_items ={
        "Source":["Не указано","Яндекс","Google","VK","Telegram","YouTube"],
        "Medium":["Не указано","cpc","cpm","cpa","organic","social"],
        "Campaign":["Не указано","Бренд","Товарная","Ретаргетинг","Поиск","КМС"],
        "Gbid":["Не указано","Группа 1","Группа 2","Группа 3","Группа 4","Группа 5"],
        "Content":["Не указано","Объявление 1","Объявление 2","Объявление 3","Объявление 4","Объявление 5"],
        "Term":["Не указано","фраза 1","фраза 2","фраза 3","фраза 4","фраза 5"],
        "Region":["Не указано"],
        "Device":["Не указано"],
        "Placement":["Не указано"],
        "Position":["Не указано"],
        "URL":["Не указано"],
        "Product":["Не указано"]
        }
        # Маппинг для отображения на кнопках
        button_labels ={
        "Source":"Источник",
        "Medium":"Тип",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза",
        "Region":"Регион",
        "Device":"Устройство",
        "Placement":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Product":"Продукт"
        }

        # Определяем функцию create_filter_popup ДО ее использования
        def create_filter_popup (filter_name ,items ):
            popup =QWidget ()
            popup .setWindowFlags (Qt .WindowType .Popup )
            popup .setStyleSheet ("""
                QWidget { background-color: white; border: 1px solid #ccc; border-radius: 5px; padding: 5px; }
                QLineEdit { border: 1px solid #ccc; border-radius: 3px; padding: 3px; margin: 2px; }
                QListWidget { border: none; }
                QListWidget::item { padding: 5px; }
                QPushButton { border: 1px solid #ccc; border-radius: 3px; padding: 3px; margin: 2px; background: #f5f5f5; }
                QPushButton:hover { background: #e5e5e5; }
            """)

            layout =QVBoxLayout ()
            popup .setLayout (layout )

            search =QLineEdit ()
            search .setPlaceholderText ("Поиск...")
            layout .addWidget (search )

            lst =QListWidget ()
            lst .setSelectionMode (QAbstractItemView .SelectionMode .NoSelection )
            for text in items :
                item =QListWidgetItem (text )
                item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                item .setCheckState (Qt .CheckState .Checked )
                lst .addItem (item )
            layout .addWidget (lst )

            btn_layout =QHBoxLayout ()
            btn_all =QPushButton ("Выбрать все")
            btn_none =QPushButton ("Снять все")
            btn_layout .addWidget (btn_all )
            btn_layout .addWidget (btn_none )
            layout .addLayout (btn_layout )

            return popup ,search ,lst ,btn_all ,btn_none 

            # Теперь создает фильтры
        for filter_index ,filter_name in enumerate (filters_names ):
            btn =QPushButton (button_labels [filter_name ])# использует русское название
            btn .setFixedWidth (110 )
            btn .setStyleSheet ("QPushButton { border: 1px solid #ccc; border-radius: 3px; padding: 5px; background: white; text-align: left; }")

            popup ,search ,lst ,btn_all ,btn_none =create_filter_popup (filter_name ,filters_items [filter_name ])

            self .filter_popups [filter_name ]=popup 
            self .filters_widgets [filter_name ]={
            'button':btn ,
            'list':lst ,
            'search':search ,
            'btn_all':btn_all ,
            'btn_none':btn_none ,
            'items':filters_items [filter_name ]
            }

            row =0
            col =filter_index
            filter_pair =QWidget ()
            filter_pair .setSizePolicy (QSizePolicy .Policy .Fixed ,QSizePolicy .Policy .Fixed )
            filter_pair_layout =QVBoxLayout (filter_pair )
            filter_pair_layout .setContentsMargins (0 ,0 ,0 ,0 )
            filter_pair_layout .setSpacing (2 )
            filter_pair_layout .setAlignment (Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignTop )
            filter_label =QLabel (f"{button_labels [filter_name ]}:")
            filter_label .setSizePolicy (QSizePolicy .Policy .Fixed ,QSizePolicy .Policy .Preferred )
            filter_pair_layout .addWidget (filter_label )
            filter_pair_layout .addWidget (btn )
            self .filters_layout .addWidget (filter_pair ,row ,col ,Qt .AlignmentFlag .AlignLeft )

            # Подключаем сигналы
            search .textChanged .connect (lambda text ,name =filter_name ,l =lst :self .on_filter_search (name ,text ,l ))
            lst .itemChanged .connect (lambda item ,name =filter_name :self .filter_item_changed (name ))
            btn_all .clicked .connect (lambda checked ,l =lst :self .select_all_items (l ,True ))
            btn_none .clicked .connect (lambda checked ,l =lst :self .select_all_items (l ,False ))
            btn .clicked .connect (lambda checked ,name =filter_name ,p =popup ,b =btn :self .show_filter_popup (name ,p ,b ))

            # Инициализация состояний фильтров (все выбраны)
            if not hasattr (self ,'filter_states'):
                self .filter_states ={}
            self .filter_states [filter_name ]={}
            for item_text in filters_items [filter_name ]:
                self .filter_states [filter_name ][item_text ]=Qt .CheckState .Checked 

        for filter_col in range (12 ):
            self .filters_layout .setColumnStretch (filter_col ,0 )
        main_layout .addLayout (self .filters_layout )

        # ===== ВКЛАДК =====
        self .tabs =QTabWidget ()
        self .tabs .currentChanged .connect (self .on_tab_changed_for_update )
        main_layout .addWidget (self .tabs )

        # Вкладка Таблица
        self .table_tab =QWidget ()
        self .tabs .addTab (self .table_tab ,"Дата")
        self .setup_table_tab ()

        # Вкладки с измерениями
        self .source_tab =QWidget ()
        self .tabs .addTab (self .source_tab ,"Источник")
        self .setup_dimension_tab (self .source_tab ,"Источник")

        self .medium_tab =QWidget ()
        self .tabs .addTab (self .medium_tab ,"Тип")
        self .setup_dimension_tab (self .medium_tab ,"Тип")

        self .campaign_tab =QWidget ()
        self .tabs .addTab (self .campaign_tab ,"Кампания")
        self .setup_dimension_tab (self .campaign_tab ,"Кампания")

        self .group_tab =QWidget ()
        self .tabs .addTab (self .group_tab ,"Группа")
        self .setup_dimension_tab (self .group_tab ,"Группа")

        self .ad_tab =QWidget ()
        self .tabs .addTab (self .ad_tab ,"Объявление")
        self .setup_dimension_tab (self .ad_tab ,"Объявление")

        self .keyword_tab =QWidget ()
        self .tabs .addTab (self .keyword_tab ,"Ключевая фраза")
        self .setup_dimension_tab (self .keyword_tab ,"Ключевая фраза")

        self .region_tab =QWidget ()
        self .tabs .addTab (self .region_tab ,"Регион")
        self .setup_dimension_tab (self .region_tab ,"Регион")

        self .device_tab =QWidget ()
        self .tabs .addTab (self .device_tab ,"Устройство")
        self .setup_dimension_tab (self .device_tab ,"Устройство")

        self .placement_tab =QWidget ()
        self .tabs .addTab (self .placement_tab ,"Площадка")
        self .setup_dimension_tab (self .placement_tab ,"Площадка")

        self .position_tab =QWidget ()
        self .tabs .addTab (self .position_tab ,"Position")
        self .setup_dimension_tab (self .position_tab ,"Position")

        self .url_tab =QWidget ()
        self .tabs .addTab (self .url_tab ,"URL")
        self .setup_dimension_tab (self .url_tab ,"URL")

        self .product_tab =QWidget ()
        self .tabs .addTab (self .product_tab ,"Продукт")
        self .setup_dimension_tab (self .product_tab ,"Продукт")

        # Вкладка Графики
        self .chart_tab =QWidget ()
        self .tabs .addTab (self .chart_tab ,"📈 Графики")
        self .setup_chart_tab ()

        # Вкладка План
        self .plan_tab =QWidget ()
        self .tabs .addTab (self .plan_tab ,"📊 План")
        self .setup_plan_tab ()

        self .tabs .currentChanged .connect (self .on_tab_changed )
        self .update_table ()
        self .apply_filter ()
        self .sync_all_table_columns_width ()

    def toggle_panel (self ):
        """Скрывает/показывает боковую панель"""
        if self .dock .isVisible ():
            self .dock .hide ()
        else :
            self .dock .show ()

    def _clean_project_list_name (self ,raw_name ):
        """Возвращает ия проекта без служебных меток."""
        if not raw_name :
            return ""
        cleaned =str (raw_name ).strip ()
        cleaned =cleaned .replace (" (активный)","").replace (" (активный)","").strip ()
        if cleaned .startswith ("⭐"):
            cleaned =cleaned [1 :].strip ()
        if cleaned .startswith ("в­ђ"):
            cleaned =cleaned .replace ("в­ђ","",1 ).strip ()
        if cleaned .startswith ("*"):
            cleaned =cleaned [1 :].strip ()
        return cleaned 

    def _create_project_backup (self ,file_path ,project_name =None ,reason ="save"):
        """Создает резервную копию проекта перед перезаписью."""
        try :
            if not file_path or not os .path .exists (file_path ):
                return None 
            if os .path .getsize (file_path )<=0 :
                return None 

            if not os .path .exists (self .project_backups_dir ):
                os .makedirs (self .project_backups_dir )

            backup_project_name =project_name or os .path .splitext (os .path .basename (file_path ))[0 ]
            timestamp =datetime .now ().strftime ("%Y%m%d_%H%M%S")
            safe_reason =str (reason ).replace (" ","_")
            backup_file_name =f"{backup_project_name }__{safe_reason }__{timestamp }.json"
            backup_path =os .path .join (self .project_backups_dir ,backup_file_name )

            shutil .copy2 (file_path ,backup_path )
            self ._cleanup_old_project_backups (backup_project_name )
            self .log (f"Создана резервная копия проекта: {backup_file_name }")
            return backup_path 
            self .update_project_status_labels ()
            self .refresh_data_loader_labels ()
        except Exception as e :
            self .log (f"Не удалось создать резервную копию проекта: {e }")
            return None 

    def _cleanup_old_project_backups (self ,project_name ,keep_last =10 ):
        """Оставляет только последние резервные копии для проекта."""
        try :
            if not os .path .exists (self .project_backups_dir ):
                return 

            prefix =f"{project_name }__"
            backup_files =[]
            for file_name in os .listdir (self .project_backups_dir ):
                if file_name .startswith (prefix )and file_name .endswith (".json"):
                    full_path =os .path .join (self .project_backups_dir ,file_name )
                    backup_files .append ((os .path .getmtime (full_path ),full_path ))

            backup_files .sort (key =lambda item :item [0 ],reverse =True )
            for _ ,old_backup_path in backup_files [keep_last :]:
                try :
                    os .remove (old_backup_path )
                except Exception :
                    pass 
        except Exception as e :
            self .log (f"Не удалось почистить резервные копии: {e }")

    def _payload_has_real_project_data (self ,project_data ):
        """Проверяетт, есть ли в payload реальные данные проекта."""
        if not project_data :
            return False 

        if project_data .get ("ads_data")or project_data .get ("crm_data"):
            return True 

        data_block =project_data .get ("data",{})
        if isinstance (data_block ,dict ):
            for values in data_block .values ():
                if isinstance (values ,dict )and len (values )>0 :
                    return True 

        clients_block =project_data .get ("clients",{})
        if isinstance (clients_block ,dict ):
            for client_data in clients_block .values ():
                client_rows =client_data .get ("data",{})if isinstance (client_data ,dict )else {}
                if isinstance (client_rows ,dict ):
                    for values in client_rows .values ():
                        if isinstance (values ,dict )and len (values )>0 :
                            return True 

        return False 

    def _should_block_empty_project_overwrite (self ,file_path ,new_project_data ):
        """Не дает случайно перезаписать заполненный проект пусты."""
        try :
            if not file_path or not os .path .exists (file_path ):
                return False 

            new_has_data =self ._payload_has_real_project_data (new_project_data )
            if new_has_data :
                return False 

            with open (file_path ,'r',encoding ='utf-8')as f :
                existing_project_data =json .load (f )

            existing_has_data =self ._payload_has_real_project_data (existing_project_data )
            if existing_has_data :
                self .log ("локировка пустого перезаписывания: существующий проект содержит данные, а новый payload пустой")
                return True 
        except Exception as e :
            self .log (f"Не удалось проверить защиту от пустого перезаписывания: {e }")

        return False 

    def on_project_selected (self ,item ):
        """Выбор проекта в списке без автоатической загрузки"""
        if item :
            self .selected_project_name =self ._clean_project_list_name (item .text ())

    def load_selected_project (self ):
        """Загружает проект, выбранный в боковой панели"""
        item =self .project_list .currentItem ()
        if not item :
            QMessageBox .warning (self ,"Проект не выбран","Сначала выберите проект в списке слева.")
            return 

        project_name =self ._clean_project_list_name (item .text ())
        file_path =os .path .join (self .projects_dir ,f"{project_name }.json")
        if not os .path .exists (file_path ):
            QMessageBox .warning (self ,"Ошибка","Файл выбранного проекта не найден.")
            return 

        if self .current_project and self .current_project_path :
            self .auto_save_project ()

        self .load_project (file_path )

        if hasattr (self ,'client_combo')and self .client_combo :
            self .client_combo .blockSignals (True )
            self .client_combo .clear ()
            self .client_combo .addItems (list (self .clients .keys ()))
            self .client_combo .setCurrentText (self .current_client )
            self .client_combo .blockSignals (False )

        self .update_plan_ui ()

    def add_ads_account (self ):
        """Добавление рекламного кабинета"""
        QMessageBox .information (self ,"Добавить кабинет","Здесь будет диалог добавления рекламного кабинета")

    def add_crm (self ):
        """Подключение CRM"""
        QMessageBox .information (self ,"Подключить CRM","Здесь будет диалог подключения CRM")

    def _get_auto_refresh_slots (self ):
        schedule_map ={
        "Вручную":[],
        "Каждые 3 часа":["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00"],
        "Каждые 6 часов":["03:00","09:00","15:00","21:00"],
        "Каждые 12 часов":["09:00","21:00"],
        "Раз в день":["09:00"],
        }
        return schedule_map .get (getattr (self ,"auto_refresh_mode","Каждые 6 часов"),["03:00","09:00","15:00","21:00"])

    def _init_auto_refresh_timer (self ):
        if hasattr (self ,"auto_refresh_timer")and self .auto_refresh_timer is not None :
            try :
                self .auto_refresh_timer .stop ()
            except Exception :
                pass 
        self .auto_refresh_timer =QTimer (self )
        self .auto_refresh_timer .timeout .connect (self ._check_auto_refresh_schedule )
        self .auto_refresh_timer .start (60000 )
        QTimer .singleShot (1500 ,self ._check_auto_refresh_schedule )

    def _merge_loaded_sources_silent (self ):
        if not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty :
            return False 
        if not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty :
            return False 
        merged =self ._build_merged_dataframe_from_sources ()
        if merged is None or merged .empty :
            return False 
        self .data =merged .copy ()
        self .original_data =merged .copy ()
        self .chart_data =merged .copy ()
        if self .current_client in self .clients :
            self .clients [self .current_client ]["data"]=merged .copy ()
        self .update_filters_from_data ()
        self .refresh_plan_dimension_options ()
        self .update_dashboard ()
        self .refresh_data_loader_labels ()
        self ._mark_sync_time ("project")
        return True 

    def _run_auto_refresh_now (self ):
        if not self .current_project :
            return False ,"Проект не выбран" 
        ads_platforms =self ._get_connected_platforms ("ads")
        crm_platforms =self ._get_connected_platforms ("crm")
        if not ads_platforms and not crm_platforms :
            return False ,"Нет подключенных источников для автообновления" 
        messages =[]
        errors =[]
        try :
            if ads_platforms :
                platform_name ,config =ads_platforms [0 ]
                if len (ads_platforms )>1 :
                    self .log (f"Автообновление: найдено несколько рекламных подключений, используем первое: {platform_name }")
                result =self ._simulate_connector_fetch ("ads",platform_name ,config or {})
                messages .append (f"{platform_name }: {result ['rows']} строк")
                if not result .get ("ok"):
                    errors .append (str (result .get ("message","Ошибка загрузки рекламы")))
                elif int (result .get ("rows",0 )or 0 )<=0 :
                    errors .append (f"{platform_name }: источник ответил без ошибок, но не вернул ни одной строки")
            if crm_platforms :
                platform_name ,config =crm_platforms [0 ]
                if len (crm_platforms )>1 :
                    self .log (f"Автообновление: найдено несколько CRM-подключений, используем первое: {platform_name }")
                result =self ._simulate_connector_fetch ("crm",platform_name ,config or {})
                messages .append (f"{platform_name }: {result ['rows']} строк")
                if not result .get ("ok"):
                    errors .append (str (result .get ("message","Ошибка загрузки CRM")))
                elif int (result .get ("rows",0 )or 0 )<=0 :
                    errors .append (f"{platform_name }: источник ответил без ошибок, но не вернул ни одной строки")
            merged_ok =self ._merge_loaded_sources_silent ()
            if merged_ok :
                messages .append ("данные объединены")
            elif not errors :
                errors .append ("Источники ответили, но объединенные данные не были сформированы")
            self .last_auto_refresh_error =None if not errors else " | ".join (errors )
            self .update_project_status_labels ()
            if self .current_project :
                self .auto_save_project ()
            return len (errors )==0 ,"; ".join (messages ) if messages else (self .last_auto_refresh_error or "Автообновление завершено")
        except Exception as e :
            self .last_auto_refresh_error =str (e )
            self .update_project_status_labels ()
            return False ,str (e )

    def _check_auto_refresh_schedule (self ):
        if not self .current_project :
            return 
        slots =self ._get_auto_refresh_slots ()
        if not slots :
            return 
        now =datetime .now ()
        current_time =now .strftime ("%H:%M")
        if current_time not in slots :
            return 
        slot_key =now .strftime ("%Y-%m-%d %H:%M")
        if self .last_auto_refresh_slot_key ==slot_key :
            return 
        ok ,message =self ._run_auto_refresh_now ()
        self .last_auto_refresh_slot_key =slot_key 
        if ok :
            self .log (f"Автообновление выполнено: {message }")
        else :
            self .log (f"Автообновление завершилось с ошибкой: {message }")
        if self .current_project :
            self .auto_save_project ()
    def open_data_loader_dialog (self ):
        """Открывает отдельное окно для загрузки данных"""
        dialog =QDialog (self )
        dialog .setWindowTitle ("Загрузка данных")
        dialog .setMinimumWidth (520 )

        layout =QVBoxLayout (dialog )
        title =QLabel ("Загрузка и объединение данных")
        title .setStyleSheet ("font-size: 16px; font-weight: bold;")
        layout .addWidget (title )

        info =QLabel ("Выберите нужное действие:")
        layout .addWidget (info )

        files_group =QGroupBox ("Выбранные файлы")
        files_layout =QVBoxLayout (files_group )
        self .ads_file_info_label =QLabel ()
        self .ads_file_info_label .setWordWrap (True )
        self .crm_file_info_label =QLabel ()
        self .crm_file_info_label .setWordWrap (True )
        files_layout .addWidget (self .ads_file_info_label )
        files_layout .addWidget (self .crm_file_info_label )
        layout .addWidget (files_group )
        self .data_loader_summary_label =QLabel ()
        self .data_loader_summary_label .setWordWrap (True )
        self .data_loader_summary_label .setStyleSheet ("padding: 8px 10px; border: 1px solid #d9e2ec; border-radius: 8px; background-color: #f8fafc;")
        layout .addWidget (self .data_loader_summary_label )
        self .refresh_data_loader_labels ()

        load_ads_btn =QPushButton ("Загрузить данные рекламы")
        load_ads_btn .clicked .connect (lambda :(self .load_ads_data (),self .refresh_data_loader_labels ()))
        layout .addWidget (load_ads_btn )

        load_crm_btn =QPushButton ("Загрузить данные CRM")
        load_crm_btn .clicked .connect (lambda :(self .load_crm_data (),self .refresh_data_loader_labels ()))
        layout .addWidget (load_crm_btn )

        self .merge_data_btn =QPushButton ("Объединить данные")
        self .merge_data_btn .clicked .connect (self .merge_data )
        layout .addWidget (self .merge_data_btn )

        close_btn =QPushButton ("Закрыть")
        close_btn .clicked .connect (dialog .accept )
        layout .addWidget (close_btn )

        dialog .exec ()

    def refresh_data_loader_labels (self ):
        """Обновляетт подписи с выбранныи файлаи в окне загрузки данных"""
        ads_status ="загружено"if hasattr (self ,"ads_data")and self .ads_data is not None and not self .ads_data .empty else "не загружено"
        crm_status ="загружено"if hasattr (self ,"crm_data")and self .crm_data is not None and not self .crm_data .empty else "не загружено"
        try :
            if hasattr (self ,"ads_file_info_label")and self .ads_file_info_label :
                self .ads_file_info_label .setText (
                f"Реклама: {os .path .basename (self .ads_file_path )if self .ads_file_path else 'файл не выбран'} ({ads_status })"
                )
                self .ads_file_info_label .setToolTip (self .ads_file_path or "")
        except RuntimeError :
            self .ads_file_info_label =None 

        try :
            if hasattr (self ,"crm_file_info_label")and self .crm_file_info_label :
                self .crm_file_info_label .setText (
                f"CRM: {os .path .basename (self .crm_file_path )if self .crm_file_path else 'файл не выбран'} ({crm_status })"
                )
                self .crm_file_info_label .setToolTip (self .crm_file_path or "")
        except RuntimeError :
            self .crm_file_info_label =None 

        ads_ready =hasattr (self ,"ads_data")and self .ads_data is not None and not self .ads_data .empty 
        crm_ready =hasattr (self ,"crm_data")and self .crm_data is not None and not self .crm_data .empty 
        merged_rows =len (self .data )if hasattr (self ,"data")and self .data is not None else 0 

        try :
            if hasattr (self ,"data_loader_summary_label")and self .data_loader_summary_label :
                if ads_ready and crm_ready :
                    summary_text =f"Шаг 1: реклама загружена. Шаг 2: CRM загружена. Можно объединять данные. Текущее объединение: {merged_rows } строк."
                elif ads_ready :
                    summary_text ="Шаг 1: реклама загружена. Осталось загрузить CRM."
                elif crm_ready :
                    summary_text ="Шаг 1: CRM загружена. Осталось загрузить рекламу."
                else :
                    summary_text ="Сначала загрузите файл рекламы и файл CRM, потом нажмите «Объединить данные»."
                self .data_loader_summary_label .setText (summary_text )
        except RuntimeError :
            self .data_loader_summary_label =None 

        try :
            if hasattr (self ,"merge_data_btn")and self .merge_data_btn :
                self .merge_data_btn .setEnabled (ads_ready and crm_ready )
                if ads_ready and crm_ready :
                    self .merge_data_btn .setText ("Объединить данные")
                elif ads_ready :
                    self .merge_data_btn .setText ("Сначала загрузите CRM")
                elif crm_ready :
                    self .merge_data_btn .setText ("Сначала загрузите рекламу")
                else :
                    self .merge_data_btn .setText ("Загрузите рекламу и CRM")
        except RuntimeError :
            self .merge_data_btn =None 

        self .update_project_status_labels ()

    def _mark_sync_time (self ,sync_kind ):
        timestamp =datetime .now ().strftime ("%d.%m.%Y %H:%M")
        if sync_kind =="ads":
            self .last_ads_sync_at =timestamp 
        elif sync_kind =="crm":
            self .last_crm_sync_at =timestamp 
        elif sync_kind =="project":
            self .last_project_refresh_at =timestamp 
        return timestamp 

    def _format_sync_label (self ,label ,value ):
        return f"{label}: {value if value else '—'}"
    def refresh_project_now (self ):
        if not self .current_project :
            QMessageBox .information (self ,"Проект не выбран","Сначала выберите или откройте проект.")
            return 
        ok ,message =self ._run_auto_refresh_now () if hasattr (self ,"_run_auto_refresh_now") else (False ,"Механизм обновления пока недоступен")
        if ok :
            QMessageBox .information (self ,"Успех",f"Обновление выполнено успешно.\n{message }")
        else :
            QMessageBox .warning (self ,"Ошибка",f"Не удалось обновить данные.\n{message }")
    def update_project_status_labels (self ):
        """Обновляетт короткие статусы проекта и данных в боковой панели."""
        active_project_text =f"Активный проект: {self .current_project if self .current_project else '—'}"
        try :
            if hasattr (self ,"active_project_label")and self .active_project_label :
                self .active_project_label .setText (active_project_text )
        except RuntimeError :
            self .active_project_label =None 

        rows_count =len (self .data )if hasattr (self ,"data")and self .data is not None else 0 
        has_ads =hasattr (self ,"ads_data")and self .ads_data is not None and not self .ads_data .empty 
        has_crm =hasattr (self ,"crm_data")and self .crm_data is not None and not self .crm_data .empty 
        has_merged =rows_count >0 

        if not self .current_project :
            project_status ="Статус проекта: проект не выбран"
        elif not has_ads and not has_crm and not has_merged :
            project_status ="Статус проекта: пустой проект"
        elif has_merged :
            project_status =f"Статус проекта: данные загружены, строк {rows_count }"
        else :
            project_status ="Статус проекта: проект открыт, источники загружены частично"

        try :
            if hasattr (self ,"project_status_label")and self .project_status_label :
                self .project_status_label .setText (project_status )
        except RuntimeError :
            self .project_status_label =None 

        ads_text ="реклама загружена"if has_ads else "реклама не загружена"
        crm_text ="CRM загружена"if has_crm else "CRM не загружена"
        merge_text =f"объединено {rows_count } строк"if has_merged else "данные не объединены"
        data_status =f"Данные: {ads_text }; {crm_text }; {merge_text }"
        try :
            if hasattr (self ,"data_status_label")and self .data_status_label :
                self .data_status_label .setText (data_status )
        except RuntimeError :
            self .data_status_label =None 

    def _load_saved_source_file (self ,file_path ,source_type ):
        """Пытается без диалога восстановить ранее выбранный файл реклаы или CRM."""
        if not file_path or not os .path .exists (file_path ):
            return None 

        if file_path .endswith ('.csv'):
            try :
                df =pd .read_csv (file_path ,encoding ='utf-8')
            except Exception :
                df =pd .read_csv (file_path ,encoding ='cp1251')
        else :
            df =pd .read_excel (file_path )

        df .columns =df .columns .str .strip ()

        if source_type =="ads":
            column_mapping ={
            "Дата":["Дата","Date","День","Day"],
            "Расход":["Расход","Стоимость","Cost","Spend","юджет","Budget"],
            "Показы":["Показы","Impressions","Просотры"],
            "Клики":["Клики","Clicks"],
            "Лиды":["Лиды","Leads","Заявки","Заявка"],
            "Продажи":["Продажи","Sales","Заказы","Orders"],
            "Ср.чек":["Ср.чек","Средний чек","Average check","AvgCheck","Средний"],
            "Источник":["Источник","Source","Канал","Channel","Площадка"],
            "Кампания":["Кампания","Campaign","РК"],
            "Группа":["Группа","Group","AdGroup","Группа объявлений"],
            "Объявление":["Объявление","Ad","Creative"],
            "Ключевая фраза":["Ключевая фраза","Keyword","Фраза","Key phrase"],
            }
            numeric_columns =["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]
        else :
            column_mapping ={
            "Дата":["Дата","Date","День","Day"],
            "Лиды":["Лиды","Leads","Заявки","Заявка"],
            "Продажи":["Продажи","Sales","Заказы","Orders"],
            "Выручка":["Выручка","Revenue","Сумма сделки","Суа","Сделка","Amount","Opportunity"],
            "Ср.чек":["Ср.чек","Средний чек","Average check","AvgCheck","Средний"],
            "Источник":["Источник","Source","Канал","Channel","Площадка"],
            "Кампания":["Кампания","Campaign","РК"],
            "Группа":["Группа","Group","AdGroup","Группа объявлений"],
            "Объявление":["Объявление","Ad","Creative"],
            "Ключевая фраза":["Ключевая фраза","Keyword","Фраза","Key phrase"],
            }
            numeric_columns =["Лиды","Продажи","Выручка","Ср.чек","Расход","Показы","Клики"]

        for sys_col ,possible_names in column_mapping .items ():
            if sys_col in df .columns :
                continue 
            for col in df .columns :
                if col in possible_names or col .lower ()in [n .lower ()for n in possible_names ]:
                    df =df .rename (columns ={col :sys_col })
                    break 

        if "Дата"not in df .columns :
            return None 

        for col in numeric_columns :
            if col not in df .columns :
                df [col ]=0 
            df [col ]=self .parse_numeric_column (df [col ],col )

        if source_type =="crm":
            if "Выручка"not in df .columns :
                df ["Выручка"]=0 
            if "Ср.чек"not in df .columns :
                df ["Ср.чек"]=0 
            if pd .to_numeric (df ["Выручка"],errors ="coerce").fillna (0 ).sum ()<=0 :
                df ["Выручка"]=pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 )*pd .to_numeric (df ["Ср.чек"],errors ="coerce").fillna (0 )
            df ["Ср.чек"]=np .where (
            pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 )>0 ,
            pd .to_numeric (df ["Выручка"],errors ="coerce").fillna (0 )/pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 ),
            0 
            )

        df =self .parse_date_column (df ,"Дата")
        df =df .dropna (subset =["Дата"])
        if df .empty :
            return None 

        for col in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            if col not in df .columns :
                df [col ]="(не указано)"
            else :
                df [col ]=df [col ].fillna ("(не указано)").astype (str )

        return df .copy ()

    def import_csv (self ):
        """порт данных из CSV"""
        file_path ,_ =QFileDialog .getOpenFileName (
        self ,"Выберите CSV файл","","CSV files (*.csv);;Excel files (*.xlsx)"
        )
        if file_path :
            self .log (f"порт файла: {file_path }")
            QMessageBox .information (self ,"порт",f"Файл выбран: {file_path }")

    def parse_date_column (self ,df ,date_column ="Дата"):
        """Универсальный парсинг дат с подробным логированием"""
        self .log (f"\n--- Парсимнг дат в колонке '{date_column }' ---")
        self .log (f"Уникальные значения дат (первые 10): {df [date_column ].unique ()[:10 ]}")

        formats =[
        "%d.%m.%Y",# 01.03.2026
        "%d.%m.%y",# 01.03.26
        "%Y-%m-%d",# 2026-03-01
        "%d/%m/%Y",# 01/03/2026
        "%d/%m/%y",# 01/03/26
        "%Y/%m/%d",# 2026/03/01
        "%m/%d/%Y",# 03/01/2026 (аериканский)
        "%d-%m-%Y",# 01-03-2026
        "%Y%m%d",# 20260301
        ]

        def parse_single_date (val ):
            if pd .isna (val ):
                return pd .NaT 
            val_str =str (val ).strip ()
            # Пробуем каждый формат
            for fmt in formats :
                try :
                    result =pd .to_datetime (val_str ,format =fmt )
                    return result 
                except :
                    continue 
                    # Если ни один формат не подошел, пробуем автоматически
            try :
                result =pd .to_datetime (val_str ,dayfirst =True )
                return result 
            except :
                return pd .NaT 

        before_count =len (df )
        df [date_column ]=df [date_column ].apply (parse_single_date )
        after_count =len (df .dropna (subset =[date_column ]))

        self .log (f"Успешно распознано: {after_count } из {before_count } строк ({after_count /before_count *100 :.1f}%)")

        if after_count >0 :
            self .log (f"Примеры распознанных дат: {df [date_column ].dropna ().head ().tolist ()}")

        return df 

    def parse_numeric_column (self ,series ,column_name ):
        """Универсальный парсинг числовых колонок с подробным логированием"""
        self .log (f"\n--- Парсимнг колонки '{column_name }' ---")
        self .log (f"сходные данные (первые 5): {series .head ().tolist ()}")
        self .log (f"Тип данных: {series .dtype }")
        self .log (f"Количество NaN: {series .isna ().sum ()}")

        # Приводи к строке и очищае
        result =series .astype (str ).str .strip ()

        # Заеняе пустые строки на '0'
        result =result .replace (['','nan','None','null'],'0')

        # Удаляет пробелы
        result =result .str .replace (' ','',regex =False )

        # Заеняе запятые на точки (для десятичных)
        result =result .str .replace (',','.',regex =False )

        # Удаляет вс крое цифр, точки и инуса
        result =result .str .replace (r'[^\d\.\-]','',regex =True )

        # Удаляет лишние точки (оставляет только первую)
        def clean_dots (x ):
            parts =x .split ('.')
            if len (parts )>2 :
            # Оставляет первую часть и объединяе остальные
                return parts [0 ]+'.'+''.join (parts [1 :])
            return x 

        result =result .apply (clean_dots )

        # Преобразуем в число, ошибки заменяем на 0
        result =pd .to_numeric (result ,errors ='coerce').fillna (0 )

        # Логируе результат
        self .log (f"После парсинга (первые 5): {result .head ().tolist ()}")
        self .log (f"Суа: {result .sum ():.2f}")
        self .log (f"Среднее: {result .mean ():.2f}")

        return result 

    def load_ads_data (self ):
        """Загрузка данных из рекламных кабинетов"""
        self .log ("\n"+"="*50 )
        self .log ("Начало загрузки рекламных данных")
        self .log ("="*50 )

        file_path ,_ =QFileDialog .getOpenFileName (
        self ,"Выберите файл с данныи реклаы","",
        "Excel files (*.xlsx *.xls);;CSV files (*.csv)"
        )
        if file_path :
            self .ads_file_path =file_path 
            self .log (f"\nВыбран файл: {file_path }")
            try :
            # Пробуем прочитать файл
                self .log ("\nЧтение файла...")
                if file_path .endswith ('.csv'):
                    try :
                        df =pd .read_csv (file_path ,encoding ='utf-8')
                        self .log (f"Файл прочитан с кодировкой utf-8, строк: {len (df )}")
                    except :
                        df =pd .read_csv (file_path ,encoding ='cp1251')
                        self .log (f"Файл прочитан с кодировкой cp1251, строк: {len (df )}")
                else :
                    df =pd .read_excel (file_path )
                    self .log (f"Excel файл прочитан, строк: {len (df )}")

                self .log (f"Колонки в файле: {df .columns .tolist ()}")
                self .log (f"Первые 3 строки:\n{df .head (3 )}")

                df .columns =df .columns .str .strip ()

                # Показывае диалог для сопоставления колонок
                self .log ("\nОткрытие диалога сопоставления колонок...")
                mapping_dialog =QDialog (self )
                mapping_dialog .setWindowTitle ("Сопоставление колонок")
                layout =QVBoxLayout (mapping_dialog )

                layout .addWidget (QLabel ("Сопоставьте колонки из файла с системными. Для CRM основное денежное поле — Выручка, а Ср.чек рассчитывается автоматически."))

                # Словарь возожных названий колонок
                column_mapping ={
                "Дата":["Дата","Date","День","Day"],
                "Расход":["Расход","Стоимость","Cost","Spend","Бюджет","Budget"],
                "Показы":["Показы","Impressions","Просмотры"],
                "Клики":["Клики","Clicks"],
                "Тип":["Тип","Medium","utm_medium","UTM_MEDIUM","Channel type","Traffic type","Placement type"],
                "Лиды":["Лиды","Leads","Заявки","Заявка"],
                "Продажи":["Продажи","Sales","Заказы","Orders"],
                "Ср.чек":["Ср.чек","Средний чек","Average check","AvgCheck","Средний"],
                "Источник":["Источник","utm_source","UTM_SOURCE","Канал","Channel"],
                "Кампания":["Кампания","Campaign","utm_campaign","UTM_CAMPAIGN","campaign_id","{{campaign_id}}","РК"],
                "Группа":["Группа","Group","AdGroup","Группа объявлений","Gbid","gbid","{gbid}"],
                "Объявление":["Объявление","Ad","Creative","ad_id","{ad_id}","AdId"],
                "Ключевая фраза":["Ключевая фраза","Keyword","Фраза","Key phrase","UTM_TERM","utm_term","Term"],
                "Регион":["Регион","Region","region_name","REGION_NAME","{region_name}"],
                "Устройство":["Устройство","Device","device_type","DEVICE_TYPE","{device_type}"],
                "Площадка":["Площадка","Placement","source","SOURCE","{source}"],
                "Position":["Position","position","POSITION","{position}"],
                "URL":["URL","Url","url","Ссылка","Сайт","Landing page"],
                "Продукт":["Продукт","Product","product","PRODUCT"]
                }

                mapping_widgets ={}
                for sys_col ,possible_names in column_mapping .items ():
                    row_layout =QHBoxLayout ()
                    row_layout .addWidget (QLabel (f"{sys_col }:"),1 )

                    combo =QComboBox ()
                    combo .addItem ("(не выбрано)")
                    combo .addItems (df .columns .tolist ())

                    # Пробуем найти автоматически
                    for col in df .columns :
                        if col in possible_names or col .lower ()in [n .lower ()for n in possible_names ]:
                            combo .setCurrentText (col )
                            self .log (f"Автоматически сопоставлено: {sys_col } -> {col }")
                            break 

                    row_layout .addWidget (combo ,2 )
                    layout .addLayout (row_layout )
                    mapping_widgets [sys_col ]=combo 

                    # Кнопки
                btn_layout =QHBoxLayout ()
                ok_btn =QPushButton ("OK")
                cancel_btn =QPushButton ("Отмена")
                btn_layout .addWidget (ok_btn )
                btn_layout .addWidget (cancel_btn )
                layout .addLayout (btn_layout )

                ok_btn .clicked .connect (mapping_dialog .accept )
                cancel_btn .clicked .connect (mapping_dialog .reject )

                self .log ("Ожидание выбора пользователя...")
                if mapping_dialog .exec ()!=QDialog .DialogCode .Accepted :
                    self .log ("Диалог закрыт пользователе")
                    return 
                self .log ("Пользователь подтвердил сопоставление")

                # Приеняе аппинг
                self .log ("\nПриенение аппинга...")
                for sys_col ,combo in mapping_widgets .items ():
                    selected_col =combo .currentText ()
                    if selected_col !="(не выбрано)":
                        if selected_col !=sys_col :
                            self .log (f"Переиенование: {selected_col } -> {sys_col }")
                            df =df .rename (columns ={selected_col :sys_col })

                            # Проверяет обязательные колонки
                required =["Дата"]
                missing =[col for col in required if col not in df .columns ]
                if missing :
                    self .log (f"Ошибка: отсутствуют колонки {missing }")
                    QMessageBox .warning (self ,"Ошибка",f"Отсутствует обязательная колонка: {missing }")
                    return 

                    # Добавляе недостающие колонки
                self .log ("\nДобавление недостающих колонок...")
                for col in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]:
                    if col not in df .columns :
                        self .log (f"Добавлена колонка {col } со значение 0")
                        df [col ]=0 
                    else :
                        self .log (f"Колонка {col } уже существует")

                self .log (f"\nКолонки после подготовки: {df .columns .tolist ()}")
                self .log (f"Первые 5 строк:\n{df .head ()}")

                # Парсим числовые колонки
                self .log ("\n"+"-"*30 )
                self .log ("Парсимнг числовых колонок:")
                for col in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]:
                    if col in df .columns :
                        self .log (f"\nОбработка колонки {col }:")
                        self .log (f"До парсинга: {df [col ].head ().tolist ()}")
                        df [col ]=self .parse_numeric_column (df [col ],col )
                        self .log (f"После парсинга: {df [col ].head ().tolist ()}")

                        # Преобразуем дату
                self .log ("\n"+"-"*30 )
                self .log ("Преобразование дат...")
                self .log (f"Колонка Дата до преобразования: {df ['Дата'].head ().tolist ()}")
                before =len (df )
                df =self .parse_date_column (df ,"Дата")
                df =df .dropna (subset =["Дата"])
                self .log (f"После преобразования: {len (df )} из {before } строк")
                self .log (f"Преобразованные даты: {df ['Дата'].head ().tolist ()}")

                if len (df )==0 :
                    self .log ("ОШКА: Не удалось распознать даты")
                    QMessageBox .warning (self ,"Ошибка","Не удалось распознать даты в файле. Проверьте формат дат.")
                    return 

                    # Добавляе колонки изерений
                self .log ("\nДобавление колонок изерений...")
                for col in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
                    if col not in df .columns :
                        self .log (f"Добавлена колонка {col } со значение '(не указано)'")
                        df [col ]="(не указано)"
                    else :
                        self .log (f"Колонка {col } уже существует, заполняе пропуски...")
                        df [col ]=df [col ].fillna ("(не указано)").astype (str )

                self .ads_data =self ._normalize_source_dataframe (df ,"ads").copy ()
                self ._mark_sync_time ("ads")

                # Показывае итоговую инфорацию
                self .log ("\n"+"="*50 )
                self .log ("ЗАГРУЗКА ЗАВЕРШЕНА УСПЕШНО")
                self .log ("="*50 )
                self .log (f"Всего строк: {len (df )}")
                self .log (f"Колонки: {df .columns .tolist ()}")
                self .log (f"Расход (суа): {df ['Расход'].sum ():,.2f}")
                self .log (f"Лиды (суа): {df ['Лиды'].sum ():,.0f}")
                self .log (f"Продажи (сумма): {df ['Продажи'].sum ():,.0f}")

                info =f"Загружено {len (df )} строк данных реклаы\n"
                info +=f"Колонки: {', '.join (df .columns .tolist ())}\n"
                info +=f"Расход (суа): {df ['Расход'].sum ():,.2f} руб\n"
                info +=f"Лиды (суа): {df ['Лиды'].sum ():,.0f}\n"
                info +=f"Продажи (сумма): {df ['Продажи'].sum ():,.0f}\n"
                if len (df )>0 and pd .notna (df ['Дата'].min ())and pd .notna (df ['Дата'].max ()):
                    info +=f"Диапазон дат: {df ['Дата'].min ().strftime ('%d.%m.%Y')} - {df ['Дата'].max ().strftime ('%d.%m.%Y')}"
                else :
                    info +="Диапазон дат: не определн"
                QMessageBox .information (self ,"Успех",info )
                self .refresh_data_loader_labels ()

            except Exception as e :
                self .log ("\n"+"="*50 )
                self .log ("ПРОЗОШЛА ОШКА:")
                self .log (f"Тип ошибки: {type (e ).__name__ }")
                self .log (f"Сообщение: {str (e )}")
                self .log ("="*50 )
                import traceback 
                traceback .print_exc ()
                self .log (traceback .format_exc (),"error")
                QMessageBox .warning (self ,"Ошибка",f"Ошибка загрузки: {str (e )}")
        else :
            self .log ("Файл не выбран")

    def load_crm_data (self ):
        """Загрузка данных из CRM"""
        file_path ,_ =QFileDialog .getOpenFileName (
        self ,"Выберите файл с данныи CRM","",
        "Excel files (*.xlsx *.xls);;CSV files (*.csv)"
        )
        if file_path :
            self .crm_file_path =file_path 
            try :
                if file_path .endswith ('.csv'):
                    df =pd .read_csv (file_path ,encoding ='utf-8')
                    if len (df )==0 :
                        df =pd .read_csv (file_path ,encoding ='cp1251')
                else :
                    df =pd .read_excel (file_path )

                df .columns =df .columns .str .strip ()

                mapping_dialog =QDialog (self )
                mapping_dialog .setWindowTitle ("Сопоставление колонок CRM")
                layout =QVBoxLayout (mapping_dialog )
                layout .addWidget (QLabel ("Сопоставьте колонки CRM из файла с системными. Основное денежное поле — Выручка, а Ср.чек рассчитывается автоматически."))

                # Словарь возожных названий колонок для CRM
                column_mapping ={
                "Дата":["Дата","Date","День","Day"],
                "Лиды":["Лиды","Leads","Заявки","Заявка"],
                "Продажи":["Продажи","Sales","Заказы","Orders"],
                "Выручка":["Выручка","Revenue","Сумма сделки","Сумма","Сделка","Amount","Opportunity"],
                "Ср.чек":["Ср.чек","Средний чек","Average check","AvgCheck","Средний"],
                "Источник":["Источник","utm_source","UTM_SOURCE","Канал","Channel"],
                "Тип":["Тип","Medium","utm_medium","UTM_MEDIUM"],
                "Кампания":["Кампания","Campaign","utm_campaign","UTM_CAMPAIGN","campaign_id","{{campaign_id}}","РК"],
                "Группа":["Группа","Group","AdGroup","Группа объявлений","Gbid","gbid","{gbid}"],
                "Объявление":["Объявление","Ad","Creative","Content","content","UTM_CONTENT","utm_content","ad_id","{ad_id}"],
                "Ключевая фраза":["Ключевая фраза","Keyword","Фраза","Key phrase","UTM_TERM","utm_term","Term"],
                "Регион":["Регион","Region","region_name","REGION_NAME","{region_name}"],
                "Устройство":["Устройство","Device","device_type","DEVICE_TYPE","{device_type}"],
                "Площадка":["Площадка","Placement","source","SOURCE","{source}"],
                "Position":["Position","position","POSITION","{position}"],
                "URL":["URL","Url","url","Ссылка","Сайт","Landing page"],
                "Продукт":["Продукт","Product","product","PRODUCT"]
                }

                mapping_widgets ={}
                for sys_col ,possible_names in column_mapping .items ():
                    row_layout =QHBoxLayout ()
                    row_layout .addWidget (QLabel (f"{sys_col }:"),1 )

                    combo =QComboBox ()
                    combo .addItem ("(не выбрано)")
                    combo .addItems (df .columns .tolist ())

                    # Пробуем найти автоматически
                    for col in df .columns :
                        if col in possible_names or col .lower ()in [n .lower ()for n in possible_names ]:
                            combo .setCurrentText (col )
                            break 

                    row_layout .addWidget (combo ,2 )
                    layout .addLayout (row_layout )
                    mapping_widgets [sys_col ]=combo 

                    # Кнопки
                btn_layout =QHBoxLayout ()
                ok_btn =QPushButton ("OK")
                cancel_btn =QPushButton ("Отмена")
                btn_layout .addWidget (ok_btn )
                btn_layout .addWidget (cancel_btn )
                layout .addLayout (btn_layout )

                ok_btn .clicked .connect (mapping_dialog .accept )
                cancel_btn .clicked .connect (mapping_dialog .reject )

                if mapping_dialog .exec ()!=QDialog .DialogCode .Accepted :
                    return 

                    # Приеняе аппинг
                for sys_col ,combo in mapping_widgets .items ():
                    selected_col =combo .currentText ()
                    if selected_col !="(не выбрано)":
                        if selected_col !=sys_col :
                            df =df .rename (columns ={selected_col :sys_col })

                            # Проверяет обязательные колонки
                required =["Дата"]
                missing =[col for col in required if col not in df .columns ]
                if missing :
                    QMessageBox .warning (self ,"Ошибка",f"Отсутствует обязательная колонка: {missing }")
                    return 

                    # Добавляе недостающие колонки
                for col in ["Лиды","Продажи","Выручка","Ср.чек","Расход","Показы","Клики"]:
                    if col not in df .columns :
                        df [col ]=0 

                        # Парсим числовые колонки с помощью улучшенного метода
                for col in ["Лиды","Продажи","Выручка","Ср.чек","Расход","Показы","Клики"]:
                    if col in df .columns :
                        df [col ]=self .parse_numeric_column (df [col ],col )

                if "Выручка"not in df .columns :
                    df ["Выручка"]=0 
                if "Ср.чек"not in df .columns :
                    df ["Ср.чек"]=0 
                if df ["Выручка"].sum ()<=0 and {"Продажи","Ср.чек"}.issubset (df .columns ):
                    df ["Выручка"]=pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 )*pd .to_numeric (df ["Ср.чек"],errors ="coerce").fillna (0 )
                if {"Выручка","Продажи"}.issubset (df .columns ):
                    df ["Ср.чек"]=np .where (
                    pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 )>0 ,
                    pd .to_numeric (df ["Выручка"],errors ="coerce").fillna (0 )/pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 ),
                    0 
                    )

                    # Преобразуем дату универсальным методом
                before =len (df )
                df =self .parse_date_column (df ,"Дата")
                df =df .dropna (subset =["Дата"])
                self .log (f"Даты распознаны: {len (df )} из {before } строк")

                if len (df )==0 :
                    QMessageBox .warning (self ,"Ошибка","Не удалось распознать даты в файле. Проверьте формат дат.")
                    return 

                    # Добавляе колонки изерений
                for col in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
                    if col not in df .columns :
                        df [col ]="(не указано)"
                    else :
                        df [col ]=df [col ].fillna ("(не указано)").astype (str )

                self .crm_data =self ._normalize_source_dataframe (df ,"crm").copy ()
                self ._mark_sync_time ("crm")

                # Показывае инфорацию о загруженных данных
                info =f"Загружено {len (df )} строк данных CRM\n"
                info +=f"Колонки: {', '.join (df .columns .tolist ())}\n"
                info +=f"Лиды (суа): {df ['Лиды'].sum ():,.0f}\n"
                info +=f"Продажи (сумма): {df ['Продажи'].sum ():,.0f}\n"
                if len (df )>0 and pd .notna (df ['Дата'].min ())and pd .notna (df ['Дата'].max ()):
                    info +=f"Диапазон дат: {df ['Дата'].min ().strftime ('%d.%m.%Y')} - {df ['Дата'].max ().strftime ('%d.%m.%Y')}"
                else :
                    info +="Диапазон дат: не определн"
                QMessageBox .information (self ,"Успех",info )
                self .refresh_data_loader_labels ()

            except Exception as e :
                QMessageBox .warning (self ,"Ошибка",f"Ошибка загрузки: {str (e )}")

    def merge_data (self ):
        """Объединяет данные из реклаы и CRM с правильны сопоставление по измерения"""
        self .log ("\n=== ОЪЕДНЕНЕ ДАННЫХ ===")

        if (not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty )and self .ads_file_path :
            restored_ads =self ._load_saved_source_file (self .ads_file_path ,"ads")
            if restored_ads is not None and not restored_ads .empty :
                self .ads_data =restored_ads 
                self .log (f"Рекламные данные автоматически восстановлены из файла: {self .ads_file_path }")

        if (not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty )and self .crm_file_path :
            restored_crm =self ._load_saved_source_file (self .crm_file_path ,"crm")
            if restored_crm is not None and not restored_crm .empty :
                self .crm_data =restored_crm 
                self .log (f"CRM данные автоматически восстановлены из файла: {self .crm_file_path }")

        self .refresh_data_loader_labels ()

        if not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty :
            QMessageBox .warning (self ,"Ошибка","Сначала загрузите данные реклаы")
            return 
        if not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty :
            QMessageBox .warning (self ,"Ошибка","Сначала загрузите данные CRM")
            return 

        try :
        # Убеждаеся, что даты в правильно формате
            self .ads_data ["Дата"]=pd .to_datetime (self .ads_data ["Дата"],errors ='coerce')
            self .crm_data ["Дата"]=pd .to_datetime (self .crm_data ["Дата"],errors ='coerce')

            # Удаляет строки с пустыи датаи
            self .ads_data =self .ads_data .dropna (subset =["Дата"])
            self .crm_data =self .crm_data .dropna (subset =["Дата"])

            self .log (f"Реклаа: {len (self .ads_data )} строк")
            self .log (f"CRM: {len (self .crm_data )} строк")

            self ._ensure_datetime ()

            # Список колонок изерений
            dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]

            # Для рекламных данных заполняе пропуски в измерениях
            for col in dimension_cols :
                if col in self .ads_data .columns :
                    self .ads_data [col ]=self .ads_data [col ].fillna ("").astype (str )
                    self .ads_data [col ]=self .ads_data [col ].replace ("","не указано")
                else :
                    self .ads_data [col ]="не указано"

                    # Для CRM данных заполняе пропуски в измерениях
            for col in dimension_cols :
                if col in self .crm_data .columns :
                    self .crm_data [col ]=self .crm_data [col ].fillna ("").astype (str )
                    self .crm_data [col ]=self .crm_data [col ].replace ("","не указано")
                else :
                    self .crm_data [col ]="не указано"

                    # Убеждаеся, что числовые колонки иеют правильный тип
            numeric_cols_ads =["Расход","Показы","Клики"]
            for col in numeric_cols_ads :
                if col in self .ads_data .columns :
                    self .ads_data [col ]=pd .to_numeric (self .ads_data [col ],errors ='coerce').fillna (0 )
                else :
                    self .ads_data [col ]=0 

            numeric_cols_crm =["Лиды","Продажи","Ср.чек"]
            for col in numeric_cols_crm :
                if col in self .crm_data .columns :
                    self .crm_data [col ]=pd .to_numeric (self .crm_data [col ],errors ='coerce').fillna (0 )
                else :
                    self .crm_data [col ]=0 

                    # Объединяе данные по все измерения и дате
            merge_cols =["Дата"]+dimension_cols 

            # Подготавливае данные для объединения
            ads_for_merge =self .ads_data [merge_cols +["Расход","Показы","Клики"]]
            crm_for_merge =self .crm_data [merge_cols +["Лиды","Продажи","Ср.чек"]]

            merged =pd .merge (
            ads_for_merge ,
            crm_for_merge ,
            on =merge_cols ,
            how ="outer"
            )

            # Заполняе пропуски
            for col in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]:
                merged [col ]=merged [col ].fillna (0 )

                # Заполняе пропуски в измерениях
            for col in dimension_cols :
                merged [col ]=merged [col ].fillna ("не указано")

            self .log (f"После объединения: {len (merged )} строк")

            # Группируе по дате и все измерения, чтобы объединить дубликаты
            self .log ("\nГруппировка данных...")
            group_cols =["Дата"]+dimension_cols 
            agg_dict ={
            "Расход":"sum",
            "Показы":"sum",
            "Клики":"sum",
            "Лиды":"sum",
            "Продажи":"sum",
            "Ср.чек":"mean"
            }

            merged =merged .groupby (group_cols ).agg (agg_dict ).reset_index ()
            self .log (f"После группировки: {len (merged )} строк")

            # Пересчитывает выручку
            merged ["Выручка"]=merged ["Продажи"]*merged ["Ср.чек"]
            merged ["Выручка"]=merged ["Выручка"].round (0 ).astype (int )

            # Пересчитывает остальные метрики
            # CTR
            merged ["CTR"]=merged .apply (
            lambda row :(row ["Клики"]/row ["Показы"]*100 )if row ["Показы"]>0 else 0 ,
            axis =1 
            ).round (2 )

            # CR1
            merged ["CR1"]=merged .apply (
            lambda row :(row ["Лиды"]/row ["Клики"]*100 )if row ["Клики"]>0 else 0 ,
            axis =1 
            ).round (2 )

            # CPC
            merged ["CPC"]=merged .apply (
            lambda row :round (row ["Расход"]/row ["Клики"])if row ["Клики"]>0 else 0 ,
            axis =1 
            ).astype (int )

            # CPL
            merged ["CPL"]=merged .apply (
            lambda row :round (row ["Расход"]/row ["Лиды"])if row ["Лиды"]>0 else 0 ,
            axis =1 
            ).astype (int )

            # CR2
            merged ["CR2"]=merged .apply (
            lambda row :(row ["Продажи"]/row ["Лиды"]*100 )if row ["Лиды"]>0 else 0 ,
            axis =1 
            ).round (2 )

            # Маржа
            merged ["Маржа"]=(merged ["Выручка"]-merged ["Расход"]).round (0 ).astype (int )

            # ROMI
            merged ["ROMI"]=merged .apply (
            lambda row :((row ["Выручка"]-row ["Расход"])/row ["Расход"]*100 )if row ["Расход"]>0 else -100 ,
            axis =1 
            ).round (2 )

            # Сохраняе как основные данные
            self .data =merged 

            # ===== ПРЕОБРАЗУЕМ ДАТУ В DATETIME =====
            if "Дата"in self .data .columns :
                self .data ["Дата"]=self ._parse_date_series (self .data ["Дата"])
                self .data =self .data .dropna (subset =["Дата"])

            self .original_data =self .data .copy ()
            self .filtered_data =self .data .copy ()
            self .chart_data =self .data .copy ()

            # Обновляет фильтры
            self .update_filters_from_data ()

            # Обновляет интерфейс
            self .update_dashboard ()

            # Обновляет вкладки с измерениями
            from_date =self .date_from .date ().toPyDate ()
            to_date =self .date_to .date ().toPyDate ()

            for dimension_name in ["Источник","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
                if dimension_name =="Тип"or dimension_name in self .data .columns :
                    self .update_dimension_table_with_filter (dimension_name ,from_date ,to_date )
                else :
                    empty_df =pd .DataFrame (columns =[dimension_name ])
                    self .dimension_data [dimension_name ]=empty_df 
                    self .display_dimension_table (dimension_name ,empty_df )


            QMessageBox .information (self ,"Успех",
            f"Данные объединены!\n\n"
            f"Всего строк: {len (self .data )}\n"
            f"Расход: {self .data ['Расход'].sum ():,.0f} руб\n"
            f"Лиды: {self .data ['Лиды'].sum ():,.0f}\n"
            f"Продажи: {self .data ['Продажи'].sum ():,.0f}\n"
            f"Выручка: {self .data ['Выручка'].sum ():,.0f}")

        except Exception as e :
            self .log (f"Ошибка: {e }")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")
            QMessageBox .warning (self ,"Ошибка",f"Ошибка объединения: {e }")

    def calculate_metrics (self ):
        """Пересчитываетт все метрики корректно"""
        self .log ("\n=== ПЕРЕСЧЕТ МЕТРК ===")

        try :
        # 1. CTR = Клики / Показы * 100
            if "Клики"in self .data .columns and "Показы"in self .data .columns :
                self .data ["CTR"]=self .data .apply (
                lambda row :(row ["Клики"]/row ["Показы"]*100 )if row ["Показы"]>0 else 0 ,
                axis =1 
                ).round (2 )
                self .log (f"CTR рассчитан, среднее: {self .data ['CTR'].mean ():.2f}")

                # 2. CR1 (конверсия в лиды) = Лиды / Клики * 100
            if "Лиды"in self .data .columns and "Клики"in self .data .columns :
                self .data ["CR1"]=self .data .apply (
                lambda row :(row ["Лиды"]/row ["Клики"]*100 )if row ["Клики"]>0 else 0 ,
                axis =1 
                ).round (2 )
                self .log (f"CR1 рассчитан, среднее: {self .data ['CR1'].mean ():.2f}")

                # 3. CPC = Расход / Клики
            if "Расход"in self .data .columns and "Клики"in self .data .columns :
                self .data ["CPC"]=self .data .apply (
                lambda row :round (row ["Расход"]/row ["Клики"])if row ["Клики"]>0 else 0 ,
                axis =1 
                ).astype (int )
                self .log (f"CPC рассчитан, среднее: {self .data ['CPC'].mean ():.2f}")

                # 4. CPL = Расход / Лиды
            if "Расход"in self .data .columns and "Лиды"in self .data .columns :
                self .data ["CPL"]=self .data .apply (
                lambda row :round (row ["Расход"]/row ["Лиды"])if row ["Лиды"]>0 else 0 ,
                axis =1 
                ).astype (int )
                self .log (f"CPL рассчитан, среднее: {self .data ['CPL'].mean ():.2f}")

                # 5. Выручка = Продажи * Ср.чек (важно: Ср.чек - это средний чек из CRM)
            if "Продажи"in self .data .columns and "Ср.чек"in self .data .columns :
            # Если Ср.чек = 0, но есть продажи, нужно подставить значение из данных
                self .data ["Выручка"]=self .data .apply (
                lambda row :row ["Продажи"]*row ["Ср.чек"]if row ["Ср.чек"]>0 else 0 ,
                axis =1 
                ).round (0 ).astype (int )
                self .log (f"Выручка рассчитана, суа: {self .data ['Выручка'].sum ():,.0f}")

                # 6. Маржа = Выручка - Расход
            if "Выручка"in self .data .columns and "Расход"in self .data .columns :
                self .data ["Маржа"]=self .data .apply (
                lambda row :row ["Выручка"]-row ["Расход"],
                axis =1 
                ).round (0 ).astype (int )
                self .log (f"Маржа рассчитана, суа: {self .data ['Маржа'].sum ():,.0f}")

                # 7. CR2 = Продажи / Лиды * 100 (конверсия из лидов в продажи)
            if "Продажи"in self .data .columns and "Лиды"in self .data .columns :
                self .data ["CR2"]=self .data .apply (
                lambda row :(row ["Продажи"]/row ["Лиды"]*100 )if row ["Лиды"]>0 else 0 ,
                axis =1 
                ).round (2 )
                self .log (f"CR2 рассчитан, среднее: {self .data ['CR2'].mean ():.2f}")

                # 8. ROMI = (Выручка - Расход) / Расход * 100
            if "Выручка"in self .data .columns and "Расход"in self .data .columns :
                self .data ["ROMI"]=self .data .apply (
                lambda row :((row ["Выручка"]-row ["Расход"])/row ["Расход"]*100 )if row ["Расход"]>0 else -100 ,
                axis =1 
                ).round (2 )
                self .log (f"ROMI рассчитан, среднее: {self .data ['ROMI'].mean ():.2f}")

            self .log ("Все метрики успешно пересчитаны")

        except Exception as e :
            self .log (f"Ошибка при расчете метрик: {e }")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")

    def update_dimension_table_with_filter (self ,dimension_name ,from_date ,to_date ):
        """Обновляетт таблицу для измерения с учето фильтра по дата"""

        self .log (f"\n{'='*60 }")
        self .log (f"ОНОВЛЕНЕ ВКЛАДК: {dimension_name }")
        self .log (f"Период: {from_date } - {to_date }")
        self .log (f"{'='*60 }")

        # Проверяет, есть ли данные
        if self .data .empty :
            self .log ("Нет данных в self.data")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        self .log (f"Колонки в self.data: {self .data .columns .tolist ()}")
        self .log (f"Всего строк в self.data: {len (self .data )}")

        source_df =self .data .copy ()
        column_name =dimension_name 
        if dimension_name =="Тип":
            if "Medium"not in source_df .columns :
                source_df ["Medium"]="Не указано"
            source_df ["Medium"]=(
            source_df ["Medium"]
            .fillna ("Не указано")
            .astype (str )
            .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
            )
            column_name ="Medium"

            # Проверяет наличие колонки измерения
        if column_name not in source_df .columns :
            self .log (f"Колонка '{column_name }' не найдена в данных")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

            # Фильтруе данные по дате
        self .log (f"\n--- Фильтрация по дате ---")
        self .log (f"Диапазон дат в данных: {source_df ['Дата'].min ()} - {source_df ['Дата'].max ()}")

        filtered =source_df [
        (source_df ["Дата"]>=pd .Timestamp (from_date ))&
        (source_df ["Дата"]<=pd .Timestamp (to_date ))
        ]

        self .log (f"После фильтрации: {len (filtered )} строк")

        if filtered .empty :
            self .log ("Нет данных за выбранный период")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

            # Показывае уникальные значения измерения
        self .log (f"\n--- Уникальные значения {dimension_name } ---")
        unique_vals =filtered [column_name ].unique ()
        self .log (f"Всего уникальных: {len (unique_vals )}")
        self .log (f"Первые 10: {unique_vals [:10 ].tolist ()}")

        # Группируе данные по изерению
        self .log (f"\n--- Группировка по {dimension_name } ---")
        self .log (f"Колонки для агрегации: Расход, Показы, Клики, Лиды, Продажи, Выручка, Ср.чек")

        # ВАЖНО: Выручка уже есть в данных, ее нужно суировать, а не пересчитывать!
        grouped =filtered .groupby (dimension_name ).agg ({
        "Расход":"sum",
        "Показы":"sum",
        "Клики":"sum",
        "Лиды":"sum",
        "Продажи":"sum",
        "Выручка":"sum",# Суируе выручку
        "Ср.чек":"mean"# Ср.чек бере как средний
        }).reset_index ()

        self .log (f"После группировки: {len (grouped )} строк")
        self .log (f"Сумма расходов: {grouped ['Расход'].sum ():,.0f}")
        self .log (f"Сумма лидов: {grouped ['Лиды'].sum ():,.0f}")
        self .log (f"Суа продаж: {grouped ['Продажи'].sum ():,.0f}")
        self .log (f"Суа выручки: {grouped ['Выручка'].sum ():,.0f}")

        # Показывае данные до расчета метрик
        self .log (f"\n--- ДАННЫЕ ДО РАСЧЕТА МЕТРК (первые 3 строки) ---")
        for idx in range (min (3 ,len (grouped ))):
            row =grouped .iloc [idx ]
            self .log (f"Строка {idx } - {dimension_name }: {row [dimension_name ]}")
            for col in ["Расход","Показы","Клики","Лиды","Продажи","Выручка","Ср.чек"]:
                if col in grouped .columns :
                    self .log (f"  {col }: {row [col ]}")

                    # Рассчитывает метрики
        self .log (f"\n--- РАСЧЕТ МЕТРИК ДЛЯ {dimension_name } ---")
        grouped =self .calculate_dimension_metrics_fixed (grouped ,dimension_name )

        # Показывае результаты
        self .log (f"\n--- РЕЗУЛЬТАТЫ ПОСЛЕ РАСЧЕТА МЕТРК (первые 3 строки) ---")
        for idx in range (min (3 ,len (grouped ))):
            row =grouped .iloc [idx ]
            self .log (f"Строка {idx } - {dimension_name }: {row [dimension_name ]}")
            for col in ["Расход","Выручка","Маржа","ROMI","CR2","Ср.чек"]:
                if col in grouped .columns :
                    self .log (f"  {col }: {row [col ]}")

        self .log (f"\nТОГОВЫЕ СУММЫ ПО {dimension_name }:")
        self .log (f"  Расход: {grouped ['Расход'].sum ():,.0f}")
        self .log (f"  Выручка: {grouped ['Выручка'].sum ():,.0f}")
        self .log (f"  Маржа: {grouped ['Маржа'].sum ():,.0f}")
        self .log (f"  Лиды: {grouped ['Лиды'].sum ():,.0f}")
        self .log (f"  Продажи: {grouped ['Продажи'].sum ():,.0f}")
        self .log ("="*60 +"\n")

        self .dimension_raw_data [dimension_name ]=grouped .copy ()
        self .dimension_data [dimension_name ]=grouped .copy ()
        self .display_dimension_table (dimension_name ,grouped )

    def calculate_dimension_metrics (self ,df ,dimension_name ):
        """Рассчитывает метрики для сгруппированных данных по измерению"""

        self .log (f"\n--- ВНУТР calculate_dimension_metrics для {dimension_name } ---")

        if df .empty :
            self .log ("DataFrame пуст")
            return df 

        self .log (f"Количество строк: {len (df )}")
        self .log (f"Колонки: {df .columns .tolist ()}")

        # Сначала рассчитывае выручку (на основе Продажи и Ср.чек)
        if "Продажи"in df .columns and "Ср.чек"in df .columns :
            self .log (f"\n1. Расчет ВЫРУЧК:")
            self .log (f"   Продажи: {df ['Продажи'].head (3 ).tolist ()}")
            self .log (f"   Ср.чек: {df ['Ср.чек'].head (3 ).tolist ()}")
            df ["Выручка"]=(df ["Продажи"]*df ["Ср.чек"]).round (0 ).fillna (0 ).astype (int )
            self .log (f"   Выручка: {df ['Выручка'].head (3 ).tolist ()}")

            # Зате аржа
        if "Выручка"in df .columns and "Расход"in df .columns :
            self .log (f"\n2. Расчет МАРЖ:")
            self .log (f"   Выручка: {df ['Выручка'].head (3 ).tolist ()}")
            self .log (f"   Расход: {df ['Расход'].head (3 ).tolist ()}")
            df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).round (0 ).fillna (0 ).astype (int )
            self .log (f"   Маржа: {df ['Маржа'].head (3 ).tolist ()}")

            # CTR
        if "Клики"in df .columns and "Показы"in df .columns :
            self .log (f"\n3. Расчет CTR:")
            df ["CTR"]=np .where (
            df ["Показы"]>0 ,
            (df ["Клики"]/df ["Показы"]*100 ).round (2 ),
            0 
            )
            df ["CTR"]=df ["CTR"].fillna (0 )

            # CR1
        if "Лиды"in df .columns and "Клики"in df .columns :
            self .log (f"\n4. Расчет CR1:")
            df ["CR1"]=np .where (
            df ["Клики"]>0 ,
            (df ["Лиды"]/df ["Клики"]*100 ).round (2 ),
            0 
            )
            df ["CR1"]=df ["CR1"].fillna (0 )

            # CPC
        if "Расход"in df .columns and "Клики"in df .columns :
            self .log (f"\n5. Расчет CPC:")
            df ["CPC"]=np .where (
            df ["Клики"]>0 ,
            (df ["Расход"]/df ["Клики"]).round (0 ),
            0 
            )
            df ["CPC"]=df ["CPC"].fillna (0 ).astype (int )

            # CPL
        if "Расход"in df .columns and "Лиды"in df .columns :
            self .log (f"\n6. Расчет CPL:")
            cpl_values =np .where (
            df ["Лиды"]>0 ,
            df ["Расход"]/df ["Лиды"],
            0 
            )
            cpl_values =np .where (np .isfinite (cpl_values ),cpl_values ,0 )
            df ["CPL"]=cpl_values .round (0 ).fillna (0 ).astype (int )
            self .log (f"   CPL: {df ['CPL'].head (3 ).tolist ()}")

            # CR2
        if "Продажи"in df .columns and "Лиды"in df .columns :
            self .log (f"\n7. Расчет CR2:")
            self .log (f"   Продажи: {df ['Продажи'].head (3 ).tolist ()}")
            self .log (f"   Лиды: {df ['Лиды'].head (3 ).tolist ()}")
            df ["CR2"]=np .where (
            df ["Лиды"]>0 ,
            (df ["Продажи"]/df ["Лиды"]*100 ).round (2 ),
            0 
            )
            df ["CR2"]=df ["CR2"].fillna (0 )
            self .log (f"   CR2: {df ['CR2'].head (3 ).tolist ()}")

            # ROMI
        if "Выручка"in df .columns and "Расход"in df .columns :
            self .log (f"\n8. Расчет ROMI:")
            self .log (f"   Выручка: {df ['Выручка'].head (3 ).tolist ()}")
            self .log (f"   Расход: {df ['Расход'].head (3 ).tolist ()}")
            romi_values =np .where (
            df ["Расход"]>0 ,
            ((df ["Выручка"]-df ["Расход"])/df ["Расход"]*100 ).round (2 ),
            -100 
            )
            romi_values =np .where (np .isfinite (romi_values ),romi_values ,-100 )
            df ["ROMI"]=romi_values .fillna (-100 )
            self .log (f"   ROMI: {df ['ROMI'].head (3 ).tolist ()}")

        self .log (f"\n--- ТОГО ПО {dimension_name } ---")
        self .log (f"Суа выручки: {df ['Выручка'].sum ():,.0f}")
        self .log (f"Суа аржи: {df ['Маржа'].sum ():,.0f}")
        self .log (f"Сумма расходов: {df ['Расход'].sum ():,.0f}")

        return df 

    def calculate_dimension_metrics_fixed (self ,df ,dimension_name ):
        """Рассчитывает метрики для сгруппированных данных"""

        self .log (f"\n--- ВНУТР calculate_dimension_metrics_fixed для {dimension_name } ---")

        if df .empty :
            self .log ("DataFrame пуст")
            return df 

        self .log (f"Количество строк: {len (df )}")
        self .log (f"Колонки: {df .columns .tolist ()}")

        # Убеждаеся, что все числовые колонки в правильно формате
        numeric_cols =["Расход","Показы","Клики","Лиды","Продажи","Выручка","Ср.чек"]
        for col in numeric_cols :
            if col in df .columns :
                df [col ]=pd .to_numeric (df [col ],errors ='coerce').fillna (0 )

                # Маржа = Выручка - Расход (с защитой от inf)
        if "Выручка"in df .columns and "Расход"in df .columns :
            df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).replace ([float ('inf'),-float ('inf')],0 ).fillna (0 ).round (0 ).astype (int )
            self .log (f"  Маржа (суа): {df ['Маржа'].sum ():,.0f}")

            # CTR = Клики / Показы * 100
        if "Клики"in df .columns and "Показы"in df .columns :
            df ["CTR"]=np .where (
            df ["Показы"]>0 ,
            (df ["Клики"]/df ["Показы"]*100 ).round (2 ),
            0 
            )
            df ["CTR"]=pd .Series (df ["CTR"]).fillna (0 )

            # CR1 = Лиды / Клики * 100
        if "Лиды"in df .columns and "Клики"in df .columns :
            df ["CR1"]=np .where (
            df ["Клики"]>0 ,
            (df ["Лиды"]/df ["Клики"]*100 ).round (2 ),
            0 
            )
            df ["CR1"]=pd .Series (df ["CR1"]).fillna (0 )

            # CPC = Расход / Клики
        if "Расход"in df .columns and "Клики"in df .columns :
            df ["CPC"]=np .where (
            df ["Клики"]>0 ,
            (df ["Расход"]/df ["Клики"]).round (0 ),
            0 
            )
            df ["CPC"]=pd .Series (df ["CPC"]).fillna (0 ).astype (int )

            # CPL = Расход / Лиды
        if "Расход"in df .columns and "Лиды"in df .columns :
            cpl_values =np .where (
            df ["Лиды"]>0 ,
            df ["Расход"]/df ["Лиды"],
            0 
            )
            cpl_values =np .where (np .isfinite (cpl_values ),cpl_values ,0 )
            df ["CPL"]=pd .Series (cpl_values ).round (0 ).fillna (0 ).astype (int )

            # CR2 = Продажи / Лиды * 100
        if "Продажи"in df .columns and "Лиды"in df .columns :
            df ["CR2"]=np .where (
            df ["Лиды"]>0 ,
            (df ["Продажи"]/df ["Лиды"]*100 ).round (2 ),
            0 
            )
            df ["CR2"]=pd .Series (df ["CR2"]).fillna (0 )

            # ROMI = (Выручка - Расход) / Расход * 100
        if "Выручка"in df .columns and "Расход"in df .columns :
            romi_values =np .where (
            df ["Расход"]>0 ,
            ((df ["Выручка"]-df ["Расход"])/df ["Расход"]*100 ).round (2 ),
            -100 
            )
            romi_values =np .where (np .isfinite (romi_values ),romi_values ,-100 )
            df ["ROMI"]=pd .Series (romi_values ).fillna (-100 )

        self .log (f"\n--- ТОГО ПО {dimension_name } ---")
        self .log (f"Суа выручки: {df ['Выручка'].sum ():,.0f}")
        self .log (f"Суа аржи: {df ['Маржа'].sum ():,.0f}")
        self .log (f"Сумма расходов: {df ['Расход'].sum ():,.0f}")
        self .log (f"Суа продаж: {df ['Продажи'].sum ():,.0f}")

        return df 

    def change_grouping (self ):
        """Группировка данных - просто обновляет дашборд"""
        self .log (f"Смена группировки на: {self .group_combo .currentText ()}")
        self .update_dashboard ()

        # ===== ВАЖНО: использует original_data, а не original_filtered_data =====
        # original_data хранит исходные данные с правильны типо datetime
        if not hasattr (self ,'original_data')or self .original_data .empty :
            return 

            # Всегда начинае с полных данных
        data =self .original_data .copy ()

        # ===== УЕЖДАЕМСЯ, ЧТО ДАТА В ПРАВЛЬНОМ ФОРМАТЕ =====
        if "Дата"in data .columns :
        # Выводим для отладки
            self .log (f"Тип даты до преобразования: {data ['Дата'].dtype }")

            # Если дата не datetime, преобразуе
            if not pd .api .types .is_datetime64_any_dtype (data ["Дата"]):
                data ["Дата"]=pd .to_datetime (data ["Дата"],errors ='coerce',dayfirst =True )
                self .log (f"Даты преобразованы в datetime")

                # Удаляетм строки с некорректными датами
            data =data .dropna (subset =["Дата"])

            self .log (f"Тип даты после: {data ['Дата'].dtype }")
            self .log (f"Первые 5 дат: {data ['Дата'].head ().tolist ()}")

        if data .empty :
            self .log ("Нет данных после преобразования дат")
            self .filtered_data =pd .DataFrame ()
            self ._refresh_display ()
            return 

            # Приеняе фильтр по дата
        from_dt =pd .to_datetime (self .date_from .date ().toPyDate ())
        to_dt =pd .to_datetime (self .date_to .date ().toPyDate ())
        data =data [(data ["Дата"]>=from_dt )&(data ["Дата"]<=to_dt )]

        if data .empty :
            self .log ("Нет данных за выбранный период")
            self .filtered_data =pd .DataFrame ()
            self ._refresh_display ()
            return 

        group_type =self .group_combo .currentText ()

        if group_type =="день":
            self .filtered_data =data 
        else :
        # Логика группировки
            try :
                if group_type =="неделя":
                    data ["Группа_ноер"]=data ["Дата"].dt .isocalendar ().week 
                    data ["Год"]=data ["Дата"].dt .year 
                    data ["Группа"]="Неделя "+data ["Группа_ноер"].astype (str )+" ("+data ["Год"].astype (str )+")"
                    data ["Сортировка"]=data ["Год"]*100 +data ["Группа_ноер"]
                elif group_type =="есяц":
                    data ["Группа_ноер"]=data ["Дата"].dt .month 
                    data ["Год"]=data ["Дата"].dt .year 
                    data ["Группа"]=data ["Дата"].dt .strftime ("%B %Y")
                    data ["Сортировка"]=data ["Год"]*100 +data ["Группа_ноер"]
                elif group_type =="квартал":
                    data ["Группа_ноер"]=data ["Дата"].dt .quarter 
                    data ["Год"]=data ["Дата"].dt .year 
                    data ["Группа"]="Q"+data ["Группа_ноер"].astype (str )+" "+data ["Год"].astype (str )
                    data ["Сортировка"]=data ["Год"]*10 +data ["Группа_ноер"]
                elif group_type =="год":
                    data ["Группа_ноер"]=data ["Дата"].dt .year 
                    data ["Год"]=data ["Группа_ноер"]
                    data ["Группа"]=data ["Год"].astype (str )
                    data ["Сортировка"]=data ["Год"]
                else :
                    return 
            except Exception as e :
                self .log (f"Ошибка при группировке: {e }")
                self .log (f"Тип данных в колонке Дата: {data ['Дата'].dtype }")
                self .log (f"Примеры дат: {data ['Дата'].head ().tolist ()}")
                return 

                # Агрегация
            agg_dict ={col :"sum"for col in ["Расход","Показы","Клики","Лиды","Продажи","Выручка"]}
            if "Ср.чек"in data .columns :
                agg_dict ["Ср.чек"]="mean"

            grouped =data .groupby (["Группа","Группа_ноер","Сортировка"]).agg (agg_dict ).reset_index ()

            # Сортируе по Сортировка
            grouped =grouped .sort_values ("Сортировка").reset_index (drop =True )

            # Удаляет вреенные колонки
            cols_to_drop =["Группа_ноер","Сортировка"]
            grouped =grouped .drop (columns =cols_to_drop ,errors ='ignore')
            grouped =grouped .rename (columns ={"Группа":"Дата"})

            self .filtered_data =grouped 

            # Пересчитывает планы и метрики
        self ._calculate_all_plan_metrics ()
        self ._refresh_display ()

    def _calculate_all_plan_metrics (self ):
        """Вспомогательный метод для расчета всех недостающих колонок"""
        df =self .filtered_data .copy ()

        # Создает плановые колонки, если их нет
        for col in ["Расход план","Лиды план","CPL план","Расход %","Лиды %","CPL %"]:
            if col not in df .columns :
                df [col ]=0.0 

                # Приеняе планы из истории
        if self .current_client in self .plans_history and self .plans_history [self .current_client ]:
        # Создает дневные планы
            daily_plans ={}
            for period_key ,plan in self .plans_history [self .current_client ].items ():
                plan_from =plan ["period_from"]
                plan_to =plan ["period_to"]
                if plan_from and plan_to :
                    plan_days =(plan_to -plan_from ).days +1 
                    daily_budget =plan ["budget"]/plan_days 
                    daily_leads =plan ["leads"]/plan_days 
                    daily_cpl =daily_budget /daily_leads if daily_leads >0 else 0 

                    current_date =plan_from 
                    while current_date <=plan_to :
                        daily_plans [current_date ]={
                        "budget":daily_budget ,
                        "leads":daily_leads ,
                        "cpl":daily_cpl 
                        }
                        current_date +=timedelta (days =1 )

                        # Заполняе плановые значения
            for idx in range (len (df )):
                date_val =df .iloc [idx ]["Дата"]
                if isinstance (date_val ,pd .Timestamp ):
                    date_to_check =date_val .date ()
                else :
                    try :
                        date_to_check =pd .to_datetime (date_val ).date ()
                    except :
                        continue 

                if date_to_check in daily_plans :
                    plan =daily_plans [date_to_check ]
                    df .loc [idx ,"Расход план"]=plan ["budget"]
                    df .loc [idx ,"Лиды план"]=plan ["leads"]
                    df .loc [idx ,"CPL план"]=plan ["cpl"]

                    # Рассчитывает проценты выполнения
                    if plan ["budget"]>0 :
                        df .loc [idx ,"Расход %"]=round ((df .loc [idx ,"Расход"]/plan ["budget"])*100 ,2 )
                    if plan ["leads"]>0 :
                        df .loc [idx ,"Лиды %"]=round ((df .loc [idx ,"Лиды"]/plan ["leads"])*100 ,2 )
                    if plan ["cpl"]>0 :
                        actual_cpl =df .loc [idx ,"CPL"]if "CPL"in df .columns else 0 
                        df .loc [idx ,"CPL %"]=round ((actual_cpl /plan ["cpl"])*100 ,2 )

                        # ===== ПРЕОБРАЗУЕМ ВСЕ ЧСЛОВЫЕ КОЛОНК, ЗАМЕНЯЯ INF  NaN =====
        numeric_cols =["Расход","Показы","Клики","Лиды","Продажи","Выручка",
        "Ср.чек","Расход план","Лиды план","CPL план",
        "Расход %","Лиды %","CPL %"]

        for col in numeric_cols :
            if col in df .columns :
            # Заеняе inf и -inf на 0
                df [col ]=df [col ].replace ([float ('inf'),-float ('inf')],0 )
                # Заеняе NaN на 0
                df [col ]=df [col ].fillna (0 )

                # Пересчитывает базовые метрики с защитой от деления на ноль
        if "Расход"in df .columns and "Клики"in df .columns :
            df ["CPC"]=df .apply (
            lambda x :round (x ["Расход"]/x ["Клики"])if x ["Клики"]>0 else 0 ,
            axis =1 
            ).fillna (0 ).astype (int )

        if "Выручка"in df .columns and "Расход"in df .columns :
            df ["ROMI"]=df .apply (
            lambda x :round (((x ["Выручка"]-x ["Расход"])/x ["Расход"])*100 ,2 )if x ["Расход"]>0 else -100 ,
            axis =1 
            ).fillna (-100 )

        if "Лиды"in df .columns and "Клики"in df .columns :
            df ["CR1"]=df .apply (
            lambda x :round ((x ["Лиды"]/x ["Клики"])*100 ,2 )if x ["Клики"]>0 else 0 ,
            axis =1 
            ).fillna (0 )

        if "Продажи"in df .columns and "Лиды"in df .columns :
            df ["CR2"]=df .apply (
            lambda x :round ((x ["Продажи"]/x ["Лиды"])*100 ,2 )if x ["Лиды"]>0 else 0 ,
            axis =1 
            ).fillna (0 )

        if "Выручка"in df .columns and "Продажи"in df .columns :
            df ["Ср.чек"]=df .apply (
            lambda x :round (x ["Выручка"]/x ["Продажи"])if x ["Продажи"]>0 else 0 ,
            axis =1 
            ).fillna (0 ).astype (int )

        if "Выручка"in df .columns and "Расход"in df .columns :
        # Сначала заменяем бесконечные значения
            df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).replace ([float ('inf'),-float ('inf')],0 ).fillna (0 ).round (0 ).astype (int )

            # Финальная очистка от inf и NaN
        for col in df .columns :
            if df [col ].dtype in ['float64','float32']:
                df [col ]=df [col ].replace ([float ('inf'),-float ('inf')],0 ).fillna (0 )

        self .filtered_data =df 

    def _apply_plans_to_filtered_data (self ):
        """Применяет планы к отфильтрованны данны (для дневной группировки)"""
        if "Дата"not in self .filtered_data .columns :
            return 

            # Получаем все планы для текущего клиента
        plans =self .plans_history .get (self .current_client ,{})
        if not plans :
            return 

            # Для каждой даты в данных приеняе план
        for idx in range (len (self .filtered_data )):
            date_val =self .filtered_data .iloc [idx ]["Дата"]

            # Преобразуем в date
            if isinstance (date_val ,pd .Timestamp ):
                date_to_check =date_val .date ()
            else :
                try :
                    date_to_check =pd .to_datetime (date_val ).date ()
                except :
                    continue 

                    # ще план, который покрывает эту дату
            for period_key ,plan in plans .items ():
                plan_from =plan ["period_from"]
                plan_to =plan ["period_to"]

                if plan_from <=date_to_check <=plan_to :
                # Рассчитывает дневной план
                    plan_days =(plan_to -plan_from ).days +1 
                    daily_budget =plan ["budget"]/plan_days 
                    daily_leads =plan ["leads"]/plan_days 
                    daily_cpl =daily_budget /daily_leads if daily_leads >0 else 0 

                    # Устанавливае плановые значения
                    self .filtered_data .loc [idx ,"Расход план"]=daily_budget 
                    self .filtered_data .loc [idx ,"Лиды план"]=daily_leads 
                    self .filtered_data .loc [idx ,"CPL план"]=daily_cpl 

                    # Рассчитывает проценты
                    if daily_budget >0 :
                        self .filtered_data .loc [idx ,"Расход %"]=(self .filtered_data .loc [idx ,"Расход"]/daily_budget )*100 
                    if daily_leads >0 :
                        self .filtered_data .loc [idx ,"Лиды %"]=(self .filtered_data .loc [idx ,"Лиды"]/daily_leads )*100 
                    if daily_cpl >0 :
                        actual_cpl =self .filtered_data .loc [idx ,"CPL"]if "CPL"in self .filtered_data .columns else 0 
                        self .filtered_data .loc [idx ,"CPL %"]=(actual_cpl /daily_cpl )*100 

                    break # Нашли план для этой даты, выходи из цикла

    def toggle_theme (self ):
        """Переключает тему между светлой и темной"""
        self .dark_mode =not self .dark_mode 

        if self .dark_mode :
        # Темная тема
            self .setStyleSheet ("""
                QMainWindow, QDialog, QWidget {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QPushButton {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                }
                QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 3px;
                }
                QTableWidget {
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                    gridline-color: #3a3a3a;
                    color: #e0e0e0;
                }
                QTabWidget::pane {
                    border: 1px solid #3a3a3a;
                    background-color: #1e1e1e;
                }
                QTabBar::tab {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    padding: 6px 12px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #3a3a3a;
                }
                QTabBar::tab:hover {
                    background-color: #3a3a3a;
                }
                QGroupBox {
                    border: 1px solid #3a3a3a;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    color: #e0e0e0;
                }
                QCheckBox {
                    color: #e0e0e0;
                }
                QFrame {
                    border: 1px solid #3a3a3a;
                }
                QListWidget {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #3a3a3a;
                }
            """)

            # Обновляет стиль фильтров
            for filter_name in self .filters_widgets :
                btn =self .filters_widgets [filter_name ]['button']
                btn .setStyleSheet ("""
                    QPushButton {
                        background-color: #2d2d2d;
                        color: #e0e0e0;
                        border: 1px solid #555;
                        border-radius: 3px;
                        padding: 5px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #3a3a3a;
                    }
                """)

                # Обновляет стиль карточек KPI
            for i in range (self .kpi_layout .count ()):
                widget =self .kpi_layout .itemAt (i ).widget ()
                if isinstance (widget ,QFrame ):
                    widget .setStyleSheet ("""
                        QFrame {
                            background-color: #252525;
                            border: 1px solid #3a3a3a;
                            border-radius: 10px;
                            padding: 10px;
                        }
                        QLabel {
                            color: #e0e0e0;
                        }
                    """)
                    title =widget .layout ().itemAt (0 ).widget ()
                    if title :
                        title .setStyleSheet ("font-size: 13px; font-weight: bold; color: #a9b4c0; letter-spacing: 0.4px;")
                    value =widget .layout ().itemAt (1 ).widget ()
                    if value :
                        value .setStyleSheet ("font-size: 18px; font-weight: bold; color: #f4f7fb;")

                        # Обновляет стиль группировки
            if hasattr (self ,'group_combo'):
                self .group_combo .setStyleSheet ("""
                    QComboBox {
                        background-color: #2d2d2d;
                        color: #e0e0e0;
                        border: 1px solid #555;
                        border-radius: 3px;
                        padding: 3px;
                    }
                    QComboBox::drop-down {
                        background-color: #2d2d2d;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #2d2d2d;
                        color: #e0e0e0;
                        selection-background-color: #3a3a3a;
                    }
                """)

                # Обновляет стиль чекбокса
            if hasattr (self ,'hide_plan_checkbox'):
                self .hide_plan_checkbox .setStyleSheet ("""
                    QCheckBox {
                        color: #e0e0e0;
                    }
                """)

            self .theme_btn .setText ("☀️ Светлая тема")

        else :
        # Светлая тема
            self .setStyleSheet ("""
                QMainWindow, QDialog, QWidget {
                    background-color: #f5f5f5;
                    color: #2c3e50;
                }
                QLabel {
                    color: #2c3e50;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #2c3e50;
                    border: 1px solid #c0c0c0;
                    border-radius: 4px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                    background-color: white;
                    color: #2c3e50;
                    border: 1px solid #c0c0c0;
                    border-radius: 3px;
                    padding: 3px;
                }
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    gridline-color: #e0e0e0;
                    color: #2c3e50;
                }
                QTabWidget::pane {
                    border: 1px solid #e0e0e0;
                    background-color: white;
                }
                QTabBar::tab {
                    background-color: #f0f0f0;
                    color: #2c3e50;
                    padding: 6px 12px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: white;
                }
                QTabBar::tab:hover {
                    background-color: #e5e5e5;
                }
                QGroupBox {
                    border: 1px solid #e0e0e0;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    color: #2c3e50;
                }
                QCheckBox {
                    color: #2c3e50;
                }
                QFrame {
                    border: 1px solid #e0e0e0;
                }
                QListWidget {
                    background-color: white;
                    color: #2c3e50;
                    border: 1px solid #e0e0e0;
                }
            """)

            # Обновляет стиль фильтров
            for filter_name in self .filters_widgets :
                btn =self .filters_widgets [filter_name ]['button']
                btn .setStyleSheet ("""
                    QPushButton {
                        background-color: white;
                        color: #2c3e50;
                        border: 1px solid #c0c0c0;
                        border-radius: 3px;
                        padding: 5px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #f0f0f0;
                    }
                """)

                # Обновляет стиль карточек KPI
            for i in range (self .kpi_layout .count ()):
                widget =self .kpi_layout .itemAt (i ).widget ()
                if isinstance (widget ,QFrame ):
                    widget .setStyleSheet ("""
                        QFrame {
                            border: 1px solid #d9e2ec;
                            border-radius: 10px;
                            padding: 10px;
                            background-color: #fbfcfd;
                        }
                        QLabel {
                            color: #2c3e50;
                        }
                    """)
                    title =widget .layout ().itemAt (0 ).widget ()
                    if title :
                        title .setStyleSheet ("font-size: 13px; font-weight: bold; color: #6b7b8c; letter-spacing: 0.4px;")
                    value =widget .layout ().itemAt (1 ).widget ()
                    if value :
                        value .setStyleSheet ("font-size: 18px; font-weight: bold; color: #1f2d3d;")

                        # Обновляет стиль группировки
            if hasattr (self ,'group_combo'):
                self .group_combo .setStyleSheet ("""
                    QComboBox {
                        background-color: white;
                        color: #2c3e50;
                        border: 1px solid #c0c0c0;
                        border-radius: 3px;
                        padding: 3px;
                    }
                    QComboBox::drop-down {
                        background-color: white;
                    }
                    QComboBox QAbstractItemView {
                        background-color: white;
                        color: #2c3e50;
                        selection-background-color: #e5e5e5;
                    }
                """)

                # Обновляет стиль чекбокса
            if hasattr (self ,'hide_plan_checkbox'):
                self .hide_plan_checkbox .setStyleSheet ("""
                    QCheckBox {
                        color: #2c3e50;
                    }
                """)

            self .theme_btn .setText ("🌙 Темная тема")

            # Обновляет заголовки таблицы
        if hasattr (self ,'table'):
        # Сохраняе текущие заголовки
            headers =[]
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    headers .append (header .text ())

                    # Обновляет стиль заголовков
            self ._apply_header_style_to_table (self .table )

            # Восстанавливае стрелочки сортировки, если есть
            if hasattr (self ,'sort_column')and self .sort_column :
                self .update_sort_indicators ()

                # Обновляет таблицы в вкладках с измерениями
        for dim_name ,table in self .dimension_tables .items ():
            if table :
                self ._apply_header_style_to_table (table )

                # Обновляет таблицу и пересчитывае цвета заново под новую теу
        self .update_table ()

        # Обновляет график
        self .update_chart ()

        # Обновляет вкладки с измерениями
        self .refresh_all_dimension_tabs ()

        self .setup_table_header_style ()

        self .sync_all_table_columns_width ()

        self ._apply_consistent_widget_styles ()
        QTimer .singleShot (0 ,self ._refresh_all_table_headers_geometry )
        QTimer .singleShot (50 ,self ._refresh_all_table_headers_geometry )

    def _apply_consistent_widget_styles (self ):
        """Приводит поля, попапы и блоки формы к единоу виду для текущей темы"""
        if self .dark_mode :
            field_style ="""
                QLineEdit, QComboBox, QDateEdit {
                    min-height: 32px;
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 6px;
                    padding: 4px 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    selection-background-color: #3a3a3a;
                }
            """
            popup_style ="""
                QWidget { background-color: #252525; border: 1px solid #444; border-radius: 6px; padding: 5px; }
                QLineEdit { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #555; border-radius: 4px; padding: 4px 6px; margin: 2px; }
                QListWidget { background-color: #2d2d2d; color: #e0e0e0; border: none; }
                QListWidget::item { padding: 5px; }
                QPushButton { border: 1px solid #555; border-radius: 4px; padding: 4px 8px; margin: 2px; background: #333; color: #e0e0e0; }
                QPushButton:hover { background: #3c3c3c; }
            """
            group_style ="""
                QGroupBox {
                    border: 1px solid #3a3a3a;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 14px;
                    background-color: #232323;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                    color: #e0e0e0;
                    font-weight: bold;
                }
            """
        else :
            field_style ="""
                QLineEdit, QComboBox, QDateEdit {
                    min-height: 32px;
                    background-color: #ffffff;
                    color: #2c3e50;
                    border: 1px solid #cfd7df;
                    border-radius: 6px;
                    padding: 4px 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #2c3e50;
                    selection-background-color: #e9eef3;
                }
            """
            popup_style ="""
                QWidget { background-color: #ffffff; border: 1px solid #d7dee6; border-radius: 6px; padding: 5px; }
                QLineEdit { background-color: #ffffff; color: #2c3e50; border: 1px solid #cfd7df; border-radius: 4px; padding: 4px 6px; margin: 2px; }
                QListWidget { background-color: #ffffff; color: #2c3e50; border: none; }
                QListWidget::item { padding: 5px; }
                QPushButton { border: 1px solid #cfd7df; border-radius: 4px; padding: 4px 8px; margin: 2px; background: #f7f9fb; color: #2c3e50; }
                QPushButton:hover { background: #edf2f7; }
            """
            group_style ="""
                QGroupBox {
                    border: 1px solid #dbe3ea;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 14px;
                    background-color: #fbfcfd;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                    color: #2c3e50;
                    font-weight: bold;
                }
            """

        for name in [
        "date_from","date_to","group_combo","metric_combo","chart_group_combo","client_combo",
        "plan_date_from","plan_date_to","plan_source","plan_medium","plan_budget","plan_leads"
        ]:
            if hasattr (self ,name ):
                widget =getattr (self ,name )
                if widget :
                    widget .setStyleSheet (field_style )

        if hasattr (self ,"plan_tab")and self .plan_tab :
            for child in self .plan_tab .findChildren (QGroupBox ):
                child .setStyleSheet (group_style )

        self ._apply_plan_form_card_style ()

        for popup in self .filter_popups .values ():
            popup .setStyleSheet (popup_style )

        if hasattr (self ,"project_list")and self .project_list :
            self .project_list .setStyleSheet (
            """
                QListWidget {
                    border: 1px solid #3a3a3a;
                    border-radius: 8px;
                    background-color: #232323;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 8px 10px;
                    border-radius: 6px;
                    margin: 2px 0;
                }
                QListWidget::item:selected {
                    background-color: #334155;
                    color: #ffffff;
                }
                """
            if self .dark_mode else 
            """
                QListWidget {
                    border: 1px solid #d8dee6;
                    border-radius: 8px;
                    background-color: #ffffff;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 8px 10px;
                    border-radius: 6px;
                    margin: 2px 0;
                }
                QListWidget::item:selected {
                    background-color: #e8f0fe;
                    color: #1f2d3d;
                }
                """
            )

        if hasattr (self ,"dock")and self .dock and self .dock .widget ():
            self .dock .widget ().setStyleSheet (
            """
                QPushButton {
                    min-height: 34px;
                    border-radius: 8px;
                    padding: 6px 10px;
                    border: 1px solid #4b5563;
                    background-color: #2d3748;
                    color: #f8fafc;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #374151;
                }
                QLabel {
                    color: #e5e7eb;
                }
                """
            if self .dark_mode else 
            """
                QPushButton {
                    min-height: 34px;
                    border-radius: 8px;
                    padding: 6px 10px;
                    border: 1px solid #cbd5e1;
                    background-color: #f8fafc;
                    color: #1f2d3d;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #eef2f7;
                }
                QLabel {
                    color: #1f2d3d;
                }
                """
            )

        if hasattr (self ,"plan_source")and self .plan_source .lineEdit ():
            self .plan_source .lineEdit ().setPlaceholderText ("Введите или выберите источник")
        if hasattr (self ,"plan_medium")and self .plan_medium .lineEdit ():
            self .plan_medium .lineEdit ().setPlaceholderText ("Введите или выберите тип")

    def _build_project_payload (self ,project_name ):
        """Собирает единый payload проекта для обычного и автосохранения."""
        ads_data_dict =None 
        if hasattr (self ,'ads_data')and self .ads_data is not None :
            ads_data_dict =self .ads_data .replace ({np .nan :None }).to_dict ()

        crm_data_dict =None 
        if hasattr (self ,'crm_data')and self .crm_data is not None :
            crm_data_dict =self .crm_data .replace ({np .nan :None }).to_dict ()

        project_df =self .data .copy ()
        rebuilt_df =self ._build_merged_dataframe_from_sources ()
        if (
        rebuilt_df is not None 
        and not rebuilt_df .empty 
        and "Расход"in rebuilt_df .columns 
        ):
            current_expense =pd .to_numeric (project_df .get ("Расход"),errors ="coerce").fillna (0 ).sum ()if "Расход"in project_df .columns else 0 
            rebuilt_expense =pd .to_numeric (rebuilt_df .get ("Расход"),errors ="coerce").fillna (0 ).sum ()
            if project_df .empty or current_expense <=0 or abs (current_expense -rebuilt_expense )>1 :
                project_df =rebuilt_df .copy ()

        data_dict =project_df .replace ({np .nan :None })

        has_client_level_data =False 
        for client_data in self .clients .values ():
            client_df =client_data .get ("data",pd .DataFrame ())
            if client_df is not None and not client_df .empty :
                has_client_level_data =True 
                break 

        project_has_real_data =(
        not project_df .empty 
        or ads_data_dict is not None 
        or crm_data_dict is not None 
        or has_client_level_data 
        )

        dimension_data_dict ={}
        for dim_name ,df in self .dimension_data .items ():
            if df is not None and not df .empty :
                dimension_data_dict [dim_name ]=df .replace ({np .nan :None }).to_dict ()

        dimension_raw_data_dict ={}
        for dim_name ,df in self .dimension_raw_data .items ():
            if df is not None and not df .empty :
                dimension_raw_data_dict [dim_name ]=df .replace ({np .nan :None }).to_dict ()

        clients_payload ={}
        for client_name ,client_data in self .clients .items ():
            client_df =client_data .get ("data",pd .DataFrame ())
            if not project_has_real_data :
                client_df =pd .DataFrame ()
            clients_payload [client_name ]={
            "data":client_df .replace ({np .nan :None }).to_dict (),
            "plan_data":client_data ["plan_data"]
            }

        return {
        "name":project_name ,
        "data":data_dict .to_dict (),
        "ads_data":ads_data_dict ,
        "crm_data":crm_data_dict ,
        "ads_connections":self .ads_connections ,
        "crm_connections":self .crm_connections ,
        "last_ads_sync_at":self .last_ads_sync_at ,
        "last_crm_sync_at":self .last_crm_sync_at ,
        "last_project_refresh_at":self .last_project_refresh_at ,
        "ads_file_path":self .ads_file_path if ads_data_dict is not None else None ,
        "crm_file_path":self .crm_file_path if crm_data_dict is not None else None ,
        "dimension_data":dimension_data_dict ,
        "dimension_raw_data":dimension_raw_data_dict ,
        "plan_data":self .plan_data ,
        "clients":clients_payload ,
        "filter_states":{
        filter_name :{
        item :state .value 
        for item ,state in states .items ()
        }
        for filter_name ,states in self .filter_states .items ()
        },
        "current_client":self .current_client ,
        "current_project":project_name ,
        "date_range":{
        "from":self .date_from .date ().toPyDate ().isoformat (),
        "to":self .date_to .date ().toPyDate ().isoformat ()
        },
        "group_combo":self .group_combo .currentText (),
        "hide_plan":self .hide_plan_checkbox .isChecked (),
        "dark_mode":self .dark_mode 
        }

    def save_project (self ,project_name ):
        """Сохраняет текущий проект в JSON файл"""
        if not project_name :
            return 

            # Убеждаеся, что директория существует
        if not os .path .exists (self .projects_dir ):
            os .makedirs (self .projects_dir )
        self .project_backups_dir =os .path .join (self .projects_dir ,"_backups")
        if not os .path .exists (self .project_backups_dir ):
            os .makedirs (self .project_backups_dir )

        project_data =self ._build_project_payload (project_name )

        # Сохраняе в файл
        file_path =os .path .join (self .projects_dir ,f"{project_name }.json")
        try :
            if self ._should_block_empty_project_overwrite (file_path ,project_data ):
                self .log (f"Пустое сохранение проекта заблокировано: {project_name }")
                QMessageBox .warning (
                self ,
                "Защита проекта",
                f"Проект '{project_name }' уже содержит данные. Пустое состояние не будет сохранено поверх заполненного проекта."
                )
                return 
            self ._create_project_backup (file_path ,project_name ,reason ="manual")
            with open (file_path ,'w',encoding ='utf-8')as f :
                json .dump (project_data ,f ,ensure_ascii =False ,indent =2 ,default =str )
            self .current_project =project_name 
            self .current_project_path =file_path 

            self .update_project_list ()
            QMessageBox .information (self ,"Успех",f"Проект '{project_name }' сохранен!")
            self .log (f"Проект сохранен: {file_path }")
            self .log (f"  - Данные: {len (self .data )} строк")
            if project_data .get ("ads_data"):
                self .log (f"  - Рекламные данные: сохранены")
            if project_data .get ("crm_data"):
                self .log (f"  - CRM данные: сохранены")
        except Exception as e :
            QMessageBox .warning (self ,"Ошибка",f"Ошибка сохранения: {e }")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")

        self .save_projects_index ()

    def load_project (self ,file_path ):
        """Загружает проект из JSON файла"""
        try :
            with open (file_path ,'r',encoding ='utf-8')as f :
                project_data =json .load (f )

            self .log (f"Загрузка проекта: {file_path }")

            # Загружае основные данные
            self .data =pd .DataFrame (project_data ["data"])

            # ===== ПРИНУДИТЕЛЬНОЕ ПРЕОБРАЗОВАНИЕ ДАТ =====
            self .data =self ._convert_dates_to_datetime (self .data )

            self ._ensure_datetime ()

            # ===== ПРЕОБРАЗУЕМ ДАТУ В DATETIME =====
            if "Дата"in self .data .columns :
                self .data ["Дата"]=pd .to_datetime (self .data ["Дата"],errors ='coerce',dayfirst =True )
                self .data =self .data .dropna (subset =["Дата"])

                # Преобразуем все числовые колонки
            numeric_cols =["Расход","Показы","Клики","Лиды","Продажи","Ср.чек","Выручка","Маржа","CPC","CPL","CTR","CR1","CR2","ROMI"]
            for col in numeric_cols :
                if col in self .data .columns :
                    self .data [col ]=pd .to_numeric (self .data [col ],errors ='coerce').fillna (0 )

                    # Преобразуем дату
            if "Дата"in self .data .columns :
                self .data ["Дата"]=self ._parse_date_series (self .data ["Дата"])
                self .data =self .data .dropna (subset =["Дата"])

                # Загружаем рекламные данные
            if "ads_data"in project_data and project_data ["ads_data"]:
                self .ads_data =pd .DataFrame (project_data ["ads_data"])
                self .log (f"  - Загружены рекламные данные: {len (self .ads_data )} строк")
            else :
                self .ads_data =None 

                # Загружае CRM данные
            if "crm_data"in project_data and project_data ["crm_data"]:
                self .crm_data =pd .DataFrame (project_data ["crm_data"])
                self .log (f"  - Загружены CRM данные: {len (self .crm_data )} строк")
            else :
                self .crm_data =None 

            self .ads_connections =project_data .get ("ads_connections",{})or {}
            self .crm_connections =project_data .get ("crm_connections",{})or {}
            self .last_ads_sync_at =project_data .get ("last_ads_sync_at")
            self .last_crm_sync_at =project_data .get ("last_crm_sync_at")
            self .last_project_refresh_at =project_data .get ("last_project_refresh_at")
            if hasattr (self ,"refresh_connection_lists"):
                self .refresh_connection_lists ()

            project_is_empty_without_sources =self .data .empty and self .ads_data is None and self .crm_data is None 

            self .ads_file_path =project_data .get ("ads_file_path")if self .ads_data is not None else None 
            self .crm_file_path =project_data .get ("crm_file_path")if self .crm_data is not None else None 

            rebuilt_df =self ._build_merged_dataframe_from_sources ()
            loaded_expense =pd .to_numeric (self .data .get ("Расход"),errors ="coerce").fillna (0 ).sum ()if "Расход"in self .data .columns else 0 
            ads_expense =pd .to_numeric (self .ads_data .get ("Расход"),errors ="coerce").fillna (0 ).sum ()if self .ads_data is not None and "Расход"in self .ads_data .columns else 0 
            if (
            rebuilt_df is not None 
            and not rebuilt_df .empty 
            and (
            self .data is None 
            or self .data .empty 
            or "Расход"not in self .data .columns 
            or loaded_expense <=0 
            or (ads_expense >0 and abs (loaded_expense -ads_expense )>1 )
            )
            ):
                self .data =rebuilt_df 
                self .log (f"  - Основные данные восстановлены из реклаы + CRM: {len (self .data )} строк")

            has_legacy_client_data =False 
            self .current_client =project_data .get ("current_client","Клиент 1")

            # Загружае клиентомв
            self .clients ={}
            for client_name ,client_data in project_data .get ("clients",{}).items ():
                client_plan =client_data .get ("plan_data",{})
                from datetime import date 

                client_df =pd .DataFrame (client_data ["data"])
                if not client_df .empty :
                    has_legacy_client_data =True 
                for col in numeric_cols :
                    if col in client_df .columns :
                        client_df [col ]=pd .to_numeric (client_df [col ],errors ='coerce').fillna (0 )
                if "Дата"in client_df .columns :
                    client_df ["Дата"]=pd .to_datetime (client_df ["Дата"],errors ='coerce')

                self .clients [client_name ]={
                "data":client_df ,
                "plan_data":{
                "period_from":date .fromisoformat (client_plan ["period_from"])if client_plan .get ("period_from")else None ,
                "period_to":date .fromisoformat (client_plan ["period_to"])if client_plan .get ("period_to")else None ,
                "source":client_plan .get ("source","Все"),
                "medium":client_plan .get ("medium","Все"),
                "budget":client_plan .get ("budget",0 ),
                "leads":client_plan .get ("leads",0 ),
                "cpl":client_plan .get ("cpl",0 )
                }
                }

            if project_is_empty_without_sources and not has_legacy_client_data :
                self .log ("  - Проект пустой: клиентские данные и пути к файла очищены")
            elif self .data .empty and has_legacy_client_data and self .current_client in self .clients :
                self .data =self .clients [self .current_client ]["data"].copy ()
                self .original_data =self .data .copy ()
                self .log (f"  - Основные данные восстановлены из блока clients: {len (self .data )} строк")

                # Восстанавливае текущего клиента
            self .current_client =project_data .get ("current_client","Клиент 1")
            if self .current_client not in self .clients and self .clients :
                self .current_client =list (self .clients .keys ())[0 ]

                # Загружае план
            if self .current_client in self .clients :
                self .plan_data =self .clients [self .current_client ]["plan_data"].copy ()
            else :
                self .plan_data =project_data .get ("plan_data",{
                "period_from":None ,"period_to":None ,"source":"Все",
                "medium":"Все","budget":0 ,"leads":0 ,"cpl":0 
                })

                # Восстанавливае фильтры
            if "filter_states"in project_data :
                for filter_name ,states in project_data ["filter_states"].items ():
                    if filter_name in self .filter_states :
                        for item ,state_value in states .items ():
                            if item in self .filter_states [filter_name ]:
                                self .filter_states [filter_name ][item ]=Qt .CheckState (state_value )

                                # Восстанавливае период
            if "date_range"in project_data :
                from datetime import date 
                from_date =date .fromisoformat (project_data ["date_range"]["from"])
                to_date =date .fromisoformat (project_data ["date_range"]["to"])
                self .date_from .setDate (QDate (from_date .year ,from_date .month ,from_date .day ))
                self .date_to .setDate (QDate (to_date .year ,to_date .month ,to_date .day ))

                # Восстанавливае настройки
            if "group_combo"in project_data :
                self .group_combo .setCurrentText (project_data ["group_combo"])
            if "hide_plan"in project_data :
                self .hide_plan_checkbox .setChecked (project_data ["hide_plan"])
            if "dark_mode"in project_data :
                self .dark_mode =project_data ["dark_mode"]
                if self .dark_mode :
                    self .theme_btn .setText ("☀️ Светлая тема")
                else :
                    self .theme_btn .setText ("🌙 Темная тема")

                    # Обновляет интерфейс
            self .data =self .initialize_plan_columns (self .data )
            self .original_data =self .data .copy ()
            self .filtered_data =self .data .copy ()
            self .chart_data =self .data .copy ()

            # Обновляет комбобокс клиентомв
            self .client_combo .blockSignals (True )
            self .client_combo .clear ()
            if self .clients :
                self .client_combo .addItems (list (self .clients .keys ()))
                self .client_combo .setCurrentText (self .current_client )
            self .client_combo .blockSignals (False )

            # Обновляет план в интерфейсе
            self .update_plan_ui ()
            self .refresh_data_loader_labels ()

            # Устанавливае текущий проект
            self .current_project =project_data .get ("current_project",os .path .basename (file_path ).replace (".json",""))
            self .current_project_path =file_path 

            # Обновляет список проектов
            self .update_project_list ()

            # Обновляет фильтры на основе данных
            self .update_filters_from_data ()

            # ===== АВТОМАТЧЕСКАЯ ЗАГРУЗКА ПЛАНА ДЛЯ ТЕКУЩЕГО ПЕРОДА =====
            current_from =self .date_from .date ().toPyDate ()
            current_to =self .date_to .date ().toPyDate ()
            period_key =f"{current_from .isoformat ()}_{current_to .isoformat ()}"

            self .log (f"=== ЗАГРУЗКА ПЛАНА В load_project ===")
            self .log (f"Текущий клиент: {self .current_client }")
            self .log (f"Период: {current_from } - {current_to }")
            self .log (f"Доступные планы для клиента: {list (self .plans_history .get (self .current_client ,{}).keys ())}")

            if self .current_client in self .plans_history and period_key in self .plans_history [self .current_client ]:
                    plan =self .plans_history [self .current_client ][period_key ]
                    self .plan_data =plan .copy ()
                    self .current_plan =plan .copy ()
                    self .log (f"ЗАГРУЖЕН план (точное совпадение): {self .current_plan }")
            else :
            # ще план, покрывающий период
                found =False 
                for stored_key ,stored_plan in self .plans_history .get (self .current_client ,{}).items ():
                    stored_from =stored_plan ["period_from"]
                    stored_to =stored_plan ["period_to"]
                    if stored_from <=current_from and stored_to >=current_to :
                        self .plan_data =stored_plan .copy ()
                        self .current_plan =stored_plan .copy ()
                        self .log (f"ЗАГРУЖЕН план (покрывает период): {self .current_plan }")
                        found =True 
                        break 
                if not found :
                    self .current_plan =None 
                    self .log ("План НЕ НАЙДЕН")

                    # Обновляет интерфейс плана
            self .update_plan_ui ()

            # Приеняе фильтр (с проверкой наличия колонки Расход)
            if "Расход"in self .data .columns :
                try :
                    self .update_dashboard ()
                except Exception as e :
                    self .log (f"Ошибка при приенении фильтра: {e }")
                    self .update_table ()
            else :
                self .log ("Предупреждение: колонка 'Расход' отсутствует в данных")
                self .update_table ()

                # Обновляет вкладки с измерениями
            from_date =self .date_from .date ().toPyDate ()
            to_date =self .date_to .date ().toPyDate ()

            for dimension_name in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
                try :
                    if dimension_name in self .data .columns :
                        self .update_dimension_table_with_filter (dimension_name ,from_date ,to_date )
                    else :
                        empty_df =pd .DataFrame (columns =[dimension_name ])
                        self .dimension_data [dimension_name ]=empty_df 
                        self .display_dimension_table (dimension_name ,empty_df )
                except Exception as e :
                    self .log (f"Ошибка при обновлении {dimension_name }: {e }")
                    empty_df =pd .DataFrame (columns =[dimension_name ])
                    self .dimension_data [dimension_name ]=empty_df 
                    self .display_dimension_table (dimension_name ,empty_df )

            self .update_plan_display ()

            self .sync_all_table_columns_width ()

            # Приеняе теу
            if self .dark_mode :
                self .toggle_theme ()

                # Показывае сообщение об успешной загрузке с проверкой наличия колонок
            msg =f"Проект '{self .current_project }' загружен!\n\nВсего строк: {len (self .data )}"
            if "Расход"in self .data .columns :
                msg +=f"\nРасход: {self .data ['Расход'].sum ():,.0f} руб"
            if "Лиды"in self .data .columns :
                msg +=f"\nЛиды: {self .data ['Лиды'].sum ():,.0f}"
            if "Продажи"in self .data .columns :
                msg +=f"\nПродажи: {self .data ['Продажи'].sum ():,.0f}"

            self .log ("=== ПРОЕКТ ВОССТАНОВЛЕН ===")
            self .log (f"Проект: {self .current_project }")
            self .log (f"Строк в основных данных: {len (self .data )}")
            if hasattr (self ,"filtered_data")and self .filtered_data is not None and not self .filtered_data .empty :
                self .log (f"Строк в текуще периоде: {len (self .filtered_data )}")
            if "Расход"in self .data .columns :
                self .log (f"тоговый расход проекта: {self .data ['Расход'].sum ():,.0f} руб")
            if hasattr (self ,"filtered_data")and self .filtered_data is not None and not self .filtered_data .empty and "Расход"in self .filtered_data .columns :
                self .log (f"Расход в текуще периоде: {self .filtered_data ['Расход'].sum ():,.0f} руб")
            if "Лиды"in self .data .columns :
                self .log (f"тоговые лиды проекта: {self .data ['Лиды'].sum ():,.0f}")
            if "Продажи"in self .data .columns :
                self .log (f"тоговые продажи проекта: {self .data ['Продажи'].sum ():,.0f}")
            self .log (f"Текущий период после загрузки: {self .date_from .date ().toString ('dd.MM.yyyy')} - {self .date_to .date ().toString ('dd.MM.yyyy')}")
            self .log ("=== КОНЕЦ ВОССТАНОВЛЕНЯ ПРОЕКТА ===")
            QTimer .singleShot (0 ,self ._refresh_all_table_headers_geometry )
            QTimer .singleShot (50 ,self ._refresh_all_table_headers_geometry )

            QMessageBox .information (self ,"Успех",msg )

        except Exception as e :
            self .log (f"Ошибка загрузки: {e }")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")
            QMessageBox .warning (self ,"Ошибка",f"Ошибка загрузки проекта: {e }")

    def update_project_list (self ):
        """Обновляетт список проектов в боковой панели"""
        if not hasattr (self ,'project_list')or self .project_list is None :
            return 
        self .project_list .clear ()
        active_row =-1 
        selected_row =-1 
        if os .path .exists (self .projects_dir ):
            for file in os .listdir (self .projects_dir ):
                if file .endswith (".json")and file not in ["projects_index.json","plans_history.json"]:
                    project_name =file .replace (".json","")
                    if self .current_project and project_name ==self .current_project :
                        self .project_list .addItem (f"⭐ {project_name } (активный)")
                        active_row =self .project_list .count ()-1 
                    else :
                        self .project_list .addItem (project_name )
                    if self .selected_project_name and project_name ==self .selected_project_name :
                        selected_row =self .project_list .count ()-1 
        if active_row >=0 :
            self .project_list .setCurrentRow (active_row )
        elif selected_row >=0 :
            self .project_list .setCurrentRow (selected_row )
        if hasattr (self ,'active_project_label'):
            pass 
        self .update_project_status_labels ()


    def save_projects_index (self ):
        """Сохраняет список всех проектов"""
        projects =[]
        if os .path .exists (self .projects_dir ):
            for file in os .listdir (self .projects_dir ):
                if file .endswith (".json")and file not in ["projects_index.json","plans_history.json"]:
                    projects .append (file .replace (".json",""))

        with open (self .projects_index_file ,'w',encoding ='utf-8')as f :
            json .dump (projects ,f ,ensure_ascii =False ,indent =2 )

    def load_projects_index (self ):
        """Загружает список проектов"""
        if os .path .exists (self .projects_index_file ):
            try :
                with open (self .projects_index_file ,'r',encoding ='utf-8')as f :
                    projects =json .load (f )
                    # Обновляет список в боковой панели
                self .update_project_list ()
            except :
                pass 

    def new_project (self ,default_name =None ):
        """Создание нового проекта"""
        # Сохраняе текущий проект
        if self .current_project and self .current_project_path :
            self .auto_save_project ()

        if default_name :
            project_name =default_name 
        else :
            project_name ,ok =QInputDialog .getText (self ,"Новый проект","Введите название проекта:")
            if not ok or not project_name :
                return 

        self .data =pd .DataFrame ()
        self .original_data =pd .DataFrame ()
        self .filtered_data =pd .DataFrame ()
        self .chart_data =pd .DataFrame ()
        self .filtered_source_data =pd .DataFrame ()

        # Создает клиента
        self .clients ={
        "Клиент 1":{
        "data":pd .DataFrame (),
        "plan_data":{"period_from":None ,"period_to":None ,"source":"Все","medium":"Все","budget":0 ,"leads":0 ,"cpl":0 }
        }
        }
        self .current_client ="Клиент 1"

        # Сбрасывае план
        self .plan_data ={
        "period_from":None ,
        "period_to":None ,
        "source":"Все",
        "medium":"Все",
        "budget":0 ,
        "leads":0 ,
        "cpl":0 
        }

        # Сбрасывае загруженные данные
        self .ads_data =None 
        self .crm_data =None 
        self .ads_file_path =None 
        self .crm_file_path =None 
        self .ads_connections ={}
        self .crm_connections ={}
        self .last_ads_sync_at =None 
        self .last_crm_sync_at =None 
        self .last_project_refresh_at =None 
        if hasattr (self ,"refresh_connection_lists"):
            self .refresh_connection_lists ()
        self .refresh_data_loader_labels ()

        # Обновляет интерфейс
        self .client_combo .clear ()
        self .client_combo .addItems (list (self .clients .keys ()))
        self .client_combo .setCurrentText (self .current_client )

        # Сбрасывае группировку и фильтры
        if hasattr (self ,'group_combo'):
            self .group_combo .setCurrentText ("день")
        if hasattr (self ,'hide_plan_checkbox'):
            self .hide_plan_checkbox .setChecked (False )

            # Очищае фильтры без део-данных
        self ._clear_filter_widgets_state ()

        # Сохраняе проект в файл
        self .current_project =project_name 
        self .current_project_path =os .path .join (self .projects_dir ,f"{project_name }.json")

        # Сохраняе проект
        self .save_project (project_name )

        # Обновляет список проектов (покажет активный)
        self .update_project_list ()

        self .display_empty_table ()
        self ._clear_dimension_tabs ()
        self .update_chart ()
        self .update_plan_display ()
        QTimer .singleShot (0 ,self ._refresh_all_table_headers_geometry )

        QMessageBox .information (self ,"Успех",f"Создан проект '{project_name }'")

    def open_project (self ):
        """Открытие существующего проекта"""
        # Сохраняе текущий проект перед открытие нового
        if self .current_project and self .current_project_path :
            self .auto_save_project ()

        file_path ,_ =QFileDialog .getOpenFileName (
        self ,"Открыть проект",self .projects_dir ,"Project files (*.json)"
        )
        if file_path :
            self .load_project (file_path )

    def save_current_project (self ):
        """Сохранить текущий проект"""
        if self .current_project :
            self .save_project (self .current_project )
        else :
            project_name ,ok =QInputDialog .getText (self ,"Сохранить проект","Введите название проекта:")
            if ok and project_name :
                self .save_project (project_name )

    def delete_project (self ):
        """Удаляетт текущий проект"""
        target_project =self .current_project 
        target_project_path =self .current_project_path 

        selected_item =self .project_list .currentItem ()if hasattr (self ,'project_list')else None 
        if selected_item :
            selected_project =self ._clean_project_list_name (selected_item .text ())
            selected_path =os .path .join (self .projects_dir ,f"{selected_project }.json")
            if os .path .exists (selected_path ):
                target_project =selected_project 
                target_project_path =selected_path 

        if not target_project :
            QMessageBox .warning (self ,"Ошибка","Нет открытого проекта для удаления")
            return 

            # Подтверждение удаления
        reply =QMessageBox .question (
        self ,"Подтверждение удаления",
        f"Вы уверены, что хотите удалить проект '{target_project }'?\nЭто действие нельзя отменить.",
        QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No 
        )

        if reply ==QMessageBox .StandardButton .Yes :
            try :
            # Удаляет файл проекта
                if os .path .exists (target_project_path ):
                    os .remove (target_project_path )

                    # Удаляет из индекса
                self .save_projects_index ()

                # Сбрасывае текущий проект
                if self .current_project ==target_project :
                    self ._set_empty_project_view ()
                if self .selected_project_name ==target_project :
                    self .selected_project_name =None 

                    # Обновляет список проектов
                self .update_project_list ()
                if not self .current_project :
                    self ._set_empty_project_view ()

                QMessageBox .information (self ,"Успех","Проект удален")

            except Exception as e :
                QMessageBox .warning (self ,"Ошибка",f"Ошибка удаления проекта: {e }")

    def auto_save_project (self ):
        """Автоатическое сохранение текущего проекта"""
        if self .current_project and self .current_project_path :
            try :
                self .log (f"Автосохранение проекта: {self .current_project }")
                project_data =self ._build_project_payload (self .current_project )
                if self ._should_block_empty_project_overwrite (self .current_project_path ,project_data ):
                    self .log (f"Пустое автосохранение проекта заблокировано: {self .current_project }")
                    return 
                self ._create_project_backup (self .current_project_path ,self .current_project ,reason ="auto")

                with open (self .current_project_path ,'w',encoding ='utf-8')as f :
                    json .dump (project_data ,f ,ensure_ascii =False ,indent =2 ,default =str )

                self .save_projects_index ()
                self .log ("Проект автосохранен")
            except Exception as e :
                self .log (f"Ошибка автосохранения: {e }")

    def update_plan_ui (self ):
        """Обновляетт интерфейс вкладки План"""
        self .refresh_plan_dimension_options ()
        if hasattr (self ,'plan_date_from')and self .plan_data ["period_from"]:
            self .plan_date_from .setDate (QDate (
            self .plan_data ["period_from"].year ,
            self .plan_data ["period_from"].month ,
            self .plan_data ["period_from"].day 
            ))
        if hasattr (self ,'plan_date_to')and self .plan_data ["period_to"]:
            self .plan_date_to .setDate (QDate (
            self .plan_data ["period_to"].year ,
            self .plan_data ["period_to"].month ,
            self .plan_data ["period_to"].day 
            ))
        if hasattr (self ,'plan_source'):
            self .plan_source .setCurrentText (self .plan_data ["source"])
        if hasattr (self ,'plan_medium'):
            self .plan_medium .setCurrentText (self .plan_data ["medium"])
        if hasattr (self ,'plan_budget'):
            self .plan_budget .setText (f"{self .plan_data ['budget']:,.0f}".replace (","," ")if self .plan_data ["budget"]>0 else "")
        if hasattr (self ,'plan_leads'):
            self .plan_leads .setText (f"{self .plan_data ['leads']:,.0f}".replace (","," ")if self .plan_data ["leads"]>0 else "")
        if hasattr (self ,'plan_cpl'):
            self .plan_cpl .setText (f"{self .plan_data ['cpl']:,.0f}".replace (","," ")if self .plan_data ["cpl"]>0 else "0")

    def update_filters_from_data (self ):
        """Обновляетт значения фильтров на основе данных в self.data"""
        self .log ("\n=== ОНОВЛЕНЕ ФИЛЬТРОВ З ДАННЫХ ===")

        if self .data .empty :
            self .log ("Нет данных для обновления фильтров (self.data пуст)")
            return 

        self .log (f"Всего строк в данных: {len (self .data )}")
        self .log (f"Колонки в данных: {self .data .columns .tolist ()}")

        # Маппинг ежду названияи фильтров и колонкаи в данных
        filter_column_mapping ={
        "Source":"Источник",
        "Medium":"Medium",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза"
        }

        # Маппинг для отображения на кнопках
        button_labels ={
        "Source":"Источник",
        "Medium":"Тип",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза",
        "Region":"Регион",
        "Device":"Устройство",
        "Placement":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Product":"Продукт"
        }

        # Для каждого фильтра получае уникальные значения из данных
        for filter_key ,column_name in filter_column_mapping .items ():
            if filter_key not in self .filters_widgets :
                self .log (f"  Фильтр {filter_key } не найден в filters_widgets")
                continue 

            display_name =button_labels .get (filter_key ,filter_key )

            real_column_name =column_name 
            if filter_key =="Medium"and real_column_name not in self .data .columns and "Тип"in self .data .columns :
                real_column_name ="Тип"

            if real_column_name in self .data .columns :
            # Получаем уникальные значения напряую из данных
                series =self .data [real_column_name ].copy ()
                series =series .fillna ("Не указано").astype (str )
                series =series .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
                unique_values =series .unique ().tolist ()
                unique_values =sorted (unique_values )

                self .log (f"  {filter_key } ({real_column_name }): {unique_values [:10 ]}... (всего {len (unique_values )})")

                # Обновляет список элементов в фильтре
                self .filters_widgets [filter_key ]['items']=unique_values 

                # Обновляет список в popup
                list_widget =self .filters_widgets [filter_key ]['list']
                list_widget .blockSignals (True )
                list_widget .clear ()

                # Добавляе новые элементы
                for value in unique_values :
                    item =QListWidgetItem (value )
                    item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                    item .setCheckState (Qt .CheckState .Checked )
                    list_widget .addItem (item )

                list_widget .blockSignals (False )

                # Обновляет filter_states (полностью перезаписывае!)
                self .filter_states [filter_key ]={}
                for value in unique_values :
                    self .filter_states [filter_key ][value ]=Qt .CheckState .Checked 

                    # Обновляет текст на кнопке
                button =self .filters_widgets [filter_key ]['button']
                button .setText (display_name )

            else :
                self .log (f"  Колонка {column_name } не найдена в данных для фильтра {filter_key }")
                list_widget =self .filters_widgets [filter_key ]['list']
                list_widget .blockSignals (True )
                list_widget .clear ()
                fallback_items =["Не указано"]if filter_key =="Medium"else []
                for value in fallback_items :
                    item =QListWidgetItem (value )
                    item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                    item .setCheckState (Qt .CheckState .Checked )
                    list_widget .addItem (item )
                list_widget .blockSignals (False )
                self .filters_widgets [filter_key ]['items']=fallback_items 
                self .filter_states [filter_key ]={value :Qt .CheckState .Checked for value in fallback_items }
                button =self .filters_widgets [filter_key ]['button']
                button .setText (display_name )

        self .refresh_plan_dimension_options ()
        self .log ("=== ОНОВЛЕНЕ ФИЛЬТРОВ ЗАВЕРШЕНО ===\n")

    def reset_filters_to_default (self ):
        """Сбрасывает фильтры к значения по уолчанию (део-данные)"""
        self .log ("\n=== СРОС ФИЛЬТРОВ К ЗНАЧЕНЯМ ПО УМОЛЧАНЮ ===")

        filters_items ={
        "Source":["Яндекс","Google","VK","Telegram","YouTube"],
        "Medium":["Не указано","cpc","cpm","cpa","organic","social"],
        "Campaign":["Бренд","Товарная","Ретаргетинг","Поиск","КМС"],
        "Gbid":["Группа 1","Группа 2","Группа 3","Группа 4","Группа 5"],
        "Content":["Объявление 1","Объявление 2","Объявление 3","Объявление 4","Объявление 5"],
        "Term":["фраза 1","фраза 2","фраза 3","фраза 4","фраза 5"]
        }

        for filter_key in self .filters_widgets :
            if filter_key in filters_items :
                self .filters_widgets [filter_key ]['items']=filters_items [filter_key ]

                # Обновляет список в popup
                list_widget =self .filters_widgets [filter_key ]['list']
                list_widget .blockSignals (True )
                list_widget .clear ()

                for value in filters_items [filter_key ]:
                    item =QListWidgetItem (value )
                    item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                    item .setCheckState (Qt .CheckState .Checked )
                    list_widget .addItem (item )

                list_widget .blockSignals (False )

                # Обновляет filter_states
                self .filter_states [filter_key ]={}
                for value in filters_items [filter_key ]:
                    self .filter_states [filter_key ][value ]=Qt .CheckState .Checked 

        self .log ("=== СРОС ФИЛЬТРОВ ЗАВЕРШЕН ===\n")
        self .refresh_plan_dimension_options ()

    def get_filtered_values (self ,filter_name ,selected_filters ):
        """Получаем значения для фильтра с учетом выбранных значений в других фильтрах"""

        if self .data .empty :
            return []

            # Маппинг иерархии (какой фильтр зависит от какого)
        hierarchy ={
        "Источник":[],# не зависит от других
        "Кампания":["Источник"],
        "Группа":["Источник","Кампания"],
        "Объявление":["Источник","Кампания","Группа"],
        "Ключевая фраза":["Источник","Кампания","Группа","Объявление"]
        }

        # Маппинг названий фильтров к колонка в данных
        filter_to_column ={
        "Источник":"Источник",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза"
        }

        # Получаем колонку для текущего фильтра
        column_name =filter_to_column .get (filter_name )
        if not column_name or column_name not in self .data .columns :
            self .log (f"  Колонка {column_name } не найдена в данных")
            return []

            # Строи условие фильтрации на основе выбранных значений в зависиых фильтрах
        filter_condition =pd .Series ([True ]*len (self .data ))

        for dependent_filter in hierarchy .get (filter_name ,[]):
            if dependent_filter in selected_filters and selected_filters [dependent_filter ]:
                dep_column =filter_to_column .get (dependent_filter )
                if dep_column and dep_column in self .data .columns :
                # Фильтруе по выбранны значения
                    condition =self .data [dep_column ].isin (selected_filters [dependent_filter ])
                    filter_condition =filter_condition &condition 

                    # Приеняе фильтр и получае уникальные значения
        filtered_data =self .data [filter_condition ]

        if filtered_data .empty :
            return []

        unique_values =filtered_data [column_name ].unique ().tolist ()

        # Очищае от None и пустых строк
        unique_values =[str (v )for v in unique_values if v and str (v )!='nan'and str (v )!='None'and str (v )!='']

        return sorted (unique_values )

    def refresh_all_filters (self ):
        """Обновляетт все фильтры и применяет их"""
        self .update_filters_from_data ()
        self .apply_all_filters ()

    def export_logs (self ):
        """Экспортирует текущий лог в выбранное место"""
        # Сохраняе текущий лог
        self .logger .info ("Пользователь запросил экспорт логов")

        # Открывае диалог выбора файла
        file_path ,_ =QFileDialog .getSaveFileName (
        self ,"Сохранить лог",
        os .path .expanduser (f"~/analytics_log_{datetime .now ().strftime ('%Y%m%d_%H%M%S')}.txt"),
        "Text files (*.txt);;All files (*.*)"
        )

        if file_path :
            try :
            # Копируе текущий лог-файл
                import shutil 
                shutil .copy2 (self .log_file_path ,file_path )
                QMessageBox .information (self ,"Успех",f"Лог сохранен в:\n{file_path }")
                self .logger .info (f"Лог экспортирован в {file_path }")
            except Exception as e :
                QMessageBox .warning (self ,"Ошибка",f"Не удалось сохранить лог: {e }")
                self .logger .error (f"Ошибка экспорта лога: {e }")

    def _get_current_report_table_for_export (self ):
        """Возвращает текущую видимую таблицу для экспорта."""
        if not hasattr (self ,"tabs"):
            return None ,"report"

        current_tab_text =self .tabs .tabText (self .tabs .currentIndex ())
        safe_tab_text =self ._sanitize_export_name (current_tab_text )

        if current_tab_text in getattr (self ,"dimension_tables",{}):
            return self .dimension_tables [current_tab_text ],safe_tab_text 

        if hasattr (self ,"table")and self .table is not None :
            return self .table ,safe_tab_text or "date_report"

        return None ,safe_tab_text or "report"

    def _table_widget_to_dataframe (self ,table ):
        """Преобразуем текущую QTableWidget в DataFrame."""
        if table is None or table .columnCount ()==0 :
            return pd .DataFrame ()

        visible_columns =[col for col in range (table .columnCount ())if not table .isColumnHidden (col )]
        headers =[]
        for col in visible_columns :
            header_item =table .horizontalHeaderItem (col )
            header_text =header_item .text ()if header_item else f"Column {col +1 }"
            header_text =header_text .replace (" в–І","").replace (" в–","")
            headers .append (header_text )

        rows =[]
        for row in range (table .rowCount ()):
            row_data =[]
            has_any_value =False 
            for col in visible_columns :
                item =table .item (row ,col )
                text =item .text ()if item is not None else ""
                if text not in ["",None ]:
                    has_any_value =True 
                row_data .append (text )
            if has_any_value :
                rows .append (row_data )

        return pd .DataFrame (rows ,columns =headers )

    def _get_current_report_table_for_export (self ):
        """Возвращает текущую видимую таблицу для экспорта."""
        if not hasattr (self ,"tabs")or self .tabs is None :
            return None ,"report"

        current_tab_text =self .tabs .tabText (self .tabs .currentIndex ())
        safe_tab_text =self ._sanitize_export_name (current_tab_text )

        if hasattr (self ,"dimension_tables")and current_tab_text in self .dimension_tables :
            return self .dimension_tables [current_tab_text ],safe_tab_text or "report"

        if hasattr (self ,"table")and self .table is not None :
            return self .table ,safe_tab_text or "date_report"

        return None ,safe_tab_text or "report"

    def _table_widget_to_dataframe (self ,table ):
        """Преобразуем текущую таблицу в DataFrame с учетом видимых колонок."""
        if table is None or table .columnCount ()==0 :
            return pd .DataFrame ()

        visible_columns =[col for col in range (table .columnCount ())if not table .isColumnHidden (col )]
        headers =[]
        for col in visible_columns :
            header_item =table .horizontalHeaderItem (col )
            header_text =header_item .text ()if header_item else f"Column {col +1 }"
            header_text =(
            header_text 
            .replace (" ▲","")
            .replace (" ","")
            .replace (" в–І","")
            .replace (" в–","")
            )
            headers .append (header_text )

        rows =[]
        for row in range (table .rowCount ()):
            row_data =[]
            has_any_value =False 
            for col in visible_columns :
                item =table .item (row ,col )
                text =item .text ()if item is not None else ""
                if text not in ["",None ]:
                    has_any_value =True 
                row_data .append (text )
            if has_any_value :
                rows .append (row_data )

        return pd .DataFrame (rows ,columns =headers )

    def _sanitize_export_name (self ,value ):
        """РћС‡Рщает РРСЏ Рля РспользованРСЏ РІ РРенРфайла."""
        if not value :
            return "report"
        safe =str (value ).strip ()
        for bad in ['<','>',':','"','/','\\','|','?','*']:
            safe =safe .replace (bad ,"_")
        safe =safe .replace (" ","_")
        return safe or "report"

    def _build_export_default_path (self ,extension ):
        """Формирует дефолтное имя файла для экспорта."""
        project_name =self ._sanitize_export_name (self .current_project or "project")
        _ ,tab_name =self ._get_current_report_table_for_export ()
        timestamp =datetime .now ().strftime ("%Y%m%d_%H%M")
        file_name =f"{project_name }_{tab_name }_{timestamp }.{extension }"
        return os .path .join (os .path .expanduser ("~"),file_name )

    def export_current_report_excel (self ):
        """Экспортирует текущий отчет в Excel."""
        table ,_ =self ._get_current_report_table_for_export ()
        export_df =self ._table_widget_to_dataframe (table )

        if export_df .empty :
            QMessageBox .information (self ,"Экспорт","Нет данных для экспорта.")
            return 

        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "Экспорт отчета в Excel",
        self ._build_export_default_path ("xlsx"),
        "Excel Files (*.xlsx)"
        )
        if not file_path :
            return 

        try :
            export_df .to_excel (file_path ,index =False )
            self .log (f"РћС‚С‡РµС‚ СЌРєСЃРїРѕСЂС‚РСЂРѕРІР°РЅ РІ Excel: {file_path }")
            QMessageBox .information (self ,"Успех",f"РћС‚С‡РµС‚ РІС‹РіСЂСѓР¶РµРЅ РІ Excel:\n{file_path }")
        except Exception as e :
            self .log (f"РћС€РР±РєР° СЌРєСЃРїРѕСЂС‚Р° РѕС‚С‡РµС‚Р° РІ Excel: {e }")
            QMessageBox .warning (self ,"РћС€РР±РєР°",f"РќРµ СѓРР°Р»РѕСЃСЊ РІС‹РіСЂСѓР·РС‚СЊ РѕС‚С‡РµС‚ РІ Excel:\n{e }")

    def export_current_report_csv (self ):
        """Экспортирует текущий отчет в CSV."""
        table ,_ =self ._get_current_report_table_for_export ()
        export_df =self ._table_widget_to_dataframe (table )

        if export_df .empty :
            QMessageBox .information (self ,"Экспорт","Нет данных для экспорта.")
            return 

        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "Экспорт отчета в CSV",
        self ._build_export_default_path ("csv"),
        "CSV Files (*.csv)"
        )
        if not file_path :
            return 

        try :
            export_df .to_csv (file_path ,index =False ,encoding ="utf-8-sig",sep =";")
            self .log (f"Отчет экспортирован в CSV: {file_path }")
            QMessageBox .information (self ,"Успех",f"Отчет выгружен в CSV:\n{file_path }")
        except Exception as e :
            self .log (f"Ошибка экспорта отчета в CSV: {e }")
            QMessageBox .warning (self ,"Ошибка",f"Не удалось выгрузить отчет в CSV:\n{e }")

    def open_logs_folder (self ):
        """Открывает папку с логами"""
        log_dir =os .path .join (os .path .expanduser ("~"),"AnalyticsLogs")
        if os .path .exists (log_dir ):
        # Открывае папку в проводнике
            os .startfile (log_dir )
            self .logger .info (f"Открыта папка с логами: {log_dir }")
        else :
            QMessageBox .warning (self ,"Ошибка","Папка с логами не найдена")

    def closeEvent (self ,event ):
        """Событие закрытия окна"""
        # Сохраняе текущий проект
        if self .current_project and self .current_project_path :
            self .save_project (self .current_project )
        event .accept ()

    def setup_table_tab (self ):
            """Настройка вкладки с основной таблицей"""
            layout =QVBoxLayout (self .table_tab )

            # Панель управления над таблицей
            controls_layout =QHBoxLayout ()

            controls_layout .addWidget (QLabel ("Группировка:"))
            self .group_combo =QComboBox ()
            self .group_combo .addItems (["день","неделя","месяц","квартал","год"])
            self .group_combo .currentTextChanged .connect (self .change_grouping )
            controls_layout .addWidget (self .group_combo )

            # Тот саый чекбокс, который вызывал ошибку
            self .hide_plan_checkbox =QCheckBox ("Скрыть плановые показатели")
            self .hide_plan_checkbox .stateChanged .connect (self .on_hide_plan_changed )
            controls_layout .addWidget (self .hide_plan_checkbox )

            controls_layout .addStretch ()
            layout .addLayout (controls_layout )

            # Создание таблицы
            self .table =QTableWidget ()
            layout .addWidget (self .table )
            self .table .setSortingEnabled (False )
            self .table .horizontalHeader ().sectionClicked .connect (self .custom_sort )


            # Настройка стиля заголовков
            self .setup_table_header_style ()

    def on_hide_plan_changed (self ,state ):
            """Перестраивает таблицу при скрытии или показе плановых колонок."""
            if not hasattr (self ,'table'):
                return 

            is_hidden =state ==2 or state ==Qt .CheckState .Checked 
            status ="скрыты"if is_hidden else "отображены"
            self .log (f"Плановые показатели {status }")

            self .update_table ()

            if hasattr (self ,"current_sort_col")and self .current_sort_col >=0 :
                self .update_sort_indicators ()

    def setup_dimension_tab (self ,tab ,dimension_name ):
        """Настраивает вкладку с измерениями"""
        layout =QVBoxLayout ()
        tab .setLayout (layout )

        # Таблица
        table =QTableWidget ()
        self ._apply_header_style_to_table (table )

        table .horizontalHeader ().sectionClicked .connect (lambda col ,name =dimension_name :self .on_dimension_header_clicked (name ,col ))
        layout .addWidget (table )

        self .dimension_tables [dimension_name ]=table 
        self .dimension_data [dimension_name ]=None 
        self .dimension_sort_column [dimension_name ]=None 
        self .dimension_sort_ascending [dimension_name ]=True 

        # нициализируе dimension_raw_data
        if not hasattr (self ,'dimension_raw_data'):
            self .dimension_raw_data ={}
        self .dimension_raw_data [dimension_name ]=None 

        # Мметрики для отображения внизу
        metrics_layout =QHBoxLayout ()
        expense_label =QLabel ()
        clicks_label =QLabel ()
        sales_label =QLabel ()
        romi_label =QLabel ()

        metrics_layout .addWidget (expense_label )
        metrics_layout .addWidget (clicks_label )
        metrics_layout .addWidget (sales_label )
        metrics_layout .addWidget (romi_label )
        metrics_layout .addStretch ()

        layout .addLayout (metrics_layout )

        self .dimension_metrics [dimension_name ]={
        'expense':expense_label ,
        'clicks':clicks_label ,
        'sales':sales_label ,
        'romi':romi_label 
        }

        # Показывае пустую таблицу
        empty_df =pd .DataFrame (columns =[dimension_name ])
        self .display_dimension_table (dimension_name ,empty_df )

    def setup_chart_tab (self ):
        layout =QVBoxLayout ()
        self .chart_tab .setLayout (layout )

        # Панель управления
        controls_layout =QHBoxLayout ()
        controls_layout .addWidget (QLabel ("Показатель:"))

        self .metric_combo =QComboBox ()
        self .metric_combo .addItems ([
        "Расход","Показы","Клики","CPC","CTR",
        "Лиды","CPL","CR1","Продажи","CR2",
        "Ср.чек","Выручка","Маржа","ROMI"
        ])
        self .metric_combo .currentTextChanged .connect (lambda x :self .update_chart ())
        controls_layout .addWidget (self .metric_combo )

        controls_layout .addSpacing (20 )
        controls_layout .addWidget (QLabel ("Группировка:"))

        self .chart_group_combo =QComboBox ()
        self .chart_group_combo .addItems (["день","неделя","месяц","квартал","год"])
        self .chart_group_combo .currentTextChanged .connect (lambda x :self .update_chart ())
        controls_layout .addWidget (self .chart_group_combo )
        controls_layout .addStretch ()

        layout .addLayout (controls_layout )

        self .figure =plt .Figure (figsize =(8 ,4 ))
        self .canvas =FigureCanvas (self .figure )
        layout .addWidget (self .canvas )

        self .update_chart ()

    def setup_plan_tab (self ):
        layout =QVBoxLayout ()
        layout .setSpacing (8 )
        self .plan_tab .setLayout (layout )

        title_host =QWidget ()
        title_host_layout =QHBoxLayout (title_host )
        title_host_layout .setContentsMargins (48 ,0 ,0 ,0 )
        title_host_layout .setSpacing (0 )
        self .plan_screen_title =QLabel ("Планирование")
        self .plan_screen_title .setObjectName ("planScreenTitle")
        title_host_layout .addWidget (self .plan_screen_title )
        title_host_layout .addStretch ()
        layout .addWidget (title_host )

        plan_display_group =QGroupBox ("Текущий план")
        plan_display_group .setObjectName ("planSummaryGroup")
        plan_display_layout =QHBoxLayout ()
        plan_display_layout .setContentsMargins (16 ,12 ,16 ,14 )
        plan_display_layout .setSpacing (12 )

        self .plan_budget_label =QLabel ("юджет: —")
        self .plan_budget_label .setObjectName ("planSummaryValue")
        self .plan_leads_label =QLabel ("Лиды: —")
        self .plan_leads_label .setObjectName ("planSummaryValue")

        plan_display_layout .addWidget (self .plan_budget_label )
        plan_display_layout .addWidget (self .plan_leads_label )
        plan_display_layout .addStretch ()

        plan_display_group .setLayout (plan_display_layout )
        plan_summary_host =QWidget ()
        plan_summary_host_layout =QHBoxLayout (plan_summary_host )
        plan_summary_host_layout .setContentsMargins (48 ,0 ,0 ,0 )
        plan_summary_host_layout .setSpacing (0 )
        plan_display_group .setFixedWidth (760 )
        plan_summary_host_layout .addWidget (plan_display_group )
        plan_summary_host_layout .addStretch ()
        layout .addWidget (plan_summary_host )
        layout .addSpacing (4 )

        card_host =QWidget ()
        card_host_layout =QHBoxLayout (card_host )
        card_host_layout .setContentsMargins (48 ,0 ,0 ,0 )
        card_host_layout .setSpacing (0 )

        self .plan_form_card =QFrame ()
        self .plan_form_card .setObjectName ("planFormCard")
        self .plan_form_card .setFixedWidth (760 )
        self .plan_form_card .setFrameShape (QFrame .Shape .StyledPanel )

        card_layout =QVBoxLayout (self .plan_form_card )
        card_layout .setContentsMargins (28 ,26 ,28 ,24 )
        card_layout .setSpacing (18 )

        self .plan_form_title =QLabel ("Фора планирования")
        self .plan_form_title .setObjectName ("planFormTitle")
        card_layout .addWidget (self .plan_form_title )

        self .plan_form_divider =QFrame ()
        self .plan_form_divider .setObjectName ("planFormDivider")
        self .plan_form_divider .setFrameShape (QFrame .Shape .HLine )
        self .plan_form_divider .setFixedHeight (1 )
        card_layout .addWidget (self .plan_form_divider )

        form_grid =QGridLayout ()
        form_grid .setHorizontalSpacing (18 )
        form_grid .setVerticalSpacing (14 )
        form_grid .setColumnMinimumWidth (0 ,120 )
        form_grid .setColumnMinimumWidth (1 ,560 )

        date_from_width =235 
        date_to_width =255 

        period_label =QLabel ("Период:")
        period_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (period_label ,0 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )

        period_widget =QWidget ()
        period_layout =QHBoxLayout (period_widget )
        period_layout .setContentsMargins (0 ,0 ,0 ,0 )
        period_layout .setSpacing (10 )
        period_widget .setFixedWidth (560 )

        period_from_label =QLabel ("с")
        period_from_label .setObjectName ("planMutedLabel")
        period_to_label =QLabel ("по")
        period_to_label .setObjectName ("planMutedLabel")
        self .plan_date_from =QDateEdit ()
        self .plan_date_from .setDate (QDate (2026 ,3 ,1 ))
        self .plan_date_from .setCalendarPopup (True )
        self .plan_date_from .setFixedWidth (date_from_width )
        self .plan_date_to =QDateEdit ()
        self .plan_date_to .setDate (QDate (2026 ,3 ,31 ))
        self .plan_date_to .setCalendarPopup (True )
        self .plan_date_to .setFixedWidth (date_to_width )
        period_layout .addWidget (period_from_label )
        period_layout .addWidget (self .plan_date_from )
        period_layout .addWidget (period_to_label )
        period_layout .addWidget (self .plan_date_to )
        period_layout .addStretch ()
        form_grid .addWidget (period_widget ,0 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        source_label =QLabel ("Источник:")
        source_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (source_label ,1 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )
        self .plan_source =QComboBox ()
        self .plan_source .setEditable (True )
        self .plan_source .setInsertPolicy (QComboBox .InsertPolicy .NoInsert )
        self .plan_source .setFixedWidth (560 )
        self .plan_source .setMinimumHeight (42 )
        self .plan_source .setMaximumHeight (42 )
        form_grid .addWidget (self .plan_source ,1 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        type_label =QLabel ("Тип:")
        type_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (type_label ,2 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )
        self .plan_medium =QComboBox ()
        self .plan_medium .setEditable (True )
        self .plan_medium .setInsertPolicy (QComboBox .InsertPolicy .NoInsert )
        self .plan_medium .setFixedWidth (560 )
        self .plan_medium .setMinimumHeight (42 )
        self .plan_medium .setMaximumHeight (42 )
        form_grid .addWidget (self .plan_medium ,2 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        budget_label =QLabel ("Расход план:")
        budget_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (budget_label ,3 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )
        self .plan_budget =QLineEdit ()
        self .plan_budget .setPlaceholderText ("Введите бюджет")
        self .plan_budget .setFixedWidth (560 )
        self .plan_budget .setMinimumHeight (42 )
        self .plan_budget .setMaximumHeight (42 )
        form_grid .addWidget (self .plan_budget ,3 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        leads_label =QLabel ("Лиды план:")
        leads_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (leads_label ,4 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )
        self .plan_leads =QLineEdit ()
        self .plan_leads .setPlaceholderText ("Введите количество лидов")
        self .plan_leads .setFixedWidth (560 )
        self .plan_leads .setMinimumHeight (42 )
        self .plan_leads .setMaximumHeight (42 )
        form_grid .addWidget (self .plan_leads ,4 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        cpl_label =QLabel ("CPL план:")
        cpl_label .setObjectName ("planFieldLabel")
        form_grid .addWidget (cpl_label ,5 ,0 ,alignment =Qt .AlignmentFlag .AlignLeft |Qt .AlignmentFlag .AlignVCenter )
        self .plan_cpl =QLabel ("0")
        self .plan_cpl .setObjectName ("planCplValue")
        self .plan_cpl .setStyleSheet ("font-weight: bold;")
        cpl_widget =QWidget ()
        cpl_widget .setFixedWidth (560 )
        cpl_widget .setMinimumHeight (42 )
        cpl_widget .setMaximumHeight (42 )
        cpl_layout =QHBoxLayout (cpl_widget )
        cpl_layout .setContentsMargins (0 ,0 ,0 ,0 )
        cpl_layout .setSpacing (8 )
        cpl_layout .addWidget (self .plan_cpl )
        self .plan_cpl_suffix =QLabel ("руб")
        self .plan_cpl_suffix .setObjectName ("planCplSuffix")
        cpl_layout .addWidget (self .plan_cpl_suffix )
        cpl_layout .addStretch ()
        form_grid .addWidget (cpl_widget ,5 ,1 ,alignment =Qt .AlignmentFlag .AlignLeft )

        card_layout .addLayout (form_grid )
        self .refresh_plan_dimension_options ()

        btn_widget =QWidget ()
        btn_layout =QHBoxLayout (btn_widget )
        btn_layout .setSpacing (12 )
        btn_layout .setContentsMargins (0 ,8 ,0 ,0 )

        self .save_plan_btn =QPushButton ("Применить")
        self .save_plan_btn .setFixedWidth (160 )
        self .save_plan_btn .setFixedHeight (42 )
        self .save_plan_btn .setObjectName ("planPrimaryButton")
        self .save_plan_btn .clicked .connect (self .save_plan )
        btn_layout .addWidget (self .save_plan_btn )

        self .reset_plan_btn =QPushButton ("Сбросить")
        self .reset_plan_btn .setFixedWidth (160 )
        self .reset_plan_btn .setFixedHeight (42 )
        self .reset_plan_btn .setObjectName ("planDangerButton")
        self .reset_plan_btn .clicked .connect (self .reset_plan )
        btn_layout .addWidget (self .reset_plan_btn )

        self .plans_list_btn =QPushButton ("📋 стория планов")
        self .plans_list_btn .setFixedWidth (160 )
        self .plans_list_btn .setFixedHeight (42 )
        self .plans_list_btn .setObjectName ("planSecondaryButton")
        self .plans_list_btn .clicked .connect (self .show_plans_list )
        btn_layout .addWidget (self .plans_list_btn )
        btn_layout .addStretch ()

        card_layout .addWidget (btn_widget )
        card_host_layout .addWidget (self .plan_form_card )
        card_host_layout .addStretch ()

        layout .addWidget (card_host )
        layout .addStretch ()

        self ._apply_plan_form_card_style ()

        # Подключаем авторасчет CPL
        self .plan_budget .textChanged .connect (self .update_plan_cpl )
        self .plan_leads .textChanged .connect (self .update_plan_cpl )

    def update_plan_cpl (self ):
        """Автоматически рассчитывает CPL план"""
        try :
            budget =float (self .plan_budget .text ().replace (" ",""))if self .plan_budget .text ()else 0 
            leads =float (self .plan_leads .text ().replace (" ",""))if self .plan_leads .text ()else 0 
            if leads >0 :
                cpl =budget /leads 
                self .plan_cpl .setText (f"{cpl :,.0f}".replace (","," "))
            else :
                self .plan_cpl .setText ("0")
        except :
            self .plan_cpl .setText ("0")

    def save_plan (self ):
        """Сохраняет план для текущего периода"""
        try :
            from_date =self .plan_date_from .date ().toPyDate ()
            to_date =self .plan_date_to .date ().toPyDate ()

            self .log (f"\n=== СОХРАНЕНЕ ПЛАНА ===")
            self .log (f"Период: {from_date } - {to_date }")
            self .log (f"юджет: {self .plan_budget .text ()}")
            self .log (f"Лиды: {self .plan_leads .text ()}")

            self .debug_plans ()
            self .update_plan_display ()

            # Создает ключ для периода
            period_key =f"{from_date .isoformat ()}_{to_date .isoformat ()}"

            plan ={
            "period_from":from_date ,
            "period_to":to_date ,
            "source":self .plan_source .currentText (),
            "medium":self .plan_medium .currentText (),
            "budget":float (self .plan_budget .text ().replace (" ",""))if self .plan_budget .text ()else 0 ,
            "leads":float (self .plan_leads .text ().replace (" ",""))if self .plan_leads .text ()else 0 ,
            "cpl":float (self .plan_cpl .text ().replace (" ",""))if self .plan_cpl .text ()else 0 
            }

            self .current_plan =plan .copy ()
            self .plan_data =plan .copy ()
            self .log (f"План: {plan }")

            # Сохраняе в историю планов для текущего клиента
            if self .current_client not in self .plans_history :
                self .plans_history [self .current_client ]={}
            self .plans_history [self .current_client ][period_key ]=plan 

            self .log (f"стория планов для {self .current_client }: {list (self .plans_history [self .current_client ].keys ())}")

            # Сохраняе историю в файл
            self .save_plans_history ()

            # Устанавливае текущий план
            self .plan_data =plan .copy ()

            self .log (f"Текущий план установлен: {self .plan_data }")

            # Сохраняе план для текущего клиента в clients
            if self .current_client in self .clients :
                self .clients [self .current_client ]["plan_data"]=self .plan_data .copy ()

                # Обновляет таблицу
            self .update_dashboard ()
            self .update_plan_display ()

            QMessageBox .information (self ,"Успех",
            f"План для периода {from_date .strftime ('%d.%m.%Y')} - {to_date .strftime ('%d.%m.%Y')}\n"
            f"сохранен!")

        except Exception as e :
            self .log (f"Ошибка сохранения плана: {e }","error")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")
            QMessageBox .warning (self ,"Ошибка",f"Ошибка сохранения плана: {e }")


    def load_plan_for_period (self ,from_date ,to_date ):
        """Загружает план для указанного периода"""
        period_key =f"{from_date .isoformat ()}_{to_date .isoformat ()}"

        if self .current_client in self .plans_history and period_key in self .plans_history [self .current_client ]:
            plan =self .plans_history [self .current_client ][period_key ]
            self .plan_data =plan .copy ()
            self .current_plan =plan .copy ()

            # Обновляет интерфейс
            self .plan_date_from .setDate (QDate (plan ["period_from"].year ,plan ["period_from"].month ,plan ["period_from"].day ))
            self .plan_date_to .setDate (QDate (plan ["period_to"].year ,plan ["period_to"].month ,plan ["period_to"].day ))
            self .plan_source .setCurrentText (plan ["source"])
            self .plan_medium .setCurrentText (plan ["medium"])
            self .plan_budget .setText (f"{plan ['budget']:,.0f}".replace (","," ")if plan ["budget"]>0 else "")
            self .plan_leads .setText (f"{plan ['leads']:,.0f}".replace (","," ")if plan ["leads"]>0 else "")
            self .plan_cpl .setText (f"{plan ['cpl']:,.0f}".replace (","," ")if plan ["cpl"]>0 else "0")

            self .update_plan_display ()

            # Обновляет таблицу
            self .update_table ()

            QMessageBox .information (self ,"Успех",f"Загружен план для периода {from_date .strftime ('%d.%m.%Y')} - {to_date .strftime ('%d.%m.%Y')}")
            return True 

        QMessageBox .warning (self ,"Ошибка",f"План для периода {from_date .strftime ('%d.%m.%Y')} - {to_date .strftime ('%d.%m.%Y')} не найден")
        return False 



    def show_plans_list (self ):
        """Показывает список сохраненных планов"""
        if self .current_client not in self .plans_history or not self .plans_history [self .current_client ]:
            QMessageBox .information (self ,"Планы","Нет сохраненных планов")
            return 

            # Создает диалог со списком планов
        dialog =QDialog (self )
        dialog .setWindowTitle ("Сохраненные планы")
        dialog .setMinimumWidth (400 )

        layout =QVBoxLayout (dialog )

        layout .addWidget (QLabel ("Выберите период для загрузки плана:"))

        list_widget =QListWidget ()
        for period_key ,plan in self .plans_history [self .current_client ].items ():
            from_date =plan ["period_from"].strftime ("%d.%m.%Y")
            to_date =plan ["period_to"].strftime ("%d.%m.%Y")
            budget =plan ["budget"]
            leads =plan ["leads"]
            item_text =f"{from_date } - {to_date } | юджет: {budget :,.0f} руб | Лиды: {leads }"
            list_widget .addItem (item_text )

        layout .addWidget (list_widget )

        # Кнопки
        btn_layout =QHBoxLayout ()
        load_btn =QPushButton ("Загрузить")
        delete_btn =QPushButton ("Удалить")
        close_btn =QPushButton ("Закрыть")
        btn_layout .addWidget (load_btn )
        btn_layout .addWidget (delete_btn )
        btn_layout .addWidget (close_btn )
        layout .addLayout (btn_layout )

        def load_selected ():
            current_row =list_widget .currentRow ()
            if current_row >=0 :
                period_key =list (self .plans_history [self .current_client ].keys ())[current_row ]
                plan =self .plans_history [self .current_client ][period_key ]
                self .load_plan_for_period (plan ["period_from"],plan ["period_to"])
                dialog .accept ()

        def delete_selected ():
            current_row =list_widget .currentRow ()
            if current_row >=0 :
                period_key =list (self .plans_history [self .current_client ].keys ())[current_row ]
                del self .plans_history [self .current_client ][period_key ]
                self .save_plans_history ()
                list_widget .takeItem (current_row )
                QMessageBox .information (dialog ,"Успех","План удален")

        load_btn .clicked .connect (load_selected )
        delete_btn .clicked .connect (delete_selected )
        close_btn .clicked .connect (dialog .reject )

        dialog .exec ()

    def save_plans_history (self ):
        """Сохраняет историю планов в файл"""
        try :
            plans_file =os .path .join (self .projects_dir ,"plans_history.json")

            # Преобразуем для JSON
            plans_data ={}
            for client ,periods in self .plans_history .items ():
                plans_data [client ]={}
                for period_key ,plan in periods .items ():
                    plans_data [client ][period_key ]={
                    "period_from":plan ["period_from"].isoformat (),
                    "period_to":plan ["period_to"].isoformat (),
                    "source":plan ["source"],
                    "medium":plan ["medium"],
                    "budget":plan ["budget"],
                    "leads":plan ["leads"],
                    "cpl":plan ["cpl"]
                    }

            with open (plans_file ,'w',encoding ='utf-8')as f :
                json .dump (plans_data ,f ,ensure_ascii =False ,indent =2 )

            self .log (f"стория планов сохранена в {plans_file }")
        except Exception as e :
            self .log (f"Ошибка сохранения истории планов: {e }")

    def load_plans_history (self ):
        """Загружает историю планов из файла"""
        plans_file =os .path .join (self .projects_dir ,"plans_history.json")

        if not os .path .exists (plans_file ):
            return 

        try :
            with open (plans_file ,'r',encoding ='utf-8')as f :
                plans_data =json .load (f )

            from datetime import date 

            for client ,periods in plans_data .items ():
                self .plans_history [client ]={}
                for period_key ,plan_data in periods .items ():
                    self .plans_history [client ][period_key ]={
                    "period_from":date .fromisoformat (plan_data ["period_from"]),
                    "period_to":date .fromisoformat (plan_data ["period_to"]),
                    "source":plan_data ["source"],
                    "medium":plan_data ["medium"],
                    "budget":plan_data ["budget"],
                    "leads":plan_data ["leads"],
                    "cpl":plan_data ["cpl"]
                    }

            self .log (f"стория планов загружена")
        except Exception as e :
            self .log (f"Ошибка загрузки истории планов: {e }")

    def debug_plans (self ):
        """Выводит в лог все сохраненные планы"""
        self .log ("\n=== ДЕАГ СТОР ПЛАНОВ ===")
        for client ,periods in self .plans_history .items ():
            self .log (f"Клиент: {client }")
            for period_key ,plan in periods .items ():
                self .log (f"  {period_key }: {plan ['period_from']} - {plan ['period_to']}, бюджет={plan ['budget']}, лиды={plan ['leads']}")
        self .log ("=== КОНЕЦ ДЕАГА ===\n")

    def reset_plan (self ):
        """Сбрасывает план для текущего периода"""
        from_date =self .plan_date_from .date ().toPyDate ()
        to_date =self .plan_date_to .date ().toPyDate ()
        period_key =f"{from_date .isoformat ()}_{to_date .isoformat ()}"

        self .update_plan_display ()

        # Удаляет план для этого периода из истории
        if self .current_client in self .plans_history and period_key in self .plans_history [self .current_client ]:
            del self .plans_history [self .current_client ][period_key ]
            self .save_plans_history ()

            # Если это был текущий план, сбрасывае его
        if self .plan_data .get ("period_from")==from_date and self .plan_data .get ("period_to")==to_date :
            self .plan_data ={
            "period_from":None ,
            "period_to":None ,
            "source":"Все",
            "medium":"Все",
            "budget":0 ,
            "leads":0 ,
            "cpl":0 
            }
            if self .current_client in self .clients :
                self .clients [self .current_client ]["plan_data"]=self .plan_data .copy ()

                # Очищае поля
        self .plan_budget .clear ()
        self .plan_leads .clear ()
        self .plan_cpl .setText ("0")
        self .plan_source .setCurrentText ("Все")
        self .plan_medium .setCurrentText ("Все")

        # Обновляет таблицу
        self .update_table ()

        QMessageBox .information (self ,"Успех",f"План для периода {from_date .strftime ('%d.%m.%Y')} - {to_date .strftime ('%d.%m.%Y')} сброшен")
        self .auto_save_project ()

    def save_plan_to_file (self ):
        """Сохраняет планы всех клиентомв в файл"""
        try :
            all_plans ={}
            for client_name ,client_data in self .clients .items ():
                plan =client_data .get ("plan_data",{})
                all_plans [client_name ]={
                "period_from":plan .get ("period_from").isoformat ()if plan .get ("period_from")else None ,
                "period_to":plan .get ("period_to").isoformat ()if plan .get ("period_to")else None ,
                "source":plan .get ("source","Все"),
                "medium":plan .get ("medium","Все"),
                "budget":plan .get ("budget",0 ),
                "leads":plan .get ("leads",0 ),
                "cpl":plan .get ("cpl",0 )
                }

            with open (self .plan_file ,'w',encoding ='utf-8')as f :
                json .dump (all_plans ,f ,ensure_ascii =False ,indent =2 )
            self .log (f"Планы сохранены в {self .plan_file }")
        except Exception as e :
            self .log (f"Ошибка сохранения планов: {e }")

    def load_plan (self ):
        """Загружает план из файла"""
        if not os .path .exists (self .plan_file ):
            return 

        try :
            with open (self .plan_file ,'r',encoding ='utf-8')as f :
                all_plans =json .load (f )

                # Загружае план для текущего клиента
            if hasattr (self ,'current_client')and self .current_client in all_plans :
                plan =all_plans [self .current_client ]
                from datetime import date 
                self .plan_data ={
                "period_from":date .fromisoformat (plan ["period_from"])if plan .get ("period_from")else None ,
                "period_to":date .fromisoformat (plan ["period_to"])if plan .get ("period_to")else None ,
                "source":plan .get ("source","Все"),
                "medium":plan .get ("medium","Все"),
                "budget":plan .get ("budget",0 ),
                "leads":plan .get ("leads",0 ),
                "cpl":plan .get ("cpl",0 )
                }
                if self .current_client in self .clients :
                    self .clients [self .current_client ]["plan_data"]=self .plan_data .copy ()

                    # Обновляет интерфейс вкладки План (если уже создан)
            self .update_plan_ui ()

            self .log ("План загружен")
        except Exception as e :
            self .log (f"Ошибка загрузки плана: {e }")

    def apply_filter_old (self ):
        """Применяет фильтр по дате (периоду) с генерацией полного календаря"""
        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()

        self .log (f"\n=== ПРМЕНЕНЕ ФЛЬТРА ПО ДАТЕ ===")
        self .log (f"Период: {from_date } - {to_date }")

        # 1. Создает базовый DataFrame со всеми датами
        date_range =pd .date_range (start =from_date ,end =to_date ,freq ='D')

        # Создает словарь для данных
        data_dict ={"Дата":date_range }

        # 2. Добавляе фактические данные (если есть)
        if not self .original_data .empty and "Дата"in self .original_data .columns :
        # Убеждаеся, что даты в правильно формате
            data_copy =self .original_data .copy ()
            if not pd .api .types .is_datetime64_any_dtype (data_copy ["Дата"]):
                data_copy ["Дата"]=pd .to_datetime (data_copy ["Дата"],errors ='coerce',dayfirst =True )
            data_copy =data_copy .dropna (subset =["Дата"])

            # Фильтруе по дате
            filtered_data =data_copy [
            (data_copy ["Дата"].dt .date >=from_date )&
            (data_copy ["Дата"].dt .date <=to_date )
            ]

            self .log (f"Найдено данных за период: {len (filtered_data )} строк")

            if not filtered_data .empty :
            # Группируе данные по дате
                grouped =filtered_data .groupby (filtered_data ["Дата"].dt .date ).agg ({
                "Расход":"sum",
                "Показы":"sum",
                "Клики":"sum",
                "Лиды":"sum",
                "Продажи":"sum",
                "Выручка":"sum",
                "Ср.чек":"mean"
                }).reset_index ()

                # Создает словарь для быстрого доступа
                data_by_date ={}
                for _ ,row in grouped .iterrows ():
                    date_key =row ["Дата"]
                    data_by_date [date_key ]={
                    "Расход":row ["Расход"],
                    "Показы":row ["Показы"],
                    "Клики":row ["Клики"],
                    "Лиды":row ["Лиды"],
                    "Продажи":row ["Продажи"],
                    "Выручка":row ["Выручка"],
                    "Ср.чек":row ["Ср.чек"]
                    }

                    # Заполняе данные для каждой даты
                cost_values =[]
                impression_values =[]
                click_values =[]
                lead_values =[]
                sale_values =[]
                revenue_values =[]
                avg_check_values =[]

                for dt in date_range :
                    date_key =dt .date ()
                    if date_key in data_by_date :
                        cost_values .append (data_by_date [date_key ][""])
                        impression_values .append (data_by_date [date_key ][""])
                        click_values .append (data_by_date [date_key ][""])
                        lead_values .append (data_by_date [date_key ][""])
                        sale_values .append (data_by_date [date_key ][""])
                        revenue_values .append (data_by_date [date_key ][""])
                        avg_check_values .append (data_by_date [date_key ]["."])
                    else :
                        cost_values .append (0 )
                        impression_values .append (0 )
                        click_values .append (0 )
                        lead_values .append (0 )
                        sale_values .append (0 )
                        revenue_values .append (0 )
                        avg_check_values .append (0 )

                data_dict [""]=cost_values 
                data_dict [""]=impression_values 
                data_dict [""]=click_values 
                data_dict [""]=lead_values 
                data_dict [""]=sale_values 
                data_dict [""]=revenue_values 
                data_dict ["."]=avg_check_values 
            else :
            # Если нет данных, заполняе нуляи
                data_dict ["Расход"]=[0 ]*len (date_range )
                data_dict ["Показы"]=[0 ]*len (date_range )
                data_dict ["Клики"]=[0 ]*len (date_range )
                data_dict ["Лиды"]=[0 ]*len (date_range )
                data_dict ["Продажи"]=[0 ]*len (date_range )
                data_dict ["Выручка"]=[0 ]*len (date_range )
                data_dict ["Ср.чек"]=[0 ]*len (date_range )
        else :
        # Если нет исходных данных, заполняе нуляи
            data_dict ["Расход"]=[0 ]*len (date_range )
            data_dict ["Показы"]=[0 ]*len (date_range )
            data_dict ["Клики"]=[0 ]*len (date_range )
            data_dict ["Лиды"]=[0 ]*len (date_range )
            data_dict ["Продажи"]=[0 ]*len (date_range )
            data_dict ["Выручка"]=[0 ]*len (date_range )
            data_dict ["Ср.чек"]=[0 ]*len (date_range )

            # 3. Добавляе колонки изерений (если есть)
        if not self .original_data .empty :
            dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]
            for col in dimension_cols :
                if col in self .original_data .columns :
                # ере первое значение или стави "(не указано)"
                    first_val =self .original_data [col ].iloc [0 ]if len (self .original_data )>0 else "(не указано)"
                    data_dict [col ]=[str (first_val )]*len (date_range )
                else :
                    data_dict [col ]=["(не указано)"]*len (date_range )

                    # 4. Создает DataFrame
        full_calendar =pd .DataFrame (data_dict )

        # 5. Добавляе плановые значения
        plans =self .plans_history .get (self .current_client ,{})

        # нициализируе плановые колонки
        full_calendar ["Расход план"]=0.0 
        full_calendar ["Лиды план"]=0.0 
        full_calendar ["CPL план"]=0.0 

        # Для каждого плана распределяе его по дня
        for period_key ,plan in plans .items ():
            plan_from =plan ["period_from"]
            plan_to =plan ["period_to"]

            if plan_from and plan_to :
                total_plan_days =(plan_to -plan_from ).days +1 
                daily_budget =plan ["budget"]/total_plan_days 
                daily_leads =plan ["leads"]/total_plan_days 
                daily_cpl =daily_budget /daily_leads if daily_leads >0 else 0 

                # Заполняе для каждой даты в диапазоне
                for idx ,dt in enumerate (date_range ):
                    dt_date =dt .date ()
                    if plan_from <=dt_date <=plan_to :
                        full_calendar .loc [idx ,"Расход план"]=daily_budget 
                        full_calendar .loc [idx ,"Лиды план"]=daily_leads 
                        full_calendar .loc [idx ,"CPL план"]=daily_cpl 

                        # 6. Рассчитывает CPL (если есть данные)
                        # Сначала создает колонку CPL
        full_calendar ["CPL"]=0.0 
        for idx in range (len (full_calendar )):
            if full_calendar .loc [idx ,"Лиды"]>0 :
                full_calendar .loc [idx ,"CPL"]=round (full_calendar .loc [idx ,"Расход"]/full_calendar .loc [idx ,"Лиды"],0 )

                # 7. Рассчитывает проценты выполнения
        full_calendar ["Расход %"]=0.0 
        full_calendar ["Лиды %"]=0.0 
        full_calendar ["CPL %"]=0.0 

        for idx in range (len (full_calendar )):
            if full_calendar .loc [idx ,"Расход план"]>0 :
                full_calendar .loc [idx ,"Расход %"]=round ((full_calendar .loc [idx ,"Расход"]/full_calendar .loc [idx ,"Расход план"])*100 ,2 )

            if full_calendar .loc [idx ,"Лиды план"]>0 :
                full_calendar .loc [idx ,"Лиды %"]=round ((full_calendar .loc [idx ,"Лиды"]/full_calendar .loc [idx ,"Лиды план"])*100 ,2 )

            if full_calendar .loc [idx ,"CPL план"]>0 and full_calendar .loc [idx ,"CPL"]>0 :
                full_calendar .loc [idx ,"CPL %"]=round ((full_calendar .loc [idx ,"CPL"]/full_calendar .loc [idx ,"CPL план"])*100 ,2 )

                # 8. Рассчитывает остальные метрики
        full_calendar =self ._calculate_metrics_for_df (full_calendar )

        # 9. Сохраняе данные
        self .filtered_data =full_calendar 
        self .original_filtered_data =self .filtered_data .copy ()
        self .chart_data =self .filtered_data .copy ()

        self .log (f"тоговое количество строк: {len (self .filtered_data )}")
        self .log (f"Первые 5 дат: {self .filtered_data ['Дата'].head ().tolist ()}")
        self .log (f"Последние 5 дат: {self .filtered_data ['Дата'].tail ().tolist ()}")
        self .log (f"Дней с плановы расходо > 0: {(self .filtered_data ['Расход план']>0 ).sum ()}")

        # 10. Загружае план для периода
        period_key =f"{from_date .isoformat ()}_{to_date .isoformat ()}"
        if self .current_client in self .plans_history and period_key in self .plans_history [self .current_client ]:
            self .plan_data =self .plans_history [self .current_client ][period_key ].copy ()
            self .current_plan =self .plan_data .copy ()
        else :
            found =False 
            for stored_key ,stored_plan in self .plans_history .get (self .current_client ,{}).items ():
                stored_from =stored_plan ["period_from"]
                stored_to =stored_plan ["period_to"]
                if stored_from <=from_date and stored_to >=to_date :
                    self .plan_data =stored_plan .copy ()
                    self .current_plan =stored_plan .copy ()
                    found =True 
                    break 
            if not found :
                self .current_plan =None 

        self .update_plan_ui ()
        self .update_filters_from_data ()

        # 11. Приеняе все фильтры
        self .apply_all_filters ()

        self .log (f"=== ПРМЕНЕНЕ ФЛЬТРА ПО ДАТЕ ЗАВЕРШЕНО ===\n")

    def generate_full_calendar (self ,from_date ,to_date ):
        """Генерируетт полный календарь на выбранный период со всеи дняи"""
        # Создает все даты от from_date до to_date
        date_range =pd .date_range (start =from_date ,end =to_date ,freq ='D')

        self .log (f"Генерация календаря от {from_date } до {to_date }")
        self .log (f"Количество дней: {len (date_range )}")
        self .log (f"Первые 5 дат: {date_range [:5 ].tolist ()}")
        self .log (f"Последние 5 дат: {date_range [-5 :].tolist ()}")

        # Создает DataFrame со всеми датами
        full_calendar =pd .DataFrame ({
        "Дата":date_range ,
        "Расход":0 ,
        "Показы":0 ,
        "Клики":0 ,
        "Лиды":0 ,
        "Продажи":0 ,
        "Ср.чек":0 ,
        "Выручка":0 
        })

        # Добавляе колонки изерений, если они есть в данных
        if hasattr (self ,'data')and not self .data .empty :
            dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]
            for col in dimension_cols :
                if col in self .data .columns :
                    full_calendar [col ]="(не указано)"

                    # ===== ЗАПОЛНЯЕМ ПЛАНОВЫЕ ЗНАЧЕНЯ ДЛЯ КАЖДОГО ДНЯ =====
                    # Получаем планы для текущего клиента
        plans =self .plans_history .get (self .current_client ,{})

        # Создает словарь дневных планов
        daily_plans ={}
        for period_key ,plan in plans .items ():
            plan_from =plan ["period_from"]
            plan_to =plan ["period_to"]
            if plan_from and plan_to :
                plan_days =(plan_to -plan_from ).days +1 
                daily_budget =plan ["budget"]/plan_days 
                daily_leads =plan ["leads"]/plan_days 
                daily_cpl =daily_budget /daily_leads if daily_leads >0 else 0 

                self .log (f"План {plan_from } - {plan_to }: дневной бюджет={daily_budget :.2f}, дневные лиды={daily_leads :.2f}")

                current_date =plan_from 
                while current_date <=plan_to :
                    daily_plans [current_date ]={
                    "budget":daily_budget ,
                    "leads":daily_leads ,
                    "cpl":daily_cpl 
                    }
                    current_date +=timedelta (days =1 )

                    # Добавляе плановые колонки в календарь
        full_calendar ["Расход план"]=0.0 
        full_calendar ["Лиды план"]=0.0 
        full_calendar ["CPL план"]=0.0 
        full_calendar ["Расход %"]=0.0 
        full_calendar ["Лиды %"]=0.0 
        full_calendar ["CPL %"]=0.0 

        # Заполняе плановые значения для каждой даты
        plan_filled_count =0 
        for idx in range (len (full_calendar )):
            date_val =full_calendar .iloc [idx ]["Дата"]
            date_to_check =date_val .date ()if hasattr (date_val ,'date')else date_val 

            if date_to_check in daily_plans :
                plan =daily_plans [date_to_check ]
                full_calendar .loc [idx ,"Расход план"]=plan ["budget"]
                full_calendar .loc [idx ,"Лиды план"]=plan ["leads"]
                full_calendar .loc [idx ,"CPL план"]=plan ["cpl"]
                plan_filled_count +=1 

        self .log (f"Заполнено планаи {plan_filled_count } из {len (full_calendar )} дней")

        # Рассчитывает метрики
        full_calendar ["CTR"]=0 
        full_calendar ["CR1"]=0 
        full_calendar ["CPC"]=0 
        full_calendar ["CPL"]=0 
        full_calendar ["CR2"]=0 
        full_calendar ["Маржа"]=0 
        full_calendar ["ROMI"]=-100 

        return full_calendar 

    def change_client (self ,client_name ):
        """Переключает данные при сене клиента"""
        if not client_name or client_name not in self .clients :
            return 

        print (f"Переключение на клиента: {client_name }")
        print (f"План до сохранения: {self .plan_data }")

        # Сохраняе план текущего клиента
        if hasattr (self ,'current_client')and self .current_client in self .clients :
            self .clients [self .current_client ]["plan_data"]=self .plan_data .copy ()
            print (f"Сохранен план для {self .current_client }: {self .plan_data }")

        self .current_client =client_name 

        # Загружае данные клиента
        self .data =self .clients [client_name ]["data"].copy ()
        self .original_data =self .data .copy ()

        # ===== ЗАГРУЖАЕМ ПЛАН ДЛЯ ТЕКУЩЕГО ПЕРОДА =====
        current_from =self .date_from .date ().toPyDate ()
        current_to =self .date_to .date ().toPyDate ()
        period_key =f"{current_from .isoformat ()}_{current_to .isoformat ()}"

        if self .current_client in self .plans_history and period_key in self .plans_history [self .current_client ]:
            self .plan_data =self .plans_history [self .current_client ][period_key ].copy ()
            self .current_plan =self .plan_data .copy ()
            print (f"Загружен план для {client_name } на период {current_from } - {current_to }")
        else :
        # ще план, покрывающий период
            found =False 
            for stored_key ,stored_plan in self .plans_history .get (self .current_client ,{}).items ():
                stored_from =stored_plan ["period_from"]
                stored_to =stored_plan ["period_to"]
                if stored_from <=current_from and stored_to >=current_to :
                    self .plan_data =stored_plan .copy ()
                    self .current_plan =stored_plan .copy ()
                    self .log (f"Загружен план {stored_from } - {stored_to } (покрывает период {current_from } - {current_to })")
                    found =True 
                    break 
            if not found :
                self .current_plan =None 
                self .plan_data ={"period_from":None ,"period_to":None ,"source":"Все","medium":"Все","budget":0 ,"leads":0 ,"cpl":0 }
                print (f"Нет плана для периода {current_from } - {current_to }")

                # Обновляет интерфейс плана
        self .update_plan_ui ()

        # Приеняе текущий фильтр по дате
        self .update_dashboard ()

        # Обновляет фильтры (данные для вкладок с измерениями)
        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        for dimension_name in ["Источник","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            self .update_dimension_table_with_filter (dimension_name ,from_date ,to_date )

        self .apply_all_filters ()
        self .auto_save_project ()

    def update_table (self ):
        """Обновляетт таблицу с группировкой по дате и строкой ТОГО в конце"""
        if self .filtered_data .empty :
            self .filtered_data =self .data .copy ()
            self .filtered_data =self .initialize_plan_columns (self .filtered_data )

            # Создает копию для отображения
        display_data =self .filtered_data .copy ()

        # Проверяет, нужно ли группировать по дате
        group_type =self .group_combo .currentText ()

        # Проверяет, есть ли колонка Дата
        if "Дата"not in display_data .columns :
            print ("Колонка 'Дата' отсутствует в данных")
            self .display_empty_table ()
            return 

            # Форматируе дату для отображения
        if group_type =="день":
            if "Дата"in display_data .columns :
                if pd .api .types .is_datetime64_any_dtype (display_data ["Дата"]):
                    display_data ["Дата"]=display_data ["Дата"].dt .strftime ("%d.%m.%Y")
                else :
                    display_data ["Дата"]=display_data ["Дата"].astype (str )
                    display_data ["Дата"]=display_data ["Дата"].str .split (' ').str [0 ]

                    # Новый порядок столбцов
        column_order =[
        "Дата",
        "Расход","Расход план","Расход %",
        "Показы","Клики","CPC","CTR",
        "Лиды","Лиды план","Лиды %",
        "CPL","CPL план","CPL %",
        "CR1","Продажи","CR2","Ср.чек","Выручка","Маржа","ROMI"
        ]

        # Если включено скрытие плана, убирае плановые столбцы
        if self .hide_plan_checkbox .isChecked ():
            column_order =[col for col in column_order if col not in [
            "Расход план","Расход %",
            "Лиды план","Лиды %",
            "CPL план","CPL %"
            ]]

            # Оставляет только существующие столбцы
        visible_columns =[col for col in column_order if col in display_data .columns ]
        display_data =display_data [visible_columns ]

        # Сохраняе базовые заголовки для стрелок
        self .base_headers =list (display_data .columns )

        # Вычисляе итоговую строку
        total_row_data =self .calculate_total_row (display_data )

        # Отключаем сортировку таблицы
        self .table .setSortingEnabled (False )
        self .table .clearContents ()

        # Устанавливае количество строк: данные + 1 для ТОГО
        self .table .setRowCount (len (display_data )+1 )
        self .table .setColumnCount (len (display_data .columns ))
        self .table .setHorizontalHeaderLabels (self .base_headers )
        self .table .verticalHeader ().setVisible (False )

        # Заполняе основные данные
        for row_idx in range (len (display_data )):
            row_data =display_data .iloc [row_idx ]
            for col_idx ,col_name in enumerate (display_data .columns ):
                val =row_data [col_name ]

                # Форматируе значение для отображения
                if col_name =="Дата":
                    display_val =str (val )
                elif col_name in ["CTR","CR1","CR2","ROMI","Расход %","Лиды %","CPL %"]:
                    try :
                        display_val =f"{float (val ):.2f}".replace (".",",")
                    except :
                        display_val =str (val )
                else :
                    try :
                        num_val =float (val )
                        if num_val ==int (num_val ):
                            display_val =f"{int (num_val ):,}".replace (","," ")
                        else :
                            display_val =f"{num_val :,.2f}".replace (","," ").replace (".",",")
                    except (ValueError ,TypeError ):
                        display_val =str (val )

                item =NumericTableWidgetItem (display_val )
                item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )

                # ===== ПРАВЛЬНОЕ ЦВЕТОВОЕ ФОРМАТРОВАНЕ =====
                try :
                    num_val =float (val )

                    # ROMI
                    if col_name =="ROMI":
                        if num_val >10 :
                            if num_val >50 :
                                color =QColor (30 ,150 ,30 )
                            else :
                                green =120 +int (min (100 ,num_val ))
                                red =max (30 ,120 -int (num_val ))
                                blue =max (30 ,120 -int (num_val ))
                                color =QColor (red ,green ,blue )
                            item .setBackground (color )
                            item .setForeground (QColor (255 ,255 ,255 ))
                        elif num_val <-10 :
                            if num_val <-50 :
                                color =QColor (180 ,50 ,50 )
                            else :
                                red =180 
                                green =80 +int (min (100 ,abs (num_val )))
                                blue =80 +int (min (100 ,abs (num_val )))
                                color =QColor (red ,green ,blue )
                            item .setBackground (color )
                            item .setForeground (QColor (255 ,255 ,255 ))

                            # Расход % - че МЕНЬШЕ, те ЛУЧШЕ (эконоия бюджета)
                    elif col_name =="Расход %":
                        if num_val <=100 :
                        # Хорошо - потратили еньше или равно плану
                            ratio =num_val /100 
                            red =int (30 +30 *ratio )
                            green =int (100 +40 *ratio )
                            blue =int (30 +30 *ratio )
                            color =QColor (red ,green ,blue )
                        else :
                        # Плохо - перерасход
                            color =QColor (180 ,60 ,60 )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))

                        # Лиды % - че ОЛЬШЕ, те ЛУЧШЕ (больше лидов)
                    elif col_name =="Лиды %":
                        if num_val >=100 :
                        # Хорошо - выполнили план или перевыполнили
                            ratio =min (1 ,(num_val -100 )/100 )if num_val >100 else 0 
                            red =int (30 +30 *ratio )
                            green =int (100 +40 *ratio )
                            blue =int (30 +30 *ratio )
                            color =QColor (red ,green ,blue )
                        else :
                        # Плохо - недовыполнили
                            color =QColor (180 ,60 ,60 )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))

                        # CPL % - че МЕНЬШЕ, те ЛУЧШЕ (дешевле лид)
                    elif col_name =="CPL %":
                        if num_val <=100 :
                        # Хорошо - CPL ниже плана
                            ratio =num_val /100 
                            red =int (30 +30 *ratio )
                            green =int (100 +40 *ratio )
                            blue =int (30 +30 *ratio )
                            color =QColor (red ,green ,blue )
                        else :
                        # Плохо - CPL выше плана
                            color =QColor (180 ,60 ,60 )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))

                except (ValueError ,TypeError ,KeyError ):
                    pass 

                self .table .setItem (row_idx ,col_idx ,item )

                # Добавляе строку ТОГО с цветовы форматирование
        if total_row_data :
            row_pos =len (display_data )
            for col_idx ,col_name in enumerate (display_data .columns ):
                if col_name =="Дата":
                    value ="ТОГО"
                elif col_name in total_row_data :
                    val =total_row_data [col_name ]
                    if pd .isna (val ):
                        value ="0"
                    elif col_name in ["CTR","CR1","CR2","ROMI","Расход %","Лиды %","CPL %"]:
                        value =f"{val :.2f}".replace (".",",")
                    else :
                        value =f"{int (round (val )):,}".replace (","," ")
                else :
                    value =""

                item =QTableWidgetItem (value )
                self ._style_total_row_item (item )

                # ===== ЦВЕТОВОЕ ФОРМАТРОВАНЕ ДЛЯ СТРОК ТОГО =====
                try :
                    if col_name in ["ROMI","Расход %","Лиды %","CPL %"]:
                        clean_val =str (value ).replace (' ','').replace ('%','').replace (',','.')
                        num_val =float (clean_val )

                        if col_name =="ROMI":
                            if num_val >10 :
                                if num_val >50 :
                                    color =QColor (30 ,150 ,30 )
                                else :
                                    green =120 +int (min (100 ,num_val ))
                                    red =max (30 ,120 -int (num_val ))
                                    blue =max (30 ,120 -int (num_val ))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                            elif num_val <-10 :
                                if num_val <-50 :
                                    color =QColor (180 ,50 ,50 )
                                else :
                                    red =180 
                                    green =80 +int (min (100 ,abs (num_val )))
                                    blue =80 +int (min (100 ,abs (num_val )))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))

                        elif col_name =="Расход %":
                            if num_val <=100 :
                                ratio =num_val /100 
                                red =int (30 +30 *ratio )
                                green =int (100 +40 *ratio )
                                blue =int (30 +30 *ratio )
                                color =QColor (red ,green ,blue )
                            else :
                                color =QColor (180 ,60 ,60 )
                            item .setBackground (color )
                            item .setForeground (QColor (255 ,255 ,255 ))

                        elif col_name =="Лиды %":
                            if num_val >=100 :
                                ratio =min (1 ,(num_val -100 )/100 )if num_val >100 else 0 
                                red =int (30 +30 *ratio )
                                green =int (100 +40 *ratio )
                                blue =int (30 +30 *ratio )
                                color =QColor (red ,green ,blue )
                            else :
                                color =QColor (180 ,60 ,60 )
                            item .setBackground (color )
                            item .setForeground (QColor (255 ,255 ,255 ))

                        elif col_name =="CPL %":
                            if num_val <=100 :
                                ratio =num_val /100 
                                red =int (30 +30 *ratio )
                                green =int (100 +40 *ratio )
                                blue =int (30 +30 *ratio )
                                color =QColor (red ,green ,blue )
                            else :
                                color =QColor (180 ,60 ,60 )
                            item .setBackground (color )
                            item .setForeground (QColor (255 ,255 ,255 ))

                except :
                    pass 

                self .table .setItem (row_pos ,col_idx ,item )

                # Включае сортировку обратно
        self .table .setSortingEnabled (False )

        # Обновляет KPI и ширину колонок
        self .update_kpi ()

        for col in range (self .table .columnCount ()):
            self .table .resizeColumnToContents (col )

        self .setup_table_header_style ()
        self .sync_all_table_columns_width ()
        self .update_sort_indicators ()

    def fill_footer_totals (self ,df ):
        """Расчет и заполнение строки итогов с корректным пересчетом метрик"""
        self .footer_table .setRowCount (1 )

        # Считаем суы для базовых метрик
        sums ={
        "Расход":df ["Расход"].sum (),
        "Показы":df ["Показы"].sum (),
        "Клики":df ["Клики"].sum (),
        "Лиды":df ["Лиды"].sum (),
        "Продажи":df ["Продажи"].sum (),
        "Выручка":df ["Выручка"].sum ()
        }

        for j ,col_name in enumerate (df .columns ):
            footer_text =""

            if col_name =="Дата":
                footer_text ="ТОГО:"
            elif col_name in sums :
                val =sums [col_name ]
                footer_text =f"{val :,.0f}".replace (","," ")
            elif col_name =="CTR":
                val =(sums ["Клики"]/sums ["Показы"]*100 )if sums ["Показы"]>0 else 0 
                footer_text =f"{val :.2f}%"
            elif col_name =="CR1":
                val =(sums ["Лиды"]/sums ["Клики"]*100 )if sums ["Клики"]>0 else 0 
                footer_text =f"{val :.2f}%"
            elif col_name =="CPC":
                val =(sums ["Расход"]/sums ["Клики"])if sums ["Клики"]>0 else 0 
                footer_text =f"{val :,.0f}"
            elif col_name =="CPL":
                val =(sums ["Расход"]/sums ["Лиды"])if sums ["Лиды"]>0 else 0 
                footer_text =f"{val :,.0f}"
            elif col_name =="ROMI":
                val =((sums ["Выручка"]-sums ["Расход"])/sums ["Расход"]*100 )if sums ["Расход"]>0 else -100 
                footer_text =f"{val :.2f}%"
            elif col_name =="Маржа":
                val =sums ["Выручка"]-sums ["Расход"]
                footer_text =f"{val :,.0f}"

            item =QTableWidgetItem (footer_text )
            item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )
            item .setFont (QFont ("Arial",10 ,QFont .Weight .Bold ))
            self .footer_table .setItem (0 ,j ,item )

    def sync_footer_columns (self ,logical_index ,old_size ,new_size ):
        """Синхронизирует ширину колонок футера с основной таблицей"""
        if self .footer_table .columnCount ()>logical_index :
            self .footer_table .setColumnWidth (logical_index ,new_size )

    def custom_sort (self ,column_index ):
        """Кастоная сортировка + стрелки"""

        if self .current_sort_col ==column_index :
            self .sort_order =(
            Qt .SortOrder .DescendingOrder 
            if self .sort_order ==Qt .SortOrder .AscendingOrder 
            else Qt .SortOrder .AscendingOrder 
            )
        else :
            self .current_sort_col =column_index 
            self .sort_order =Qt .SortOrder .AscendingOrder 

        header_item =self .table .horizontalHeaderItem (column_index )
        if not header_item :
            return 

        col_name =header_item .text ().replace (" ▲","").replace (" ","")

        if col_name not in self .filtered_data .columns :
            return 

        df =self .filtered_data .copy ()
        ascending =self .sort_order ==Qt .SortOrder .AscendingOrder 

        # убирае ТОГО
        total_row =None 
        if "Дата"in df .columns :
            mask =df ["Дата"].astype (str ).str .contains ("ТОГО",na =False )
            if mask .any ():
                total_row =df [mask ]
                df =df [~mask ]

                # сортировка
        if col_name =="Дата":
            df ["_date"]=pd .to_datetime (df ["Дата"],format ="%d.%m.%Y",errors ="coerce")
            df =df .sort_values ("_date",ascending =ascending ).drop (columns =["_date"])
        else :
            df =df .sort_values (col_name ,ascending =ascending )

            # возвращае ТОГО
        if total_row is not None :
            df =pd .concat ([df ,total_row ],ignore_index =True )

        self .filtered_data =df .reset_index (drop =True )

        self .update_table ()

        # 🔥 ВАЖНО: обновляе стрелки ПОСЛЕ перерисовки
        self .update_sort_indicators ()

    def _extract_sort_key (self ,date_str ):
        """Извлекает числовой ключ для сортировки группированных дат"""
        date_str =str (date_str )

        # Для недель
        if "Неделя"in date_str :
            import re 
            match =re .search (r'Неделя (\d+)',date_str )
            if match :
                return int (match .group (1 ))

                # Для есяцев
        months =["январь","февраль","арт","апрель","ай","июнь",
        "июль","август","сентябрь","октябрь","ноябрь","декабрь"]
        for i ,month in enumerate (months ):
            if month in date_str .lower ():
                return i 

                # Для кварталов
        if "Q"in date_str :
            import re 
            match =re .search (r'Q(\d+)',date_str )
            if match :
                return int (match .group (1 ))

                # Для годов
        if date_str .isdigit ():
            return int (date_str )

        return 0 

    def _extract_sort_key (self ,date_str ):
        """Извлекает числовой ключ для сортировки группированных дат"""
        if "Неделя"in date_str :
        # звлекае ноер недели
            import re 
            match =re .search (r'Неделя (\d+)',date_str )
            if match :
                return int (match .group (1 ))
        elif "есяц"in date_str .lower ()or any (month in date_str for month in ["январь","февраль","арт","апрель","ай","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"]):
        # Для есяцев - сортируе по порядку
            months =["январь","февраль","арт","апрель","ай","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"]
            for i ,month in enumerate (months ):
                if month in date_str .lower ():
                    return i 
        elif "Q"in date_str :
        # Для кварталов
            import re 
            match =re .search (r'Q(\d+)',date_str )
            if match :
                return int (match .group (1 ))
        return 0 

    def _apply_cell_formatting_to_item (self ,item ,col_name ,val ):
        """Применяет цветовое форматирование к элементу таблицы"""
        try :
            num_val =float (val )
        except :
            return 

            # ROMI
        if col_name =="ROMI":
            if num_val >10 :
                if num_val >50 :
                    color =QColor (30 ,150 ,30 )
                else :
                    green =120 +int (min (100 ,num_val ))
                    red =max (30 ,120 -int (num_val ))
                    blue =max (30 ,120 -int (num_val ))
                    color =QColor (red ,green ,blue )
                item .setBackground (color )
                item .setForeground (QColor (255 ,255 ,255 ))
            elif num_val <-10 :
                if num_val <-50 :
                    color =QColor (180 ,50 ,50 )
                else :
                    red =180 
                    green =80 +int (min (100 ,abs (num_val )))
                    blue =80 +int (min (100 ,abs (num_val )))
                    color =QColor (red ,green ,blue )
                item .setBackground (color )
                item .setForeground (QColor (255 ,255 ,255 ))

                # Расход %, Лиды %, CPL %
        elif col_name in ["Расход %","Лиды %","CPL %"]:
            if num_val >0 :
                if num_val <=100 :
                    ratio =num_val /100 
                    red =int (30 +30 *ratio )
                    green =int (100 +40 *ratio )
                    blue =int (30 +30 *ratio )
                else :
                    red =180 
                    green =60 
                    blue =60 
                color =QColor (red ,green ,blue )
                item .setBackground (color )
                item .setForeground (QColor (255 ,255 ,255 ))

    def _style_total_row_item (self ,item ):
        """Приводит ячейку строки ТОГО к единоу стилю."""
        font =item .font ()
        font .setBold (True )
        item .setFont (font )
        item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )
        item .setBackground (QColor ("#334155")if self .dark_mode else QColor ("#5b6c7d"))
        item .setForeground (QColor (255 ,255 ,255 ))

    def _restore_plan_column_colors (self ):
        """Восстанавливает цвета для плановых колонок после сортировки"""
        # Находи индексы плановых колонок
        plan_columns =["Расход %","Лиды %","CPL %","ROMI"]
        col_indices ={}

        for col in range (self .table .columnCount ()):
            header =self .table .horizontalHeaderItem (col )
            if header :
                col_name =header .text ()
                # Убираем стрелку
                for symbol in [" ▲"," "]:
                    if col_name .endswith (symbol ):
                        col_name =col_name [:-2 ]
                        break 
                if col_name in plan_columns :
                    col_indices [col_name ]=col 

        if not col_indices :
            return 

            # Восстанавливае цвета
        for row in range (self .table .rowCount ()):
            item =self .table .item (row ,0 )
            if item and item .text ()=="ТОГО":
                continue # Пропускае строку ТОГО, у не уже есть свой цвет

            for col_name ,col_idx in col_indices .items ():
                item =self .table .item (row ,col_idx )
                if item :
                # Парсим значение для определения цвета
                    text =item .text ()
                    try :
                        val =float (text .replace (',','.').replace ('%',''))
                        if col_name =="ROMI":
                            if val >10 :
                                if val >50 :
                                    color =QColor (30 ,150 ,30 )
                                else :
                                    green =120 +int (min (100 ,val ))
                                    red =max (30 ,120 -int (val ))
                                    blue =max (30 ,120 -int (val ))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                            elif val <-10 :
                                if val <-50 :
                                    color =QColor (180 ,50 ,50 )
                                else :
                                    red =180 
                                    green =80 +int (min (100 ,abs (val )))
                                    blue =80 +int (min (100 ,abs (val )))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                        elif col_name in ["Расход %","Лиды %","CPL %"]:
                            if val >0 :
                                if val <=100 :
                                    ratio =val /100 
                                    red =int (30 +30 *ratio )
                                    green =int (100 +40 *ratio )
                                    blue =int (30 +30 *ratio )
                                else :
                                    red =180 
                                    green =60 
                                    blue =60 
                                color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                    except :
                        pass 

    def apply_cell_coloring (self ,item ,col ,display_data ,row ):
        """Применяет цветовое форматирование для ячейки"""
        # ROMI
        if col =="ROMI":
            try :
                val =float (display_data .iloc [row ]["ROMI"])
                if not pd .isna (val ):
                    if val >10 :
                        if val >50 :
                            color =QColor (30 ,150 ,30 )
                        else :
                            green =120 +int (min (100 ,val ))
                            red =max (30 ,120 -int (val ))
                            blue =max (30 ,120 -int (val ))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
                    elif val <-10 :
                        if val <-50 :
                            color =QColor (180 ,50 ,50 )
                        else :
                            red =180 
                            green =80 +int (min (100 ,abs (val )))
                            blue =80 +int (min (100 ,abs (val )))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
                    elif -10 <=val <=10 :
                        ratio =(val +10 )/20 
                        red =200 
                        green =200 -int (100 *ratio )
                        blue =100 
                        color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # Расход %
        if col =="Расход %":
            try :
                val =float (display_data .iloc [row ]["Расход %"])
                if not pd .isna (val )and val >0 :
                    if val <=100 :
                        ratio =val /100 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # Лиды %
        if col =="Лиды %":
            try :
                val =float (display_data .iloc [row ]["Лиды %"])
                if not pd .isna (val )and val >0 :
                    if val >=100 :
                        ratio =min (1 ,(val -100 )/100 )if val >100 else 0 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # CPL %
        if col =="CPL %":
            try :
                val =float (display_data .iloc [row ]["CPL %"])
                if not pd .isna (val )and val >0 :
                    if val <=100 :
                        ratio =val /100 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 


    def apply_total_row_coloring (self ,item ,col ,val ):
        """Применяет цветовое форматирование для строки ТОГО"""
        if col =="ROMI":
            try :
                if not pd .isna (val ):
                    if val >10 :
                        if val >50 :
                            color =QColor (30 ,150 ,30 )
                        else :
                            green =120 +int (min (100 ,val ))
                            red =max (30 ,120 -int (val ))
                            blue =max (30 ,120 -int (val ))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
                    elif val <-10 :
                        if val <-50 :
                            color =QColor (180 ,50 ,50 )
                        else :
                            red =180 
                            green =80 +int (min (100 ,abs (val )))
                            blue =80 +int (min (100 ,abs (val )))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

    def calculate_total_row (self ,data ):
        """Вычисляет итоговую строку для данных"""
        if data .empty :
            return {}

        total_row ={}

        # Суируе числовые колонки
        numeric_cols =data .select_dtypes (include =['number']).columns 
        for col in numeric_cols :
            total_row [col ]=data [col ].sum ()

            # Пересчитывает процентные метрики на основе су
            # CTR = Суа кликов / Суа показов * 100
        if "Клики"in data .columns and "Показы"in data .columns :
            total_clicks =data ["Клики"].sum ()
            total_impressions =data ["Показы"].sum ()
            if total_impressions >0 :
                total_row ["CTR"]=(total_clicks /total_impressions )*100 
            else :
                total_row ["CTR"]=0 

                # CR1 = Сумма лидов / Суа кликов * 100
        if "Лиды"in data .columns and "Клики"in data .columns :
            total_leads =data ["Лиды"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CR1"]=(total_leads /total_clicks )*100 
            else :
                total_row ["CR1"]=0 

                # CPC = Сумма расходов / Суа кликов
        if "Расход"in data .columns and "Клики"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CPC"]=total_expense /total_clicks 
            else :
                total_row ["CPC"]=0 

                # CPL = Сумма расходов / Сумма лидов
        if "Расход"in data .columns and "Лиды"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CPL"]=total_expense /total_leads 
            else :
                total_row ["CPL"]=0 

                # CR2 = Суа продаж / Сумма лидов * 100
        if "Продажи"in data .columns and "Лиды"in data .columns :
            total_sales =data ["Продажи"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CR2"]=(total_sales /total_leads )*100 
            else :
                total_row ["CR2"]=0 

                # Ср.чек = Суа выручки / Суа продаж
        if "Выручка"in data .columns and "Продажи"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_sales =data ["Продажи"].sum ()
            if total_sales >0 :
                total_row ["Ср.чек"]=total_revenue /total_sales 
            else :
                total_row ["Ср.чек"]=0 

                # Маржа = Выручка - Расход
        if "Выручка"in data .columns and "Расход"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_expense =data ["Расход"].sum ()
            total_row ["Маржа"]=total_revenue -total_expense 

            # ROMI = (Выручка - Расход) / Расход * 100
        if "Выручка"in data .columns and "Расход"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_expense =data ["Расход"].sum ()
            if total_expense >0 :
                total_row ["ROMI"]=((total_revenue -total_expense )/total_expense )*100 
            else :
                total_row ["ROMI"]=-100 

                # Плановые итоги
        if "Расход план"in data .columns :
            total_row ["Расход план"]=data ["Расход план"].sum ()
        if "Лиды план"in data .columns :
            total_row ["Лиды план"]=data ["Лиды план"].sum ()

            # Пересчитывает CPL план
        if "Расход план"in total_row and "Лиды план"in total_row and total_row ["Лиды план"]>0 :
            total_row ["CPL план"]=total_row ["Расход план"]/total_row ["Лиды план"]

            # Проценты выполнения плана
        if "Расход"in total_row and "Расход план"in total_row and total_row ["Расход план"]>0 :
            total_row ["Расход %"]=(total_row ["Расход"]/total_row ["Расход план"])*100 
        if "Лиды"in total_row and "Лиды план"in total_row and total_row ["Лиды план"]>0 :
            total_row ["Лиды %"]=(total_row ["Лиды"]/total_row ["Лиды план"])*100 
        if "CPL"in total_row and "CPL план"in total_row and total_row ["CPL план"]>0 :
            total_row ["CPL %"]=(total_row ["CPL"]/total_row ["CPL план"])*100 

        return total_row 

    def on_header_clicked (self ,column ):
        """Сортировка при клике на заголовок"""
        col_name =self .table .horizontalHeaderItem (column ).text ()

        # Убираем стрелку
        for symbol in [" ▲"," "]:
            if col_name .endswith (symbol ):
                col_name =col_name [:-2 ]
                break 

                # Проверяет, ожно ли сортировать
        if col_name not in self .filtered_data .columns :
            return 

            # Меняе направление
        if self .sort_column ==col_name :
            self .sort_ascending =not self .sort_ascending 
        else :
            self .sort_column =col_name 
            self .sort_ascending =True 

        try :
        # Разделяе данные и ТОГО
            if "Дата"in self .filtered_data .columns :
                total_mask =self .filtered_data ["Дата"]=="ТОГО"
                total_rows =self .filtered_data [total_mask ].copy ()
                data_rows =self .filtered_data [~total_mask ].copy ()
            else :
                total_rows =pd .DataFrame ()
                data_rows =self .filtered_data .copy ()

                # Сортируе только данные (без ТОГО)
            data_rows =data_rows .sort_values (
            by =col_name ,
            ascending =self .sort_ascending 
            ).reset_index (drop =True )

            # Собирае: данные сначала, ТОГО в конце
            if not total_rows .empty :
                self .filtered_data =pd .concat ([data_rows ,total_rows ],ignore_index =True )
            else :
                self .filtered_data =data_rows 

                # Обновляет отображение
            self .update_table ()
            self .update_sort_indicators ()

        except Exception as e :
            self .log (f"Ошибка сортировки: {e }")

    def add_plan_columns (self ,df ):
        """Добавляет плановые колонки"""
        # Сначала проверяе, есть ли уже колонки
        if "Расход план"not in df .columns :
            df ["Расход план"]=0 
        if "Лиды план"not in df .columns :
            df ["Лиды план"]=0 
        if "CPL план"not in df .columns :
            df ["CPL план"]=0 
        if "Расход %"not in df .columns :
            df ["Расход %"]=0 
        if "Лиды %"not in df .columns :
            df ["Лиды %"]=0 
        if "CPL %"not in df .columns :
            df ["CPL %"]=0 

            # Преобразуем в числовые типы
        for col in ["Расход план","Лиды план","CPL план","Расход %","Лиды %","CPL %"]:
            if col in df .columns :
                df [col ]=pd .to_numeric (df [col ],errors ='coerce').fillna (0 )

    def _apply_plans_to_daily_data (self ):
        """Применяет планы к дневны данны"""
        if "Дата"not in self .filtered_data .columns :
            return 

            # Добавляе плановые колонки
        self .add_plan_columns (self .filtered_data )

        plans =self .plans_history .get (self .current_client ,{})
        if not plans :
            return 

        for idx in range (len (self .filtered_data )):
            date_val =self .filtered_data .iloc [idx ]["Дата"]

            if isinstance (date_val ,pd .Timestamp ):
                date_to_check =date_val .date ()
            else :
                try :
                    date_to_check =pd .to_datetime (date_val ).date ()
                except :
                    continue 

            for period_key ,plan in plans .items ():
                plan_from =plan ["period_from"]
                plan_to =plan ["period_to"]

                if plan_from <=date_to_check <=plan_to :
                    plan_days =(plan_to -plan_from ).days +1 
                    daily_budget =plan ["budget"]/plan_days 
                    daily_leads =plan ["leads"]/plan_days 

                    self .filtered_data .loc [idx ,"Расход план"]=daily_budget 
                    self .filtered_data .loc [idx ,"Лиды план"]=daily_leads 
                    self .filtered_data .loc [idx ,"CPL план"]=daily_budget /daily_leads if daily_leads >0 else 0 

                    if daily_budget >0 :
                        self .filtered_data .loc [idx ,"Расход %"]=round ((self .filtered_data .loc [idx ,"Расход"]/daily_budget )*100 ,2 )
                    if daily_leads >0 :
                        self .filtered_data .loc [idx ,"Лиды %"]=round ((self .filtered_data .loc [idx ,"Лиды"]/daily_leads )*100 ,2 )

                    actual_cpl =self .filtered_data .loc [idx ,"CPL"]if "CPL"in self .filtered_data .columns else 0 
                    plan_cpl =self .filtered_data .loc [idx ,"CPL план"]
                    if plan_cpl >0 :
                        self .filtered_data .loc [idx ,"CPL %"]=round ((actual_cpl /plan_cpl )*100 ,2 )

                    break 

    def _refill_table_with_sort (self ):
        """Перезаполняет таблицу с учето текущей сортировки"""
        if self .filtered_data .empty :
            return 

            # Получаем данные для отображения
        display_data =self .filtered_data .copy ()

        # ... здесь код заполнения таблицы (как в update_table, но без группировки)
        # Можно скопировать часть кода из update_table, которая заполняет таблицу

        # Обновляет KPI
        self .update_kpi ()

        # Синхронизируе ширину
        self .sync_all_table_columns_width ()

    def _refill_table_from_filtered_data (self ):
        """Перезаполняет таблицу из self.filtered_data без изенения данных"""
        if self .filtered_data .empty :
            return 

            # Создает копию для отображения
        display_data =self .filtered_data .copy ()

        # Форматируе дату для отображения
        if "Дата"in display_data .columns :
            if pd .api .types .is_datetime64_any_dtype (display_data ["Дата"]):
                display_data ["Дата"]=display_data ["Дата"].dt .strftime ("%d.%m.%Y")
            else :
                display_data ["Дата"]=display_data ["Дата"].astype (str )

                # Определяем порядок столбцов
        column_order =[
        "Дата",
        "Расход","Расход план","Расход %",
        "Показы","Клики","CPC","CTR",
        "Лиды","Лиды план","Лиды %",
        "CPL","CPL план","CPL %",
        "CR1","Продажи","CR2","Ср.чек","Выручка","Маржа","ROMI"
        ]

        # Если включено скрытие плана
        if self .hide_plan_checkbox .isChecked ():
            column_order =[col for col in column_order if col not in [
            "Расход план","Расход %",
            "Лиды план","Лиды %",
            "CPL план","CPL %"
            ]]

            # Оставляет только существующие столбцы
        visible_columns =[col for col in column_order if col in display_data .columns ]
        display_data =display_data [visible_columns ]

        # Очищае и настраивае таблицу
        self .table .clearContents ()
        self .table .setRowCount (0 )
        self .table .setColumnCount (len (display_data .columns ))
        self .table .setHorizontalHeaderLabels (self .base_headers )
        self .table .verticalHeader ().setVisible (False )

        # Заполняе данные
        for i in range (len (display_data )):
            self .table .insertRow (i )
            for j ,col in enumerate (display_data .columns ):
                value =display_data .iloc [i ][col ]

                if col =="Дата":
                    value =str (value )
                elif col in ["CTR","CR1","CR2","ROMI","Расход %","Лиды %","CPL %"]:
                    try :
                        val =float (value )
                        value =f"{val :.2f}".replace (".",",")
                    except :
                        value =str (value )
                else :
                    try :
                        num_value =float (value )
                        if num_value ==int (num_value ):
                            value =f"{int (num_value ):,}".replace (","," ")
                        else :
                            value =f"{num_value :,.2f}".replace (","," ").replace (".",",")
                    except (ValueError ,TypeError ):
                        value =str (value )

                item =QTableWidgetItem (str (value ))
                item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )
                self .table .setItem (i ,j ,item )


                # Обновляет KPI
        self .update_kpi ()

    def _refresh_display (self ):
        """Обновленное отображение таблицы"""
        if not hasattr (self ,'table')or self .filtered_data .empty :
            return 

            # Просто вызывае update_table, который уже все сделает правильно
        self .update_table ()


    def _apply_cell_formatting (self ,item ,col ,val ):
        """Применяет цветовое форматирование для ячейки"""
        # ROMI
        if col =="ROMI":
            try :
                val =float (val )
                if not pd .isna (val ):
                    if val >10 :
                        if val >50 :
                            color =QColor (30 ,150 ,30 )
                        else :
                            green =120 +int (min (100 ,val ))
                            red =max (30 ,120 -int (val ))
                            blue =max (30 ,120 -int (val ))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
                    elif val <-10 :
                        if val <-50 :
                            color =QColor (180 ,50 ,50 )
                        else :
                            red =180 
                            green =80 +int (min (100 ,abs (val )))
                            blue =80 +int (min (100 ,abs (val )))
                            color =QColor (red ,green ,blue )
                        item .setBackground (color )
                        item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # Расход %
        if col =="Расход %":
            try :
                val =float (val )
                if not pd .isna (val )and val >0 :
                    if val <=100 :
                        ratio =val /100 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # Лиды %
        if col =="Лиды %":
            try :
                val =float (val )
                if not pd .isna (val )and val >0 :
                    if val >=100 :
                        ratio =min (1 ,(val -100 )/100 )if val >100 else 0 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

                # CPL %
        if col =="CPL %":
            try :
                val =float (val )
                if not pd .isna (val )and val >0 :
                    if val <=100 :
                        ratio =val /100 
                        red =int (30 +30 *ratio )
                        green =int (100 +40 *ratio )
                        blue =int (30 +30 *ratio )
                    else :
                        red =180 
                        green =60 
                        blue =60 
                    color =QColor (red ,green ,blue )
                    item .setBackground (color )
                    item .setForeground (QColor (255 ,255 ,255 ))
            except :
                pass 

    def debug_sort_data (self ):
        """Выводит инфорацию о данных перед и после сортировки"""
        self .log ("\n=== ОТЛАДКА СОРТРОВК ===")

        # Проверяет filtered_data
        if hasattr (self ,'filtered_data')and not self .filtered_data .empty :
            self .log (f"filtered_data существует, строк: {len (self .filtered_data )}")
            self .log (f"Колонки: {self .filtered_data .columns .tolist ()}")
            self .log (f"Первые 3 строки filtered_data:")
            for i in range (min (3 ,len (self .filtered_data ))):
                self .log (f"  {self .filtered_data .iloc [i ].to_dict ()}")
        else :
            self .log ("filtered_data пуст или не существует")

            # Проверяет original_filtered_data
        if hasattr (self ,'original_filtered_data')and not self .original_filtered_data .empty :
            self .log (f"original_filtered_data существует, строк: {len (self .original_filtered_data )}")
        else :
            self .log ("original_filtered_data пуст или не существует")

            # Проверяет таблицу
        if hasattr (self ,'table')and self .table :
            self .log (f"Таблица иеет строк: {self .table .rowCount ()}")
            if self .table .rowCount ()>0 :
                self .log (f"Первая строка таблицы: {self .table .item (0 ,0 ).text ()if self .table .item (0 ,0 )else 'None'}")

        self .log ("=== КОНЕЦ ОТЛАДК ===\n")

    def update_sort_indicators (self ):
        """Обновляет заголовки и показывае стрелку сортировки"""
        if not hasattr (self ,"base_headers"):
            return 

        header =self .table .horizontalHeader ()
        header .setSortIndicatorShown (False )

        # Восстанавливае базовые тексты заголовков
        for col ,text in enumerate (self .base_headers ):
            item =self .table .horizontalHeaderItem (col )
            if item :
                if col ==getattr (self ,"current_sort_col",-1 ):
                    arrow ="▲"if self .sort_order ==Qt .SortOrder .AscendingOrder else ""
                    item .setText (f"{text } {arrow }")
                else :
                    item .setText (text )

    def debug_sorting (self ):
        """Отладочный метод для проверки сортировки"""
        self .log ("\n=== ОТЛАДКА СОРТРОВК ===")

        # Проверяет filtered_data
        if hasattr (self ,'filtered_data')and not self .filtered_data .empty :
            self .log (f"filtered_data строк: {len (self .filtered_data )}")
            self .log (f"Колонки в filtered_data: {self .filtered_data .columns .tolist ()}")

            # Проверяет наличие строки ТОГО
            if "Дата"in self .filtered_data .columns :
                total_exists =(self .filtered_data ["Дата"]=="ТОГО").any ()
                self .log (f"Строка ТОГО есть: {total_exists }")
                if total_exists :
                    total_row =self .filtered_data [self .filtered_data ["Дата"]=="ТОГО"]
                    self .log (f"Содержиое ТОГО: {total_row .iloc [0 ].to_dict ()if len (total_row )>0 else 'пусто'}")

                    # Выводим первые 3 строки
            self .log ("Первые 3 строки filtered_data:")
            for i in range (min (3 ,len (self .filtered_data ))):
                row =self .filtered_data .iloc [i ]
                self .log (f"  {i }: Дата={row .get ('Дата','НЕТ')}, Расход={row .get ('Расход',0 )}")
        else :
            self .log ("filtered_data пуст")

            # Проверяет таблицу
        if hasattr (self ,'table')and self .table :
            self .log (f"Таблица строк: {self .table .rowCount ()}")
            if self .table .rowCount ()>0 :
                self .log ("Первые 3 строки таблицы:")
                for i in range (min (3 ,self .table .rowCount ())):
                    item =self .table .item (i ,0 )
                    self .log (f"  {i }: {item .text ()if item else 'НЕТ'}")

        self .log ("=== КОНЕЦ ОТЛАДК СОРТРОВК ===\n")

    def debug_plan_columns (self ):
        """Отладочный метод для проверки плановых столбцов"""
        self .log ("\n=== ОТЛАДКА ПЛАНОВЫХ СТОЛЦОВ ===")

        # Проверяет filtered_data
        if hasattr (self ,'filtered_data')and not self .filtered_data .empty :
            plan_cols =["Расход план","Расход %","Лиды план","Лиды %","CPL план","CPL %"]
            existing =[col for col in plan_cols if col in self .filtered_data .columns ]
            missing =[col for col in plan_cols if col not in self .filtered_data .columns ]

            self .log (f"Существующие плановые колонки: {existing }")
            self .log (f"Отсутствующие плановые колонки: {missing }")

            if existing :
                self .log (f"Приер данных:")
                for col in existing [:3 ]:
                    self .log (f"  {col }: {self .filtered_data [col ].head (3 ).tolist ()}")
        else :
            self .log ("filtered_data пуст")

        self .log ("=== КОНЕЦ ОТЛАДК ПЛАНОВЫХ СТОЛЦОВ ===\n")

    def debug_date_format (self ):
        """Отладочный метод для проверки формата даты"""
        self .log ("\n=== ОТЛАДКА ФОРМАТА ДАТЫ ===")

        if hasattr (self ,'filtered_data')and not self .filtered_data .empty :
            if "Дата"in self .filtered_data .columns :
                self .log (f"Тип данных в колонке Дата: {self .filtered_data ['Дата'].dtype }")
                self .log (f"Первые 3 значения дат:")
                for i in range (min (3 ,len (self .filtered_data ))):
                    val =self .filtered_data .iloc [i ]["Дата"]
                    self .log (f"  {i }: {val } (тип: {type (val )})")

                    # Проверяет, есть ли врея
                sample =str (self .filtered_data .iloc [0 ]["Дата"])if len (self .filtered_data )>0 else ""
                if "00:00:00"in sample :
                    self .log ("ВНМАНЕ: В дате есть врея 00:00:00")
                else :
                    self .log ("Врея в дате отсутствует")
        else :
            self .log ("filtered_data пуст")

        self .log ("=== КОНЕЦ ОТЛАДК ФОРМАТА ДАТЫ ===\n")

    def debug_romi_width (self ):
        """Отладочный метод для проверки ширины ROMI"""
        self .log ("\n=== ОТЛАДКА ШРНЫ ROMI ===")

        if hasattr (self ,'table')and self .table :
        # Находи колонку ROMI
            romi_col =-1 
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    # Убираем стрелку
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name =="ROMI":
                        romi_col =col 
                        width =self .table .columnWidth (col )
                        self .log (f"Колонка ROMI найдена на позиции {col }, ширина: {width }px")
                        break 

            if romi_col ==-1 :
                self .log ("Колонка ROMI не найдена")

                # Находи колонку Выручка для сравнения
            revenue_col =-1 
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name =="Выручка":
                        revenue_col =col 
                        width =self .table .columnWidth (col )
                        self .log (f"Колонка Выручка на позиции {col }, ширина: {width }px")
                        break 

                        # Находи колонку Маржа для сравнения
            margin_col =-1 
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name =="Маржа":
                        margin_col =col 
                        width =self .table .columnWidth (col )
                        self .log (f"Колонка Маржа на позиции {col }, ширина: {width }px")
                        break 
        else :
            self .log ("Таблица не существует")

        self .log ("=== КОНЕЦ ОТЛАДК ШРНЫ ROMI ===\n")

    def update_table_preserve_colors (self ):
        """Обновляетт таблицу, сохраняя цвета в плановых колонках"""
        self .log ("\n=== update_table_preserve_colors ВЫЗВАН ===")

        # Сохраняе текущие цвета ячеек в плановых колонках
        saved_colors ={}

        if hasattr (self ,'table')and self .table .rowCount ()>0 :
        # Находи индексы плановых колонок
            plan_columns =["Расход %","Лиды %","CPL %"]
            col_indices ={}

            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    # Убираем стрелку
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name in plan_columns :
                        col_indices [col_name ]=col 
                        self .log (f"Найдена колонка {col_name } на позиции {col }")

                        # Сохраняе цвета и тексты для каждой ячейки в плановых колонках
            for row in range (self .table .rowCount ()):
                for col_name ,col_idx in col_indices .items ():
                    item =self .table .item (row ,col_idx )
                    if item :
                        key =(row ,col_name )
                        saved_colors [key ]={
                        "background":item .background ().color (),
                        "foreground":item .foreground ().color (),
                        "text":item .text ()
                        }
                        if row <3 :
                            fg =item .foreground ().color ()
                            self .log (f"Сохранен цвет для строка {row }, колонка {col_name }: текст=({fg .red ()},{fg .green ()},{fg .blue ()})")

            self .log (f"Сохранено {len (saved_colors )} цветов")

            # Обновляет таблицу обычны способо
        self .update_table ()

        # Восстанавливае цвета для плановых колонок
        if saved_colors :
        # Находи индексы колонок после обновления
            col_indices ={}
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name in ["Расход %","Лиды %","CPL %"]:
                        col_indices [col_name ]=col 

            restored_count =0 
            for (row ,col_name ),color_data in saved_colors .items ():
                if col_name in col_indices :
                    item =self .table .item (row ,col_indices [col_name ])
                    if item :
                        item .setBackground (color_data ["background"])
                        item .setForeground (color_data ["foreground"])
                        restored_count +=1 
                        if row <3 :
                            fg =color_data ["foreground"]
                            self .log (f"Восстановлен цвет для строка {row }, колонка {col_name }: текст=({fg .red ()},{fg .green ()},{fg .blue ()})")
                            # Убеждаеся, что текст не изенился
                        if color_data ["text"]!=item .text ():
                            item .setText (color_data ["text"])

            self .log (f"Восстановлено {restored_count } цветов")
        else :
            self .log ("Нет сохраненных цветов")

            # Обновляет таблицу обычны способо
        self .update_table ()

        # Восстанавливае цвета для плановых колонок
        if saved_colors :
        # Находи индексы колонок после обновления
            col_indices ={}
            for col in range (self .table .columnCount ()):
                header =self .table .horizontalHeaderItem (col )
                if header :
                    col_name =header .text ()
                    for symbol in [" ▲"," "]:
                        if col_name .endswith (symbol ):
                            col_name =col_name [:-2 ]
                            break 
                    if col_name in ["Расход %","Лиды %","CPL %"]:
                        col_indices [col_name ]=col 

            for (row ,col_name ),color_data in saved_colors .items ():
                if col_name in col_indices :
                    item =self .table .item (row ,col_indices [col_name ])
                    if item :
                        item .setBackground (color_data ["background"])
                        item .setForeground (color_data ["foreground"])
                        # Убеждаеся, что текст не изенился
                        if color_data ["text"]!=item .text ():
                            item .setText (color_data ["text"])

    def debug_table_colors (self ):
        """Выводит в лог инфорацию о цветах в таблице"""
        self .log ("\n=== ДЕАГ ЦВЕТОВ ТАЛЦЫ ===")

        if not hasattr (self ,'table')or self .table .rowCount ()==0 :
            self .log ("Таблица пуста")
            return 

            # Находи индексы плановых колонок
        plan_columns =["Расход %","Лиды %","CPL %"]
        col_indices ={}

        for col in range (self .table .columnCount ()):
            header =self .table .horizontalHeaderItem (col )
            if header :
                col_name =header .text ()
                # Убираем стрелку
                for symbol in [" ▲"," "]:
                    if col_name .endswith (symbol ):
                        col_name =col_name [:-2 ]
                        break 
                if col_name in plan_columns :
                    col_indices [col_name ]=col 
                    self .log (f"Найдена колонка {col_name } на позиции {col }")

        if not col_indices :
            self .log ("Плановые колонки не найдены")
            return 

            # Выводим инфорацию для первых 3 строк
        for row in range (min (3 ,self .table .rowCount ())):
            self .log (f"\n--- Строка {row } ---")
            for col_name ,col_idx in col_indices .items ():
                item =self .table .item (row ,col_idx )
                if item :
                    bg_color =item .background ().color ()
                    fg_color =item .foreground ().color ()
                    text =item .text ()
                    self .log (f"  {col_name }: текст='{text }', фон=({bg_color .red ()},{bg_color .green ()},{bg_color .blue ()}), текст=({fg_color .red ()},{fg_color .green ()},{fg_color .blue ()})")

                    # Также выводи инфорацию о строке ТОГО
        row_pos =self .table .rowCount ()-1 
        if row_pos >=0 :
            self .log (f"\n--- Строка ТОГО (строка {row_pos }) ---")
            for col_name ,col_idx in col_indices .items ():
                item =self .table .item (row_pos ,col_idx )
                if item :
                    bg_color =item .background ().color ()
                    fg_color =item .foreground ().color ()
                    text =item .text ()
                    self .log (f"  {col_name }: текст='{text }', фон=({bg_color .red ()},{bg_color .green ()},{bg_color .blue ()}), текст=({fg_color .red ()},{fg_color .green ()},{fg_color .blue ()})")

        self .log ("=== КОНЕЦ ДЕАГА ЦВЕТОВ ===\n")

    def display_empty_table (self ):
        """Отображает пустую таблицу"""
        if hasattr (self ,'table')and self .table :
            self .table .setSortingEnabled (False )
            self .table .clearContents ()
            self .table .setRowCount (0 )
            self .table .setColumnCount (0 )
            self .table .setHorizontalHeaderLabels ([])
            self .table .update ()

            # Обнуляе KPI
        for kpi ,label in self .kpi_labels .items ():
            label .setText ("0")

        self .log ("Отображена пустая таблица")

    def add_plan_columns (self ,df ):
        """Добавляет пустые плановые колонки"""
        df ["Расход план"]=0 
        df ["Лиды план"]=0 
        df ["CPL план"]=0 
        df ["Расход %"]=0 
        df ["Лиды %"]=0 
        df ["CPL %"]=0 

    def calculate_metrics_for_df (self ,df ):
        """Рассчитывает метрики для DataFrame с подробным логированием"""
        if df .empty :
            self .log ("DataFrame пуст, расчет метрик пропущен")
            return df 

        self .log ("\n"+"="*60 )
        self .log (f"РАСЧЕТ МЕТРИК ДЛЯ DATAFRAME")
        self .log (f"Количество строк: {len (df )}")
        self .log (f"Колонки: {df .columns .tolist ()}")
        self .log ("="*60 )

        # Показывае исходные данные
        self .log ("\n--- СХОДНЫЕ ДАННЫЕ (первые 3 строки) ---")
        for idx in range (min (3 ,len (df ))):
            row =df .iloc [idx ]
            self .log (f"Строка {idx }:")
            for col in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]:
                if col in df .columns :
                    self .log (f"  {col }: {row [col ]}")

                    # CTR = Клики / Показы * 100
        if "Клики"in df .columns and "Показы"in df .columns :
            self .log ("\n--- Расчет CTR ---")
            df ["CTR"]=df .apply (
            lambda row :(row ["Клики"]/row ["Показы"]*100 )if row ["Показы"]>0 else 0 ,
            axis =1 
            ).round (2 )
            self .log (f"CTR: {df ['CTR'].head (3 ).tolist ()}")

            # CR1 = Лиды / Клики * 100
        if "Лиды"in df .columns and "Клики"in df .columns :
            self .log ("\n--- Расчет CR1 ---")
            df ["CR1"]=df .apply (
            lambda row :(row ["Лиды"]/row ["Клики"]*100 )if row ["Клики"]>0 else 0 ,
            axis =1 
            ).round (2 )
            self .log (f"CR1: {df ['CR1'].head (3 ).tolist ()}")

            # CPC = Расход / Клики
        if "Расход"in df .columns and "Клики"in df .columns :
            self .log ("\n--- Расчет CPC ---")
            df ["CPC"]=df .apply (
            lambda row :round (row ["Расход"]/row ["Клики"])if row ["Клики"]>0 else 0 ,
            axis =1 
            ).astype (int )
            self .log (f"CPC: {df ['CPC'].head (3 ).tolist ()}")

            # CPL = Расход / Лиды
        if "Расход"in df .columns and "Лиды"in df .columns :
            self .log ("\n--- Расчет CPL ---")
            df ["CPL"]=df .apply (
            lambda row :round (row ["Расход"]/row ["Лиды"])if row ["Лиды"]>0 else 0 ,
            axis =1 
            ).astype (int )
            self .log (f"CPL: {df ['CPL'].head (3 ).tolist ()}")

            # Выручка = Продажи * Ср.чек
        if "Продажи"in df .columns and "Ср.чек"in df .columns :
            self .log ("\n--- Расчет ВЫРУЧК ---")
            self .log (f"Продажи (первые 3): {df ['Продажи'].head (3 ).tolist ()}")
            self .log (f"Ср.чек (первые 3): {df ['Ср.чек'].head (3 ).tolist ()}")
            df ["Выручка"]=df .apply (
            lambda row :row ["Продажи"]*row ["Ср.чек"]if row ["Ср.чек"]>0 else 0 ,
            axis =1 
            ).round (0 ).astype (int )
            self .log (f"Выручка (первые 3): {df ['Выручка'].head (3 ).tolist ()}")
            self .log (f"Суа выручки: {df ['Выручка'].sum ():,.0f}")

            # Маржа = Выручка - Расход
        if "Выручка"in df .columns and "Расход"in df .columns :
            self .log ("\n--- Расчет МАРЖ ---")
            self .log (f"Выручка (первые 3): {df ['Выручка'].head (3 ).tolist ()}")
            self .log (f"Расход (первые 3): {df ['Расход'].head (3 ).tolist ()}")
            df ["Маржа"]=df .apply (
            lambda row :row ["Выручка"]-row ["Расход"],
            axis =1 
            ).round (0 ).astype (int )
            self .log (f"Маржа (первые 3): {df ['Маржа'].head (3 ).tolist ()}")
            self .log (f"Суа аржи: {df ['Маржа'].sum ():,.0f}")

            # CR2 = Продажи / Лиды * 100
        if "Продажи"in df .columns and "Лиды"in df .columns :
            self .log ("\n--- Расчет CR2 ---")
            self .log (f"Продажи (первые 3): {df ['Продажи'].head (3 ).tolist ()}")
            self .log (f"Лиды (первые 3): {df ['Лиды'].head (3 ).tolist ()}")
            df ["CR2"]=df .apply (
            lambda row :(row ["Продажи"]/row ["Лиды"]*100 )if row ["Лиды"]>0 else 0 ,
            axis =1 
            ).round (2 )
            self .log (f"CR2 (первые 3): {df ['CR2'].head (3 ).tolist ()}")

            # ROMI = (Выручка - Расход) / Расход * 100
        if "Выручка"in df .columns and "Расход"in df .columns :
            self .log ("\n--- Расчет ROMI ---")
            self .log (f"Выручка (первые 3): {df ['Выручка'].head (3 ).tolist ()}")
            self .log (f"Расход (первые 3): {df ['Расход'].head (3 ).tolist ()}")
            df ["ROMI"]=df .apply (
            lambda row :((row ["Выручка"]-row ["Расход"])/row ["Расход"]*100 )if row ["Расход"]>0 else -100 ,
            axis =1 
            ).round (2 )
            self .log (f"ROMI (первые 3): {df ['ROMI'].head (3 ).tolist ()}")

        self .log ("\n"+"="*60 )
        self .log ("ТОГОВЫЕ ДАННЫЕ (первые 3 строки):")
        for col in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек","Выручка","Маржа","ROMI","CR2"]:
            if col in df .columns :
                self .log (f"  {col }: {df [col ].head (3 ).tolist ()}")
        self .log ("="*60 +"\n")

        return df 

    def add_total_row (self ):
        total_row =self .filtered_data .select_dtypes (include =['number']).sum ()

        for col in ["CTR","CR1","ROMI"]:
            if col in total_row .index :
                total_row [col ]=self .filtered_data [col ].mean ()

        if "CPL"in total_row .index :
            total_row ["CPL"]=self .filtered_data ["CPL"].mean ()
        if "CPC"in total_row .index :
            total_row ["CPC"]=self .filtered_data ["CPC"].mean ()

            # CR2 считае правильно: суа Лидов / суа Продаж
        total_leads =self .filtered_data [""].sum ()
        total_sales =self .filtered_data [""].sum ()
        if total_leads >0 :
            total_row ["CR2"]=(total_sales /total_leads )*100 
        else :
            total_row ["CR2"]=0 

        row_pos =self .table .rowCount ()
        self .table .insertRow (row_pos )

        for j ,col in enumerate (self .filtered_data .columns ):
            if col =="Дата":
                value ="ТОГО"
                item =QTableWidgetItem (value )
                font =item .font ()
                font .setBold (True )
                item .setFont (font )
                item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )
                self .table .setItem (row_pos ,j ,item )
            elif col in total_row .index :
                if col in ["CTR","CR1","CR2","ROMI"]:
                    value =f"{total_row [col ]:.2f}".replace (".",",")
                else :
                    value =f"{int (total_row [col ]):,}".replace (","," ")

                item =QTableWidgetItem (value )
                font =item .font ()
                font .setBold (True )
                item .setFont (font )
                item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )
                self .table .setItem (row_pos ,j ,item )

    def add_total_row_with_plan (self ,data ):
        """Добавляет строку ТОГО с плановыи столбцаи"""

        # Если уже есть строка ТОГО, не добавляе
        if "Дата"in data .columns and (data ["Дата"]=="ТОГО").any ():
            return 

            # Суируе числовые колонки
        total_row =data .select_dtypes (include =['number']).sum ()

        # Пересчитывает процентные метрики на основе сумм, а не средних

        # CTR = Суа кликов / Суа показов * 100
        if "Клики"in data .columns and "Показы"in data .columns :
            total_clicks =data ["Клики"].sum ()
            total_impressions =data ["Показы"].sum ()
            if total_impressions >0 :
                total_row ["CTR"]=(total_clicks /total_impressions )*100 
            else :
                total_row ["CTR"]=0 

                # CR1 = Сумма лидов / Суа кликов * 100
        if "Лиды"in data .columns and "Клики"in data .columns :
            total_leads =data ["Лиды"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CR1"]=(total_leads /total_clicks )*100 
            else :
                total_row ["CR1"]=0 

                # CPC = Сумма расходов / Суа кликов
        if "Расход"in data .columns and "Клики"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CPC"]=total_expense /total_clicks 
            else :
                total_row ["CPC"]=0 

                # CPL = Сумма расходов / Сумма лидов
        if "Расход"in data .columns and "Лиды"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CPL"]=total_expense /total_leads 
            else :
                total_row ["CPL"]=0 

                # CR2 = Суа продаж / Сумма лидов * 100
        if "Продажи"in data .columns and "Лиды"in data .columns :
            total_sales =data ["Продажи"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CR2"]=(total_sales /total_leads )*100 
            else :
                total_row ["CR2"]=0 

                # Ср.чек = Суа выручки / Суа продаж
        if "Выручка"in data .columns and "Продажи"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_sales =data ["Продажи"].sum ()
            if total_sales >0 :
                total_row ["Ср.чек"]=total_revenue /total_sales 
            else :
                total_row ["Ср.чек"]=0 

                # ROMI = (Суа выручки - Сумма расходов) / Сумма расходов * 100
        if "Выручка"in data .columns and "Расход"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_expense =data ["Расход"].sum ()
            if total_expense >0 :
                total_row ["ROMI"]=((total_revenue -total_expense )/total_expense )*100 
            else :
                total_row ["ROMI"]=-100 

                # Плановые итоги
        if "Расход план"in data .columns :
            total_row ["Расход план"]=data ["Расход план"].sum ()
        if "Лиды план"in data .columns :
            total_row ["Лиды план"]=data ["Лиды план"].sum ()

            # Пересчитывает CPL план
        if "Расход план"in total_row and "Лиды план"in total_row and total_row ["Лиды план"]>0 :
            total_row ["CPL план"]=total_row ["Расход план"]/total_row ["Лиды план"]

            # Проценты выполнения плана (пересчитывае на основе су)
        if "Расход"in total_row and "Расход план"in total_row and total_row ["Расход план"]>0 :
            total_row ["Расход %"]=(total_row ["Расход"]/total_row ["Расход план"])*100 
        if "Лиды"in total_row and "Лиды план"in total_row and total_row ["Лиды план"]>0 :
            total_row ["Лиды %"]=(total_row ["Лиды"]/total_row ["Лиды план"])*100 
        if "CPL"in total_row and "CPL план"in total_row and total_row ["CPL план"]>0 :
            total_row ["CPL %"]=(total_row ["CPL"]/total_row ["CPL план"])*100 

        row_pos =self .table .rowCount ()
        self .table .insertRow (row_pos )

        for j ,col in enumerate (data .columns ):
            if col =="Дата":
                value ="ТОГО"
                item =QTableWidgetItem (value )
                self ._style_total_row_item (item )
                self .table .setItem (row_pos ,j ,item )
            elif col in total_row .index :
                val =total_row [col ]
                if pd .isna (val ):
                    value ="0"
                elif col in ["CTR","CR1","CR2","ROMI","Расход %","Лиды %","CPL %"]:
                    value =f"{val :.2f}".replace (".",",")
                elif col in ["CPC","CPL","Ср.чек","CPL план"]:
                    value =f"{int (round (val )):,}".replace (","," ")
                else :
                    value =f"{int (round (val )):,}".replace (","," ")

                item =QTableWidgetItem (value )
                self ._style_total_row_item (item )
                self ._apply_cell_formatting_to_item (item ,col ,val )
                self .table .setItem (row_pos ,j ,item )

    def change_grouping (self ):
        """Смена группировки использует уже выбранный период без повторного Apply"""
        self .log (f"Смена группировки на: {self .group_combo .currentText ()}")
        self .update_dashboard ()

    def update_dimension_table (self ,dimension_name ):
        """Обновляетт таблицу для измерения (первоначальная загрузка)"""

        # Проверяет, есть ли данные для этого измерения
        if dimension_name not in self .data .columns :
        # Если нет данных, создает пустую таблицу
            empty_df =pd .DataFrame (columns =[dimension_name ,"Расход","Показы","Клики","CPC","CTR","Лиды","CPL","CR1","Продажи","CR2","Ср.чек","Выручка","Маржа","ROMI"])
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

            # Группируе по изерению без фильтра по дате (показывае все данные)
        grouped =self .data .groupby (dimension_name ).agg ({
        "Расход":"sum",
        "Показы":"sum",
        "Клики":"sum",
        "CPC":"mean",
        "CTR":"mean",
        "Лиды":"sum",
        "CPL":"mean",
        "CR1":"mean",
        "Продажи":"sum",
        "CR2":"mean",
        "Ср.чек":"mean",
        "Выручка":"sum",
        "Маржа":"sum",
        "ROMI":"mean"
        }).reset_index ()

        # Пересчитывает CR2
        for idx ,row in grouped .iterrows ():
            if row ["Лиды"]>0 :
                grouped .at [idx ,"CR2"]=(row ["Продажи"]/row ["Лиды"])*100 
            else :
                grouped .at [idx ,"CR2"]=0 
        grouped ["CR2"]=grouped ["CR2"].round (2 )

        self .dimension_data [dimension_name ]=grouped 
        self .dimension_sort_column [dimension_name ]=None 
        self .dimension_sort_ascending [dimension_name ]=True 

        self .display_dimension_table (dimension_name ,grouped )
        self .update_kpi ()

    def update_dimension_table_with_filter (self ,dimension_name ,from_date ,to_date ):
        """Обновляетт таблицу для измерения с учето фильтра по дата"""

        self .log (f"\n{'='*60 }")
        self .log (f"ОНОВЛЕНЕ ВКЛАДК: {dimension_name }")
        self .log (f"Период: {from_date } - {to_date }")
        self .log (f"{'='*60 }")

        # Проверяет, есть ли данные
        if self .data .empty :
            self .log ("Нет данных в self.data")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        self .log (f"Колонки в self.data: {self .data .columns .tolist ()}")
        self .log (f"Всего строк в self.data: {len (self .data )}")

        source_df =self .data .copy ()
        column_name =dimension_name 
        if dimension_name =="Тип":
            if "Medium"not in source_df .columns :
                source_df ["Medium"]="Не указано"
            source_df ["Medium"]=(
            source_df ["Medium"]
            .fillna ("Не указано")
            .astype (str )
            .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
            )
            column_name ="Medium"

            # Проверяет наличие колонки измерения
        if column_name not in source_df .columns :
            self .log (f"Колонка '{column_name }' не найдена в данных")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

            # Фильтруе данные по дате
        self .log (f"\n--- Фильтрация по дате ---")
        self .log (f"Диапазон дат в данных: {source_df ['Дата'].min ()} - {source_df ['Дата'].max ()}")

        filtered =source_df [
        (source_df ["Дата"]>=pd .Timestamp (from_date ))&
        (source_df ["Дата"]<=pd .Timestamp (to_date ))
        ]

        self .log (f"После фильтрации: {len (filtered )} строк")

        if filtered .empty :
            self .log ("Нет данных за выбранный период")
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

            # Убеждаеся, что выручка есть в данных
        if "Выручка"not in filtered .columns :
            self .log ("  ВНМАНЕ: Выручка отсутствует в данных! Пересчитывает...")
            filtered ["Выручка"]=filtered ["Продажи"]*filtered ["Ср.чек"]

            # Показывае уникальные значения измерения
        self .log (f"\n--- Уникальные значения {dimension_name } ---")
        unique_vals =filtered [column_name ].unique ()
        self .log (f"Всего уникальных: {len (unique_vals )}")
        self .log (f"Первые 10: {unique_vals [:10 ].tolist ()}")

        # Группируе данные по изерению
        self .log (f"\n--- Группировка по {dimension_name } ---")
        self .log (f"Колонки для агрегации: Расход, Показы, Клики, Лиды, Продажи, Выручка")

        agg_dict ={
        "Расход":"sum",
        "Показы":"sum",
        "Клики":"sum",
        "Лиды":"sum",
        "Продажи":"sum",
        "Выручка":"sum"# Суируе выручку
        }

        grouped =filtered .groupby (column_name ).agg (agg_dict ).reset_index ()
        if column_name !=dimension_name :
            grouped =grouped .rename (columns ={column_name :dimension_name })

            # Пересчитывает Ср.чек = Выручка / Продажи (средневзвешенный)
        grouped ["Ср.чек"]=grouped .apply (
        lambda row :round (row ["Выручка"]/row ["Продажи"])if row ["Продажи"]>0 else 0 ,
        axis =1 
        ).astype (int )

        self .log (f"После группировки: {len (grouped )} строк")
        self .log (f"Сумма расходов: {grouped ['Расход'].sum ():,.0f}")
        self .log (f"Сумма лидов: {grouped ['Лиды'].sum ():,.0f}")
        self .log (f"Суа продаж: {grouped ['Продажи'].sum ():,.0f}")
        self .log (f"Суа выручки: {grouped ['Выручка'].sum ():,.0f}")

        # Показывае данные до расчета метрик
        self .log (f"\n--- ДАННЫЕ ДО РАСЧЕТА МЕТРК ---")
        for idx in range (min (3 ,len (grouped ))):
            row =grouped .iloc [idx ]
            self .log (f"Строка {idx } - {dimension_name }: {row [dimension_name ]}")
            for col in ["Расход","Показы","Клики","Лиды","Продажи","Выручка","Ср.чек"]:
                if col in grouped .columns :
                    self .log (f"  {col }: {row [col ]:,.0f}")

                    # Рассчитывает метрики
        self .log (f"\n--- РАСЧЕТ МЕТРИК ДЛЯ {dimension_name } ---")
        grouped =self .calculate_dimension_metrics_fixed (grouped ,dimension_name )

        # Показывае результаты
        self .log (f"\n--- РЕЗУЛЬТАТЫ ПОСЛЕ РАСЧЕТА МЕТРК ---")
        for idx in range (min (3 ,len (grouped ))):
            row =grouped .iloc [idx ]
            self .log (f"Строка {idx } - {dimension_name }: {row [dimension_name ]}")
            for col in ["Расход","Выручка","Маржа","ROMI","CR2","Ср.чек"]:
                if col in grouped .columns :
                    self .log (f"  {col }: {row [col ]:,.0f}")

        self .log (f"\nТОГОВЫЕ СУММЫ ПО {dimension_name }:")
        self .log (f"  Расход: {grouped ['Расход'].sum ():,.0f}")
        self .log (f"  Выручка: {grouped ['Выручка'].sum ():,.0f}")
        self .log (f"  Маржа: {grouped ['Маржа'].sum ():,.0f}")
        self .log (f"  Лиды: {grouped ['Лиды'].sum ():,.0f}")
        self .log (f"  Продажи: {grouped ['Продажи'].sum ():,.0f}")
        self .log ("="*60 +"\n")

        self .dimension_raw_data [dimension_name ]=grouped .copy ()
        self .dimension_data [dimension_name ]=grouped .copy ()
        self .display_dimension_table (dimension_name ,grouped )

    def refresh_all_dimension_tabs (self ):
        """Обновляетт все вкладки с измерениями на основе текущих данных"""
        self .log ("\n=== Обновление вкладок с измерениями ===")

        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()

        # Список изерений, которые есть в данных
        dimension_mapping ={
        "Источник":"Источник",
        "Тип":"Medium",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза"
        }

        for display_name ,column_name in dimension_mapping .items ():
            self .log (f"\nОбработка {display_name } (колонка: {column_name })")

            # Проверяет, есть ли такая колонка в данных
            if hasattr (self ,'data')and self .data is not None and column_name in self .data .columns :
                self .log (f"  Колонка {column_name } найдена в данных")
                self .log (f"  Уникальные значения: {self .data [column_name ].unique ()[:10 ]}")

                # Фильтруе данные по дате
                filtered =self .data [
                (self .data ["Дата"]>=pd .Timestamp (from_date ))&
                (self .data ["Дата"]<=pd .Timestamp (to_date ))
                ]

                if filtered .empty :
                    self .log (f"  Нет данных за выбранный период")
                    empty_df =pd .DataFrame (columns =[display_name ])
                    self .dimension_data [display_name ]=empty_df 
                    self .display_dimension_table (display_name ,empty_df )
                    continue 

                    # Убеждаеся, что выручка есть в данных
                if "Выручка"not in filtered .columns :
                    self .log ("  ВНМАНЕ: Выручка отсутствует в данных! Пересчитывает...")
                    filtered ["Выручка"]=filtered ["Продажи"]*filtered ["Ср.чек"]
                    filtered ["Выручка"]=filtered ["Выручка"].round (0 ).astype (int )

                    # Группируе по изерению
                agg_dict ={
                "Расход":"sum",
                "Показы":"sum",
                "Клики":"sum",
                "Лиды":"sum",
                "Продажи":"sum",
                "Выручка":"sum"
                }

                grouped =filtered .groupby (column_name ).agg (agg_dict ).reset_index ()

                # Пересчитывает Ср.чек = Выручка / Продажи
                grouped ["Ср.чек"]=grouped .apply (
                lambda row :round (row ["Выручка"]/row ["Продажи"])if row ["Продажи"]>0 else 0 ,
                axis =1 
                ).astype (int )

                grouped =grouped .rename (columns ={column_name :display_name })

                # Выводим выручку по группа для проверки
                self .log (f"\n  --- ВЫРУЧКА ПО ГРУППАМ ---")
                total_check =0 
                for idx ,row in grouped .iterrows ():
                    self .log (f"    {display_name }: {row [display_name ]} -> Выручка: {row ['Выручка']:,.0f}, Ср.чек: {row ['Ср.чек']:,.0f}")
                    total_check +=row ['Выручка']
                self .log (f"  Общая суа выручки: {total_check :,.0f}")

                # Рассчитывает остальные метрики
                grouped =self .calculate_dimension_metrics_fixed (grouped ,display_name )

                self .log (f"  Сгруппировано: {len (grouped )} строк")

                self .dimension_data [display_name ]=grouped 
                self .display_dimension_table (display_name ,grouped )
            else :
                self .log (f"  Колонка {column_name } НЕ найдена в данных")
                empty_df =pd .DataFrame (columns =[display_name ])
                self .dimension_data [display_name ]=empty_df 
                self .display_dimension_table (display_name ,empty_df )

    def display_dimension_table (self ,dimension_name ,data ):
        """Отображает таблицу для измерения"""
        self .log (f"Отображае {dimension_name }, строк: {len (data )if data is not None else 0 }")

        table =self .dimension_tables [dimension_name ]

        if data is None or len (data )==0 :
            table .clearContents ()
            table .setRowCount (0 )
            table .setColumnCount (0 )
            table .setHorizontalHeaderLabels ([])
            table .update ()
            return 

            # Порядок столбцов
        column_order =[dimension_name ,"Расход","Показы","Клики","CPC","CTR",
        "Лиды","CPL","CR1","Продажи","CR2","Ср.чек",
        "Выручка","Маржа","ROMI"]

        # Оставляет только существующие столбцы
        visible_columns =[col for col in column_order if col in data .columns ]
        data_display =data [visible_columns ]

        # локируе сигналы, чтобы избежать рекурсии
        table .blockSignals (True )

        table .clearContents ()
        table .setRowCount (0 )
        table .setColumnCount (len (data_display .columns ))
        table .setHorizontalHeaderLabels (data_display .columns )
        table .verticalHeader ().setVisible (False )

        # Заполняе данные
        for i in range (len (data_display )):
            table .insertRow (i )
            for j ,col in enumerate (data_display .columns ):
                value =data_display .iloc [i ][col ]

                if col ==dimension_name :
                    value =str (value )
                elif col in ["CTR","CR1","CR2","ROMI"]:
                    try :
                        val =float (value )
                        value =f"{val :.2f}".replace (".",",")
                    except :
                        value =str (value )
                else :
                    try :
                        num_value =float (value )
                        if num_value ==int (num_value ):
                            value =f"{int (num_value ):,}".replace (","," ")
                        else :
                            value =f"{num_value :,.2f}".replace (","," ").replace (".",",")
                    except (ValueError ,TypeError ):
                        value =str (value )

                item =QTableWidgetItem (str (value ))
                item .setTextAlignment (Qt .AlignmentFlag .AlignCenter )

                # ===== ЦВЕТОВОЕ ФОРМАТРОВАНЕ ROMI ДЛЯ ВКЛАДОК =====
                if col =="ROMI":
                    try :
                        val =float (data_display .iloc [i ][col ])
                        if not pd .isna (val ):
                            if val >10 :
                                if val >50 :
                                    color =QColor (30 ,150 ,30 )
                                else :
                                    green =120 +int (min (100 ,val ))
                                    red =max (30 ,120 -int (val ))
                                    blue =max (30 ,120 -int (val ))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                            elif val <-10 :
                                if val <-50 :
                                    color =QColor (180 ,50 ,50 )
                                else :
                                    red =180 
                                    green =80 +int (min (100 ,abs (val )))
                                    blue =80 +int (min (100 ,abs (val )))
                                    color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                            elif -10 <=val <=10 :
                                ratio =(val +10 )/20 
                                red =200 
                                green =200 -int (100 *ratio )
                                blue =100 
                                color =QColor (red ,green ,blue )
                                item .setBackground (color )
                                item .setForeground (QColor (255 ,255 ,255 ))
                    except :
                        pass 

                table .setItem (i ,j ,item )

                # Добавляе строку ТОГО
        self .add_total_row_dimension (table ,data_display ,dimension_name )

        self .sync_all_table_columns_width ()

        # Разблокируе сигналы
        table .blockSignals (False )

        # Принудительная перерисовка
        table .viewport ().update ()
        table .update ()
        table .repaint ()

    def _apply_plans_to_daily_data (self ):
        """Применяет планы к дневны данны"""
        if "Дата"not in self .filtered_data .columns :
            return 

            # Добавляе плановые колонки
        self .add_plan_columns (self .filtered_data )

        plans =self .plans_history .get (self .current_client ,{})
        if not plans :
            return 

        for idx in range (len (self .filtered_data )):
            date_val =self .filtered_data .iloc [idx ]["Дата"]

            if isinstance (date_val ,pd .Timestamp ):
                date_to_check =date_val .date ()
            else :
                try :
                    date_to_check =pd .to_datetime (date_val ).date ()
                except :
                    continue 

            for period_key ,plan in plans .items ():
                plan_from =plan ["period_from"]
                plan_to =plan ["period_to"]

                if plan_from <=date_to_check <=plan_to :
                    plan_days =(plan_to -plan_from ).days +1 
                    daily_budget =plan ["budget"]/plan_days 
                    daily_leads =plan ["leads"]/plan_days 

                    self .filtered_data .loc [idx ,"Расход план"]=daily_budget 
                    self .filtered_data .loc [idx ,"Лиды план"]=daily_leads 
                    self .filtered_data .loc [idx ,"CPL план"]=daily_budget /daily_leads if daily_leads >0 else 0 

                    if daily_budget >0 :
                        self .filtered_data .loc [idx ,"Расход %"]=round ((self .filtered_data .loc [idx ,"Расход"]/daily_budget )*100 ,2 )
                    if daily_leads >0 :
                        self .filtered_data .loc [idx ,"Лиды %"]=round ((self .filtered_data .loc [idx ,"Лиды"]/daily_leads )*100 ,2 )

                    actual_cpl =self .filtered_data .loc [idx ,"CPL"]if "CPL"in self .filtered_data .columns else 0 
                    plan_cpl =self .filtered_data .loc [idx ,"CPL план"]
                    if plan_cpl >0 :
                        self .filtered_data .loc [idx ,"CPL %"]=round ((actual_cpl /plan_cpl )*100 ,2 )

                    break 

    def apply_all_filters (self ):
        """Применяет фильтры к данны - перенаправляет на update_dashboard"""
        self .update_dashboard ()
        selected =self .get_selected_filters ()
        self .log (f"\n=== ПРМЕНЕНЕ ФИЛЬТРОВ ===")
        self .log (f"Выбранные фильтры:")
        for filter_name ,values in selected .items ():
            if values :
                self .log (f"  {filter_name }: {values [:5 ]}... (всего {len (values )})")
            else :
                self .log (f"  {filter_name }: НЧЕГО НЕ ВЫРАНО (все данные будут исключены)")

                # Получаем текущий период
        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        self .log (f"Период: {from_date } - {to_date }")

        # Получаем код периода для группировки
        period_code =self .get_current_period_code ()
        self .log (f"Период группировки: {period_code }")

        # Получаем выбранные фильтры
        filters_dict =self .get_current_filters_dict ()

        # ===== ПРМЕНЯЕМ ФЛЬТРЫ К ОСНОВНОЙ ТАЛЦЕ =====
        if self .original_data .empty :
            self .log ("Нет исходных данных")
            self .filtered_data =pd .DataFrame ()
            self .update_table ()
            return 

            # Фильтруе данные по дате
        filtered_by_date =self .original_data [
        (self .original_data ["Дата"].dt .date >=from_date )&
        (self .original_data ["Дата"].dt .date <=to_date )
        ]

        if filtered_by_date .empty :
            self .log ("Нет данных за выбранный период")
            self .filtered_data =pd .DataFrame ()
            self .update_table ()
            return 

            # Приеняе фильтры по измерения
        filtered_data =filtered_by_date .copy ()

        for column_name ,filter_value in filters_dict .items ():
            if column_name in filtered_data .columns :
                if isinstance (filter_value ,list ):
                # Если несколько значений
                    filtered_data =filtered_data [filtered_data [column_name ].isin (filter_value )]
                    self .log (f"  Приенен фильтр {column_name }: {len (filtered_data )} строк")
                else :
                # Если одно значение
                    filtered_data =filtered_data [filtered_data [column_name ]==filter_value ]
                    self .log (f"  Приенен фильтр {column_name }={filter_value }: {len (filtered_data )} строк")

        if filtered_data .empty :
            self .log ("После приенения фильтров нет данных")
            self .filtered_data =pd .DataFrame ()
            self .update_table ()
            return 

            # Группируе по вреени с помощью resample
            # Для дневной группировки ииспользует обычную группировку по дате
        if period_code =="D":
        # Группируе по дате
            grouped =filtered_data .groupby ("Дата").agg ({
            "Расход":"sum",
            "Показы":"sum",
            "Клики":"sum",
            "Лиды":"sum",
            "Продажи":"sum",
            "Выручка":"sum"
            }).reset_index ()
        else :
        # использует resample для недель, есяцев и т.д.
        # Создает копию и устанавливает дату как индекс
            temp_df =filtered_data .copy ()
            temp_df ["Дата"]=pd .to_datetime (temp_df ["Дата"])
            temp_df .set_index ("Дата",inplace =True )

            # Агрегируе
            agg_dict ={
            "Расход":"sum",
            "Показы":"sum",
            "Клики":"sum",
            "Лиды":"sum",
            "Продажи":"sum",
            "Выручка":"sum"
            }

            grouped =temp_df .resample (period_code ).agg (agg_dict ).fillna (0 ).reset_index ()

            # Пересчитывает метрики
        if "Клики"in grouped .columns and "Показы"in grouped .columns :
            grouped ["CTR"]=(grouped ["Клики"]/grouped ["Показы"]*100 ).round (2 ).fillna (0 )

        if "Лиды"in grouped .columns and "Клики"in grouped .columns :
            grouped ["CR1"]=(grouped ["Лиды"]/grouped ["Клики"]*100 ).round (2 ).fillna (0 )

        if "Расход"in grouped .columns and "Клики"in grouped .columns :
            grouped ["CPC"]=(grouped ["Расход"]/grouped ["Клики"]).round (0 ).fillna (0 ).astype (int )

        if "Расход"in grouped .columns and "Лиды"in grouped .columns :
            grouped ["CPL"]=(grouped ["Расход"]/grouped ["Лиды"]).round (0 ).fillna (0 ).astype (int )

        if "Продажи"in grouped .columns and "Лиды"in grouped .columns :
            grouped ["CR2"]=(grouped ["Продажи"]/grouped ["Лиды"]*100 ).round (2 ).fillna (0 )

        if "Выручка"in grouped .columns and "Продажи"in grouped .columns :
            grouped ["Ср.чек"]=(grouped ["Выручка"]/grouped ["Продажи"]).round (0 ).fillna (0 ).astype (int )

        if "Выручка"in grouped .columns and "Расход"in grouped .columns :
            grouped ["Маржа"]=(grouped ["Выручка"]-grouped ["Расход"]).round (0 ).astype (int )
            grouped ["ROMI"]=((grouped ["Выручка"]-grouped ["Расход"])/grouped ["Расход"]*100 ).round (2 ).fillna (-100 )

            # Форматируе дату для отображения
        if period_code =="D":
            grouped ["Дата"]=grouped ["Дата"].dt .strftime ("%d.%m.%Y")
        elif period_code =="W":
        # Форматируе недели
            grouped ["Дата"]="Неделя "+grouped ["Дата"].dt .isocalendar ().week .astype (str )+" ("+grouped ["Дата"].dt .year .astype (str )+")"
        elif period_code =="M":
            grouped ["Дата"]=grouped ["Дата"].dt .strftime ("%B %Y")
        elif period_code =="Q":
            grouped ["Дата"]="Q"+grouped ["Дата"].dt .quarter .astype (str )+" "+grouped ["Дата"].dt .year .astype (str )
        elif period_code =="Y":
            grouped ["Дата"]=grouped ["Дата"].dt .year .astype (str )

            # Сохраняе данные
        self .filtered_data =grouped 
        self .original_filtered_data =grouped .copy ()
        self .chart_data =grouped .copy ()

        # нициализируе плановые столбцы
        self .filtered_data =self .initialize_plan_columns (self .filtered_data )

        self .log (f"После фильтрации и группировки: {len (self .filtered_data )} строк")

        # ===== ОНОВЛЯЕМ ВКЛАДК С ЗМЕРЕНЯМ =====
        # Для вкладок с измерениями ииспользует ту же логику, но без группировки по вреени
        for dim_name in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            self .update_dimension_table_with_filter (dim_name ,from_date ,to_date )

            # Обновляет основную таблицу
        self .update_table ()

        # Обновляет KPI для текущей вкладки
        current_tab =self .tabs .tabText (self .tabs .currentIndex ())
        self .log (f"\n=== ОНОВЛЕНЕ KPI ДЛЯ ВКЛАДК: {current_tab } ===")
        self .update_kpi_for_current_tab (current_tab )

        # Обновляет график
        self .update_chart ()

        self .log ("=== ПРМЕНЕНЕ ФИЛЬТРОВ ЗАВЕРШЕНО ===\n")

    def initialize_plan_columns (self ,df ):
        """нициализирует плановые столбцы в DataFrame"""
        # Создает плановые колонки если их нет
        for col in ["Расход план","Лиды план","CPL план","Расход %","Лиды %","CPL %"]:
            if col not in df .columns :
                df [col ]=0.0 

                # Если есть планы в истории, заполняе значения
        if self .current_client in self .plans_history and self .plans_history [self .current_client ]:
        # Создает дневные планы
            daily_plans ={}
            for period_key ,plan in self .plans_history [self .current_client ].items ():
                plan_from =plan ["period_from"]
                plan_to =plan ["period_to"]
                if plan_from and plan_to :
                    plan_days =(plan_to -plan_from ).days +1 
                    daily_budget =plan ["budget"]/plan_days 
                    daily_leads =plan ["leads"]/plan_days 
                    daily_cpl =daily_budget /daily_leads if daily_leads >0 else 0 

                    current_date =plan_from 
                    while current_date <=plan_to :
                        daily_plans [current_date ]={
                        "budget":daily_budget ,
                        "leads":daily_leads ,
                        "cpl":daily_cpl 
                        }
                        current_date +=timedelta (days =1 )

                        # Заполняе плановые значения для каждой строки
            for idx in range (len (df )):
            # Проверяет, есть ли колонка Дата и она datetime
                if "Дата"not in df .columns :
                    continue 

                date_val =df .iloc [idx ]["Дата"]
                if isinstance (date_val ,pd .Timestamp ):
                    date_to_check =date_val .date ()
                else :
                    try :
                        date_to_check =pd .to_datetime (date_val ).date ()
                    except :
                        continue 

                if date_to_check in daily_plans :
                    plan =daily_plans [date_to_check ]
                    df .loc [idx ,"Расход план"]=plan ["budget"]
                    df .loc [idx ,"Лиды план"]=plan ["leads"]
                    df .loc [idx ,"CPL план"]=plan ["cpl"]

                    # Рассчитывает проценты выполнения
                    if plan ["budget"]>0 :
                        actual_expense =df .loc [idx ,"Расход"]if "Расход"in df .columns else 0 
                        df .loc [idx ,"Расход %"]=round ((actual_expense /plan ["budget"])*100 ,2 )
                    if plan ["leads"]>0 :
                        actual_leads =df .loc [idx ,"Лиды"]if "Лиды"in df .columns else 0 
                        df .loc [idx ,"Лиды %"]=round ((actual_leads /plan ["leads"])*100 ,2 )
                    if plan ["cpl"]>0 :
                        actual_cpl =df .loc [idx ,"CPL"]if "CPL"in df .columns else 0 
                        df .loc [idx ,"CPL %"]=round ((actual_cpl /plan ["cpl"])*100 ,2 )

        return df 

    def filter_search_changed (self ,filter_name ,text ):
        """Фильтрует список по поисковоу запросу"""
        list_widget =self .filters_widgets [filter_name ]['list']
        filters_items =self .filters_widgets [filter_name ].get ('items',[])

        # Сохраняе текущие состояния всех элементов (не только видиых)
        if not hasattr (self ,'filter_states'):
            self .filter_states ={}
        if filter_name not in self .filter_states :
            self .filter_states [filter_name ]={}

            # Сохраняе состояния всех элементов из текущего списка
        for i in range (list_widget .count ()):
            item =list_widget .item (i )
            if item is not None :# Добавляе проверку
                self .filter_states [filter_name ][item .text ()]=item .checkState ()

                # Очищае и перезаполняе с учето поиска
        list_widget .clear ()
        for item_text in filters_items :
            if text .lower ()in item_text .lower ():
                item =QListWidgetItem (item_text )
                item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                # Восстанавливае сохраненное состояние или стави Checked по уолчанию
                if filter_name in self .filter_states and item_text in self .filter_states [filter_name ]:
                    item .setCheckState (self .filter_states [filter_name ][item_text ])
                else :
                    item .setCheckState (Qt .CheckState .Checked )
                list_widget .addItem (item )

        list_widget .itemChanged .connect (lambda item ,name =filter_name :self .filter_item_changed (name ))

    def on_filter_search (self ,filter_name ,text ,list_widget ):
        """Обработчик поиска"""
        filters_items =self .filters_widgets [filter_name ].get ('items',[])

        # Сохраняе текущие состояния из списка в filter_states
        for i in range (list_widget .count ()):
            item =list_widget .item (i )
            if item is not None :# Добавляе проверку
                self .filter_states [filter_name ][item .text ()]=item .checkState ()

                # локируе сигналы
        list_widget .blockSignals (True )

        # Очищае и перезаполняе только элементы, подходящие под поиск
        list_widget .clear ()
        for item_text in filters_items :
            if text .lower ()in item_text .lower ():
                it =QListWidgetItem (item_text )
                it .setFlags (it .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                # ере состояние из filter_states
                it .setCheckState (self .filter_states [filter_name ].get (item_text ,Qt .CheckState .Unchecked ))
                list_widget .addItem (it )

                # Разблокируе сигналы
        list_widget .blockSignals (False )

        # Не вызывае apply_all_filters здесь

    def show_filter_popup (self ,filter_name ,popup ,button ):
        """Показывает выпадающее окно фильтра"""
        # Обновляет список перед показо (восстанавливает все элементы)
        self .refresh_filter_list (filter_name )

        # Позиционируе под кнопкой
        pos =button .mapToGlobal (button .rect ().bottomLeft ())
        popup .move (pos )
        popup .resize (button .width (),300 )
        popup .show ()

    def refresh_filter_list (self ,filter_name ):
        """Обновляетт список фильтра, показывая все элементы с сохраненныи состояниями"""
        # Получаем актуальные значения из self.filters_widgets[filter_name]['items']
        items =self .filters_widgets [filter_name ].get ('items',[])

        list_widget =self .filters_widgets [filter_name ]['list']
        search_edit =self .filters_widgets [filter_name ]['search']

        # Сохраняе текущий текст поиска
        search_text =search_edit .text ()

        # локируе сигналы
        list_widget .blockSignals (True )

        # Очищае и перезаполняе все элементы с учето поиска
        list_widget .clear ()
        for item_text in items :
            if search_text .lower ()in item_text .lower ():
                it =QListWidgetItem (item_text )
                it .setFlags (it .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                # ере состояние из filter_states
                state =self .filter_states .get (filter_name ,{}).get (item_text ,Qt .CheckState .Checked )
                it .setCheckState (state )
                list_widget .addItem (it )

                # Разблокируе сигналы
        list_widget .blockSignals (False )

    def select_all_items_filter (self ,filter_name ,select ):
        """Выбирает или сниает все пункты в списке фильтра"""
        list_widget =self .filters_widgets [filter_name ]['list']
        state =Qt .CheckState .Checked if select else Qt .CheckState .Unchecked 
        for i in range (list_widget .count ()):
            item =list_widget .item (i )
            if item is not None :# Добавляе проверку
                item .setCheckState (state )
        self .apply_all_filters ()

    def select_all_items (self ,list_widget ,select ):
        """Выбирает или сниает все пункты в списке"""
        state =Qt .CheckState .Checked if select else Qt .CheckState .Unchecked 
        for i in range (list_widget .count ()):
            item =list_widget .item (i )
            if item is not None :# Добавляе проверку
                item .setCheckState (state )

    def filter_item_changed (self ,filter_name ):
        """Вызывается при изенении любого чекбокса - обновляет дашборд"""
        self .log (f"\n=== ФЛЬТР ЗМЕНЕН: {filter_name } ===")

        # Сохраняе состояние в filter_states для всех элементов в списке
        if filter_name in self .filters_widgets :
            list_widget =self .filters_widgets [filter_name ]['list']
            for i in range (list_widget .count ()):
                item =list_widget .item (i )
                if item is not None :
                    self .filter_states [filter_name ][item .text ()]=item .checkState ()

                    # Если изенилась капания, обновляе список групп
        if filter_name =="Campaign"or filter_name =="Источник":
            self .update_dependent_filters ()

            # Обновляет дашборд
        self .update_dashboard ()

        self .auto_save_project ()
        self .log ("=== ОРАОТКА ФЛЬТРА ЗАВЕРШЕНА ===\n")

    def get_selected_filters (self ):
        """Возвращает словарь с выбранныи значенияи фильтров"""
        selected ={}

        # Маппинг названий фильтров для отображения
        display_names ={
        "Source":"Источник",
        "Medium":"Тип",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза"
        }

        self .log (f"\n=== ПОЛУЧЕНЕ ВЫРАННЫХ ФИЛЬТРОВ ===")
        for filter_key in self .filters_widgets :
            display_name =display_names .get (filter_key ,filter_key )

            if filter_key in self .filter_states :
                selected_items =[]
                for item_text ,state in self .filter_states [filter_key ].items ():
                    if state ==Qt .CheckState .Checked :
                        selected_items .append (item_text )
                selected [display_name ]=selected_items 
                self .log (f"  {display_name }: {selected_items [:5 ]}... (всего {len (selected_items )})")
            else :
                selected [display_name ]=[]
                self .log (f"  {display_name }: пусто")

                # Обновляет текст на кнопке
            button =self .filters_widgets [filter_key ]['button']
            total_items =len (self .filter_states .get (filter_key ,{}))

            if len (selected [display_name ])==0 :
                button .setText ("Ничего")
            elif len (selected [display_name ])==total_items :
                button .setText ("Все")
            else :
                button .setText (f"{len (selected [display_name ])} выбрано")

        return selected 

    def sync_all_table_columns_width (self ):
        """Устанавливает одинаковую ширину колонок, включая ROMI"""
        standard_width =95 
        date_width =110 
        header =self .table .horizontalHeader ()

        for i in range (self .table .columnCount ()):
            header_text =self .table .horizontalHeaderItem (i ).text ()
            if header_text =="Дата":
                header .resizeSection (i ,date_width )
            else :
                header .resizeSection (i ,standard_width )

                # Не растягивае последний столбец
        header .setStretchLastSection (False )

    def on_dimension_header_clicked (self ,dimension_name ,column ):
        """Сортировка при клике на заголовок во вкладках с измерениями"""
        table =self .dimension_tables [dimension_name ]
        data =self .dimension_data [dimension_name ]

        if data is None or data .empty :
            return 

            # Получаем ия колонки из заголовка таблицы (с учето возожной стрелки)
        col_name =table .horizontalHeaderItem (column ).text ()
        # Убираем стрелку
        for symbol in [" ▲"," "]:
            if col_name .endswith (symbol ):
                col_name =col_name [:-2 ]
                break 

                # Проверяет, существует ли такая колонка в данных
        if col_name not in data .columns :
            return 

        if self .dimension_sort_column [dimension_name ]==col_name :
            self .dimension_sort_ascending [dimension_name ]=not self .dimension_sort_ascending [dimension_name ]
        else :
            self .dimension_sort_column [dimension_name ]=col_name 
            self .dimension_sort_ascending [dimension_name ]=True 

        sorted_data =data .sort_values (
        by =col_name ,
        ascending =self .dimension_sort_ascending [dimension_name ]
        ).reset_index (drop =True )

        self .dimension_data [dimension_name ]=sorted_data 

        # Обновляет отображение
        self .display_dimension_table (dimension_name ,sorted_data )

        # Обновляет стрелочку
        self .update_dimension_sort_indicators (dimension_name ,col_name )

    def on_header_clicked (self ,column ):
        col_name =self .table .horizontalHeaderItem (column ).text ()

        # Убираем стрелку
        for symbol in [" ▲"," "]:
            if col_name .endswith (symbol ):
                col_name =col_name [:-2 ]
                break 

                # Проверяет, ожно ли сортировать
        if col_name not in self .filtered_data .columns :
            return 

            # Меняе направление
        if self .sort_column ==col_name :
            self .sort_ascending =not self .sort_ascending 
        else :
            self .sort_column =col_name 
            self .sort_ascending =True 

        try :
        # Разделяе данные и ТОГО
            if "Дата"in self .filtered_data .columns :
                total_mask =self .filtered_data ["Дата"]=="ТОГО"
                total_rows =self .filtered_data [total_mask ].copy ()
                data_rows =self .filtered_data [~total_mask ].copy ()
            else :
                total_rows =pd .DataFrame ()
                data_rows =self .filtered_data .copy ()

                # Сортируе данные
            data_rows =data_rows .sort_values (
            by =col_name ,
            ascending =self .sort_ascending 
            ).reset_index (drop =True )

            # Собирае: данные сначала, ТОГО в конце
            if not total_rows .empty :
                self .filtered_data =pd .concat ([data_rows ,total_rows ],ignore_index =True )
            else :
                self .filtered_data =data_rows 

                # Обновляет отображение
            self ._refresh_display ()

        except Exception as e :
            self .log (f"Ошибка сортировки: {e }")

    def update_dimension_sort_indicators (self ,dimension_name ,clicked_column_name ):
        """Обновляетт стрелочки в заголовках для вкладок с измерениями"""
        table =self .dimension_tables [dimension_name ]
        data =self .dimension_data [dimension_name ]

        if data is None or data .empty :
            return 

        for col in range (table .columnCount ()):
            col_name =table .horizontalHeaderItem (col ).text ()
            # Убираем стрелку для сравнения
            clean_name =col_name 
            for symbol in [" ▲"," "]:
                if clean_name .endswith (symbol ):
                    clean_name =clean_name [:-2 ]
                    break 

            if self .dimension_sort_column [dimension_name ]==clean_name :
                if self .dimension_sort_ascending [dimension_name ]:
                    table .horizontalHeaderItem (col ).setText (f"{clean_name } ▲")
                else :
                    table .horizontalHeaderItem (col ).setText (f"{clean_name } ")
            else :
                table .horizontalHeaderItem (col ).setText (clean_name )

    def add_total_row_dimension (self ,table ,data ,dimension_name ):
        """Добавляет строку ТОГО для вкладок с измерениями"""

        # Суируе числовые колонки
        total_row =data .select_dtypes (include =['number']).sum ()

        # Для процентных метрик пересчитывае на основе итоговых су
        # CTR = Суа кликов / Суа показов * 100
        if "Клики"in data .columns and "Показы"in data .columns :
            total_clicks =data ["Клики"].sum ()
            total_impressions =data ["Показы"].sum ()
            if total_impressions >0 :
                total_row ["CTR"]=(total_clicks /total_impressions )*100 
            else :
                total_row ["CTR"]=0 

                # CR1 = Сумма лидов / Суа кликов * 100
        if "Лиды"in data .columns and "Клики"in data .columns :
            total_leads =data ["Лиды"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CR1"]=(total_leads /total_clicks )*100 
            else :
                total_row ["CR1"]=0 

                # CPC = Сумма расходов / Суа кликов
        if "Расход"in data .columns and "Клики"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_clicks =data ["Клики"].sum ()
            if total_clicks >0 :
                total_row ["CPC"]=total_expense /total_clicks 
            else :
                total_row ["CPC"]=0 

                # CPL = Сумма расходов / Сумма лидов
        if "Расход"in data .columns and "Лиды"in data .columns :
            total_expense =data ["Расход"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CPL"]=total_expense /total_leads 
            else :
                total_row ["CPL"]=0 

                # CR2 = Суа продаж / Сумма лидов * 100
        if "Продажи"in data .columns and "Лиды"in data .columns :
            total_sales =data ["Продажи"].sum ()
            total_leads =data ["Лиды"].sum ()
            if total_leads >0 :
                total_row ["CR2"]=(total_sales /total_leads )*100 
            else :
                total_row ["CR2"]=0 

                # Ср.чек = Суа выручки / Суа продаж
        if "Выручка"in data .columns and "Продажи"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_sales =data ["Продажи"].sum ()
            if total_sales >0 :
                total_row ["Ср.чек"]=total_revenue /total_sales 
            else :
                total_row ["Ср.чек"]=0 

                # ROMI = (Суа выручки - Сумма расходов) / Сумма расходов * 100
        if "Выручка"in data .columns and "Расход"in data .columns :
            total_revenue =data ["Выручка"].sum ()
            total_expense =data ["Расход"].sum ()
            if total_expense >0 :
                total_row ["ROMI"]=((total_revenue -total_expense )/total_expense )*100 
            else :
                total_row ["ROMI"]=-100 

                # Выручка и Маржа уже суированы правильно через total_row

        row_pos =table .rowCount ()
        table .insertRow (row_pos )

        for j ,col in enumerate (data .columns ):
            if col ==dimension_name :
                value ="ТОГО"
                item =QTableWidgetItem (value )
                self ._style_total_row_item (item )
                table .setItem (row_pos ,j ,item )
            elif col in total_row .index :
                val =total_row [col ]
                if pd .isna (val ):
                    value ="0"
                elif col in ["CTR","CR1","CR2","ROMI"]:
                    value =f"{val :.2f}".replace (".",",")
                elif col in ["CPC","CPL","Ср.чек"]:
                    value =f"{int (round (val )):,}".replace (","," ")
                else :
                    value =f"{int (round (val )):,}".replace (","," ")

                item =QTableWidgetItem (value )
                self ._style_total_row_item (item )
                self ._apply_cell_formatting_to_item (item ,col ,val )
                table .setItem (row_pos ,j ,item )

    def update_chart (self ):
        if self .chart_data .empty :
            self .figure .clear ()
            ax =self .figure .add_subplot (111 )
            ax .text (0.5 ,0.5 ,"Нет данных",ha ='center',va ='center')
            self .canvas .draw ()
            return 

        metric =self .metric_combo .currentText ()
        group_type =self .chart_group_combo .currentText ()

        self .log (f"update_chart: metric={metric }, group_type={group_type }")

        if len (self .chart_data )==0 :
            self .figure .clear ()
            ax =self .figure .add_subplot (111 )
            ax .text (0.5 ,0.5 ,"Нет данных",ha ='center',va ='center')
            self .canvas .draw ()
            return 

        if metric not in self .chart_data .columns :
            return 

        data_copy =self .chart_data .copy ()

        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()

        grouped =self ._group_dashboard_periods (data_copy ,group_type ,from_date ,to_date )
        if grouped .empty or metric not in grouped .columns :
            return 

        if group_type =="день":
            if pd .api .types .is_datetime64_any_dtype (grouped ["Дата"]):
                dates =grouped ["Дата"].dt .strftime ("%d.%m.%Y")
            else :
                parsed_dates =self ._parse_date_series (grouped ["Дата"])
                if parsed_dates is not None and pd .api .types .is_datetime64_any_dtype (parsed_dates ):
                    dates =parsed_dates .dt .strftime ("%d.%m.%Y")
                else :
                    dates =grouped ["Дата"].astype (str )
        else :
            dates =grouped ["Дата"].astype (str )

        values =grouped [metric ]

        self .log (f"После группировки {group_type }: {dates .tolist ()}")
        self .log (f"Значения: {values .tolist ()}")

        self .figure .clear ()
        ax =self .figure .add_subplot (111 )

        if self .dark_mode :
            line_color ="#5dade2"
            fill_color ="#5dade2"
            face_color ="#20252b"
            grid_color ="#4b5563"
            text_color ="#e5edf5"
        else :
            line_color ="#2f80ed"
            fill_color ="#5aa2ff"
            face_color ="#f8fbff"
            grid_color ="#d7e3f1"
            text_color ="#2c3e50"

        ax .set_facecolor (face_color )
        self .figure .patch .set_facecolor (face_color )

        ax .plot (range (len (dates )),values ,marker ='o',linewidth =2.4 ,color =line_color ,markersize =7 )
        ax .fill_between (range (len (dates )),values ,alpha =0.18 ,color =fill_color )
        ax .set_xticks (range (len (dates )))
        ax .set_xticklabels (dates ,rotation =45 ,ha ='right',fontsize =9 )
        ax .set_title (f"{metric }",fontsize =12 ,fontweight ='bold',color =text_color ,pad =12 )
        ax .set_xlabel ("Период",color =text_color )
        ax .set_ylabel (metric ,color =text_color )
        ax .tick_params (axis ='x',colors =text_color )
        ax .tick_params (axis ='y',colors =text_color )
        ax .grid (True ,alpha =0.35 ,axis ='y',color =grid_color ,linestyle ='--',linewidth =0.8 )

        for spine in ax .spines .values ():
            spine .set_color (grid_color )
            spine .set_linewidth (1.0 )

        self .figure .tight_layout ()
        self .canvas .draw ()
        self .update_plan_display ()

    def update_kpi (self ):
        if self .filtered_data .empty :
            self .filtered_data =self .data .copy ()
        self .update_kpi_with_data (self .filtered_data )

    def update_plan_display (self ):
        """Обновление отображения плана в зависимости от текущей группировки"""
        self .log ("=== update_plan_display ВЫЗВАН ===")
        try :
        # Проверяет наличие лейблов
            if not hasattr (self ,'plan_budget_label')or not self .plan_budget_label :
                return 

                # Получаем текущую группировку
            current_group_type =self .group_combo .currentText ()
            self .log (f"current_group_type = {current_group_type }")

            # Получаем все планы для текущего клиента
            if self .current_client not in self .plans_history or not self .plans_history [self .current_client ]:
                self .log ("Нет планов для текущего клиента")
                self .plan_budget_label .setText ("юджет: —")
                self .plan_leads_label .setText ("Лиды: —")
                return 

            plans =self .plans_history [self .current_client ]
            self .log (f"Доступные планы: {list (plans .keys ())}")

            # Получаем данные для группировки
            if not hasattr (self ,'filtered_data')or self .filtered_data .empty :
                self .log ("Нет filtered_data")
                self .plan_budget_label .setText ("юджет: —")
                self .plan_leads_label .setText ("Лиды: —")
                return 

                # Получаем уникальные даты из отфильтрованных данных
            if hasattr (self ,'original_filtered_data')and not self .original_filtered_data .empty :
                source_data =self .original_filtered_data 
            else :
                source_data =self .filtered_data 

            self .log (f"Источник данных: {'original_filtered_data'if hasattr (self ,'original_filtered_data')and not self .original_filtered_data .empty else 'filtered_data'}")
            self .log (f"Количество строк в источнике: {len (source_data )}")

            # Получаем все даты в текуще периоде
            if 'Дата'not in source_data .columns :
                self .log ("Колонка 'Дата' отсутствует")
                self .plan_budget_label .setText ("юджет: —")
                self .plan_leads_label .setText ("Лиды: —")
                return 

                # ===== СПРАВЛЕННОЕ ПРЕОРАЗОВАНЕ ДАТ =====
            try :
            # Пробуем преобразовать с dayfirst=True
                current_dates =pd .to_datetime (source_data ['Дата'].unique (),errors ='coerce',dayfirst =True )
                # Удаляет NaT
                current_dates =current_dates [~pd .isna (current_dates )]
            except Exception as e :
                self .log (f"Ошибка преобразования дат: {e }")
                # Пробуем другой подход
                try :
                    current_dates =[]
                    for d in source_data ['Дата'].unique ():
                        try :
                            if isinstance (d ,str ):
                            # Парсим строку формата DD.MM.YYYY
                                day ,month ,year =d .split ('.')
                                current_dates .append (pd .Timestamp (year =int (year ),month =int (month ),day =int (day )))
                            elif isinstance (d ,pd .Timestamp ):
                                current_dates .append (d )
                        except :
                            pass 
                    current_dates =pd .Series (current_dates )
                except :
                    self .log ("Не удалось преобразовать даты")
                    self .plan_budget_label .setText ("юджет: —")
                    self .plan_leads_label .setText ("Лиды: —")
                    return 

            self .log (f"Уникальных дат в текуще периоде: {len (current_dates )}")
            if len (current_dates )>0 :
                self .log (f"Первые 5 дат: {current_dates [:5 ].tolist ()}")

                # Суируе планы по дня
            total_budget =0 
            total_leads =0 

            for single_date in current_dates :
                date_found =False 
                for period_key ,plan in plans .items ():
                    plan_from =plan ["period_from"]
                    plan_to =plan ["period_to"]

                    date_to_check =single_date .date ()if hasattr (single_date ,'date')else single_date 

                    if plan_from <=date_to_check <=plan_to :
                        plan_days =(plan_to -plan_from ).days +1 
                        daily_budget =plan ["budget"]/plan_days 
                        daily_leads =plan ["leads"]/plan_days 

                        total_budget +=daily_budget 
                        total_leads +=daily_leads 
                        date_found =True 
                        break 

                if not date_found :
                    self .log (f"  Дата {date_to_check }: план не найден")

            self .log (f"Суарный план за выбранный период: бюджет={total_budget :.0f}, лиды={total_leads :.0f}")

            # В зависимости от группировки, показывае соответствующее значение
            if current_group_type =='день':
                days_count =len (current_dates )
                if days_count >0 :
                    avg_budget =total_budget /days_count 
                    avg_leads =total_leads /days_count 
                    self .plan_budget_label .setText (f"юджет: {avg_budget :,.0f}")
                    self .plan_leads_label .setText (f"Лиды: {avg_leads :.0f}")
                else :
                    self .plan_budget_label .setText ("юджет: —")
                    self .plan_leads_label .setText ("Лиды: —")

            elif current_group_type in ['неделя','есяц','квартал','год']:
                self .plan_budget_label .setText (f"юджет: {total_budget :,.0f}")
                self .plan_leads_label .setText (f"Лиды: {total_leads :.0f}")
            else :
                self .plan_budget_label .setText (f"юджет: {total_budget :,.0f}")
                self .plan_leads_label .setText (f"Лиды: {total_leads :.0f}")

        except Exception as e :
            self .logger .error (f"Ошибка при обновлении отображения плана: {e }")
            import traceback 
            traceback .print_exc ()
            self .log (traceback .format_exc (),"error")
            if hasattr (self ,'plan_budget_label')and self .plan_budget_label :
                self .plan_budget_label .setText ("юджет: —")
            if hasattr (self ,'plan_leads_label')and self .plan_leads_label :
                self .plan_leads_label .setText ("Лиды: —")

    def get_current_period (self ):
        """Получение текущего периода из отфильтрованных данных"""
        if hasattr (self ,'filtered_data')and not self .filtered_data .empty :
            min_date =self .filtered_data ['Дата'].min ()
            max_date =self .filtered_data ['Дата'].max ()
            return (min_date ,max_date )
        return (None ,None )

    def on_tab_changed (self ,index ):
        """Обработчик переключения вкладок"""
        tab_text =self .tabs .tabText (index )
        self .log (f"\n=== ПЕРЕКЛЮЧЕНЕ НА ВКЛАДКУ: {tab_text } ===")
        self .update_kpi_for_current_tab (tab_text )

        if tab_text =="Дата":
            self .update_kpi_with_data (self .filtered_data )
            self .update_plan_display ()

        elif tab_text in ["????????????????","??????","????????????????","????????????","????????????????????","???????????????? ??????????"]:
            if tab_text in self .dimension_data and self .dimension_data [tab_text ]is not None :
                data =self .dimension_data [tab_text ]
                if len (data )>0 :
                # Создает агрегированные данные для KPI
                    kpi_data =pd .DataFrame ({
                    "Расход":[data ["Расход"].sum ()],
                    "Клики":[data ["Клики"].sum ()],
                    "Лиды":[data ["Лиды"].sum ()],
                    "Продажи":[data ["Продажи"].sum ()],
                    "Выручка":[data ["Выручка"].sum ()],
                    "Ср.чек":[data ["Ср.чек"].mean ()]
                    })
                    self .update_kpi_with_data (kpi_data )
                else :
                    empty_data =pd .DataFrame ({
                    "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
                    "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ]
                    })
                    self .update_kpi_with_data (empty_data )
            else :
                empty_data =pd .DataFrame ({
                "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
                "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ]
                })
                self .update_kpi_with_data (empty_data )

        elif tab_text =="__unused_type_tab_branch__":
            empty_data =pd .DataFrame ({
            "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
            "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ]
            })
            self .update_kpi_with_data (empty_data )

        elif tab_text in ["📈 Графики","📊 План"]:
            self .update_kpi_with_data (self .filtered_data )
            self .update_plan_display ()

    def update_kpi_with_data (self ,data ):
        """Обновляетт KPI на основе данных - исправленная версия"""
        if data is None or data .empty :
            return 

        if shared_calculate_kpi_metrics is not None and shared_format_kpi_values is not None :
            self .log (f"\n=== ОНОВЛЕНЕ KPI ===")
            self .log (f"Количество строк в данных: {len (data )}")

            metrics =shared_calculate_kpi_metrics (data )
            cost_value =metrics .get ("",metrics .get ("Расход",0 ))
            clicks_value =metrics .get ("",metrics .get ("Клики",0 ))
            leads_value =metrics .get ("",metrics .get ("Лиды",0 ))
            sales_value =metrics .get ("",metrics .get ("Продажи",0 ))
            revenue_value =metrics .get ("",metrics .get ("Выручка",0 ))
            avg_check_value =metrics .get (".",metrics .get ("Ср.чек",0 ))
            margin_value =metrics .get ("",metrics .get ("Маржа",0 ))
            self .log (f"\n---  KPI ---")
            self .log (f": {cost_value :,.0f}")
            self .log (f": {clicks_value :,.0f}")
            self .log (f": {leads_value :,.0f}")
            self .log (f": {sales_value :,.0f}")
            self .log (f": {revenue_value :,.0f}")
            self .log (f"CPL: {metrics ['CPL']:,.0f}")
            self .log (f"CR1: {metrics ['CR1']:.2f}%")
            self .log (f"CR2: {metrics ['CR2']:.2f}%")
            self .log (f".: {avg_check_value :,.0f}")
            self .log (f": {margin_value :,.0f}")
            self .log (f"ROMI: {metrics ['ROMI']:.2f}%")
            kpi_values =shared_format_kpi_values (metrics )
            for kpi ,value in kpi_values .items ():
                if kpi in self .kpi_labels :
                    self .kpi_labels [kpi ].setText (value )
                    self .log (f"  {kpi }: {value }")

            self .log ("="*40 )
            return 

        self .log (f"\n=== ОНОВЛЕНЕ KPI ===")
        self .log (f"Количество строк в данных: {len (data )}")

        #     
        total_cost =data [""].sum ()if ""in data .columns else 0 
        total_clicks =data [""].sum ()if ""in data .columns else 0 
        total_leads =data [""].sum ()if ""in data .columns else 0 
        total_sales =data [""].sum ()if ""in data .columns else 0 
        total_revenue =data [""].sum ()if ""in data .columns else 0 

        #  
        if total_leads >0 :
            avg_cpl =total_cost /total_leads 
        else :
            avg_cpl =0 

        if total_clicks >0 :
            avg_cr1 =(total_leads /total_clicks )*100 
        else :
            avg_cr1 =0 

        if total_leads >0 :
            avg_cr2 =(total_sales /total_leads )*100 
        else :
            avg_cr2 =0 

        if total_sales >0 :
            avg_avg_check =total_revenue /total_sales 
        else :
            avg_avg_check =0 

        total_margin =total_revenue -total_cost 

        if total_cost >0 :
            avg_romi =((total_revenue -total_cost )/total_cost )*100 
        else :
            avg_romi =-100 
        self .log (f"\n---  KPI ---")
        self .log (f": {total_cost :,.0f}")
        self .log (f": {total_clicks :,.0f}")
        self .log (f": {total_leads :,.0f}")
        self .log (f": {total_sales :,.0f}")
        self .log (f": {total_revenue :,.0f}")
        self .log (f"CPL: {avg_cpl :,.0f}")
        self .log (f"CR1: {avg_cr1 :.2f}%")
        self .log (f"CR2: {avg_cr2 :.2f}%")
        self .log (f".: {avg_avg_check :,.0f}")
        self .log (f": {total_margin :,.0f}")
        self .log (f"ROMI: {avg_romi :.2f}%")

        kpi_values ={
        "":f"{total_cost :,.0f}".replace (","," "),
        "":f"{total_clicks :,.0f}".replace (","," "),
        "":f"{total_leads :,.0f}".replace (","," "),
        "CPL":f"{avg_cpl :,.0f}".replace (","," "),
        "CR1":f"{avg_cr1 :.2f}".replace (".",","),
        "":f"{total_sales :,.0f}".replace (","," "),
        "CR2":f"{avg_cr2 :.2f}".replace (".",","),
        ".":f"{avg_avg_check :,.0f}".replace (","," "),
        "":f"{total_revenue :,.0f}".replace (","," "),
        "":f"{total_margin :,.0f}".replace (","," "),
        "ROMI":f"{avg_romi :.2f}%".replace (".",",")
        }

        # Обновляет отображение
        for kpi ,value in kpi_values .items ():
            if kpi in self .kpi_labels :
                self .kpi_labels [kpi ].setText (value )
                self .log (f"  {kpi }: {value }")

        self .log ("="*40 )

    def update_kpi_for_current_tab (self ,tab_text ):
        """Обновляетт KPI для текущей вкладки"""
        self .log (f"\nОбновление KPI для вкладки: {tab_text }")

        if tab_text =="Дата":
            self .update_kpi_with_data (self .filtered_data )

        elif tab_text in ["????????????????","??????","????????????????","????????????","????????????????????","???????????????? ??????????"]:
        # использует dimension_data, который содержит отфильтрованные данные
            if tab_text in self .dimension_data and self .dimension_data [tab_text ]is not None :
                data =self .dimension_data [tab_text ]
                if len (data )>0 :
                    self .log (f"  Данные для {tab_text }: {len (data )} строк")
                    self .log (f"  Суа выручки: {data ['Выручка'].sum ():,.0f}")
                    self .log (f"  Суа продаж: {data ['Продажи'].sum ():,.0f}")
                    self .log (f"  Сумма расходов: {data ['Расход'].sum ():,.0f}")

                    # Создает агрегированные данные для KPI
                    total_sales =data ["Продажи"].sum ()
                    total_revenue =data ["Выручка"].sum ()
                    total_expense =data ["Расход"].sum ()
                    total_clicks =data ["Клики"].sum ()
                    total_leads =data ["Лиды"].sum ()

                    # Пересчитывает средний чек
                    avg_check =total_revenue /total_sales if total_sales >0 else 0 
                    # Пересчитывает CPL
                    avg_cpl =total_expense /total_leads if total_leads >0 else 0 
                    # Пересчитывает CR1
                    avg_cr1 =(total_leads /total_clicks *100 )if total_clicks >0 else 0 
                    # Пересчитывает CR2
                    avg_cr2 =(total_sales /total_leads *100 )if total_leads >0 else 0 
                    # Пересчитывает ROMI
                    avg_romi =((total_revenue -total_expense )/total_expense *100 )if total_expense >0 else -100 

                    kpi_data =pd .DataFrame ({
                    "Расход":[total_expense ],
                    "Клики":[total_clicks ],
                    "Лиды":[total_leads ],
                    "Продажи":[total_sales ],
                    "Выручка":[total_revenue ],
                    "Ср.чек":[avg_check ],
                    "CPL":[avg_cpl ],
                    "CR1":[avg_cr1 ],
                    "CR2":[avg_cr2 ],
                    "ROMI":[avg_romi ],
                    "Маржа":[total_revenue -total_expense ]
                    })
                    self .update_kpi_with_data (kpi_data )
                else :
                    self .log (f"  Нет данных для {tab_text }")
                    empty_data =pd .DataFrame ({
                    "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
                    "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ],
                    "CPL":[0 ],"CR1":[0 ],"CR2":[0 ],"ROMI":[-100 ],"Маржа":[0 ]
                    })
                    self .update_kpi_with_data (empty_data )
            else :
                self .log (f"  dimension_data[{tab_text }] не существует")
                empty_data =pd .DataFrame ({
                "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
                "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ],
                "CPL":[0 ],"CR1":[0 ],"CR2":[0 ],"ROMI":[-100 ],"Маржа":[0 ]
                })
                self .update_kpi_with_data (empty_data )

        elif tab_text =="__unused_type_tab_branch__":
            empty_data =pd .DataFrame ({
            "Расход":[0 ],"Клики":[0 ],"Лиды":[0 ],
            "Продажи":[0 ],"Выручка":[0 ],"Ср.чек":[0 ],
            "CPL":[0 ],"CR1":[0 ],"CR2":[0 ],"ROMI":[-100 ],"Маржа":[0 ]
            })
            self .update_kpi_with_data (empty_data )

        elif tab_text in ["📈 Графики","📊 План"]:
            self .update_kpi_with_data (self .filtered_data )

    def get_filtered_dynamics (self ,df ,column_name ,filter_value ,time_period ='D'):
        """
        Возвращает отфильтрованные и сгруппированные по вреени данные
        
        Args:
            df: исходный DataFrame
            column_name: название колонки для фильтрации
            filter_value: значение фильтра
            time_period: период группировки ('D', 'W', 'M', 'Q', 'Y')
        
        Returns:
            DataFrame с отфильтрованными и сгруппированными данныи
        """
        # 1. Создает копию данных
        filtered_df =df .copy ()

        # 2. Фильтруем по выбранному параметру (если не "Все")
        if filter_value !="Все"and filter_value !="Все капании":
            filtered_df =filtered_df [filtered_df [column_name ]==filter_value ]

        if filtered_df .empty :
            return pd .DataFrame ()

            # 3. Убеждаеся, что дата в правильно формате
        filtered_df ["Дата"]=pd .to_datetime (filtered_df ["Дата"])

        # 4. Устанавливае дату как индекс
        filtered_df .set_index ("Дата",inplace =True )

        # 5. Группируе по периоду и агрегируе
        agg_dict ={}

        # Определяем какие колонки суировать
        sum_cols =["Расход","Показы","Клики","Лиды","Продажи","Выручка"]
        for col in sum_cols :
            if col in filtered_df .columns :
                agg_dict [col ]="sum"

                # Средние значения для метрик (которые не суируются)
        mean_cols =["CPC","CPL","CTR","CR1","CR2","ROMI","Ср.чек"]
        for col in mean_cols :
            if col in filtered_df .columns :
                agg_dict [col ]="mean"

                # Выполняе ресеплинг
        result_df =filtered_df .resample (time_period ).agg (agg_dict ).fillna (0 ).reset_index ()

        # Пересчитывает метрики, которые должны быть пересчитаны на основе су
        if "Клики"in result_df .columns and "Показы"in result_df .columns :
            result_df ["CTR"]=(result_df ["Клики"]/result_df ["Показы"]*100 ).round (2 ).fillna (0 )

        if "Лиды"in result_df .columns and "Клики"in result_df .columns :
            result_df ["CR1"]=(result_df ["Лиды"]/result_df ["Клики"]*100 ).round (2 ).fillna (0 )

        if "Расход"in result_df .columns and "Клики"in result_df .columns :
            result_df ["CPC"]=(result_df ["Расход"]/result_df ["Клики"]).round (0 ).fillna (0 ).astype (int )

        if "Расход"in result_df .columns and "Лиды"in result_df .columns :
            result_df ["CPL"]=(result_df ["Расход"]/result_df ["Лиды"]).round (0 ).fillna (0 ).astype (int )

        if "Продажи"in result_df .columns and "Лиды"in result_df .columns :
            result_df ["CR2"]=(result_df ["Продажи"]/result_df ["Лиды"]*100 ).round (2 ).fillna (0 )

        if "Выручка"in result_df .columns and "Продажи"in result_df .columns :
            result_df ["Ср.чек"]=(result_df ["Выручка"]/result_df ["Продажи"]).round (0 ).fillna (0 ).astype (int )

        if "Выручка"in result_df .columns and "Расход"in result_df .columns :
            result_df ["Маржа"]=(result_df ["Выручка"]-result_df ["Расход"]).round (0 ).astype (int )
            result_df ["ROMI"]=((result_df ["Выручка"]-result_df ["Расход"])/result_df ["Расход"]*100 ).round (2 ).fillna (-100 )

        return result_df 

    def get_current_period_code (self ):
        """Возвращает код периода для resample на основе выбранной группировки"""
        group_type =self .group_combo .currentText ()
        period_map ={
        "день":"D",
        "неделя":"W",
        "есяц":"M",
        "квартал":"Q",
        "год":"Y"
        }
        return period_map .get (group_type ,"D")

    def get_current_filters_dict (self ):
        """Возвращает словарь с выбранныи значенияи фильтров для основной таблицы"""
        selected =self .get_selected_filters ()

        # Преобразуем в формат для фильтрации
        filters_dict ={}

        # Маппинг названий фильтров к колонка
        filter_to_column ={
        "Источник":"Источник",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза"
        }

        for display_name ,column_name in filter_to_column .items ():
            if display_name in selected and selected [display_name ]:
            # Если выбрано одно значение, бере его
                if len (selected [display_name ])==1 :
                    filters_dict [column_name ]=selected [display_name ][0 ]
                else :
                # Если выбрано несколько, пока не поддерживае
                # Можно добавить логику для нескольких значений позже
                    filters_dict [column_name ]=selected [display_name ]

        return filters_dict 

    def get_current_period_code (self ):
        """Возвращает код периода для resample на основе выбранной группировки"""
        if not hasattr (self ,'group_combo'):
            return "D"

        group_type =self .group_combo .currentText ()
        period_map ={
        "день":"D",
        "неделя":"W",
        "есяц":"M",
        "квартал":"Q",
        "год":"Y"
        }
        return period_map .get (group_type ,"D")

    def _recalculate_metrics (self ,df ):
        """Пересчитываетт все метрики для сгруппированных данных"""
        if df .empty :
            return df 

            # CTR = Клики / Показы * 100
        if "Клики"in df .columns and "Показы"in df .columns :
            df ["CTR"]=(df ["Клики"]/df ["Показы"]*100 ).round (2 ).fillna (0 )

            # CR1 = Лиды / Клики * 100
        if "Лиды"in df .columns and "Клики"in df .columns :
            df ["CR1"]=(df ["Лиды"]/df ["Клики"]*100 ).round (2 ).fillna (0 )

            # CPC = Расход / Клики
        if "Расход"in df .columns and "Клики"in df .columns :
            df ["CPC"]=(df ["Расход"]/df ["Клики"]).round (0 ).fillna (0 ).astype (int )

            # CPL = Расход / Лиды
        if "Расход"in df .columns and "Лиды"in df .columns :
            df ["CPL"]=(df ["Расход"]/df ["Лиды"]).round (0 ).fillna (0 ).astype (int )

            # CR2 = Продажи / Лиды * 100
        if "Продажи"in df .columns and "Лиды"in df .columns :
            df ["CR2"]=(df ["Продажи"]/df ["Лиды"]*100 ).round (2 ).fillna (0 )

            # Ср.чек = Выручка / Продажи (если не было в исходных данных)
        if "Выручка"in df .columns and "Продажи"in df .columns and "Ср.чек"not in df .columns :
            df ["Ср.чек"]=(df ["Выручка"]/df ["Продажи"]).round (0 ).fillna (0 ).astype (int )

            # Маржа = Выручка - Расход
        if "Выручка"in df .columns and "Расход"in df .columns :
            df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).round (0 ).astype (int )

            # ROMI = (Выручка - Расход) / Расход * 100
        if "Выручка"in df .columns and "Расход"in df .columns :
            df ["ROMI"]=((df ["Выручка"]-df ["Расход"])/df ["Расход"]*100 ).round (2 ).fillna (-100 )

        return df 

    def _ensure_datetime (self ,df ):
        """Убеждается, что колонка Дата иеет тип datetime"""
        if df is None or df .empty :
            return df 
        if "Дата"in df .columns :
        # Проверяет, является ли колонка уже datetime
            if not pd .api .types .is_datetime64_any_dtype (df ["Дата"]):
            # Пробуем преобразовать
                try :
                    df ["Дата"]=pd .to_datetime (df ["Дата"],errors ='coerce')
                    self .log ("Даты преобразованы в формат datetime")
                except Exception as e :
                    self .log (f"Ошибка преобразования дат: {e }")
                    # Удаляетм строки с некорректными датами
            before =len (df )
            df =df .dropna (subset =["Дата"])
            after =len (df )
            if before !=after :
                self .log (f"Удалено {before -after } строк с некорректными датами")
        return df 

    def debug_data_types (self ):
        """Выводит типы данных для отладки"""
        self .log ("\n=== ОТЛАДКА ТПОВ ДАННЫХ ===")
        if hasattr (self ,'original_data')and not self .original_data .empty :
            self .log (f"Тип колонки Дата в original_data: {self .original_data ['Дата'].dtype }")
            self .log (f"Первые 5 значений дат: {self .original_data ['Дата'].head ().tolist ()}")
        else :
            self .log ("original_data пуст")

        if hasattr (self ,'data')and not self .data .empty :
            self .log (f"Тип колонки Дата в data: {self .data ['Дата'].dtype }")
            self .log (f"Первые 5 значений дат: {self .data ['Дата'].head ().tolist ()}")
        self .log ("=== КОНЕЦ ОТЛАДК ===\n")

    def _parse_date_series (self ,series ):
        """Аккуратно парсит даты из разных форматов, не лоая ISO YYYY-MM-DD."""
        if series is None :
            return series 

        sample =(
        series .dropna ()
        .astype (str )
        .str .strip ()
        .head (10 )
        .tolist ()
        )

        use_dayfirst =True 
        if sample :
            iso_like =sum (1 for val in sample if len (val )>=10 and val [:4 ].isdigit ()and val [4 ]=="-"and val [7 ]=="-")
            if iso_like >=max (1 ,len (sample )//2 ):
                use_dayfirst =False 

        return pd .to_datetime (series ,errors ="coerce",dayfirst =use_dayfirst )

    def _convert_dates_to_datetime (self ,df ):
        """Принудительно преобразует колонку Дата в datetime"""
        if df is None or df .empty :
            return df 

        if "Дата"in df .columns :
        # Проверяет текущий тип
            self .log (f"Текущий тип даты: {df ['Дата'].dtype }")
            self .log (f"Примеры дат: {df ['Дата'].head ().tolist ()}")

            # Принудительно преобразуе
            try :
                df ["Дата"]=self ._parse_date_series (df ["Дата"])
                # Удаляетм строки с некорректными датами
                before =len (df )
                df =df .dropna (subset =["Дата"])
                self .log (f"Преобразовано {before -len (df )} строк с некорректными датами")
                self .log (f"Тип после преобразования: {df ['Дата'].dtype }")
            except Exception as e :
                self .log (f"Ошибка преобразования дат: {e }")

        return df 

    def _ensure_datetime (self ):
        """Принудительно преобразует все данные в datetime"""
        if hasattr (self ,'original_data')and not self .original_data .empty :
            if "Дата"in self .original_data .columns :
                self .log (f"original_data тип даты: {self .original_data ['Дата'].dtype }")
                if not pd .api .types .is_datetime64_any_dtype (self .original_data ["Дата"]):
                    self .log ("Преобразуем original_data...")
                    self .original_data ["Дата"]=self ._parse_date_series (self .original_data ["Дата"])
                    self .original_data =self .original_data .dropna (subset =["Дата"])

        if hasattr (self ,'data')and not self .data .empty :
            if "Дата"in self .data .columns :
                self .log (f"data тип даты: {self .data ['Дата'].dtype }")
                if not pd .api .types .is_datetime64_any_dtype (self .data ["Дата"]):
                    self .log ("Преобразуем data...")
                    self .data ["Дата"]=self ._parse_date_series (self .data ["Дата"])
                    self .data =self .data .dropna (subset =["Дата"])

    def _calculate_metrics_for_df (self ,df ):
        """Рассчитывает метрики для DataFrame"""
        if df .empty :
            return df 

            # CTR = Клики / Показы * 100
        if "Клики"in df .columns and "Показы"in df .columns :
            df ["CTR"]=(df ["Клики"]/df ["Показы"]*100 ).round (2 ).fillna (0 )
        else :
            df ["CTR"]=0 

            # CR1 = Лиды / Клики * 100
        if "Лиды"in df .columns and "Клики"in df .columns :
            df ["CR1"]=(df ["Лиды"]/df ["Клики"]*100 ).round (2 ).fillna (0 )
        else :
            df ["CR1"]=0 

            # CPC = Расход / Клики
        if "Расход"in df .columns and "Клики"in df .columns :
            df ["CPC"]=(df ["Расход"]/df ["Клики"]).round (0 ).fillna (0 ).astype (int )
        else :
            df ["CPC"]=0 

            # CR2 = Продажи / Лиды * 100
        if "Продажи"in df .columns and "Лиды"in df .columns :
            df ["CR2"]=(df ["Продажи"]/df ["Лиды"]*100 ).round (2 ).fillna (0 )
        else :
            df ["CR2"]=0 

            # Ср.чек = Выручка / Продажи
        if "Выручка"in df .columns and "Продажи"in df .columns :
            avg_check =(df ["Выручка"]/df ["Продажи"]).round (0 )
            avg_check =avg_check .replace ([float ('inf'),-float ('inf')],0 ).fillna (0 )
            df ["Ср.чек"]=avg_check .astype (int )
        else :
            df ["Ср.чек"]=0 

            # Маржа = Выручка - Расход
        if "Выручка"in df .columns and "Расход"in df .columns :
            df ["Маржа"]=(df ["Выручка"]-df ["Расход"]).round (0 ).fillna (0 ).astype (int )
        else :
            df ["Маржа"]=0 

            # ROMI = (Выручка - Расход) / Расход * 100
        if "Выручка"in df .columns and "Расход"in df .columns :
            romi =((df ["Выручка"]-df ["Расход"])/df ["Расход"]*100 ).round (2 )
            romi =romi .replace ([float ('inf'),-float ('inf')],-100 ).fillna (-100 )
            df ["ROMI"]=romi 
        else :
            df ["ROMI"]=-100 

        return df 

    def _get_base_metric_columns (self ):
        """Возвращает базовые числовые колонки для дашборда"""
        return ["Расход","Показы","Клики","Лиды","Продажи","Выручка"]

    def _apply_plan_values_to_calendar (self ,calendar_df ,from_date ,to_date ):
        """Накладывает планы на дневной календарь выбранного периода"""
        result =calendar_df .copy ()

        for col in ["Расход план","Лиды план","CPL план","Расход %","Лиды %","CPL %"]:
            if col not in result .columns :
                result [col ]=0.0 

        plans =self .plans_history .get (self .current_client ,{})
        if not plans :
            return result 

        for _ ,plan in plans .items ():
            plan_from =plan .get ("period_from")
            plan_to =plan .get ("period_to")
            if not plan_from or not plan_to :
                continue 

            intersect_from =max (plan_from ,from_date )
            intersect_to =min (plan_to ,to_date )
            if intersect_from >intersect_to :
                continue 

            total_plan_days =(plan_to -plan_from ).days +1 
            if total_plan_days <=0 :
                continue 

            daily_budget =plan .get ("budget",0 )/total_plan_days 
            daily_leads =plan .get ("leads",0 )/total_plan_days 

            mask =(
            (result ["Дата"].dt .date >=intersect_from )&
            (result ["Дата"].dt .date <=intersect_to )
            )

            result .loc [mask ,"Расход план"]+=daily_budget 
            result .loc [mask ,"Лиды план"]+=daily_leads 

        result ["CPL план"]=0.0 
        plan_leads_mask =result ["Лиды план"]>0 
        result .loc [plan_leads_mask ,"CPL план"]=(
        result .loc [plan_leads_mask ,"Расход план"]/result .loc [plan_leads_mask ,"Лиды план"]
        )

        result ["Расход %"]=0.0 
        result ["Лиды %"]=0.0 
        result ["CPL %"]=0.0 

        budget_mask =result ["Расход план"]>0 
        result .loc [budget_mask ,"Расход %"]=(
        result .loc [budget_mask ,"Расход"]/result .loc [budget_mask ,"Расход план"]*100 
        ).round (2 )

        result .loc [plan_leads_mask ,"Лиды %"]=(
        result .loc [plan_leads_mask ,"Лиды"]/result .loc [plan_leads_mask ,"Лиды план"]*100 
        ).round (2 )

        cpl_mask =(result ["CPL план"]>0 )&(result ["CPL"]>0 )
        result .loc [cpl_mask ,"CPL %"]=(
        result .loc [cpl_mask ,"CPL"]/result .loc [cpl_mask ,"CPL план"]*100 
        ).round (2 )

        return result 

    def _build_daily_dashboard_data (self ,df ,from_date ,to_date ):
        """Строит полный дневной календарь с нуляи на даты без факта"""
        full_range =pd .date_range (start =pd .Timestamp (from_date ),end =pd .Timestamp (to_date ),freq ="D")
        daily_df =pd .DataFrame ({"Дата":full_range })

        base_columns =self ._get_base_metric_columns ()
        source_df =df .copy ()

        if not source_df .empty :
            source_df ["Дата"]=pd .to_datetime (source_df ["Дата"],errors ="coerce",dayfirst =True ).dt .normalize ()
            source_df =source_df .dropna (subset =["Дата"])

            agg_dict ={col :"sum"for col in base_columns if col in source_df .columns }
            if agg_dict :
                grouped =source_df .groupby ("Дата",as_index =False ).agg (agg_dict )
                daily_df =daily_df .merge (grouped ,on ="Дата",how ="left")

        for col in base_columns :
            if col not in daily_df .columns :
                daily_df [col ]=0.0 

        numeric_cols =[col for col in base_columns if col in daily_df .columns ]
        daily_df [numeric_cols ]=daily_df [numeric_cols ].fillna (0 )

        daily_df ["CPL"]=0.0 
        leads_mask =daily_df ["Лиды"]>0 
        daily_df .loc [leads_mask ,"CPL"]=(
        daily_df .loc [leads_mask ,"Расход"]/daily_df .loc [leads_mask ,"Лиды"]
        ).round (0 )

        daily_df =self ._apply_plan_values_to_calendar (daily_df ,from_date ,to_date )
        daily_df =self ._calculate_metrics_for_df (daily_df )

        return daily_df 

    def _group_dashboard_periods (self ,daily_df ,group_type ,from_date ,to_date ):
        """Собирает дневной календарь в недели, есяцы, кварталы или годы"""
        if group_type =="день":
            return daily_df .copy ()

        grouped_df =daily_df .copy ()
        from_ts =pd .Timestamp (from_date )
        to_ts =pd .Timestamp (to_date )

        if group_type =="неделя":
            period =grouped_df ["Дата"].dt .to_period ("W-SUN")
            period_start =period .dt .start_time 
            period_end =period .dt .end_time .dt .normalize ()
            clipped_start =period_start .where (period_start >=from_ts ,from_ts )
            clipped_end =period_end .where (period_end <=to_ts ,to_ts )
            iso_calendar =grouped_df ["Дата"].dt .isocalendar ()
            grouped_df ["Период"]=(
            "Неделя "+iso_calendar .week .astype (str )+
            " ("+clipped_start .dt .strftime ("%d.%m.%Y")+
            " - "+clipped_end .dt .strftime ("%d.%m.%Y")+")"
            )
            grouped_df ["Сортировка"]=period_start 
        elif group_type =="месяц":
            period =grouped_df ["Дата"].dt .to_period ("M")
            period_start =period .dt .start_time 
            grouped_df ["Период"]=period_start .dt .strftime ("%m.%Y")
            grouped_df ["Сортировка"]=period_start 
        elif group_type =="квартал":
            period =grouped_df ["Дата"].dt .to_period ("Q")
            period_start =period .dt .start_time 
            grouped_df ["Период"]=(
            "Q"+period_start .dt .quarter .astype (str )+" "+period_start .dt .year .astype (str )
            )
            grouped_df ["Сортировка"]=period_start 
        elif group_type =="год":
            period =grouped_df ["Дата"].dt .to_period ("Y")
            period_start =period .dt .start_time 
            grouped_df ["Период"]=period_start .dt .year .astype (str )
            grouped_df ["Сортировка"]=period_start 
        else :
            return daily_df .copy ()

        agg_columns =[
        "Расход","Показы","Клики","Лиды","Продажи","Выручка",
        "Расход план","Лиды план"
        ]
        existing_agg_columns =[col for col in agg_columns if col in grouped_df .columns ]

        grouped_df =(
        grouped_df 
        .groupby (["Период","Сортировка"],as_index =False )[existing_agg_columns ]
        .sum ()
        .sort_values ("Сортировка")
        .reset_index (drop =True )
        )

        grouped_df ["CPL"]=0.0 
        leads_mask =grouped_df ["Лиды"]>0 
        grouped_df .loc [leads_mask ,"CPL"]=(
        grouped_df .loc [leads_mask ,"Расход"]/grouped_df .loc [leads_mask ,"Лиды"]
        ).round (0 )

        grouped_df ["CPL план"]=0.0 
        plan_leads_mask =grouped_df ["Лиды план"]>0 
        grouped_df .loc [plan_leads_mask ,"CPL план"]=(
        grouped_df .loc [plan_leads_mask ,"Расход план"]/grouped_df .loc [plan_leads_mask ,"Лиды план"]
        )

        grouped_df ["Расход %"]=0.0 
        grouped_df ["Лиды %"]=0.0 
        grouped_df ["CPL %"]=0.0 

        budget_mask =grouped_df ["Расход план"]>0 
        grouped_df .loc [budget_mask ,"Расход %"]=(
        grouped_df .loc [budget_mask ,"Расход"]/grouped_df .loc [budget_mask ,"Расход план"]*100 
        ).round (2 )

        grouped_df .loc [plan_leads_mask ,"Лиды %"]=(
        grouped_df .loc [plan_leads_mask ,"Лиды"]/grouped_df .loc [plan_leads_mask ,"Лиды план"]*100 
        ).round (2 )

        cpl_mask =(grouped_df ["CPL план"]>0 )&(grouped_df ["CPL"]>0 )
        grouped_df .loc [cpl_mask ,"CPL %"]=(
        grouped_df .loc [cpl_mask ,"CPL"]/grouped_df .loc [cpl_mask ,"CPL план"]*100 
        ).round (2 )

        grouped_df =self ._calculate_metrics_for_df (grouped_df )
        grouped_df =grouped_df .rename (columns ={"Период":"Дата"})
        grouped_df =grouped_df .drop (columns =["Сортировка"],errors ="ignore")

        return grouped_df 

    def update_dashboard (self ):
        """Обновляетт таблицу с учето фильтров, периода и выбранной группировки"""
        if not hasattr (self ,'group_combo')or self .group_combo is None :
            self .log ("group_combo не инициализирован, пропускае обновление")
            return 

        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        group_type =self .group_combo .currentText ()
        selected_filters =self .get_selected_filters ()

        self .log (f"\n=== ОНОВЛЕНЕ ДАШОРДА ===")
        self .log (f"Период: {from_date } - {to_date }")
        self .log (f"Группировка: {group_type }")

        has_selected_filters =any (values for values in selected_filters .values ())
        if not has_selected_filters :
            self .log ("Нет выбранных фильтров - очищае таблицу")
            self .filtered_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self .update_chart ()
            return 

        if self .original_data .empty :
            self .log ("Нет исходных данных")
            self .filtered_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self .update_chart ()
            return 

        df =self .original_data .copy ()

        if not pd .api .types .is_datetime64_any_dtype (df ["Дата"]):
            df ["Дата"]=pd .to_datetime (df ["Дата"],errors ='coerce',dayfirst =True )
        df =df .dropna (subset =["Дата"])

        mask =(df ["Дата"].dt .date >=from_date )&(df ["Дата"].dt .date <=to_date )
        df =df .loc [mask ]

        filter_to_column ={
        "Источник":"Источник",
        "Тип":"Medium",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза"
        }

        if "Medium"not in df .columns :
            df ["Medium"]="Не указано"
        else :
            df ["Medium"]=(
            df ["Medium"]
            .fillna ("Не указано")
            .astype (str )
            .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
            )

        empty_by_filters =False 
        for display_name ,column_name in filter_to_column .items ():
            if display_name in selected_filters and column_name in df .columns :
                if len (selected_filters [display_name ])==0 :
                    empty_by_filters =True 
                    break 
                else :
                    df =df [df [column_name ].isin (selected_filters [display_name ])]

        if empty_by_filters :
            self .log ("В одно из фильтров сняты все галочки - показывае пустой результат")
            self .filtered_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self .update_chart ()
            return 

        if df .empty :
            self .log ("После фильтров фактических строк нет, строи календарь с нуляи и плано")

        daily_df =self ._build_daily_dashboard_data (df ,from_date ,to_date )
        final_df =self ._group_dashboard_periods (daily_df ,group_type ,from_date ,to_date )

        self .filtered_data =final_df 
        self .original_filtered_data =self .filtered_data .copy ()
        self .chart_data =daily_df .copy ()

        self .log (f"тоговое количество строк: {len (self .filtered_data )}")
        self .log (f"Первая строка периода: {self .filtered_data ['Дата'].iloc [0 ]}")
        self .log (f"Последняя строка периода: {self .filtered_data ['Дата'].iloc [-1 ]}")

        self .update_table ()
        self .update_kpi ()
        self .update_chart ()

    def _clear_dimension_tabs (self ):
        """Очищает все таблицы вкладок изерений."""
        for dimension_name ,table in self .dimension_tables .items ():
            empty_df =pd .DataFrame (columns =[dimension_name ])
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            table .clearContents ()
            table .setRowCount (0 )
            table .setColumnCount (0 )
            table .setHorizontalHeaderLabels ([])
            table .update ()

    def update_dimension_table_with_filter (self ,dimension_name ,from_date ,to_date ):
        """Строит вкладку измерения из уже отфильтрованных исходных строк."""
        source_df =self .filtered_source_data .copy ()if hasattr (self ,"filtered_source_data")and self .filtered_source_data is not None else self .data .copy ()
        empty_df =pd .DataFrame (columns =[dimension_name ])

        if source_df .empty :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        if "Дата"in source_df .columns and not pd .api .types .is_datetime64_any_dtype (source_df ["Дата"]):
            source_df ["Дата"]=pd .to_datetime (source_df ["Дата"],errors ="coerce",dayfirst =True )
            source_df =source_df .dropna (subset =["Дата"])

        column_name ="Medium"if dimension_name =="Тип"else dimension_name 
        if dimension_name =="Тип":
            if "Medium"not in source_df .columns :
                source_df ["Medium"]="Не указано"
            source_df ["Medium"]=(
            source_df ["Medium"]
            .fillna ("Не указано")
            .astype (str )
            .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
            )

        if column_name not in source_df .columns :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        filtered =source_df .copy ()
        if "Дата"in filtered .columns :
            filtered =filtered [
            (filtered ["Дата"]>=pd .Timestamp (from_date ))&
            (filtered ["Дата"]<=pd .Timestamp (to_date ))
            ]

        if filtered .empty :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        if "Выручка"not in filtered .columns and {"Продажи","Ср.чек"}.issubset (filtered .columns ):
            filtered =filtered .copy ()
            filtered ["Выручка"]=filtered ["Продажи"]*filtered ["Ср.чек"]

        agg_dict ={col :"sum"for col in ["Расход","Показы","Клики","Лиды","Продажи","Выручка"]if col in filtered .columns }
        grouped =filtered .groupby (column_name ,dropna =False ).agg (agg_dict ).reset_index ()
        grouped [column_name ]=grouped [column_name ].fillna ("Не указано").replace ({"":"Не указано"})

        if column_name !=dimension_name :
            grouped =grouped .rename (columns ={column_name :dimension_name })

        if "Ср.чек"not in grouped .columns and {"Выручка","Продажи"}.issubset (grouped .columns ):
            grouped ["Ср.чек"]=grouped .apply (
            lambda row :round (row ["Выручка"]/row ["Продажи"])if row ["Продажи"]>0 else 0 ,
            axis =1 
            ).astype (int )

        grouped =self .calculate_dimension_metrics_fixed (grouped ,dimension_name )
        self .dimension_raw_data [dimension_name ]=grouped .copy ()
        self .dimension_data [dimension_name ]=grouped .copy ()
        self .display_dimension_table (dimension_name ,grouped )

    def refresh_all_dimension_tabs (self ):
        """Обновляетт все вкладки изерений из текущего отфильтрованного набора."""
        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        for dimension_name in self .dimension_tables .keys ():
            self .update_dimension_table_with_filter (dimension_name ,from_date ,to_date )

    def update_dashboard (self ):
        """Обновляетт таблицу, KPI, график и вкладки изерений с учето периода и фильтров."""
        if not hasattr (self ,"group_combo")or self .group_combo is None :
            self .log ("group_combo не инициализирован, пропускае обновление")
            return 

        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        group_type =self .group_combo .currentText ()
        selected_filters =self .get_selected_filters ()

        has_selected_filters =any (values for values in selected_filters .values ())
        if not has_selected_filters :
            self .filtered_data =pd .DataFrame ()
            self .filtered_source_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self ._clear_dimension_tabs ()
            self .update_chart ()
            return 

        if self .original_data .empty :
            self .filtered_data =pd .DataFrame ()
            self .filtered_source_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self ._clear_dimension_tabs ()
            self .update_chart ()
            return 

        df =self .original_data .copy ()
        if not pd .api .types .is_datetime64_any_dtype (df ["Дата"]):
            df ["Дата"]=pd .to_datetime (df ["Дата"],errors ="coerce",dayfirst =True )
        df =df .dropna (subset =["Дата"])

        mask =(df ["Дата"].dt .date >=from_date )&(df ["Дата"].dt .date <=to_date )
        df =df .loc [mask ]

        if "Medium"not in df .columns :
            df ["Medium"]="Не указано"
        else :
            df ["Medium"]=(
            df ["Medium"]
            .fillna ("Не указано")
            .astype (str )
            .replace ({"":"Не указано","None":"Не указано","nan":"Не указано"})
            )

        filter_to_column ={
        "Источник":"Источник",
        "Тип":"Medium",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза",
        "Регион":"Регион",
        "Устройство":"Устройство",
        "Площадка":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Продукт":"Продукт",
        }

        for display_name ,column_name in filter_to_column .items ():
            if display_name not in selected_filters :
                continue 
            selected_values =selected_filters [display_name ]
            if len (selected_values )==0 :
                self .filtered_data =pd .DataFrame ()
                self .filtered_source_data =pd .DataFrame ()
                self .chart_data =pd .DataFrame ()
                self .display_empty_table ()
                self ._clear_dimension_tabs ()
                self .update_chart ()
                return 
            if column_name in df .columns :
                df =df [df [column_name ].isin (selected_values )]

        self .filtered_source_data =df .copy ()

        if df .empty :
            self .filtered_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self ._clear_dimension_tabs ()
            self .update_chart ()
            return 

        daily_df =self ._build_daily_dashboard_data (df ,from_date ,to_date )
        final_df =self ._group_dashboard_periods (daily_df ,group_type ,from_date ,to_date )

        self .filtered_data =final_df 
        self .original_filtered_data =self .filtered_data .copy ()
        self .chart_data =daily_df .copy ()

        self .update_table ()
        self .refresh_all_dimension_tabs ()
        self .update_kpi ()
        self .update_chart ()

    def apply_filter (self ):
        """Применяет фильтр по дате - перенаправляет на update_dashboard"""
        self .update_dashboard ()

    def update_dependent_filters (self ):
        """Обновляетт список групп в зависимости от выбранной капании"""
        # Получаем выбранные фильтры
        selected =self .get_selected_filters ()

        # Маппинг названий фильтров к колонка
        filter_to_column ={
        "Источник":"Источник",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза"
        }

        # Обновляет список групп на основе выбранной капании
        if "Кампания"in selected and selected ["Кампания"]:
        # Если выбрана конкретная капания
            selected_campaign =selected ["Кампания"][0 ]if selected ["Кампания"]else None 
        else :
            selected_campaign =None 

            # Получаем все группы из данных
        if hasattr (self ,'original_data')and not self .original_data .empty :
            if selected_campaign and selected_campaign !="Все":
            # Фильтруе группы по выбранной капании
                groups =self .original_data [self .original_data ["Кампания"]==selected_campaign ]["Группа"].unique ()
            else :
            # Все группы
                groups =self .original_data ["Группа"].unique ()

                # Сортируе и преобразуе в строки
            groups =sorted ([str (g )for g in groups if g and str (g )!='nan'])

            # Обновляет filter_states для групп
            if "Группа"in self .filters_widgets :
            # локируе сигналы
                self .filters_widgets ["Группа"]['list'].blockSignals (True )

                # Обновляет список
                list_widget =self .filters_widgets ["Группа"]['list']
                list_widget .clear ()

                # Добавляе группы
                for group in groups :
                    item =QListWidgetItem (group )
                    item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                    # Проверяет, был ли этот элемент выбран ранее
                    if "Группа"in self .filter_states and group in self .filter_states ["Группа"]:
                        item .setCheckState (self .filter_states ["Группа"][group ])
                    else :
                        item .setCheckState (Qt .CheckState .Checked )
                    list_widget .addItem (item )

                    # Обновляет items
                self .filters_widgets ["Группа"]['items']=groups 

                # Разблокируе сигналы
                self .filters_widgets ["Группа"]['list'].blockSignals (False )

    def _get_dimension_tab_names (self ):
        """Возвращает иена вкладок изерений из уже созданных таблиц."""
        if hasattr (self ,"dimension_tables")and self .dimension_tables :
            return list (self .dimension_tables .keys ())
        return []

    def _build_dimension_kpi_data (self ,tab_text ):
        """Собирает единый набор KPI для вкладки измерения."""
        data =self .dimension_data .get (tab_text )if hasattr (self ,"dimension_data")else None 
        if data is None or len (data )==0 :
            return pd .DataFrame ({
            "Расход":[0 ],
            "Клики":[0 ],
            "Лиды":[0 ],
            "Продажи":[0 ],
            "Выручка":[0 ],
            "Ср.чек":[0 ],
            "CPL":[0 ],
            "CR1":[0 ],
            "CR2":[0 ],
            "ROMI":[-100 ],
            "Маржа":[0 ],
            })

        total_sales =data ["Продажи"].sum ()if "Продажи"in data .columns else 0 
        total_revenue =data ["Выручка"].sum ()if "Выручка"in data .columns else 0 
        total_expense =data ["Расход"].sum ()if "Расход"in data .columns else 0 
        total_clicks =data ["Клики"].sum ()if "Клики"in data .columns else 0 
        total_leads =data ["Лиды"].sum ()if "Лиды"in data .columns else 0 

        avg_check =total_revenue /total_sales if total_sales >0 else 0 
        avg_cpl =total_expense /total_leads if total_leads >0 else 0 
        avg_cr1 =(total_leads /total_clicks *100 )if total_clicks >0 else 0 
        avg_cr2 =(total_sales /total_leads *100 )if total_leads >0 else 0 
        avg_romi =((total_revenue -total_expense )/total_expense *100 )if total_expense >0 else -100 

        return pd .DataFrame ({
        "Расход":[total_expense ],
        "Клики":[total_clicks ],
        "Лиды":[total_leads ],
        "Продажи":[total_sales ],
        "Выручка":[total_revenue ],
        "Ср.чек":[avg_check ],
        "CPL":[avg_cpl ],
        "CR1":[avg_cr1 ],
        "CR2":[avg_cr2 ],
        "ROMI":[avg_romi ],
        "Маржа":[total_revenue -total_expense ],
        })

    def _build_merged_dataframe_from_sources (self ):
        """Собирает основную таблицу из сохраненных рекламных и CRM-данных."""
        if not hasattr (self ,"ads_data")or self .ads_data is None :
            return pd .DataFrame ()
        if not hasattr (self ,"crm_data")or self .crm_data is None :
            return pd .DataFrame ()

        ads_df =self .ads_data .copy ()
        crm_df =self .crm_data .copy ()

        if ads_df .empty or crm_df .empty :
            return pd .DataFrame ()

        ads_df ["Дата"]=self ._parse_date_series (ads_df .get ("Дата"))
        crm_df ["Дата"]=self ._parse_date_series (crm_df .get ("Дата"))
        ads_df =ads_df .dropna (subset =["Дата"])
        crm_df =crm_df .dropna (subset =["Дата"])

        dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]
        for col in dimension_cols :
            if col not in ads_df .columns :
                ads_df [col ]="не указано"
            if col not in crm_df .columns :
                crm_df [col ]="не указано"
            ads_df [col ]=ads_df [col ].fillna ("").astype (str ).replace ("","не указано")
            crm_df [col ]=crm_df [col ].fillna ("").astype (str ).replace ("","не указано")

        ads_numeric =["Расход","Показы","Клики"]
        crm_numeric =["Лиды","Продажи","Ср.чек"]
        for col in ads_numeric :
            if col not in ads_df .columns :
                ads_df [col ]=0 
            ads_df [col ]=pd .to_numeric (ads_df [col ],errors ="coerce").fillna (0 )
        for col in crm_numeric :
            if col not in crm_df .columns :
                crm_df [col ]=0 
            crm_df [col ]=pd .to_numeric (crm_df [col ],errors ="coerce").fillna (0 )

        merge_cols =["Дата"]+dimension_cols 
        ads_for_merge =ads_df [merge_cols +ads_numeric ].copy ()
        crm_for_merge =crm_df [merge_cols +crm_numeric ].copy ()

        merged =pd .merge (ads_for_merge ,crm_for_merge ,on =merge_cols ,how ="outer")
        for col in ads_numeric +crm_numeric :
            merged [col ]=pd .to_numeric (merged [col ],errors ="coerce").fillna (0 )
        for col in dimension_cols :
            merged [col ]=merged [col ].fillna ("не указано")

        merged =(
        merged .groupby (merge_cols ,dropna =False )
        .agg ({
        "Расход":"sum",
        "Показы":"sum",
        "Клики":"sum",
        "Лиды":"sum",
        "Продажи":"sum",
        "Ср.чек":"mean",
        })
        .reset_index ()
        )

        merged ["Выручка"]=(merged ["Продажи"]*merged ["Ср.чек"]).round (0 )
        merged ["CTR"]=np .where (merged ["Показы"]>0 ,merged ["Клики"]/merged ["Показы"]*100 ,0 ).round (2 )
        merged ["CR1"]=np .where (merged ["Клики"]>0 ,merged ["Лиды"]/merged ["Клики"]*100 ,0 ).round (2 )
        merged ["CPC"]=np .where (merged ["Клики"]>0 ,np .round (merged ["Расход"]/merged ["Клики"]),0 )
        merged ["CPL"]=np .where (merged ["Лиды"]>0 ,np .round (merged ["Расход"]/merged ["Лиды"]),0 )
        merged ["CR2"]=np .where (merged ["Лиды"]>0 ,merged ["Продажи"]/merged ["Лиды"]*100 ,0 ).round (2 )
        merged ["Маржа"]=(merged ["Выручка"]-merged ["Расход"]).round (0 )
        merged ["ROMI"]=np .where (
        merged ["Расход"]>0 ,
        ((merged ["Выручка"]-merged ["Расход"])/merged ["Расход"]*100 ).round (2 ),
        -100 ,
        )

        for int_col in ["Показы","Клики","Лиды","Продажи","CPC","CPL"]:
            merged [int_col ]=pd .to_numeric (merged [int_col ],errors ="coerce").fillna (0 ).round (0 ).astype (int )
        for money_col in ["Расход","Ср.чек","Выручка","Маржа"]:
            merged [money_col ]=pd .to_numeric (merged [money_col ],errors ="coerce").fillna (0 ).round (0 )

        if "Medium"in ads_df .columns or "Medium"in crm_df .columns :
            ads_medium =ads_df [["Дата"]+dimension_cols +(["Medium"]if "Medium"in ads_df .columns else [])].copy ()
            crm_medium =crm_df [["Дата"]+dimension_cols +(["Medium"]if "Medium"in crm_df .columns else [])].copy ()
            if "Medium"not in ads_medium .columns :
                ads_medium ["Medium"]="Не указано"
            if "Medium"not in crm_medium .columns :
                crm_medium ["Medium"]="Не указано"
            ads_medium ["Medium"]=ads_medium ["Medium"].fillna ("").astype (str ).replace ("","Не указано")
            crm_medium ["Medium"]=crm_medium ["Medium"].fillna ("").astype (str ).replace ("","Не указано")
            medium_map =pd .concat ([ads_medium ,crm_medium ],ignore_index =True )
            medium_map =medium_map .drop_duplicates (subset =merge_cols ,keep ="first")
            merged =merged .merge (medium_map [merge_cols +["Medium"]],on =merge_cols ,how ="left")
            merged ["Medium"]=merged ["Medium"].fillna ("Не указано")
        elif "Medium"not in merged .columns :
            merged ["Medium"]="Не указано"

        return merged .sort_values ("Дата").reset_index (drop =True )

    def _get_dimension_tab_names (self ):
        """Возвращает список вкладок изерений для единой KPI-логики."""
        return self ._get_dimension_names ()

    def _build_dimension_kpi_data (self ,tab_text ):
        """Собирает агрегированные данные для KPI по вкладке измерения."""
        if shared_calculate_kpi_metrics is not None and shared_build_kpi_dataframe_from_metrics is not None :
            if not hasattr (self ,"dimension_data")or tab_text not in self .dimension_data :
                return shared_build_kpi_dataframe_from_metrics (shared_calculate_kpi_metrics (pd .DataFrame ()))

            data =self .dimension_data .get (tab_text )
            return shared_build_kpi_dataframe_from_metrics (shared_calculate_kpi_metrics (data ))

        empty_data =pd .DataFrame ({
        "Расход":[0 ],
        "Клики":[0 ],
        "Лиды":[0 ],
        "Продажи":[0 ],
        "Выручка":[0 ],
        "Ср.чек":[0 ],
        "Маржа":[0 ],
        "ROMI":[-100 ],
        })

        if not hasattr (self ,"dimension_data")or tab_text not in self .dimension_data :
            return empty_data 

        data =self .dimension_data .get (tab_text )
        if data is None or data .empty :
            return empty_data 

        total_expense =pd .to_numeric (data ["Расход"],errors ="coerce").fillna (0 ).sum ()if "Расход"in data .columns else 0 
        total_clicks =pd .to_numeric (data ["Клики"],errors ="coerce").fillna (0 ).sum ()if "Клики"in data .columns else 0 
        total_leads =pd .to_numeric (data ["Лиды"],errors ="coerce").fillna (0 ).sum ()if "Лиды"in data .columns else 0 
        total_sales =pd .to_numeric (data ["Продажи"],errors ="coerce").fillna (0 ).sum ()if "Продажи"in data .columns else 0 
        total_revenue =pd .to_numeric (data ["Выручка"],errors ="coerce").fillna (0 ).sum ()if "Выручка"in data .columns else 0 
        avg_check =(total_revenue /total_sales )if total_sales >0 else 0 
        margin =total_revenue -total_expense 
        romi =((margin /total_expense )*100 )if total_expense >0 else -100 

        return pd .DataFrame ({
        "Расход":[total_expense ],
        "Клики":[total_clicks ],
        "Лиды":[total_leads ],
        "Продажи":[total_sales ],
        "Выручка":[total_revenue ],
        "Ср.чек":[avg_check ],
        "Маржа":[margin ],
        "ROMI":[romi ],
        })

    def get_current_period_code (self ):
        """Возвращает код периода для общей логики группировки."""
        group_type =self .group_combo .currentText ()if hasattr (self ,"group_combo")and self .group_combo else "день"
        period_map ={
        "день":"D",
        "неделя":"W",
        "есяц":"M",
        "квартал":"Q",
        "год":"Y",
        }
        return period_map .get (group_type ,"D")

    def update_kpi_for_current_tab (self ,tab_text ):
        """Обновляетт KPI для текущей вкладки по общей логике."""
        self .log (f"\nОбновление KPI для вкладки: {tab_text }")

        if tab_text =="Дата":
            self .update_kpi_with_data (self .filtered_data )
            return 

        if tab_text in self ._get_dimension_tab_names ():
            self .update_kpi_with_data (self ._build_dimension_kpi_data (tab_text ))
            return 

        if tab_text in ["📈 Графики","📊 План"]:
            self .update_kpi_with_data (self .filtered_data )

    def on_tab_changed (self ,index ):
        """Обработчик переключения вкладок с общей логикой KPI."""
        tab_text =self .tabs .tabText (index )
        self .log (f"\n=== ПЕРЕКЛЮЧЕНЕ НА ВКЛАДКУ: {tab_text } ===")
        self .update_kpi_for_current_tab (tab_text )

        if tab_text =="Дата":
            self .update_plan_display ()
        elif tab_text in ["📈 Графики","📊 План"]:
            self .update_plan_display ()

    def on_tab_changed_for_update (self ,index ):
        """Обработчик сены вкладки - обновляет дашборд"""
        tab_text =self .tabs .tabText (index )
        self .log (f"Сена вкладки на: {tab_text }")

        # Если переключились на вкладку "Дата", обновляе дашборд
        if tab_text =="Дата":
        # Проверяет, существует ли group_combo
            if hasattr (self ,'group_combo')and self .group_combo is not None :
                self .update_dashboard ()
            else :
                self .log ("group_combo еще не создан, пропускае обновление")
        else :
        # Для остальных вкладок обновляе KPI
            self .update_kpi_for_current_tab (tab_text )

    def _sanitize_export_name (self ,value ):
        """Cleans a label for use in export file names."""
        if not value :
            return "report"
        safe =str (value ).strip ()
        for bad in ['<','>',':','"','/','\\','|','?','*']:
            safe =safe .replace (bad ,"_")
        safe =safe .replace (" ","_")
        return safe or "report"

    def _build_export_default_path (self ,extension ):
        """Builds a default export path that includes project, tab, and period."""
        project_name =self ._sanitize_export_name (self .current_project or "project")
        _ ,tab_name =self ._get_current_report_table_for_export ()
        if hasattr (self ,"date_from")and hasattr (self ,"date_to"):
            period_from =self .date_from .date ().toString ("yyyy-MM-dd")
            period_to =self .date_to .date ().toString ("yyyy-MM-dd")
        else :
            period_from ="period_from"
            period_to ="period_to"
        file_name =f"{project_name }_{tab_name }_{period_from }_{period_to }.{extension }"
        return os .path .join (os .path .expanduser ("~"),file_name )

    def export_current_report_excel (self ):
        table ,_ =self ._get_current_report_table_for_export ()
        export_df =self ._table_widget_to_dataframe (table )
        if export_df .empty :
            QMessageBox .information (self ,"\u042d\u043a\u0441\u043f\u043e\u0440\u0442","\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430.")
            return 
        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043e\u0442\u0447\u0435\u0442\u0430 \u0432 Xlsx",
        self ._build_export_default_path ("xlsx"),
        "Xlsx Files (*.xlsx)"
        )
        if not file_path :
            return 
        try :
            export_df .to_excel (file_path ,index =False )
            self .log (f"\u041e\u0442\u0447\u0435\u0442 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d \u0432 Xlsx: {file_path }")
            QMessageBox .information (self ,"\u0423\u0441\u043f\u0435\u0445",f"\u041e\u0442\u0447\u0435\u0442 \u0432\u044b\u0433\u0440\u0443\u0436\u0435\u043d \u0432 Xlsx:\n{file_path }")
        except Exception as e :
            self .log (f"\u041e\u0448\u0438\u0431\u043a\u0430 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430 \u043e\u0442\u0447\u0435\u0442\u0430 \u0432 Xlsx: {e }")
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430",f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043e\u0442\u0447\u0435\u0442 \u0432 Xlsx:\n{e }")

    def export_current_report_csv (self ):
        table ,_ =self ._get_current_report_table_for_export ()
        export_df =self ._table_widget_to_dataframe (table )
        if export_df .empty :
            QMessageBox .information (self ,"\u042d\u043a\u0441\u043f\u043e\u0440\u0442","\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430.")
            return 
        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043e\u0442\u0447\u0435\u0442\u0430 \u0432 CSV",
        self ._build_export_default_path ("csv"),
        "CSV Files (*.csv)"
        )
        if not file_path :
            return 
        try :
            export_df .to_csv (file_path ,index =False ,encoding ="utf-8-sig",sep =";")
            self .log (f"\u041e\u0442\u0447\u0435\u0442 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d \u0432 CSV: {file_path }")
            QMessageBox .information (self ,"\u0423\u0441\u043f\u0435\u0445",f"\u041e\u0442\u0447\u0435\u0442 \u0432\u044b\u0433\u0440\u0443\u0436\u0435\u043d \u0432 CSV:\n{file_path }")
        except Exception as e :
            self .log (f"\u041e\u0448\u0438\u0431\u043a\u0430 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430 \u043e\u0442\u0447\u0435\u0442\u0430 \u0432 CSV: {e }")
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430",f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043e\u0442\u0447\u0435\u0442 \u0432 CSV:\n{e }")

    def _get_all_report_tables_for_export (self ):
        """Возвращает все табличные вкладки для пакетного экспорта."""
        report_tables =[]

        if hasattr (self ,"table")and self .table is not None :
            report_tables .append (("Дата",self .table ))

        for dimension_name in self ._get_dimension_names ():
            if hasattr (self ,"dimension_tables")and dimension_name in self .dimension_tables :
                table =self .dimension_tables .get (dimension_name )
                if table is not None :
                    report_tables .append ((dimension_name ,table ))

        return report_tables 

    def export_all_reports_excel (self ):
        """Экспортирует все табличные вкладки в один Xlsx-файл."""
        report_tables =self ._get_all_report_tables_for_export ()
        export_data =[]
        for tab_name ,table in report_tables :
            df =self ._table_widget_to_dataframe (table )
            if not df .empty :
                export_data .append ((tab_name ,df ))

        if not export_data :
            QMessageBox .information (self ,"\u042d\u043a\u0441\u043f\u043e\u0440\u0442","\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430.")
            return 

        default_path =self ._build_export_default_path ("xlsx").replace (".xlsx","_all_tabs.xlsx")
        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u0432\u0441\u0435\u0445 \u0432\u043a\u043b\u0430\u0434\u043e\u043a \u0432 Xlsx",
        default_path ,
        "Xlsx Files (*.xlsx)"
        )
        if not file_path :
            return 

        try :
            with pd .ExcelWriter (file_path ,engine ="openpyxl")as writer :
                for tab_name ,df in export_data :
                    sheet_name =self ._sanitize_export_name (tab_name )[:31 ]or "Sheet"
                    df .to_excel (writer ,sheet_name =sheet_name ,index =False )
            self .log (f"\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u0432 Xlsx: {file_path }")
            QMessageBox .information (self ,"\u0423\u0441\u043f\u0435\u0445",f"\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432\u044b\u0433\u0440\u0443\u0436\u0435\u043d\u044b \u0432 Xlsx:\n{file_path }")
        except Exception as e :
            self .log (f"\u041e\u0448\u0438\u0431\u043a\u0430 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430 \u0432\u0441\u0435\u0445 \u0432\u043a\u043b\u0430\u0434\u043e\u043a \u0432 Xlsx: {e }")
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430",f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0432\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 Xlsx:\n{e }")

    def export_all_reports_csv (self ):
        """Экспортирует все табличные вкладки в один CSV-файл блоками."""
        report_tables =self ._get_all_report_tables_for_export ()
        export_data =[]
        for tab_name ,table in report_tables :
            df =self ._table_widget_to_dataframe (table )
            if not df .empty :
                export_data .append ((tab_name ,df ))

        if not export_data :
            QMessageBox .information (self ,"\u042d\u043a\u0441\u043f\u043e\u0440\u0442","\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430.")
            return 

        default_path =self ._build_export_default_path ("csv").replace (".csv","_all_tabs.csv")
        file_path ,_ =QFileDialog .getSaveFileName (
        self ,
        "\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u0432\u0441\u0435\u0445 \u0432\u043a\u043b\u0430\u0434\u043e\u043a \u0432 CSV",
        default_path ,
        "CSV Files (*.csv)"
        )
        if not file_path :
            return 

        try :
            with open (file_path ,"w",encoding ="utf-8-sig",newline ="")as f :
                for index ,(tab_name ,df )in enumerate (export_data ):
                    f .write (f"{tab_name }\n")
                    df .to_csv (f ,index =False ,sep =";")
                    if index <len (export_data )-1 :
                        f .write ("\n\n")
            self .log (f"\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u0432 CSV: {file_path }")
            QMessageBox .information (self ,"\u0423\u0441\u043f\u0435\u0445",f"\u0412\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432\u044b\u0433\u0440\u0443\u0436\u0435\u043d\u044b \u0432 CSV:\n{file_path }")
        except Exception as e :
            self .log (f"\u041e\u0448\u0438\u0431\u043a\u0430 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0430 \u0432\u0441\u0435\u0445 \u0432\u043a\u043b\u0430\u0434\u043e\u043a \u0432 CSV: {e }")
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430",f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0432\u0441\u0435 \u0432\u043a\u043b\u0430\u0434\u043a\u0438 \u0432 CSV:\n{e }")

    def _fill_missing_crm_dimensions_from_ads (self ,crm_df ,ads_df ,dimension_cols ):
        """Fills missing CRM dimensions from ad data when the match is unambiguous."""
        if crm_df is None or crm_df .empty or ads_df is None or ads_df .empty :
            return crm_df 
        missing_values ={"","не указано","(не указано)","Не указано","(Не указано)","nan","None"}
        crm_df =crm_df .copy ()
        ads_df =ads_df .copy ()
        filled_counter =0 
        for col in dimension_cols :
            crm_df [col ]=crm_df [col ].fillna ("").astype (str )
            ads_df [col ]=ads_df [col ].fillna ("").astype (str )
        for idx in crm_df .index :
            candidates =ads_df [ads_df ["Дата"]==crm_df .at [idx ,"Дата"]].copy ()
            if candidates .empty :
                continue 
            for known_col in dimension_cols :
                known_value =str (crm_df .at [idx ,known_col ]).strip ()
                if known_value and known_value not in missing_values :
                    narrowed =candidates [candidates [known_col ].astype (str ).str .strip ()==known_value ]
                    if not narrowed .empty :
                        candidates =narrowed 
            if candidates .empty :
                continue 
            for target_col in dimension_cols :
                current_value =str (crm_df .at [idx ,target_col ]).strip ()
                if current_value and current_value not in missing_values :
                    continue 
                unique_values =[
                str (v ).strip ()
                for v in candidates [target_col ].dropna ().astype (str ).unique ().tolist ()
                if str (v ).strip ()and str (v ).strip ()not in missing_values 
                ]
                if len (unique_values )==1 :
                    crm_df .at [idx ,target_col ]=unique_values [0 ]
                    filled_counter +=1 
        if hasattr (self ,"log"):
            self .log (f"CRM-атрибуция: дозаполнено изерений из реклаы: {filled_counter }")
        return crm_df 

    def _build_merged_dataframe_from_sources (self ):
        """Builds the merged dataframe from ads and CRM with CRM dimension backfilling."""
        if not hasattr (self ,"ads_data")or self .ads_data is None :
            return pd .DataFrame ()
        if not hasattr (self ,"crm_data")or self .crm_data is None :
            return pd .DataFrame ()
        ads_df =self .ads_data .copy ()
        crm_df =self .crm_data .copy ()
        if ads_df .empty or crm_df .empty :
            return pd .DataFrame ()
        ads_df ["Дата"]=self ._parse_date_series (ads_df .get ("Дата"))
        crm_df ["Дата"]=self ._parse_date_series (crm_df .get ("Дата"))
        ads_df =ads_df .dropna (subset =["Дата"])
        crm_df =crm_df .dropna (subset =["Дата"])
        dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]
        for col in dimension_cols :
            if col not in ads_df .columns :
                ads_df [col ]="не указано"
            if col not in crm_df .columns :
                crm_df [col ]="не указано"
            ads_df [col ]=ads_df [col ].fillna ("").astype (str ).replace ("","не указано")
            crm_df [col ]=crm_df [col ].fillna ("").astype (str ).replace ("","не указано")
        crm_df =self ._fill_missing_crm_dimensions_from_ads (crm_df ,ads_df ,dimension_cols )
        ads_numeric =["Расход","Показы","Клики"]
        crm_numeric =["Лиды","Продажи","Ср.чек"]
        for col in ads_numeric :
            if col not in ads_df .columns :
                ads_df [col ]=0 
            ads_df [col ]=pd .to_numeric (ads_df [col ],errors ="coerce").fillna (0 )
        for col in crm_numeric :
            if col not in crm_df .columns :
                crm_df [col ]=0 
            crm_df [col ]=pd .to_numeric (crm_df [col ],errors ="coerce").fillna (0 )
        merge_cols =["Дата"]+dimension_cols 
        ads_for_merge =ads_df [merge_cols +ads_numeric ].copy ()
        crm_for_merge =crm_df [merge_cols +crm_numeric ].copy ()
        merged =pd .merge (ads_for_merge ,crm_for_merge ,on =merge_cols ,how ="outer")
        for col in ads_numeric +crm_numeric :
            merged [col ]=pd .to_numeric (merged [col ],errors ="coerce").fillna (0 )
        for col in dimension_cols :
            merged [col ]=merged [col ].fillna ("не указано")
        merged =(
        merged .groupby (merge_cols ,dropna =False )
        .agg ({"Расход":"sum","Показы":"sum","Клики":"sum","Лиды":"sum","Продажи":"sum","Ср.чек":"mean"})
        .reset_index ()
        )
        merged ["Выручка"]=(merged ["Продажи"]*merged ["Ср.чек"]).round (0 )
        merged ["CTR"]=np .where (merged ["Показы"]>0 ,merged ["Клики"]/merged ["Показы"]*100 ,0 ).round (2 )
        merged ["CR1"]=np .where (merged ["Клики"]>0 ,merged ["Лиды"]/merged ["Клики"]*100 ,0 ).round (2 )
        merged ["CPC"]=np .where (merged ["Клики"]>0 ,np .round (merged ["Расход"]/merged ["Клики"]),0 )
        merged ["CPL"]=np .where (merged ["Лиды"]>0 ,np .round (merged ["Расход"]/merged ["Лиды"]),0 )
        merged ["CR2"]=np .where (merged ["Лиды"]>0 ,merged ["Продажи"]/merged ["Лиды"]*100 ,0 ).round (2 )
        merged ["Маржа"]=(merged ["Выручка"]-merged ["Расход"]).round (0 )
        merged ["ROMI"]=np .where (merged ["Расход"]>0 ,((merged ["Выручка"]-merged ["Расход"])/merged ["Расход"]*100 ).round (2 ),-100 )
        for int_col in ["Показы","Клики","Лиды","Продажи","CPC","CPL"]:
            merged [int_col ]=pd .to_numeric (merged [int_col ],errors ="coerce").fillna (0 ).round (0 ).astype (int )
        for money_col in ["Расход","Ср.чек","Выручка","Маржа"]:
            merged [money_col ]=pd .to_numeric (merged [money_col ],errors ="coerce").fillna (0 ).round (0 )
        if "Medium"in ads_df .columns or "Medium"in crm_df .columns :
            ads_medium =ads_df [["Дата"]+dimension_cols +(["Medium"]if "Medium"in ads_df .columns else [])].copy ()
            crm_medium =crm_df [["Дата"]+dimension_cols +(["Medium"]if "Medium"in crm_df .columns else [])].copy ()
            if "Medium"not in ads_medium .columns :
                ads_medium ["Medium"]="Не указано"
            if "Medium"not in crm_medium .columns :
                crm_medium ["Medium"]="Не указано"
            ads_medium ["Medium"]=ads_medium ["Medium"].fillna ("").astype (str ).replace ("","Не указано")
            crm_medium ["Medium"]=crm_medium ["Medium"].fillna ("").astype (str ).replace ("","Не указано")
            medium_map =pd .concat ([ads_medium ,crm_medium ],ignore_index =True )
            medium_map =medium_map .drop_duplicates (subset =merge_cols ,keep ="first")
            merged =merged .merge (medium_map [merge_cols +["Medium"]],on =merge_cols ,how ="left")
            merged ["Medium"]=merged ["Medium"].fillna ("Не указано")
        elif "Medium"not in merged .columns :
            merged ["Medium"]="Не указано"

        if hasattr (self ,"log"):
            unattributed_ads =int ((merged ["Объявление"].astype (str ).str .strip ().str .lower ()=="не указано").sum ())if "Объявление"in merged .columns else 0 
            unattributed_keywords =int ((merged ["Ключевая фраза"].astype (str ).str .strip ().str .lower ()=="не указано").sum ())if "Ключевая фраза"in merged .columns else 0 
            self .log (f"После объединения: строк с 'не указано' в Объявление = {unattributed_ads }")
            self .log (f"После объединения: строк с 'не указано' в Ключевая фраза = {unattributed_keywords }")
        return merged .sort_values ("Дата").reset_index (drop =True )

    def merge_data (self ):
        """Merges ads and CRM data using the stabilized merge pipeline."""
        self .log ("\n=== ОЪЕДНЕНЕ ДАННЫХ ===")
        if (not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty )and self .ads_file_path :
            restored_ads =self ._load_saved_source_file (self .ads_file_path ,"ads")
            if restored_ads is not None and not restored_ads .empty :
                self .ads_data =restored_ads 
        if (not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty )and self .crm_file_path :
            restored_crm =self ._load_saved_source_file (self .crm_file_path ,"crm")
            if restored_crm is not None and not restored_crm .empty :
                self .crm_data =restored_crm 
        self .refresh_data_loader_labels ()
        if not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty :
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430","\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0440\u0435\u043a\u043b\u0430\u043c\u044b")
            return 
        if not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty :
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430","\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 CRM")
            return 
        try :
            merged =self ._build_merged_dataframe_from_sources ()
            if merged .empty :
                QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430","\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0438\u0442\u044c \u0434\u0430\u043d\u043d\u044b\u0435.")
                return 
            self .data =merged .copy ()
            self .original_data =merged .copy ()
            self .chart_data =merged .copy ()
            if self .current_client in self .clients :
                self .clients [self .current_client ]["data"]=merged .copy ()
            self .update_filters_from_data ()
            self .refresh_plan_dimension_options ()
            self .update_dashboard ()
            self .refresh_data_loader_labels ()
            self .auto_save_project ()
            expense =int (pd .to_numeric (merged .get ("Расход"),errors ="coerce").fillna (0 ).sum ())if "Расход"in merged .columns else 0 
            leads =int (pd .to_numeric (merged .get ("Лиды"),errors ="coerce").fillna (0 ).sum ())if "Лиды"in merged .columns else 0 
            sales =int (pd .to_numeric (merged .get ("Продажи"),errors ="coerce").fillna (0 ).sum ())if "Продажи"in merged .columns else 0 
            QMessageBox .information (self ,"\u0423\u0441\u043f\u0435\u0445",f"\u0414\u0430\u043d\u043d\u044b\u0435 \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0435\u043d\u044b\n\u0412\u0441\u0435\u0433\u043e \u0441\u0442\u0440\u043e\u043a: {len (merged )}\n\u0420\u0430\u0441\u0445\u043e\u0434: {expense :,}\n\u041b\u0438\u0434\u044b: {leads :,}\n\u041f\u0440\u043e\u0434\u0430\u0436\u0438: {sales :,}")
        except Exception as e :
            self .log (f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f \u0434\u0430\u043d\u043d\u044b\u0445: {e }")
            QMessageBox .warning (self ,"\u041e\u0448\u0438\u0431\u043a\u0430",f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f:\n{e }")

    def _normalize_source_dataframe (self ,df ,source_type ):
        """Нормализует загруженный источник перед объединением."""
        if shared_normalize_source_dataframe is not None :
            return shared_normalize_source_dataframe (df ,source_type ,date_parser =self ._parse_date_series )

        if df is None or not isinstance (df ,pd .DataFrame )or df .empty :
            return pd .DataFrame ()

        normalized =df .copy ()
        normalized .columns =[str (col ).strip ()for col in normalized .columns ]

        if "Тип"in normalized .columns and "Medium"not in normalized .columns :
            normalized ["Medium"]=normalized ["Тип"]
        elif "Medium"in normalized .columns and "Тип"not in normalized .columns :
            normalized ["Тип"]=normalized ["Medium"]

        date_col ="Дата"
        if date_col in normalized .columns :
            try :
                normalized [date_col ]=self ._parse_date_series (normalized [date_col ])
            except Exception :
                normalized [date_col ]=pd .to_datetime (normalized [date_col ],errors ="coerce",dayfirst =True )
            normalized =normalized .dropna (subset =[date_col ]).copy ()
        else :
            return pd .DataFrame ()

        text_placeholders ={"","nan","none","null","nat","не указано","(не указано)"}
        dimension_defaults ={
        "Источник":"(не указано)",
        "Кампания":"(не указано)",
        "Группа":"(не указано)",
        "Объявление":"(не указано)",
        "Ключевая фраза":"(не указано)",
        "Регион":"(не указано)",
        "Устройство":"(не указано)",
        "Площадка":"(не указано)",
        "Position":"(не указано)",
        "URL":"(не указано)",
        "Продукт":"(не указано)",
        "Medium":"Не указано",
        "Тип":"Не указано",
        }

        for col ,default_value in dimension_defaults .items ():
            if col not in normalized .columns :
                normalized [col ]=default_value 
            else :
                series =normalized [col ].fillna ("").astype (str ).str .strip ()
                normalized [col ]=series .apply (
                lambda value :default_value if value .strip ().lower ()in text_placeholders else value .strip ()
                )

        numeric_defaults ={
        "ads":["Расход","Показы","Клики"],
        "crm":["Лиды","Продажи","Выручка","Ср.чек"],
        }
        all_numeric =["Расход","Показы","Клики","Лиды","Продажи","Выручка","Ср.чек"]
        for col in all_numeric :
            if col not in normalized .columns :
                normalized [col ]=0 
            normalized [col ]=pd .to_numeric (normalized [col ],errors ="coerce").fillna (0 )

        if source_type =="ads":
            for col in ["Лиды","Продажи","Выручка","Ср.чек"]:
                if col not in df .columns :
                    normalized [col ]=0 
        elif source_type =="crm":
            for col in ["Расход","Показы","Клики"]:
                if col not in df .columns :
                    normalized [col ]=0 
            if "Выручка"not in df .columns and {"Продажи","Ср.чек"}.issubset (normalized .columns ):
                normalized ["Выручка"]=pd .to_numeric (normalized ["Продажи"],errors ="coerce").fillna (0 )*pd .to_numeric (normalized ["Ср.чек"],errors ="coerce").fillna (0 )
            if {"Выручка","Продажи"}.issubset (normalized .columns ):
                normalized ["Ср.чек"]=np .where (
                pd .to_numeric (normalized ["Продажи"],errors ="coerce").fillna (0 )>0 ,
                pd .to_numeric (normalized ["Выручка"],errors ="coerce").fillna (0 )/pd .to_numeric (normalized ["Продажи"],errors ="coerce").fillna (0 ),
                0 
                )

        normalized =normalized .sort_values ("Дата").reset_index (drop =True )
        return normalized 

    def _log_source_quality (self ,source_name ,df ):
        """Пишет в лог краткую сводку по качеству источника."""
        if df is None or df .empty :
            self .log (f"{source_name }: источник пустой")
            return 

        date_min =df ["Дата"].min ().strftime ("%d.%m.%Y")if "Дата"in df .columns and not df ["Дата"].empty else "?"
        date_max =df ["Дата"].max ().strftime ("%d.%m.%Y")if "Дата"in df .columns and not df ["Дата"].empty else "?"
        self .log (f"{source_name }: строк={len (df )}, период={date_min } - {date_max }")

        for col in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Medium"]:
            if col in df .columns :
                missing_mask =df [col ].astype (str ).str .strip ().str .lower ().isin (["(не указано)","не указано",""])
                self .log (f"{source_name }: '{col }' не указано = {int (missing_mask .sum ())}")

    def _log_crm_attribution_quality (self ,label ,df ):
        """Пишет в лог качество атрибуции CRM по ключевы измерения."""
        if df is None or df .empty :
            self .log (f"{label }: CRM-данные пустые")
            return 

        self .log (f"=== КОНТРОЛЬ АТРУЦ CRM: {label } ===")
        sales_series =pd .to_numeric (df ["Продажи"],errors ="coerce").fillna (0 )if "Продажи"in df .columns else pd .Series ([0 ]*len (df ))
        leads_series =pd .to_numeric (df ["Лиды"],errors ="coerce").fillna (0 )if "Лиды"in df .columns else pd .Series ([0 ]*len (df ))

        for col in ["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            if col not in df .columns :
                continue 
            missing_mask =df [col ].astype (str ).str .strip ().str .lower ().isin (["(не указано)","не указано",""])
            self .log (
            f"{label }: {col } -> строк без атрибуции = {int (missing_mask .sum ())}, "
            f"лидов = {int (leads_series [missing_mask ].sum ())}, продаж = {int (sales_series [missing_mask ].sum ())}"
            )

    def _fill_missing_crm_dimensions_from_ads (self ,crm_df ,ads_df ,dimension_cols ):
        """Дозаполняет отсутствующие CRM-измерения из реклаы при однозначно совпадении."""
        if shared_fill_missing_crm_dimensions_from_ads is not None :
            crm_filled ,filled_counter =shared_fill_missing_crm_dimensions_from_ads (crm_df ,ads_df ,dimension_cols )
            self .log (f"CRM-атрибуция: дозаполнено изерений из реклаы: {filled_counter }")
            return crm_filled 

        if crm_df is None or crm_df .empty or ads_df is None or ads_df .empty :
            return crm_df 

        crm_filled =crm_df .copy ()
        filled_counter =0 
        missing_values ={"","(не указано)","не указано"}

        for idx ,crm_row in crm_filled .iterrows ():
            candidates =ads_df [ads_df ["Дата"]==crm_row ["Дата"]]
            if candidates .empty :
                continue 

            for known_col in dimension_cols :
                if known_col not in crm_filled .columns or known_col not in candidates .columns :
                    continue 
                crm_value =str (crm_row .get (known_col ,"")).strip ()
                if crm_value and crm_value .lower ()not in missing_values :
                    candidates =candidates [candidates [known_col ].astype (str ).str .strip ()==crm_value ]
                    if candidates .empty :
                        break 

            if candidates .empty :
                continue 

            for target_col in dimension_cols :
                crm_value =str (crm_filled .at [idx ,target_col ]).strip ()if target_col in crm_filled .columns else ""
                if crm_value .lower ()not in missing_values :
                    continue 

                unique_values =(
                candidates [target_col ]
                .dropna ()
                .astype (str )
                .str .strip ()
                )
                unique_values =[value for value in unique_values .unique ().tolist ()if value and value .lower ()not in missing_values ]
                if len (unique_values )==1 :
                    crm_filled .at [idx ,target_col ]=unique_values [0 ]
                    filled_counter +=1 

        self .log (f"CRM-атрибуция: дозаполнено изерений из реклаы: {filled_counter }")
        return crm_filled 

    def _build_merged_dataframe_from_sources (self ):
        """Строит устойчивую merged-таблицу из реклаы и CRM."""
        if shared_build_merged_dataframe_from_sources is not None :
            if not hasattr (self ,"ads_data")or self .ads_data is None or self .ads_data .empty :
                return pd .DataFrame ()
            if not hasattr (self ,"crm_data")or self .crm_data is None or self .crm_data .empty :
                return pd .DataFrame ()

            crm_before_fill =shared_normalize_source_dataframe (
            self .crm_data ,
            "crm",
            date_parser =self ._parse_date_series ,
            )if shared_normalize_source_dataframe is not None else self ._normalize_source_dataframe (self .crm_data ,"crm")

            merged ,ads_df ,crm_df ,filled_counter =shared_build_merged_dataframe_from_sources (
            self .ads_data ,
            self .crm_data ,
            date_parser =self ._parse_date_series ,
            )

            if merged .empty :
                return pd .DataFrame ()

            self .ads_data =ads_df .copy ()
            self .crm_data =crm_df .copy ()

            self ._log_source_quality ("Реклаа",ads_df )
            self ._log_source_quality ("CRM",crm_df )
            self ._log_crm_attribution_quality ("до дозаполнения",crm_before_fill )
            self .log (f"CRM-атрибуция: дозаполнено изерений из реклаы: {filled_counter }")
            self ._log_crm_attribution_quality ("после дозаполнения",crm_df )

            unattributed_ads =int ((merged ["Объявление"].astype (str ).str .strip ().str .lower ()=="(не указано)").sum ())if "Объявление"in merged .columns else 0 
            unattributed_keywords =int ((merged ["Ключевая фраза"].astype (str ).str .strip ().str .lower ()=="(не указано)").sum ())if "Ключевая фраза"in merged .columns else 0 
            self .log (f"После объединения: строк с '(не указано)' в Объявление = {unattributed_ads }")
            self .log (f"После объединения: строк с '(не указано)' в Ключевая фраза = {unattributed_keywords }")
            self .log (f"После объединения: итоговый расход = {merged ['Расход'].sum ():,.0f}")
            self .log (f"После объединения: итоговые лиды = {merged ['Лиды'].sum ():,.0f}")
            self .log (f"После объединения: итоговые продажи = {merged ['Продажи'].sum ():,.0f}")
            unresolved_sales =int (
            pd .to_numeric (
            merged .loc [
            merged ["Объявление"].astype (str ).str .strip ().str .lower ().eq ("(не указано)")
            |merged ["Ключевая фраза"].astype (str ).str .strip ().str .lower ().eq ("(не указано)"),
            "Продажи",
            ],
            errors ="coerce",
            ).fillna (0 ).sum ()
            )if "Продажи"in merged .columns else 0 
            self .log (f"После объединения: продаж в частично неатрибутированных строках = {unresolved_sales }")
            return merged 

        if not hasattr (self ,"ads_data")or self .ads_data is None or self .ads_data .empty :
            return pd .DataFrame ()
        if not hasattr (self ,"crm_data")or self .crm_data is None or self .crm_data .empty :
            return pd .DataFrame ()

        ads_df =self ._normalize_source_dataframe (self .ads_data ,"ads")
        crm_df =self ._normalize_source_dataframe (self .crm_data ,"crm")

        if ads_df .empty or crm_df .empty :
            return pd .DataFrame ()

        self .ads_data =ads_df .copy ()
        self .crm_data =crm_df .copy ()

        self ._log_source_quality ("Реклаа",ads_df )
        self ._log_source_quality ("CRM",crm_df )
        self ._log_crm_attribution_quality ("до дозаполнения",crm_df )

        dimension_cols =["Источник","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]
        crm_df =self ._fill_missing_crm_dimensions_from_ads (crm_df ,ads_df ,dimension_cols )
        self ._log_crm_attribution_quality ("после дозаполнения",crm_df )

        merge_cols =["Дата"]+dimension_cols 

        ads_grouped =(
        ads_df .groupby (merge_cols ,dropna =False )
        .agg ({"Расход":"sum","Показы":"sum","Клики":"sum"})
        .reset_index ()
        )

        crm_df ["__crm_revenue"]=pd .to_numeric (crm_df .get ("Выручка",0 ),errors ="coerce").fillna (0 )
        crm_grouped =(
        crm_df .groupby (merge_cols ,dropna =False )
        .agg ({"Лиды":"sum","Продажи":"sum","__crm_revenue":"sum"})
        .reset_index ()
        )
        crm_grouped ["Ср.чек"]=np .where (
        crm_grouped ["Продажи"]>0 ,
        crm_grouped ["__crm_revenue"]/crm_grouped ["Продажи"],
        0 ,
        )

        merged =pd .merge (ads_grouped ,crm_grouped ,on =merge_cols ,how ="outer")

        for col in ["Расход","Показы","Клики","Лиды","Продажи","__crm_revenue","Ср.чек"]:
            if col not in merged .columns :
                merged [col ]=0 
            merged [col ]=pd .to_numeric (merged [col ],errors ="coerce").fillna (0 )

        for col in dimension_cols :
            if col not in merged .columns :
                merged [col ]="(не указано)"
            merged [col ]=merged [col ].fillna ("(не указано)").astype (str )
            merged [col ]=merged [col ].replace ("","(не указано)")

        merged ["Medium"]="Не указано"
        if "Medium"in ads_df .columns :
            ads_medium_map =(
            ads_df [merge_cols +["Medium"]]
            .drop_duplicates (subset =merge_cols ,keep ="first")
            )
            merged =merged .merge (ads_medium_map ,on =merge_cols ,how ="left",suffixes =("","_ads"))
            if "Medium_ads"in merged .columns :
                merged ["Medium"]=merged ["Medium_ads"].fillna (merged ["Medium"])
                merged =merged .drop (columns =["Medium_ads"])
        if "Medium"in crm_df .columns :
            crm_medium_map =(
            crm_df [merge_cols +["Medium"]]
            .drop_duplicates (subset =merge_cols ,keep ="first")
            )
            merged =merged .merge (crm_medium_map ,on =merge_cols ,how ="left",suffixes =("","_crm"))
            if "Medium_crm"in merged .columns :
                merged ["Medium"]=merged ["Medium"].where (
                merged ["Medium"].astype (str ).str .strip ().ne ("Не указано"),
                merged ["Medium_crm"]
                )
                merged =merged .drop (columns =["Medium_crm"])
        merged ["Medium"]=merged ["Medium"].fillna ("Не указано").astype (str ).replace ("","Не указано")

        merged ["Выручка"]=merged ["__crm_revenue"].round (0 )
        merged ["CTR"]=np .where (merged ["Показы"]>0 ,merged ["Клики"]/merged ["Показы"]*100 ,0 ).round (2 )
        merged ["CR1"]=np .where (merged ["Клики"]>0 ,merged ["Лиды"]/merged ["Клики"]*100 ,0 ).round (2 )
        merged ["CPC"]=np .where (merged ["Клики"]>0 ,merged ["Расход"]/merged ["Клики"],0 ).round (0 )
        merged ["CPL"]=np .where (merged ["Лиды"]>0 ,merged ["Расход"]/merged ["Лиды"],0 ).round (0 )
        merged ["CR2"]=np .where (merged ["Лиды"]>0 ,merged ["Продажи"]/merged ["Лиды"]*100 ,0 ).round (2 )
        merged ["Маржа"]=(merged ["Выручка"]-merged ["Расход"]).round (0 )
        merged ["ROMI"]=np .where (
        merged ["Расход"]>0 ,
        ((merged ["Выручка"]-merged ["Расход"])/merged ["Расход"])*100 ,
        -100 ,
        ).round (2 )

        for int_col in ["Показы","Клики","Лиды","Продажи","CPC","CPL"]:
            merged [int_col ]=pd .to_numeric (merged [int_col ],errors ="coerce").fillna (0 ).round (0 ).astype (int )
        for money_col in ["Расход","Ср.чек","Выручка","Маржа"]:
            merged [money_col ]=pd .to_numeric (merged [money_col ],errors ="coerce").fillna (0 ).round (0 )

        merged =merged .drop (columns =["__crm_revenue"],errors ="ignore")
        merged =merged .sort_values ("Дата").reset_index (drop =True )

        unattributed_ads =int ((merged ["Объявление"].astype (str ).str .strip ().str .lower ()=="(не указано)").sum ())if "Объявление"in merged .columns else 0 
        unattributed_keywords =int ((merged ["Ключевая фраза"].astype (str ).str .strip ().str .lower ()=="(не указано)").sum ())if "Ключевая фраза"in merged .columns else 0 
        self .log (f"После объединения: строк с '(не указано)' в Объявление = {unattributed_ads }")
        self .log (f"После объединения: строк с '(не указано)' в Ключевая фраза = {unattributed_keywords }")
        self .log (f"После объединения: итоговый расход = {merged ['Расход'].sum ():,.0f}")
        self .log (f"После объединения: итоговые лиды = {merged ['Лиды'].sum ():,.0f}")
        self .log (f"После объединения: итоговые продажи = {merged ['Продажи'].sum ():,.0f}")
        unresolved_sales =int (
        pd .to_numeric (
        merged .loc [
        merged ["Объявление"].astype (str ).str .strip ().str .lower ().eq ("(не указано)")
        |merged ["Ключевая фраза"].astype (str ).str .strip ().str .lower ().eq ("(не указано)"),
        "Продажи",
        ],
        errors ="coerce",
        ).fillna (0 ).sum ()
        )if "Продажи"in merged .columns else 0 
        self .log (f"После объединения: продаж в частично неатрибутированных строках = {unresolved_sales }")
        return merged 

    def _get_dimension_names (self ):
        """Возвращает единый список вкладок-изерений."""
        return ["Источник","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]

    def _get_reserved_project_files (self ):
        """Возвращает служебные JSON-файлы, которые не считаются проектами."""
        return {"projects_index.json","plans_history.json"}

    def update_project_list (self ):
        """Финальная стабильная версия обновления списка проектов."""
        if not hasattr (self ,"project_list")or self .project_list is None :
            return 

        self .project_list .clear ()
        active_row =-1 
        selected_row =-1 

        if os .path .exists (self .projects_dir ):
            reserved_files =self ._get_reserved_project_files ()
            project_files =sorted (
            [
            file_name for file_name in os .listdir (self .projects_dir )
            if file_name .endswith (".json")and file_name not in reserved_files 
            ],
            key =lambda file_name :file_name .lower ()
            )

            for file_name in project_files :
                project_name =file_name .replace (".json","")
                label =project_name 
                if self .current_project and project_name ==self .current_project :
                    label =f" {project_name } (активный)"
                self .project_list .addItem (label )

                row_index =self .project_list .count ()-1 
                if self .current_project and project_name ==self .current_project :
                    active_row =row_index 
                if self .selected_project_name and project_name ==self .selected_project_name :
                    selected_row =row_index 

        if active_row >=0 :
            self .project_list .setCurrentRow (active_row )
        elif selected_row >=0 :
            self .project_list .setCurrentRow (selected_row )

        self .update_project_status_labels ()

    def refresh_all_dimension_tabs (self ):
        """Финальная стабильная версия обновления всех вкладок изерений."""
        if not hasattr (self ,"dimension_data"):
            self .dimension_data ={}

        from_date =self .date_from .date ().toPyDate ()if hasattr (self ,"date_from")else None 
        to_date =self .date_to .date ().toPyDate ()if hasattr (self ,"date_to")else None 

        for dimension_name in self ._get_dimension_names ():
            try :
                self .update_dimension_table_with_filter (dimension_name ,from_date ,to_date )
            except Exception as e :
                self .log (f"Ошибка обновления вкладки '{dimension_name }': {e }")
                empty_df =pd .DataFrame (columns =[dimension_name ])
                self .dimension_data [dimension_name ]=empty_df 
                if hasattr (self ,"display_dimension_table"):
                    self .display_dimension_table (dimension_name ,empty_df )

    def _require_project_for_connections (self ):
        """Проверяетт, что есть активный проект для сохранения подключений."""
        if self .current_project :
            return True 
        QMessageBox .information (
        self ,
        "Проект не выбран",
        "Сначала создайте или загрузите проект. Подключения кабинетов и CRM сохраняются внутри проекта."
        )
        return False 

    def _format_connection_item_text (self ,platform_name ,config ):
        """Форматирует строку подключения для бокового списка."""
        if not config :
            return f"{platform_name } (не подключен)"

        account_name =str (config .get ("account_name","")).strip ()
        identifier =str (config .get ("identifier","")).strip ()
        status =str (config .get ("status","Не подключен")).strip ()or "Не подключен"
        suffix_parts =[part for part in [account_name ,identifier ]if part ]
        suffix =" / ".join (suffix_parts )
        if suffix :
            return f"{platform_name }: {suffix } ({status .lower ()})"
        return f"{platform_name } ({status .lower ()})"

    def _build_connection_tooltip (self ,platform_name ,config ):
        """Собирает tooltip для записи подключения."""
        if not config :
            return f"{platform_name }\nСтатус: не подключен"

        account_name =str (config .get ("account_name","")).strip ()or "—"
        identifier =str (config .get ("identifier","")).strip ()or "—"
        status =str (config .get ("status","Не подключен")).strip ()or "Не подключен"
        note =str (config .get ("note","")).strip ()or "—"
        updated_at =str (config .get ("updated_at","")).strip ()or "—"
        return (
        f"{platform_name }\n"
        f"Название: {account_name }\n"
        f"ID / логин: {identifier }\n"
        f"Статус: {status }\n"
        f"Комментарий: {note }\n"
        f"Обновлено: {updated_at }"
        )

    def _get_connector_catalog (self ):
        """Каталог поддерживаеых коннекторов и их базовых требований."""
        return {
        "ads":{
        "Яндекс.Директ":{
        "kind_label":"рекламный кабинет",
        "auth_hint":"Токен Direct API. Для тестового доступа используйте sandbox, для полного — боевой режим.",
        "identifier_label":"Логин клиента / ID аккаунта (необязательно для своего кабинета)",
        "required_auth_fields":["token"],
        },
        "Google Ads":{
        "kind_label":"рекламный кабинет",
        "auth_hint":"OAuth: client_id + client_secret + refresh_token",
        "identifier_label":"Customer ID / логин",
        "required_auth_fields":["client_id","client_secret","refresh_token"],
        },
        "VK Ads":{
        "kind_label":"рекламный кабинет",
        "auth_hint":"Обычно достаточно token, при необходимости можно указать client_id",
        "identifier_label":"ID кабинета / логин",
        "required_auth_fields":["token"],
        },
        "Telegram Ads":{
        "kind_label":"рекламный кабинет",
        "auth_hint":"Обычно достаточно token или внутреннего API-ключа",
        "identifier_label":"ID аккаунта / логин",
        "required_auth_fields":["token"],
        },
        },
        "crm":{
        "AmoCRM":{
        "kind_label":"CRM",
        "auth_hint":"Укажите домен аккаунта вида company.amocrm.ru и access token. Для будущего автообновления ожно добавить client_id, client_secret и refresh_token.",
        "identifier_label":"Домен аккаунта / полный URL",
        "required_auth_fields":["token"],
        },
        "Bitrix24":{
        "kind_label":"CRM",
        "auth_hint":"Укажите портал типа company.bitrix24.ru и webhook path в поле Токен, например 1/xxxxxxxxxx. Либо вставьте полный webhook URL в поле ID / логин.",
        "identifier_label":"Портал / домен / полный webhook URL",
        "required_auth_fields":["token"],
        },
        },
        }

    def _get_connector_definition (self ,connection_kind ,platform_name ):
        """Описание конкретного коннектора."""
        return self ._get_connector_catalog ().get (connection_kind ,{}).get (platform_name ,{})

    def _get_connector_adapter (self ,connection_kind ,platform_name ):
        """Возвращает единое описание адаптера коннектора."""
        definition =self ._get_connector_definition (connection_kind ,platform_name ).copy ()
        if not definition :
            definition ={
            "kind_label":"коннектор",
            "auth_hint":"Настройте параметры авторизации.",
            "identifier_label":"ID / логин",
            "required_auth_fields":[],
            }

        default_capabilities ={
        "test_connection":True ,
        "fetch_accounts":connection_kind =="ads",
        "fetch_campaigns":connection_kind =="ads",
        "fetch_stats":connection_kind =="ads",
        "fetch_leads":connection_kind =="crm",
        "fetch_sales":connection_kind =="crm",
        }
        definition ["connection_kind"]=connection_kind 
        definition ["platform"]=platform_name 
        definition ["capabilities"]=definition .get ("capabilities",default_capabilities )
        return definition 

    def _build_connection_settings_payload (self ,connection_kind ,platform_name ,account_name ,identifier ,auth_fields =None ,status ="",note =""):
        """Собирает единый payload настроек подключения."""
        auth_fields =auth_fields or {}
        adapter =self ._get_connector_adapter (connection_kind ,platform_name )
        return {
        "platform":str (platform_name ).strip (),
        "connection_kind":connection_kind ,
        "adapter_key":str (platform_name ).strip ().lower (),
        "account_name":str (account_name ).strip (),
        "identifier":str (identifier ).strip (),
        "token":str (auth_fields .get ("token","")).strip (),
        "client_id":str (auth_fields .get ("client_id","")).strip (),
        "client_secret":str (auth_fields .get ("client_secret","")).strip (),
        "refresh_token":str (auth_fields .get ("refresh_token","")).strip (),
        "status":str (status ).strip ()or "Не подключен",
        "api_mode":str (auth_fields .get ("api_mode","production")).strip ()or "production",
        "client_login_mode":str (auth_fields .get ("client_login_mode","auto")).strip ()or "auto",
        "note":str (note ).strip (),
        "auth_hint":adapter .get ("auth_hint",""),
        "capabilities":adapter .get ("capabilities",{}),
        "updated_at":datetime .now ().isoformat (timespec ="seconds"),
        }

    def _bitrix24_has_full_webhook_url (self ,identifier ):
        """Проверяетт, что в идентификаторе уже указан полный webhook URL Bitrix24."""
        identifier =str (identifier or "").strip ()
        return identifier .startswith ("http://")or identifier .startswith ("https://")

    def _build_bitrix24_method_url (self ,config ,method_name ):
        """Собирает URL метода Bitrix24 REST API."""
        identifier =str (config .get ("identifier","")).strip ()
        token =str (config .get ("token","")).strip ().strip ("/")

        if self ._bitrix24_has_full_webhook_url (identifier ):
            base_url =identifier .rstrip ("/")
            if base_url .endswith (".json"):
                base_url =base_url [:base_url .rfind ("/")]
            return f"{base_url }/{method_name }.json"

        portal =identifier .replace ("https://","").replace ("http://","").strip ().strip ("/")
        if not portal :
            raise RuntimeError ("Не указан портал Bitrix24.")
        if not token :
            raise RuntimeError ("Не указан webhook path / токен Bitrix24.")
        return f"https://{portal }/rest/{token }/{method_name }.json"

    def _build_amocrm_base_url (self ,config ):
        """Собирает базовый URL аккаунта amoCRM."""
        identifier =str (config .get ("identifier","")).strip ()
        if not identifier :
            raise RuntimeError ("Не указан домен amoCRM.")
        if identifier .startswith ("http://")or identifier .startswith ("https://"):
            return identifier .rstrip ("/")
        return f"https://{identifier .strip ('/')}"

    def _amocrm_request (self ,config ,method ,path ,params =None ,payload =None ,timeout =45 ):
        """Выполняет запрос к amoCRM API v4."""
        token =str (config .get ("token","")).strip ()
        if not token :
            raise RuntimeError ("Не указан access token amoCRM.")
        base_url =self ._build_amocrm_base_url (config )
        url =f"{base_url }{path }"
        if params :
            url =f"{url }?{urllib .parse .urlencode (params ,doseq =True )}"

        headers ={
        "Authorization":f"Bearer {token }",
        "Content-Type":"application/json",
        }
        request_data =None 
        if payload is not None :
            request_data =json .dumps (payload ).encode ("utf-8")
        request =urllib .request .Request (url ,data =request_data ,headers =headers ,method =method .upper ())
        with urllib .request .urlopen (request ,timeout =timeout )as response :
            body =response .read ().decode ("utf-8")
            return json .loads (body )if body else {}

    def _amocrm_extract_custom_field_value (self ,row ,codes ):
        """Извлекает первое значение из custom_fields_values по коду или иени поля."""
        custom_fields =row .get ("custom_fields_values")or []
        normalized_codes ={str (code ).strip ().upper ()for code in codes }
        for field in custom_fields :
            field_code =str (field .get ("field_code","")).strip ().upper ()
            field_name =str (field .get ("field_name","")).strip ().upper ()
            if field_code in normalized_codes or field_name in normalized_codes :
                values =field .get ("values")or []
                if values :
                    value =values [0 ].get ("value")
                    if value is not None :
                        return value 
        return None 

    def _test_amocrm_connection (self ,config ):
        """Реальная проверка подключения к amoCRM."""
        ok ,message =self ._validate_connection_settings (
        "crm",
        "AmoCRM",
        config .get ("account_name",""),
        config .get ("identifier",""),
        {
        "token":config .get ("token",""),
        "client_id":config .get ("client_id",""),
        "client_secret":config .get ("client_secret",""),
        "refresh_token":config .get ("refresh_token",""),
        "client_login_mode":config .get ("client_login_mode","auto"),
        },
        )
        if not ok :
            return {
            "ok":False ,
            "message":message ,
            "adapter":self ._get_connector_adapter ("crm","AmoCRM"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

        try :
            payload =self ._amocrm_request (config ,"GET","/api/v4/account",params ={"with":"users"})
            account_name =str (payload .get ("name","")).strip ()or "аккаунт amoCRM"
            return {
            "ok":True ,
            "message":f"Подключение к amoCRM подтверждено. Получен доступ к аккаунту: {account_name }.",
            "adapter":self ._get_connector_adapter ("crm","AmoCRM"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }
        except Exception as e :
            return {
            "ok":False ,
            "message":f"Не удалось проверить amoCRM: {e }",
            "adapter":self ._get_connector_adapter ("crm","AmoCRM"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

    def _fetch_amocrm_leads (self ,config ):
        """Постранично получает сделки amoCRM."""
        page =1 
        limit =250 
        rows =[]
        while True :
            payload =self ._amocrm_request (
            config ,
            "GET",
            "/api/v4/leads",
            params ={"page":page ,"limit":limit ,"with":"contacts"},
            timeout =60 ,
            )
            embedded =payload .get ("_embedded",{})if isinstance (payload ,dict )else {}
            leads =embedded .get ("leads",[])if isinstance (embedded ,dict )else []
            if not leads :
                break 
            rows .extend (leads )
            if len (leads )<limit :
                break 
            page +=1 
        return pd .DataFrame (rows )

    def _transform_amocrm_to_crm_data (self ,leads_df ,platform_name ):
        """Преобразуем сделки amoCRM в формат CRM-таблицы приложения."""
        if leads_df is None or leads_df .empty :
            return pd .DataFrame (columns =[
            "Дата","Источник","Medium","Тип","Кампания","Группа","Объявление",
            "Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт","Лиды","Продажи","Выручка","Ср.чек"
            ])

        crm_rows =[]
        leads_work =leads_df .copy ()

        for _ ,row in leads_work .iterrows ():
            created_at =pd .to_datetime (row .get ("created_at"),unit ="s",errors ="coerce")
            closed_at =pd .to_datetime (row .get ("closed_at"),unit ="s",errors ="coerce")
            price =pd .to_numeric (row .get ("price",0 ),errors ="coerce")
            price =0 if pd .isna (price )else float (price )
            status_id =pd .to_numeric (row .get ("status_id",0 ),errors ="coerce")
            status_id =0 if pd .isna (status_id )else int (status_id )

            utm_source =self ._amocrm_extract_custom_field_value (row ,["UTM_SOURCE","Источник"])
            utm_medium =self ._amocrm_extract_custom_field_value (row ,["UTM_MEDIUM","Тип","Medium"])
            utm_campaign =self ._amocrm_extract_custom_field_value (row ,["UTM_CAMPAIGN","Кампания"])
            utm_content =self ._amocrm_extract_custom_field_value (row ,["UTM_CONTENT","Объявление"])
            utm_term =self ._amocrm_extract_custom_field_value (row ,["UTM_TERM","Ключевая фраза"])
            region_value =self ._amocrm_extract_custom_field_value (row ,["REGION_NAME","Регион","region_name","{region_name}"])
            device_value =self ._amocrm_extract_custom_field_value (row ,["DEVICE_TYPE","Устройство","device_type","{device_type}"])
            placement_value =self ._amocrm_extract_custom_field_value (row ,["SOURCE","Площадка","source","{source}"])
            position_value =self ._amocrm_extract_custom_field_value (row ,["POSITION","Position","position","{position}"])
            url_value =self ._amocrm_extract_custom_field_value (row ,["URL","Url","url","Ссылка"])
            product_value =self ._amocrm_extract_custom_field_value (row ,["PRODUCT","Продукт","product"])

            if pd .notna (created_at ):
                crm_rows .append ({
                "Дата":created_at ,
                "Источник":utm_source or platform_name ,
                "Medium":utm_medium or "Не указано",
                "Тип":utm_medium or "Не указано",
                "Кампания":utm_campaign or "Не указано",
                "Группа":"Не указано",
                "Объявление":utm_content or row .get ("name")or "Не указано",
                "Ключевая фраза":utm_term or "Не указано",
                "Регион":region_value or "Не указано",
                "Устройство":device_value or "Не указано",
                "Площадка":placement_value or "Не указано",
                "Position":position_value or "Не указано",
                "URL":url_value or "Не указано",
                "Продукт":product_value or "Не указано",
                "Лиды":1 ,
                "Продажи":0 ,
                "Выручка":0 ,
                "Ср.чек":0 ,
                })

            if status_id ==142 and pd .notna (closed_at ):
                crm_rows .append ({
                "Дата":closed_at ,
                "Источник":utm_source or platform_name ,
                "Medium":utm_medium or "Не указано",
                "Тип":utm_medium or "Не указано",
                "Кампания":utm_campaign or "Не указано",
                "Группа":"Не указано",
                "Объявление":utm_content or row .get ("name")or "Не указано",
                "Ключевая фраза":utm_term or "Не указано",
                "Регион":region_value or "Не указано",
                "Устройство":device_value or "Не указано",
                "Площадка":placement_value or "Не указано",
                "Position":position_value or "Не указано",
                "URL":url_value or "Не указано",
                "Продукт":product_value or "Не указано",
                "Лиды":0 ,
                "Продажи":1 ,
                "Выручка":price ,
                "Ср.чек":price ,
                })

        if not crm_rows :
            return pd .DataFrame (columns =[
            "Дата","Источник","Medium","Тип","Кампания","Группа","Объявление",
            "Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт","Лиды","Продажи","Выручка","Ср.чек"
            ])

        crm_df =pd .DataFrame (crm_rows )
        crm_df ["Дата"]=pd .to_datetime (crm_df ["Дата"],errors ="coerce")
        crm_df =crm_df .dropna (subset =["Дата"]).copy ()
        for column_name in ["Источник","Medium","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            crm_df [column_name ]=crm_df [column_name ].fillna ("Не указано").astype (str ).str .strip ()
            crm_df .loc [crm_df [column_name ].isin (["","-","nan","None"]),column_name ]="Не указано"
        for column_name in ["Лиды","Продажи","Выручка","Ср.чек"]:
            crm_df [column_name ]=pd .to_numeric (crm_df [column_name ],errors ="coerce").fillna (0 )
        crm_df ["Ср.чек"]=np .where (
        crm_df ["Продажи"]>0 ,
        crm_df ["Выручка"]/crm_df ["Продажи"],
        0 
        )
        return crm_df .sort_values ("Дата").reset_index (drop =True )

    def _bitrix24_rest_call (self ,config ,method_name ,params =None ,timeout =45 ):
        """Выполняет REST-вызов Bitrix24 и возвращает JSON."""
        url =self ._build_bitrix24_method_url (config ,method_name )
        data =urllib .parse .urlencode (params or {}).encode ("utf-8")
        request =urllib .request .Request (url ,data =data ,method ="POST")
        with urllib .request .urlopen (request ,timeout =timeout )as response :
            body =response .read ().decode ("utf-8")
            payload =json .loads (body )if body else {}
        if isinstance (payload ,dict )and "error"in payload :
            raise RuntimeError (payload .get ("error_description")or payload .get ("error")or str (payload ))
        return payload 

    def _fetch_bitrix24_all (self ,config ,method_name ,select_fields =None ,filter_params =None ):
        """Постранично получает данные из Bitrix24."""
        rows =[]
        start =0 
        select_fields =select_fields or []
        filter_params =filter_params or {}

        while True :
            params ={
            "start":start ,
            }
            for index ,field_name in enumerate (select_fields ):
                params [f"select[{index }]"]=field_name 
            for key ,value in filter_params .items ():
                params [f"filter[{key }]"]=value 

            payload =self ._bitrix24_rest_call (config ,method_name ,params =params ,timeout =60 )
            batch =payload .get ("result",[])
            if isinstance (batch ,list ):
                rows .extend (batch )
            next_start =payload .get ("next")
            if next_start is None :
                break 
            start =next_start 

        return pd .DataFrame (rows )

    def _test_bitrix24_connection (self ,config ):
        """Реальная проверка подключения к Bitrix24 через webhook REST API."""
        identifier =str (config .get ("identifier","")).strip ()
        token =str (config .get ("token","")).strip ()
        if not self ._bitrix24_has_full_webhook_url (identifier )and not token :
            return {
            "ok":False ,
            "message":"Для Bitrix24 укажите портал и webhook path в поле Токен либо полный webhook URL в поле ID / логин.",
            "adapter":self ._get_connector_adapter ("crm","Bitrix24"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

        ok ,message =self ._validate_connection_settings (
        "crm",
        "Bitrix24",
        config .get ("account_name",""),
        identifier ,
        {
        "token":token ,
        "client_id":config .get ("client_id",""),
        "client_secret":config .get ("client_secret",""),
        "refresh_token":config .get ("refresh_token",""),
        },
        )
        if not ok :
            return {
            "ok":False ,
            "message":message ,
            "adapter":self ._get_connector_adapter ("crm","Bitrix24"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

        try :
            profile =self ._bitrix24_rest_call (config ,"profile",params ={})
            user_info =profile .get ("result",{})if isinstance (profile ,dict )else {}
            user_name =" ".join (
            part for part in [
            str (user_info .get ("NAME","")).strip (),
            str (user_info .get ("LAST_NAME","")).strip (),
            ]if part 
            )or str (user_info .get ("EMAIL","")).strip ()or "пользователь Bitrix24"
            return {
            "ok":True ,
            "message":f"Подключение к Bitrix24 подтверждено. Авторизация выполнена как {user_name }.",
            "adapter":self ._get_connector_adapter ("crm","Bitrix24"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }
        except Exception as e :
            return {
            "ok":False ,
            "message":f"Не удалось проверить Bitrix24: {e }",
            "adapter":self ._get_connector_adapter ("crm","Bitrix24"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

    def _fetch_bitrix24_leads (self ,config ):
        """Получаем лиды Bitrix24."""
        return self ._fetch_bitrix24_all (
        config ,
        "crm.lead.list",
        select_fields =[
        "ID","TITLE","DATE_CREATE","SOURCE_ID","UTM_SOURCE","UTM_MEDIUM",
        "UTM_CAMPAIGN","UTM_CONTENT","UTM_TERM"
        ],
        )

    def _fetch_bitrix24_deals (self ,config ):
        """Получаем сделки Bitrix24."""
        return self ._fetch_bitrix24_all (
        config ,
        "crm.deal.list",
        select_fields =[
        "ID","TITLE","DATE_CREATE","CLOSEDATE","STAGE_SEMANTIC_ID","OPPORTUNITY",
        "UTM_SOURCE","UTM_MEDIUM","UTM_CAMPAIGN","UTM_CONTENT","UTM_TERM"
        ],
        )

    def _transform_bitrix24_to_crm_data (self ,leads_df ,deals_df ,platform_name ):
        """Преобразуем лиды и сделки Bitrix24 в формат CRM-таблицы приложения."""
        crm_rows =[]

        if leads_df is not None and not leads_df .empty :
            leads_work =leads_df .copy ()
            leads_work ["DATE_CREATE"]=pd .to_datetime (leads_work .get ("DATE_CREATE"),errors ="coerce")
            leads_work =leads_work .dropna (subset =["DATE_CREATE"])
            for _ ,row in leads_work .iterrows ():
                crm_rows .append ({
                "Дата":row .get ("DATE_CREATE"),
                "Источник":row .get ("UTM_SOURCE")or row .get ("SOURCE_ID")or platform_name ,
                "Medium":row .get ("UTM_MEDIUM")or "Не указано",
                "Тип":row .get ("UTM_MEDIUM")or "Не указано",
                "Кампания":row .get ("UTM_CAMPAIGN")or "Не указано",
                "Группа":"Не указано",
                "Объявление":row .get ("UTM_CONTENT")or row .get ("TITLE")or "Не указано",
                "Ключевая фраза":row .get ("UTM_TERM")or "Не указано",
                "Регион":row .get ("REGION_NAME")or row .get ("region_name")or "Не указано",
                "Устройство":row .get ("DEVICE_TYPE")or row .get ("device_type")or "Не указано",
                "Площадка":row .get ("SOURCE")or row .get ("source")or "Не указано",
                "Position":row .get ("POSITION")or row .get ("position")or "Не указано",
                "URL":row .get ("URL")or row .get ("url")or "Не указано",
                "Продукт":row .get ("PRODUCT")or row .get ("product")or "Не указано",
                "Лиды":1 ,
                "Продажи":0 ,
                "Выручка":0 ,
                "Ср.чек":0 ,
                })

        if deals_df is not None and not deals_df .empty :
            deals_work =deals_df .copy ()
            deals_work ["SALE_DATE"]=pd .to_datetime (deals_work .get ("CLOSEDATE"),errors ="coerce")
            deals_work ["DATE_CREATE"]=pd .to_datetime (deals_work .get ("DATE_CREATE"),errors ="coerce")
            deals_work ["FINAL_DATE"]=deals_work ["SALE_DATE"].fillna (deals_work ["DATE_CREATE"])
            deals_work =deals_work .dropna (subset =["FINAL_DATE"])
            semantic_series =deals_work .get ("STAGE_SEMANTIC_ID",pd .Series ([""]*len (deals_work ),index =deals_work .index )).astype (str ).str .strip ().str .upper ()
            deals_work =deals_work .loc [semantic_series =="S"].copy ()
            for _ ,row in deals_work .iterrows ():
                opportunity =pd .to_numeric (row .get ("OPPORTUNITY",0 ),errors ="coerce")
                opportunity =0 if pd .isna (opportunity )else float (opportunity )
                crm_rows .append ({
                "Дата":row .get ("FINAL_DATE"),
                "Источник":row .get ("UTM_SOURCE")or platform_name ,
                "Medium":row .get ("UTM_MEDIUM")or "Не указано",
                "Тип":row .get ("UTM_MEDIUM")or "Не указано",
                "Кампания":row .get ("UTM_CAMPAIGN")or "Не указано",
                "Группа":"Не указано",
                "Объявление":row .get ("UTM_CONTENT")or row .get ("TITLE")or "Не указано",
                "Ключевая фраза":row .get ("UTM_TERM")or "Не указано",
                "Регион":row .get ("REGION_NAME")or row .get ("region_name")or "Не указано",
                "Устройство":row .get ("DEVICE_TYPE")or row .get ("device_type")or "Не указано",
                "Площадка":row .get ("SOURCE")or row .get ("source")or "Не указано",
                "Position":row .get ("POSITION")or row .get ("position")or "Не указано",
                "URL":row .get ("URL")or row .get ("url")or "Не указано",
                "Продукт":row .get ("PRODUCT")or row .get ("product")or "Не указано",
                "Лиды":0 ,
                "Продажи":1 ,
                "Выручка":opportunity ,
                "Ср.чек":opportunity ,
                })

        if not crm_rows :
            return pd .DataFrame (columns =[
            "Дата","Источник","Medium","Тип","Кампания","Группа","Объявление",
            "Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт","Лиды","Продажи","Выручка","Ср.чек"
            ])

        crm_df =pd .DataFrame (crm_rows )
        crm_df ["Дата"]=pd .to_datetime (crm_df ["Дата"],errors ="coerce")
        crm_df =crm_df .dropna (subset =["Дата"]).copy ()

        for column_name in ["Источник","Medium","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            crm_df [column_name ]=crm_df [column_name ].fillna ("Не указано").astype (str ).str .strip ()
            crm_df .loc [crm_df [column_name ].isin (["","-","nan","None"]),column_name ]="Не указано"

        for column_name in ["Лиды","Продажи","Выручка","Ср.чек"]:
            crm_df [column_name ]=pd .to_numeric (crm_df [column_name ],errors ="coerce").fillna (0 )

        crm_df ["Ср.чек"]=np .where (
        crm_df ["Продажи"]>0 ,
        crm_df ["Выручка"]/crm_df ["Продажи"],
        0 
        )

        crm_df =crm_df .sort_values ("Дата").reset_index (drop =True )
        return crm_df 

    def _test_connector_connection (self ,connection_kind ,platform_name ,account_name ,identifier ,auth_fields =None ):
        """Единая точка проверки коннектора без реального API."""
        adapter =self ._get_connector_adapter (connection_kind ,platform_name )
        if connection_kind =="ads"and platform_name =="Яндекс.Директ":
            config =self ._build_connection_settings_payload (
            connection_kind ,
            platform_name ,
            account_name ,
            identifier ,
            auth_fields or {},
            status ="Не подключен",
            note ="",
            )
            return self ._test_yandex_direct_connection (config )
        if connection_kind =="crm"and platform_name =="AmoCRM":
            config =self ._build_connection_settings_payload (
            connection_kind ,
            platform_name ,
            account_name ,
            identifier ,
            auth_fields or {},
            status ="Не подключен",
            note ="",
            )
            return self ._test_amocrm_connection (config )
        if connection_kind =="crm"and platform_name =="Bitrix24":
            config =self ._build_connection_settings_payload (
            connection_kind ,
            platform_name ,
            account_name ,
            identifier ,
            auth_fields or {},
            status ="Не подключен",
            note ="",
            )
            return self ._test_bitrix24_connection (config )
        ok ,message =self ._validate_connection_settings (
        connection_kind ,
        platform_name ,
        account_name ,
        identifier ,
        auth_fields ,
        )
        capabilities =adapter .get ("capabilities",{})
        if ok :
            capability_text =", ".join (
            label for label ,enabled in {
            "загрузка аккаунтов":capabilities .get ("fetch_accounts"),
            "загрузка кампаний":capabilities .get ("fetch_campaigns"),
            "загрузка статистики":capabilities .get ("fetch_stats"),
            "загрузка лидов":capabilities .get ("fetch_leads"),
            "загрузка продаж":capabilities .get ("fetch_sales"),
            }.items ()
            if enabled 
            )
            if capability_text :
                message =f"{message }\nДоступные возожности адаптера: {capability_text }."
        return {
        "ok":ok ,
        "message":message ,
        "adapter":adapter ,
        "checked_at":datetime .now ().isoformat (timespec ="seconds"),
        }

    def _execute_json_http_request (self ,url ,payload ,headers =None ,timeout =30 ):
        """Выполняет JSON POST-запрос и возвращает словарь ответа."""
        request_headers ={"Content-Type":"application/json; charset=utf-8"}
        if headers :
            request_headers .update (headers )
        request =urllib .request .Request (
        url ,
        data =json .dumps (payload ).encode ("utf-8"),
        headers =request_headers ,
        method ="POST",
        )
        with urllib .request .urlopen (request ,timeout =timeout )as response :
            raw_body =response .read ().decode ("utf-8")
            return json .loads (raw_body )if raw_body else {}

    def _execute_text_http_request (self ,url ,payload ,headers =None ,timeout =60 ):
        """Выполняет POST-запрос и возвращает текст ответа."""
        request_headers ={}
        if headers :
            request_headers .update (headers )
        request =urllib .request .Request (
        url ,
        data =json .dumps (payload ).encode ("utf-8"),
        headers =request_headers ,
        method ="POST",
        )
        try :
            with urllib .request .urlopen (request ,timeout =timeout )as response :
                return response .read ().decode ("utf-8")
        except urllib .error .HTTPError as error :
            error_body =""
            try :
                error_body =error .read ().decode ("utf-8",errors ="replace")
            except Exception :
                error_body =""
            raise RuntimeError (f"HTTP {error .code}: {error_body or error .reason}")from error
    def _get_yandex_direct_base_url (self ,config ):
        """  URL Yandex Direct API   sandbox/prod ."""
        api_mode =str (config .get ("api_mode","production")).strip ().lower ()
        if api_mode =="sandbox":
            return "https://api-sandbox.direct.yandex.com"
        return "https://api.direct.yandex.com"



    def _build_yandex_direct_headers (self ,config ,is_report =False ):
        """Собирает заголовки для Direct API."""
        token =str (config .get ("token","")).strip ()
        identifier =str (config .get ("identifier","")).strip ()
        if "use_client_login"in config :
            use_client_login =bool (config .get ("use_client_login",False ))
        else :
            client_login_mode =str (config .get ("client_login_mode","auto")).strip ().lower ()
            use_client_login =client_login_mode =="always"
        headers ={
        "Authorization":f"Bearer {token }",
        "Accept-Language":"ru",
        }
        if is_report :
            headers .update ({
            "processingMode":"auto",
            "returnMoneyInMicros":"false",
            "skipReportHeader":"true",
            "skipColumnHeader":"false",
            "skipReportSummary":"true",
            })
        if use_client_login and identifier and not identifier .isdigit ():
            headers ["Client-Login"]=identifier 
        return headers 

    def _test_yandex_direct_connection (self ,config ):
        """Реальная проверка подключения к Яндекс.Директ через API."""
        ok ,message =self ._validate_connection_settings (
        "ads",
        "Яндекс.Директ",
        config .get ("account_name",""),
        config .get ("identifier",""),
        {
        "token":config .get ("token",""),
        "client_id":config .get ("client_id",""),
        "client_secret":config .get ("client_secret",""),
        "refresh_token":config .get ("refresh_token",""),
        },
        )
        if not ok :
            return {
            "ok":False ,
            "message":message ,
            "adapter":self ._get_connector_adapter ("ads","Яндекс.Директ"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

        base_url =self ._get_yandex_direct_base_url (config )
        request_payload ={
        "method":"get",
        "params":{
        "SelectionCriteria":{},
        "FieldNames":["Id","Name","State","Status"],
        "Page":{"Limit":1 ,"Offset":0 },
        },
        }

        def perform_probe (use_client_login =False ):
            probe_config =dict (config )
            probe_config ["use_client_login"]=use_client_login
            return self ._execute_json_http_request (
            f"{base_url }/json/v5/campaigns",
            request_payload ,
            headers =self ._build_yandex_direct_headers (probe_config ),
            timeout =30 ,
            )

        try :
            used_client_login =False
            client_login_mode =str (config .get ("client_login_mode","auto")).strip ().lower ()
            identifier_filled =bool (str (config .get ("identifier","")).strip ())
            if client_login_mode =="always"and identifier_filled :
                response =perform_probe (True )
                used_client_login =True
            elif client_login_mode =="never"or not identifier_filled :
                response =perform_probe (False )
            else :
                response =perform_probe (False )
                if "error"in response :
                    response_with_login =perform_probe (True )
                    if "error"not in response_with_login :
                        response =response_with_login
                        used_client_login =True

            if "error"in response :
                error_block =response .get ("error",{})
                error_message =error_block .get ("error_detail")or error_block .get ("error_string")or str (error_block )
                mode_label ="sandbox"if str (config .get ("api_mode","production")).strip ().lower ()=="sandbox"else "production"
                login_mode ="с Client-Login"if used_client_login else "без Client-Login"
                return {
                "ok":False ,
                "message":f"Яндекс.Директ вернул ошибку: {error_message } (режим: {mode_label }, запрос: {login_mode }).",
                "adapter":self ._get_connector_adapter ("ads","Яндекс.Директ"),
                "checked_at":datetime .now ().isoformat (timespec ="seconds"),
                }

            campaigns =response .get ("result",{}).get ("Campaigns",[])
            mode_label ="sandbox"if str (config .get ("api_mode","production")).strip ().lower ()=="sandbox"else "production"
            login_mode ="с Client-Login"if used_client_login else "без Client-Login"
            return {
            "ok":True ,
            "message":(
            "Подключение к Яндекс.Директ подтверждено. "
            f"API ответил успешно, тестово получено кампаний: {len (campaigns )}. Режим: {mode_label }, запрос: {login_mode }."
            ),
            "adapter":self ._get_connector_adapter ("ads","Яндекс.Директ"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }
        except urllib .error .HTTPError as e :
            try :
                error_body =e .read ().decode ("utf-8")
                parsed_error =json .loads (error_body )
                error_block =parsed_error .get ("error",{})
                error_message =error_block .get ("error_detail")or error_block .get ("error_string")or error_body 
            except Exception :
                error_message =str (e )
            return {
            "ok":False ,
            "message":f"Не удалось проверить Яндекс.Директ: {error_message }",
            "adapter":self ._get_connector_adapter ("ads","Яндекс.Директ"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }
        except Exception as e :
            return {
            "ok":False ,
            "message":f"Ошибка соединения с Яндекс.Директ: {e }",
            "adapter":self ._get_connector_adapter ("ads","Яндекс.Директ"),
            "checked_at":datetime .now ().isoformat (timespec ="seconds"),
            }

    def _fetch_yandex_direct_campaigns (self ,config ):
        """Получаем список кампаний из Яндекс.Директ."""
        response =self ._execute_json_http_request (
        f"{self ._get_yandex_direct_base_url (config )}/json/v5/campaigns",
        {
        "method":"get",
        "params":{
        "SelectionCriteria":{},
        "FieldNames":["Id","Name","State","Status","Type"],
        "Page":{"Limit":1000 ,"Offset":0 },
        },
        },
        headers =self ._build_yandex_direct_headers (config ),
        timeout =45 ,
        )
        if "error"in response :
            error_block =response .get ("error",{})
            raise RuntimeError (error_block .get ("error_detail")or error_block .get ("error_string")or str (error_block ))
        campaigns =response .get ("result",{}).get ("Campaigns",[])
        return pd .DataFrame (campaigns )

    def _fetch_yandex_direct_ads_map (self ,config ,ad_ids =None ):
        """Получаем карту объявлений Яндекс.Директ: ID -> человекочитаемое название."""
        selection_criteria ={}
        normalized_ids =[]
        if ad_ids :
            for value in ad_ids :
                try :
                    normalized_ids .append (int (float (value )))
                except Exception :
                    continue 
            normalized_ids =list (dict .fromkeys (normalized_ids ))
            if normalized_ids :
                selection_criteria ["Ids"]=normalized_ids [:10000 ]
        if not normalized_ids :
            self .log ("Yandex Direct ads map: пропуск запроса ads.get, потому что список AdId пуст")
            return {}

        response =self ._execute_json_http_request (
        f"{self ._get_yandex_direct_base_url (config )}/json/v5/ads",
        {
        "method":"get",
        "params":{
        "SelectionCriteria":selection_criteria ,
        "FieldNames":["Id","Type","Subtype"],
        "TextAdFieldNames":["Title"],
        "MobileAppAdFieldNames":["Title"],
        "DynamicTextAdFieldNames":["Text"],
        "Page":{"Limit":10000 ,"Offset":0 },
        },
        },
        headers =self ._build_yandex_direct_headers (config ),
        timeout =45 ,
        )
        if "error"in response :
            error_block =response .get ("error",{})
            raise RuntimeError (error_block .get ("error_detail")or error_block .get ("error_string")or str (error_block ))

        ads_map ={}
        ads =response .get ("result",{}).get ("Ads",[])
        for ad in ads :
            ad_id =ad .get ("Id")
            if ad_id is None :
                continue 

            title =None 
            if isinstance (ad .get ("TextAd"),dict ):
                title =ad ["TextAd"].get ("Title")
            if not title and isinstance (ad .get ("MobileAppAd"),dict ):
                title =ad ["MobileAppAd"].get ("Title")
            if not title and isinstance (ad .get ("DynamicTextAd"),dict ):
                title =ad ["DynamicTextAd"].get ("Text")

            ad_type =str (ad .get ("Type","")).strip ()
            ad_subtype =str (ad .get ("Subtype","")).strip ()
            if title and str (title ).strip ():
                ads_map [int (ad_id )]=str (title ).strip ()
            elif ad_subtype and ad_subtype !="NONE":
                ads_map [int (ad_id )]=f"{ad_subtype } #{int (ad_id )}"
            elif ad_type :
                ads_map [int (ad_id )]=f"{ad_type } #{int (ad_id )}"
            else :
                ads_map [int (ad_id )]=f"ID {int (ad_id )}"

        return ads_map 

    def _fetch_yandex_direct_stats (self ,config ,date_from ,date_to ,campaign_ids =None ):
        """Получаем статистику из Reports API Яндекс.Директ."""
        selection_criteria ={
        "DateFrom":pd .Timestamp (date_from ).strftime ("%Y-%m-%d"),
        "DateTo":pd .Timestamp (date_to ).strftime ("%Y-%m-%d"),
        }
        report_filter =[]
        if campaign_ids :
            normalized_campaign_ids =[]
            for value in campaign_ids :
                try :
                    normalized_campaign_ids .append (int (float (value )))
                except Exception :
                    continue 
            normalized_campaign_ids =list (dict .fromkeys (normalized_campaign_ids ))
            if normalized_campaign_ids :
                report_filter .append ({
                "Field":"CampaignId",
                "Operator":"IN",
                "Values":[str (campaign_id )for campaign_id in normalized_campaign_ids [:10000 ]]
                })
        if report_filter :
            selection_criteria ["Filter"]=report_filter 
        self .log (f"Yandex Direct stats request: date_from={selection_criteria .get ('DateFrom')}, date_to={selection_criteria .get ('DateTo')}, filter={selection_criteria .get ('Filter',[])}")

        payload ={
        "params":{
        "SelectionCriteria":selection_criteria ,
        "FieldNames":["Date","CampaignName","AdGroupName","AdId","Criterion","AdNetworkType","Impressions","Clicks","Cost"],
        "ReportName":f"Codex export {datetime .now ().strftime ('%Y%m%d_%H%M%S')}" ,
        "ReportType":"CUSTOM_REPORT",
        "DateRangeType":"CUSTOM_DATE",
        "Format":"TSV",
        "IncludeVAT":"YES",
        "IncludeDiscount":"NO",
        }
        }
        report_text =self ._execute_text_http_request (
        f"{self ._get_yandex_direct_base_url (config )}/json/v5/reports",
        payload ,
        headers =self ._build_yandex_direct_headers (config ,is_report =True ),
        timeout =90 ,
        )
        if report_text .strip ().startswith ("{"):
            parsed_error =json .loads (report_text )
            error_block =parsed_error .get ("error",{})
            raise RuntimeError (error_block .get ("error_detail")or error_block .get ("error_string")or report_text )
        report_df =pd .read_csv (StringIO (report_text ),sep ="\t")
        self .log (f"Yandex Direct stats: строк={len (report_df )}, колонки={report_df .columns .tolist ()}")
        if not report_df .empty :
            self .log (f"Yandex Direct stats sample: {report_df .head (3 ).to_dict (orient='records')}")
        if not report_df .empty :
            return report_df
        fallback_payload ={
        "params":{
        "SelectionCriteria":selection_criteria ,
        "FieldNames":["Date","CampaignName","Impressions","Clicks","Cost"],
        "ReportName":f"Codex fallback export {datetime .now ().strftime ('%Y%m%d_%H%M%S')}" ,
        "ReportType":"CUSTOM_REPORT",
        "DateRangeType":"CUSTOM_DATE",
        "Format":"TSV",
        "IncludeVAT":"YES",
        "IncludeDiscount":"NO",
        }
        }
        self .log ("Yandex Direct stats: детальный отчет пуст, пробуем агрегированный fallback по кампании")
        fallback_text =self ._execute_text_http_request (
        f"{self ._get_yandex_direct_base_url (config )}/json/v5/reports",
        fallback_payload ,
        headers =self ._build_yandex_direct_headers (config ,is_report =True ),
        timeout =90 ,
        )
        if fallback_text .strip ().startswith ("{"):
            parsed_error =json .loads (fallback_text )
            error_block =parsed_error .get ("error",{})
            raise RuntimeError (error_block .get ("error_detail")or error_block .get ("error_string")or fallback_text )
        fallback_df =pd .read_csv (StringIO (fallback_text ),sep ="\t")
        self .log (f"Yandex Direct fallback stats: строк={len (fallback_df )}, колонки={fallback_df .columns .tolist ()}")
        if not fallback_df .empty :
            fallback_df ["AdGroupName"]="Не указано"
            fallback_df ["AdId"]=pd .NA
            fallback_df ["Criterion"]="Не указано"
            fallback_df ["AdNetworkType"]="UNKNOWN"
            self .log (f"Yandex Direct fallback sample: {fallback_df .head (3 ).to_dict (orient='records')}")
            return fallback_df
        return report_df 

    def _transform_yandex_direct_stats_to_ads_data (self ,stats_df ,platform_name ,ads_map =None ):
        """Преобразуем статистику Яндекс.Директ в формат рекламной таблицы приложения."""
        if stats_df is None or stats_df .empty :
            return pd .DataFrame (columns =[
            "Дата","Источник","Кампания","Группа","Объявление","Ключевая фраза",
            "Расход","Показы","Клики","Лиды","Продажи","Ср.чек"
            ])

        transformed =stats_df .copy ().rename (columns ={
        "Date":"Дата",
        "CampaignName":"Кампания",
        "AdGroupName":"Группа",
        "Criterion":"Ключевая фраза",
        "AdNetworkType":"Medium",
        "Impressions":"Показы",
        "Clicks":"Клики",
        "Cost":"Расход",
        })
        ads_map =ads_map or {}

        if "AdId"in transformed .columns :
            def resolve_ad_name (value ):
                if pd .isna (value )or str (value ).strip ().lower ()in {"","-","nan"}:
                    return "Не указано"
                try :
                    ad_id =int (float (value ))
                    return ads_map .get (ad_id ,f"ID {ad_id }")
                except Exception :
                    return "Не указано"
            transformed ["Объявление"]=transformed ["AdId"].apply (resolve_ad_name )
        else :
            transformed ["Объявление"]="Не указано"

        for column_name in ["Кампания","Группа","Ключевая фраза"]:
            if column_name not in transformed .columns :
                transformed [column_name ]="Не указано"

        if "Medium"in transformed .columns :
            transformed ["Medium"]=transformed ["Medium"].astype (str ).str .strip ().replace ({
            "SEARCH":"Поиск",
            "AD_NETWORK":"Сети",
            "MIXED":"Сешанный",
            "UNKNOWN":"Не указано",
            "nan":"Не указано",
            "None":"Не указано",
            "":"Не указано",
            })
        else :
            transformed ["Medium"]="Не указано"
        transformed ["Тип"]=transformed ["Medium"]

        transformed ["Источник"]=platform_name 
        transformed ["Лиды"]=0 
        transformed ["Продажи"]=0 
        transformed ["Ср.чек"]=0 

        for column_name in ["Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]:
            transformed [column_name ]=pd .to_numeric (transformed .get (column_name ,0 ),errors ="coerce").fillna (0 )

        transformed ["Дата"]=pd .to_datetime (transformed ["Дата"],errors ="coerce")
        transformed =transformed .dropna (subset =["Дата"])

        for column_name in ["Источник","Medium","Тип","Кампания","Группа","Объявление","Ключевая фраза","Регион","Устройство","Площадка","Position","URL","Продукт"]:
            transformed [column_name ]=transformed [column_name ].fillna ("Не указано").astype (str ).str .strip ()
            transformed .loc [transformed [column_name ].isin (["","-","nan","None"]),column_name ]="Не указано"
        transformed .loc [transformed ["Ключевая фраза"].str .lower ().isin (["---autotargeting"]),"Ключевая фраза"]="Автотаргетинг"

        return transformed [
        ["Дата","Источник","Medium","Тип","Кампания","Группа","Объявление","Ключевая фраза","Расход","Показы","Клики","Лиды","Продажи","Ср.чек"]
        ].sort_values ("Дата").reset_index (drop =True ).copy ()

    def _validate_connection_settings (self ,connection_kind ,platform_name ,account_name ,identifier ,auth_fields =None ):
        """Локальная проверка настройки подключения без реального API."""
        platform_name =str (platform_name ).strip ()
        account_name =str (account_name ).strip ()
        identifier =str (identifier ).strip ()
        auth_fields =auth_fields or {}
        token =str (auth_fields .get ("token","")).strip ()
        client_id =str (auth_fields .get ("client_id","")).strip ()
        client_secret =str (auth_fields .get ("client_secret","")).strip ()
        refresh_token =str (auth_fields .get ("refresh_token","")).strip ()
        client_login_mode =str (auth_fields .get ("client_login_mode","auto")).strip ().lower ()
        connector_definition =self ._get_connector_adapter (connection_kind ,platform_name )
        entity_name =connector_definition .get ("kind_label","кабинет"if connection_kind =="ads"else "CRM")
        required_auth_fields =connector_definition .get ("required_auth_fields",[])

        if not platform_name :
            return False ,f"Не выбрана платформа для подключения {entity_name }."
        if platform_name =="Яндекс.Директ"and client_login_mode =="always"and not identifier :
            return False ,"Для режима 'Всегда использовать' заполните поле ID / логин."
        if not identifier and platform_name !="Яндекс.Директ":
            identifier_label =connector_definition .get ("identifier_label","ID, логин или client_id")
            return False ,f"Для {platform_name } укажите {identifier_label .lower ()}."
        if identifier and len (identifier )<2 :
            return False ,f"Значение ID / логина для {platform_name } слишко короткое."
        if client_id and not client_secret :
            return False ,f"{platform_name }: указан client_id, но не заполнен client_secret."
        if client_secret and not client_id :
            return False ,f"{platform_name }: указан client_secret, но не заполнен client_id."
        missing_required =[]
        for field_name in required_auth_fields :
            if field_name =="token"and not token :
                missing_required .append ("token")
            elif field_name =="client_id"and not client_id :
                missing_required .append ("client_id")
            elif field_name =="client_secret"and not client_secret :
                missing_required .append ("client_secret")
            elif field_name =="refresh_token"and not refresh_token :
                missing_required .append ("refresh_token")
        if missing_required :
            return False ,f"{platform_name }: не хватает обязательных полей авторизации: {', '.join (missing_required )}."
        if not any ([token ,client_id ,client_secret ,refresh_token ]):
            auth_hint =connector_definition .get (
            "auth_hint",
            "Для реальной интеграции позже добавьте токен или client_id / client_secret."
            )
            return True ,f"{platform_name }: базовая проверка пройдена, но поля API пока пустые. {auth_hint }."
        if not account_name :
            return True ,(
            f"{platform_name }: проверка пройдена, данные авторизации заполнены. "
            f"Для удобства еще можно добавить название подключения."
            )
        return True ,f"{platform_name }: проверка пройдена, подключение выглядит готовым к следующему этапу API-интеграции."

    def refresh_connection_lists (self ):
        """Перерисовывает списки рекламных кабинетов и CRM из сохраненных настроек."""
        if hasattr (self ,"ads_list")and self .ads_list is not None :
            self .ads_list .clear ()
            for platform_name in self .available_ads_platforms :
                config =self .ads_connections .get (platform_name )
                item =QListWidgetItem (self ._format_connection_item_text (platform_name ,config ))
                item .setData (Qt .ItemDataRole .UserRole ,platform_name )
                item .setToolTip (self ._build_connection_tooltip (platform_name ,config ))
                if config and str (config .get ("status","")).strip ().lower ()=="подключен":
                    item .setForeground (QColor ("#1f7a3d"))
                elif config and "ошибка"in str (config .get ("status","")).strip ().lower ():
                    item .setForeground (QColor ("#b33a3a"))
                self .ads_list .addItem (item )

        if hasattr (self ,"crm_list")and self .crm_list is not None :
            self .crm_list .clear ()
            for platform_name in self .available_crm_platforms :
                config =self .crm_connections .get (platform_name )
                item =QListWidgetItem (self ._format_connection_item_text (platform_name ,config ))
                item .setData (Qt .ItemDataRole .UserRole ,platform_name )
                item .setToolTip (self ._build_connection_tooltip (platform_name ,config ))
                if config and str (config .get ("status","")).strip ().lower ()=="подключен":
                    item .setForeground (QColor ("#1f7a3d"))
                elif config and "ошибка"in str (config .get ("status","")).strip ().lower ():
                    item .setForeground (QColor ("#b33a3a"))
                self .crm_list .addItem (item )

    def _open_connection_settings_dialog (self ,connection_kind ,existing_platform =None ):
        """Открывает окно настройки рекламного кабинета или CRM."""
        if not self ._require_project_for_connections ():
            return 

        is_ads =connection_kind =="ads"
        platforms =self .available_ads_platforms if is_ads else self .available_crm_platforms 
        storage =self .ads_connections if is_ads else self .crm_connections 
        title ="Настройка рекламного кабинета"if is_ads else "Настройка CRM"
        existing_data =storage .get (existing_platform ,{}).copy ()if existing_platform else {}

        dialog =QDialog (self )
        dialog .setWindowTitle (title )
        dialog .setMinimumWidth (460 )

        layout =QVBoxLayout (dialog )
        form =QFormLayout ()
        form .setLabelAlignment (Qt .AlignmentFlag .AlignRight )
        form .setFormAlignment (Qt .AlignmentFlag .AlignTop )
        form .setSpacing (10 )

        platform_combo =QComboBox ()
        platform_combo .addItems (platforms )
        if existing_platform and existing_platform in platforms :
            platform_combo .setCurrentText (existing_platform )
            platform_combo .setEnabled (False )

        account_edit =QLineEdit (existing_data .get ("account_name",""))
        account_edit .setPlaceholderText ("Например: Основной кабинет")

        identifier_edit =QLineEdit (existing_data .get ("identifier",""))
        identifier_edit .setPlaceholderText ("ID аккаунта, логин или client_id (для своего Direct можно оставить пустым)")

        token_edit =QLineEdit (existing_data .get ("token",""))
        token_edit .setPlaceholderText ("Токен доступа, если используется")
        token_edit .setEchoMode (QLineEdit .EchoMode .Password )

        client_id_edit =QLineEdit (existing_data .get ("client_id",""))
        client_id_edit .setPlaceholderText ("client_id / app_id")
        api_mode_combo =QComboBox ()
        api_mode_combo .addItem ("Боевой","production")
        api_mode_combo .addItem ("Тестовый (sandbox)","sandbox")
        current_api_mode =existing_data .get ("api_mode","production")
        current_index =api_mode_combo .findData (current_api_mode )
        if current_index >=0 :
            api_mode_combo .setCurrentIndex (current_index )
        client_login_mode_combo =QComboBox ()
        client_login_mode_combo .addItem ("Авто","auto")
        client_login_mode_combo .addItem ("Всегда использовать","always")
        client_login_mode_combo .addItem ("Не использовать","never")
        current_client_login_mode =existing_data .get ("client_login_mode","auto")
        current_client_login_index =client_login_mode_combo .findData (current_client_login_mode )
        if current_client_login_index >=0 :
            client_login_mode_combo .setCurrentIndex (current_client_login_index )


        client_secret_edit =QLineEdit (existing_data .get ("client_secret",""))
        client_secret_edit .setPlaceholderText ("client_secret")
        client_secret_edit .setEchoMode (QLineEdit .EchoMode .Password )

        refresh_token_edit =QLineEdit (existing_data .get ("refresh_token",""))
        refresh_token_edit .setPlaceholderText ("refresh_token")
        refresh_token_edit .setEchoMode (QLineEdit .EchoMode .Password )

        status_combo =QComboBox ()
        status_combo .addItems (["Не подключен","Подключен","Ошибка настройки"])
        status_combo .setCurrentText (existing_data .get ("status","Подключен"if existing_platform else "Не подключен"))

        note_edit =QTextEdit (existing_data .get ("note",""))
        note_edit .setPlaceholderText ("Комментарий по подключению")
        note_edit .setFixedHeight (90 )

        show_secrets_checkbox =QCheckBox ("Показать секретные поля")

        def set_secret_visibility (checked ):
            echo_mode =QLineEdit .EchoMode .Normal if checked else QLineEdit .EchoMode .Password 
            token_edit .setEchoMode (echo_mode )
            client_secret_edit .setEchoMode (echo_mode )
            refresh_token_edit .setEchoMode (echo_mode )

        form .addRow ("Режим API:",api_mode_combo )
        show_secrets_checkbox .toggled .connect (set_secret_visibility )

        form .addRow ("Платформа:",platform_combo )
        form .addRow ("Название:",account_edit )
        form .addRow ("ID / логин:",identifier_edit )
        form .addRow ("Токен:",token_edit )
        form .addRow ("Client ID:",client_id_edit )
        form .addRow ("Client Secret:",client_secret_edit )
        form .addRow ("Refresh Token:",refresh_token_edit )
        form .addRow ("Client-Login:",client_login_mode_combo )
        form .addRow ("Статус:",status_combo )
        form .addRow ("Комментарий:",note_edit )
        account_edit .setPlaceholderText ("Например: Основной кабинет")
        identifier_edit .setPlaceholderText ("ID аккаунта, логин или client_id (для своего Direct можно оставить пустым)")
        token_edit .setPlaceholderText ("Токен доступа, если используется")
        note_edit .setPlaceholderText ("Комментарий по подключению")
        show_secrets_checkbox .setText ("Показать секретные поля")
        api_mode_combo .clear ()
        api_mode_combo .addItem ("Боевой","production")
        api_mode_combo .addItem ("Тестовый (sandbox)","sandbox")
        current_index =api_mode_combo .findData (current_api_mode )
        if current_index >=0 :
            api_mode_combo .setCurrentIndex (current_index )
        client_login_mode_combo .clear ()
        client_login_mode_combo .addItem ("Авто","auto")
        client_login_mode_combo .addItem ("Всегда использовать","always")
        client_login_mode_combo .addItem ("Не использовать","never")
        current_client_login_index =client_login_mode_combo .findData (current_client_login_mode )
        if current_client_login_index >=0 :
            client_login_mode_combo .setCurrentIndex (current_client_login_index )
        status_combo .clear ()
        status_combo .addItems (["Не подключен","Подключен","Ошибка настройки"])
        status_combo .setCurrentText (existing_data .get ("status","Подключен"if existing_platform else "Не подключен"))
        form .labelForField (api_mode_combo ).setText ("Режим API:")
        form .labelForField (platform_combo ).setText ("Платформа:")
        form .labelForField (account_edit ).setText ("Название:")
        form .labelForField (token_edit ).setText ("Токен:")
        form .labelForField (client_login_mode_combo ).setText ("Client-Login:")
        form .labelForField (status_combo ).setText ("Статус:")
        form .labelForField (note_edit ).setText ("Комментарий:")
        layout .addLayout (form )
        layout .addWidget (show_secrets_checkbox )

        validation_label =QLabel ("")
        validation_label .setWordWrap (True )
        validation_label .setStyleSheet ("padding: 8px 10px; border-radius: 6px; background: #f4f7fa; color: #506070;")
        layout .addWidget (validation_label )

        help_label =QLabel (
        "Это каркас подключения. Настройки уже сохраняются в проект, "
        "а реальную интеграцию с API добавим следующим этапом."
        )
        help_label .setWordWrap (True )
        help_label .setStyleSheet ("color: #6b7b8c; font-size: 12px;")
        layout .addWidget (help_label )

        buttons =QDialogButtonBox ()
        check_button =buttons .addButton ("Проверить подключение",QDialogButtonBox .ButtonRole .ActionRole )
        save_button =buttons .addButton ("Сохранить",QDialogButtonBox .ButtonRole .AcceptRole )
        cancel_button =buttons .addButton ("Отмена",QDialogButtonBox .ButtonRole .RejectRole )
        delete_button =None 
        if existing_platform :
            delete_button =buttons .addButton ("Удалить",QDialogButtonBox .ButtonRole .DestructiveRole )
        help_label .setText (
        "Это каркас подключения. Настройки уже сохраняются в проект, "
        "а реальную интеграцию с API добавим следующим этапом."
        )
        check_button .setText ("Проверить подключение")
        save_button .setText ("Сохранить")
        cancel_button .setText ("Отмена")
        if delete_button is not None :
            delete_button .setText ("Удалить")
        layout .addWidget (buttons )

        def update_connector_form_preset ():
            definition =self ._get_connector_adapter (connection_kind ,platform_combo .currentText ())
            identifier_label_text =definition .get ("identifier_label","ID аккаунта, логин или client_id")
            auth_hint =definition .get ("auth_hint","Позже сюда можно будет добавить реальные API-ключи.")
            identifier_edit .setPlaceholderText (identifier_label_text )
            help_label .setText (
            "Это каркас подключения. Настройки уже сохраняются в проект, "
            f"а реальную интеграцию с API добавим следующим этапом.\nТекущая схема авторизации: {auth_hint }."
            )

        def refresh_validation_hint ():
            current_status =status_combo .currentText ().strip ()or " "
            ok ,message =self ._validate_connection_settings (
            connection_kind ,
            platform_combo .currentText (),
            account_edit .text (),
            identifier_edit .text (),
            {
            "token":token_edit .text (),
            "client_id":client_id_edit .text (),
            "client_secret":client_secret_edit .text (),
            "refresh_token":refresh_token_edit .text (),
            "api_mode":api_mode_combo .currentData (),
            "client_login_mode":client_login_mode_combo .currentData (),
            }
            )
            base_color ="#1f7a3d"if ok else "#b33a3a"
            bg_color ="#edf8f1"if ok else "#fdeeee"
            if current_status =="Подключен"and ok :
                prefix ="Статус: подключение отмечено как активное."
            elif current_status =="Ошибка настройки":
                prefix ="Статус: у подключения отмечена ошибка."
            else :
                prefix ="Статус: подключение еще не подтверждено."
            validation_label .setStyleSheet (
            f"padding: 8px 10px; border-radius: 6px; background: {bg_color }; color: {base_color };"
            )
            validation_label .setText (f"{prefix }\n{message }")

        def check_connection ():
            test_result =self ._test_connector_connection (
            connection_kind ,
            platform_combo .currentText (),
            account_edit .text (),
            identifier_edit .text (),
            {
            "token":token_edit .text (),
            "client_id":client_id_edit .text (),
            "client_secret":client_secret_edit .text (),
            "refresh_token":refresh_token_edit .text (),
            "api_mode":api_mode_combo .currentData (),
            "client_login_mode":client_login_mode_combo .currentData (),
            }
            )
            ok =test_result ["ok"]
            message =test_result ["message"]
            status_combo .setCurrentText ("Подключен"if ok else "Ошибка настройки")
            refresh_validation_hint ()
            QMessageBox .information (
            dialog ,
            "Проверка подключения"if ok else "Проверка не пройдена",
            message 
            )

        check_button .clicked .connect (check_connection )
        save_button .clicked .connect (dialog .accept )
        cancel_button .clicked .connect (dialog .reject )
        if delete_button :
            delete_button .clicked .connect (lambda :dialog .done (2 ))
        for widget in (
        platform_combo ,
        account_edit ,
        identifier_edit ,
        token_edit ,
        client_id_edit ,
        client_secret_edit ,
        refresh_token_edit ,
        api_mode_combo ,
        client_login_mode_combo ,
        status_combo ,
        ):
            if hasattr (widget ,"currentTextChanged"):
                widget .currentTextChanged .connect (lambda *_ :refresh_validation_hint ())
            if hasattr (widget ,"textChanged"):
                widget .textChanged .connect (lambda *_ :refresh_validation_hint ())
        note_edit .textChanged .connect (lambda :refresh_validation_hint ())
        platform_combo .currentTextChanged .connect (lambda *_ :update_connector_form_preset ())
        update_connector_form_preset ()
        refresh_validation_hint ()

        result =dialog .exec ()
        if result ==0 :
            return 

        selected_platform =platform_combo .currentText ()
        if result ==2 :
            storage .pop (selected_platform ,None )
            self .refresh_connection_lists ()
            self .update_project_status_labels ()
            self .auto_save_project ()
            return 
        storage [selected_platform ]=self ._build_connection_settings_payload (
        connection_kind ,
        selected_platform ,
        account_edit .text (),
        identifier_edit .text (),
        {
        "token":token_edit .text (),
        "client_id":client_id_edit .text (),
        "client_secret":client_secret_edit .text (),
        "refresh_token":refresh_token_edit .text (),
        "api_mode":api_mode_combo .currentData (),
        "client_login_mode":client_login_mode_combo .currentData (),
        },
        status_combo .currentText (),
        note_edit .toPlainText (),
        )
        self .refresh_connection_lists ()
        self .update_project_status_labels ()
        self .auto_save_project ()
        QMessageBox .information (self ,"Успех",f"Настройки подключения сохранены для: {selected_platform }")

    def add_ads_account (self ):
        """Открывает список рекламных подключений."""
        self ._open_connection_settings_dialog ("ads")

    def edit_selected_ads_account (self ,item =None ):
        """Открывает список CRM-подключений."""
        if item is None and hasattr (self ,"ads_list"):
            item =self .ads_list .currentItem ()
        platform_name =item .data (Qt .ItemDataRole .UserRole )if item else None 
        if platform_name :
            self ._open_connection_settings_dialog ("ads",platform_name )

    def add_crm (self ):
        """Финальная версия настройки CRM."""
        self ._open_connection_settings_dialog ("crm")

    def edit_selected_crm_connection (self ,item =None ):
        """Открывает настройку выбранной CRM."""
        if item is None and hasattr (self ,"crm_list"):
            item =self .crm_list .currentItem ()
        platform_name =item .data (Qt .ItemDataRole .UserRole )if item else None 
        if platform_name :
            self ._open_connection_settings_dialog ("crm",platform_name )

    def _normalize_filter_value (self ,value ):
        """Приводит пустые и служебные значения фильтров к одноу виду."""
        text =""if value is None else str (value ).strip ()
        if text .lower ()in {"","nan","none","null","nat","не указано","(не указано)"}:
            return "Не указано"
        return text 

    def _normalize_filter_series (self ,series ):
        """Норализует серию значений для фильтров."""
        return series .fillna ("").astype (str ).map (self ._normalize_filter_value )

    def update_filters_from_data (self ):
        """Финальная стабильная версия обновления фильтров без дублей 'не указано'."""
        self .log ("\n=== ОНОВЛЕНЕ ФИЛЬТРОВ З ДАННЫХ ===")

        if self .data .empty :
            self .log ("Нет данных для обновления фильтров (self.data пуст)")
            return 

        filter_column_mapping ={
        "Source":"Источник",
        "Medium":"Medium",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза",
        "Region":"Регион",
        "Device":"Устройство",
        "Placement":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Product":"Продукт",
        }
        button_labels ={
        "Source":"Источник",
        "Medium":"Тип",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза",
        "Region":"Регион",
        "Device":"Устройство",
        "Placement":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Product":"Продукт"
        }

        for filter_key ,column_name in filter_column_mapping .items ():
            if filter_key not in self .filters_widgets :
                continue 

            display_name =button_labels .get (filter_key ,filter_key )
            real_column_name =column_name 
            if filter_key =="Medium"and real_column_name not in self .data .columns and "Тип"in self .data .columns :
                real_column_name ="Тип"

            if real_column_name in self .data .columns :
                series =self ._normalize_filter_series (self .data [real_column_name ])
                unique_values =sorted (series .unique ().tolist ())
            else :
                unique_values =["Не указано"]

            self .filters_widgets [filter_key ]["items"]=unique_values 
            list_widget =self .filters_widgets [filter_key ]["list"]
            list_widget .blockSignals (True )
            list_widget .clear ()
            for value in unique_values :
                item =QListWidgetItem (value )
                item .setFlags (item .flags ()|Qt .ItemFlag .ItemIsUserCheckable )
                item .setCheckState (Qt .CheckState .Checked )
                list_widget .addItem (item )
            list_widget .blockSignals (False )

            self .filter_states [filter_key ]={value :Qt .CheckState .Checked for value in unique_values }
            self .filters_widgets [filter_key ]["button"].setText (display_name )
            self .log (f"  {display_name }: {unique_values [:10 ]}... (всего {len (unique_values )})")

        self .refresh_plan_dimension_options ()
        self .log ("=== ОНОВЛЕНЕ ФИЛЬТРОВ ЗАВЕРШЕНО ===\n")

    def get_selected_filters (self ):
        """Финальная стабильная версия чтения выбранных фильтров без дублей значений."""
        selected ={}
        display_names ={
        "Source":"Источник",
        "Medium":"Тип",
        "Campaign":"Кампания",
        "Gbid":"Группа",
        "Content":"Объявление",
        "Term":"Ключевая фраза",
        "Region":"Регион",
        "Device":"Устройство",
        "Placement":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Product":"Продукт",
        }

        self .log ("\n=== ПОЛУЧЕНЕ ВЫРАННЫХ ФИЛЬТРОВ ===")
        for filter_key in self .filters_widgets :
            display_name =display_names .get (filter_key ,filter_key )
            normalized_items =[]
            for item_text ,state in self .filter_states .get (filter_key ,{}).items ():
                if state ==Qt .CheckState .Checked :
                    normalized_items .append (self ._normalize_filter_value (item_text ))

            deduped_items =list (dict .fromkeys (normalized_items ))
            selected [display_name ]=deduped_items 
            self .log (f"  {display_name }: {deduped_items [:5 ]}... (всего {len (deduped_items )})")

            button =self .filters_widgets [filter_key ]["button"]
            total_items =len (self .filter_states .get (filter_key ,{}))
            if len (deduped_items )==0 :
                button .setText ("Ничего")
            elif len (deduped_items )==total_items :
                button .setText ("Все")
            else :
                button .setText (f"{len (deduped_items )} выбрано")

        return selected 

    def update_dashboard (self ):
        """Финальная стабильная версия обновления дашборда с норализацией фильтров."""
        if not hasattr (self ,"group_combo")or self .group_combo is None :
            self .log ("group_combo не инициализирован, пропускае обновление")
            return 

        from_date =self .date_from .date ().toPyDate ()
        to_date =self .date_to .date ().toPyDate ()
        group_type =self .group_combo .currentText ()
        selected_filters =self .get_selected_filters ()

        has_selected_filters =any (values for values in selected_filters .values ())
        if not has_selected_filters :
            self .filtered_data =pd .DataFrame ()
            self .filtered_source_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self ._clear_dimension_tabs ()
            self .update_chart ()
            return 

        if self .original_data .empty :
            self .filtered_data =pd .DataFrame ()
            self .filtered_source_data =pd .DataFrame ()
            self .chart_data =pd .DataFrame ()
            self .display_empty_table ()
            self ._clear_dimension_tabs ()
            self .update_chart ()
            return 

        df =self .original_data .copy ()
        if not pd .api .types .is_datetime64_any_dtype (df ["Дата"]):
            df ["Дата"]=pd .to_datetime (df ["Дата"],errors ="coerce",dayfirst =True )
        df =df .dropna (subset =["Дата"])
        df =df [(df ["Дата"].dt .date >=from_date )&(df ["Дата"].dt .date <=to_date )]

        filter_to_column ={
        "Источник":"Источник",
        "Тип":"Medium",
        "Кампания":"Кампания",
        "Группа":"Группа",
        "Объявление":"Объявление",
        "Ключевая фраза":"Ключевая фраза",
        "Регион":"Регион",
        "Устройство":"Устройство",
        "Площадка":"Площадка",
        "Position":"Position",
        "URL":"URL",
        "Продукт":"Продукт",
        }

        for display_name ,column_name in filter_to_column .items ():
            real_column_name =column_name 
            if display_name =="Тип"and real_column_name not in df .columns and "Тип"in df .columns :
                real_column_name ="Тип"
            if real_column_name not in df .columns :
                if display_name =="Тип":
                    df [real_column_name ]="Не указано"
                else :
                    continue 

            selected_values =selected_filters .get (display_name ,[])
            if len (selected_values )==0 :
                self .filtered_data =pd .DataFrame ()
                self .filtered_source_data =pd .DataFrame ()
                self .chart_data =pd .DataFrame ()
                self .display_empty_table ()
                self ._clear_dimension_tabs ()
                self .update_chart ()
                return 

            normalized_series =self ._normalize_filter_series (df [real_column_name ])
            df =df .loc [normalized_series .isin (selected_values )].copy ()

        self .filtered_source_data =df .copy ()
        daily_df =self ._build_daily_dashboard_data (df ,from_date ,to_date )
        final_df =self ._group_dashboard_periods (daily_df ,group_type ,from_date ,to_date )

        self .filtered_data =final_df 
        self .original_filtered_data =self .filtered_data .copy ()
        self .chart_data =daily_df .copy ()

        self .update_table ()
        self .update_kpi ()
        self .refresh_all_dimension_tabs ()
        self .update_chart ()

    def update_dimension_table_with_filter (self ,dimension_name ,from_date ,to_date ):
        """Финальная стабильная версия вкладки измерения с норализацией '(не указано)'."""
        source_df =self .filtered_source_data .copy ()if hasattr (self ,"filtered_source_data")and self .filtered_source_data is not None else self .data .copy ()
        empty_df =pd .DataFrame (columns =[dimension_name ])

        if source_df .empty :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        if "Дата"in source_df .columns and not pd .api .types .is_datetime64_any_dtype (source_df ["Дата"]):
            source_df ["Дата"]=pd .to_datetime (source_df ["Дата"],errors ="coerce",dayfirst =True )
            source_df =source_df .dropna (subset =["Дата"])

        column_name ="Medium"if dimension_name =="Тип"else dimension_name 
        if dimension_name =="Тип"and column_name not in source_df .columns and "Тип"in source_df .columns :
            column_name ="Тип"
        if column_name not in source_df .columns :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        filtered =source_df .copy ()
        if "Дата"in filtered .columns :
            filtered =filtered [
            (filtered ["Дата"]>=pd .Timestamp (from_date ))&
            (filtered ["Дата"]<=pd .Timestamp (to_date ))
            ]

        if filtered .empty :
            self .dimension_raw_data [dimension_name ]=empty_df 
            self .dimension_data [dimension_name ]=empty_df 
            self .display_dimension_table (dimension_name ,empty_df )
            return 

        filtered [column_name ]=self ._normalize_filter_series (filtered [column_name ])

        if "Выручка"not in filtered .columns and {"Продажи","Ср.чек"}.issubset (filtered .columns ):
            filtered =filtered .copy ()
            filtered ["Выручка"]=filtered ["Продажи"]*filtered ["Ср.чек"]

        agg_dict ={col :"sum"for col in ["Расход","Показы","Клики","Лиды","Продажи","Выручка"]if col in filtered .columns }
        grouped =filtered .groupby (column_name ,dropna =False ).agg (agg_dict ).reset_index ()
        grouped [column_name ]=self ._normalize_filter_series (grouped [column_name ])

        if column_name !=dimension_name :
            grouped =grouped .rename (columns ={column_name :dimension_name })

        if "Ср.чек"not in grouped .columns and {"Выручка","Продажи"}.issubset (grouped .columns ):
            grouped ["Ср.чек"]=grouped .apply (
            lambda row :round (row ["Выручка"]/row ["Продажи"])if row ["Продажи"]>0 else 0 ,
            axis =1 
            ).astype (int )

        grouped =self .calculate_dimension_metrics_fixed (grouped ,dimension_name )
        self .dimension_raw_data [dimension_name ]=grouped .copy ()
        self .dimension_data [dimension_name ]=grouped .copy ()
        self .display_dimension_table (dimension_name ,grouped )

    def _get_connected_platforms (self ,connection_kind ):
        """Возвращает список реально настроенных и помеченных как подключенные платформ."""
        storage =self .ads_connections if connection_kind =="ads"else self .crm_connections 
        result =[]
        for platform_name ,config in (storage or {}).items ():
            if not isinstance (config ,dict ):
                continue 
            if str (config .get ("status","")).strip ().lower ()=="подключен":
                result .append ((platform_name ,config ))
        return result 

    def _simulate_connector_fetch (self ,connection_kind ,platform_name ,config ):
        """Заглушечная загрузка данных из подключения без реального API."""
        if connection_kind =="ads"and platform_name =="Яндекс.Директ":
            try :
                campaigns_df =self ._fetch_yandex_direct_campaigns (config )
                campaign_ids =campaigns_df ["Id"].dropna ().tolist ()if "Id"in campaigns_df .columns else []
                self .log (f"Yandex Direct campaigns ids: {campaign_ids }")
                stats_df =self ._fetch_yandex_direct_stats (
                config ,
                self .date_from .date ().toPyDate ()if hasattr (self ,"date_from")else datetime .now ().date (),
                self .date_to .date ().toPyDate ()if hasattr (self ,"date_to")else datetime .now ().date (),
                campaign_ids ,
                )
                ads_map =self ._fetch_yandex_direct_ads_map (config ,stats_df ["AdId"].dropna ().tolist ()if "AdId"in stats_df .columns else [])
                self .log (f"Yandex Direct ads map: элементов={len (ads_map )}")
                app_ads_df =self ._transform_yandex_direct_stats_to_ads_data (stats_df ,platform_name ,ads_map )
                self .log (f"Yandex Direct transformed ads: строк={len (app_ads_df )}, колонки={app_ads_df .columns .tolist () if app_ads_df is not None else []}")
                if app_ads_df is not None and not app_ads_df .empty :
                    self .log (f"Yandex Direct transformed sample: {app_ads_df .head (3 ).to_dict (orient='records')}")
                    self .log (f"Yandex Direct transformed dates: {app_ads_df ['����'].head (5 ).tolist () if '����' in app_ads_df .columns else []}")
                self .ads_data =app_ads_df .copy ()
                self ._mark_sync_time ("ads")
                self .ads_file_path =f"Подключение API: {platform_name }"
                if hasattr (self ,"refresh_data_loader_labels"):
                    self .refresh_data_loader_labels ()
                if hasattr (self ,"update_project_status_labels"):
                    self .update_project_status_labels ()
                if hasattr (self ,"auto_save_project")and self .current_project :
                    self .auto_save_project ()
                return {
                "ok":True ,
                "message":(
                f"Яндекс.Директ ответил успешно.\n"
                f"Кампаний получено: {len (campaigns_df )}.\n"
                f"Строк статистики за период: {len (stats_df )}.\n"
                f"Названий объявлений подтянуто: {len (ads_map )}.\n"
                f"Строк рекламных данных подготовлено для приложения: {len (app_ads_df )}.\n"
                f"Ключевые фразы включены в выгрузку."
                ),
                "rows":len (app_ads_df ),
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }
            except Exception as e :
                return {
                "ok":False ,
                "message":f"Яндекс.Директ не смог загрузить данные: {e }",
                "rows":0 ,
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }

        if connection_kind =="crm"and platform_name =="Bitrix24":
            try :
                leads_df =self ._fetch_bitrix24_leads (config )
                deals_df =self ._fetch_bitrix24_deals (config )
                app_crm_df =self ._transform_bitrix24_to_crm_data (leads_df ,deals_df ,platform_name )
                self .crm_data =app_crm_df .copy ()
                self ._mark_sync_time ("crm")
                self .crm_file_path =f"Подключение API: {platform_name }"
                if hasattr (self ,"refresh_data_loader_labels"):
                    self .refresh_data_loader_labels ()
                if hasattr (self ,"update_project_status_labels"):
                    self .update_project_status_labels ()
                if hasattr (self ,"auto_save_project")and self .current_project :
                    self .auto_save_project ()
                return {
                "ok":True ,
                "message":(
                f"Bitrix24 ответил успешно.\n"
                f"Лидов получено: {len (leads_df )}.\n"
                f"Сделок получено: {len (deals_df )}.\n"
                f"Строк CRM-данных подготовлено для приложения: {len (app_crm_df )}.\n"
                f"Выручка загружается как основное денежное поле, Ср.чек рассчитывается автоматически."
                ),
                "rows":len (app_crm_df ),
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }
            except Exception as e :
                return {
                "ok":False ,
                "message":f"Bitrix24 не смог загрузить данные: {e }",
                "rows":0 ,
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }

        if connection_kind =="crm"and platform_name =="AmoCRM":
            try :
                leads_df =self ._fetch_amocrm_leads (config )
                app_crm_df =self ._transform_amocrm_to_crm_data (leads_df ,platform_name )
                self .crm_data =app_crm_df .copy ()
                self ._mark_sync_time ("crm")
                self .crm_file_path =f"Подключение API: {platform_name }"
                if hasattr (self ,"refresh_data_loader_labels"):
                    self .refresh_data_loader_labels ()
                if hasattr (self ,"update_project_status_labels"):
                    self .update_project_status_labels ()
                if hasattr (self ,"auto_save_project")and self .current_project :
                    self .auto_save_project ()
                return {
                "ok":True ,
                "message":(
                f"amoCRM ответил успешно.\n"
                f"Сделок получено: {len (leads_df )}.\n"
                f"Строк CRM-данных подготовлено для приложения: {len (app_crm_df )}.\n"
                f"Выручка загружается как основное денежное поле, Ср.чек рассчитывается автоматически."
                ),
                "rows":len (app_crm_df ),
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }
            except Exception as e :
                return {
                "ok":False ,
                "message":f"amoCRM не смог загрузить данные: {e }",
                "rows":0 ,
                "adapter":self ._get_connector_adapter (connection_kind ,platform_name ),
                }

        adapter =self ._get_connector_adapter (connection_kind ,platform_name )
        test_result =self ._test_connector_connection (
        connection_kind ,
        platform_name ,
        config .get ("account_name",""),
        config .get ("identifier",""),
        {
        "token":config .get ("token",""),
        "client_id":config .get ("client_id",""),
        "client_secret":config .get ("client_secret",""),
        "refresh_token":config .get ("refresh_token",""),
        },
        )
        return {
        "ok":test_result ["ok"],
        "message":(
        f"{test_result ['message']}\n"
        f"Реальный API для {platform_name } пока не подключен. "
        f"Тестовый адаптер вернул 0 строк и не изменил текущие данные."
        ),
        "rows":0 ,
        "adapter":adapter ,
        }

    def _load_from_connection_stub (self ,connection_kind ):
        """Общий сценарий загрузки из настроенного подключения без реального API."""
        if not self ._require_project_for_connections ():
            return 

        connected_platforms =self ._get_connected_platforms (connection_kind )
        source_label ="рекламы"if connection_kind =="ads"else "CRM"
        if not connected_platforms :
            QMessageBox .information (
            self ,
            "Нет подключений",
            f"Сначала настройте и проверьте хотя бы одно подключение {source_label }."
            )
            return 

        selected_platform =None 
        selected_config =None 
        if len (connected_platforms )==1 :
            selected_platform ,selected_config =connected_platforms [0 ]
        else :
            dialog =QDialog (self )
            dialog .setWindowTitle (f"Выбор подключения {source_label }")
            dialog .setMinimumWidth (420 )
            layout =QVBoxLayout (dialog )
            info =QLabel ("Выберите подключение, из которого нужно выполнить загрузку:")
            info .setWordWrap (True )
            layout .addWidget (info )
            combo =QComboBox ()
            for platform_name ,config in connected_platforms :
                combo .addItem (self ._format_connection_item_text (platform_name ,config ),platform_name )
            layout .addWidget (combo )
            buttons =QDialogButtonBox (QDialogButtonBox .StandardButton .Ok |QDialogButtonBox .StandardButton .Cancel )
            buttons .accepted .connect (dialog .accept )
            buttons .rejected .connect (dialog .reject )
            layout .addWidget (buttons )
            if dialog .exec ()!=QDialog .DialogCode .Accepted :
                return 
            selected_platform =combo .currentData ()
            selected_config =dict (self .ads_connections if connection_kind =="ads"else self .crm_connections ).get (selected_platform ,{})

        result =self ._simulate_connector_fetch (connection_kind ,selected_platform ,selected_config or {})
        self .log (
        f"Загрузка из подключения ({connection_kind }): {selected_platform }; "
        f"строк={result ['rows']}; ok={result ['ok']}"
        )
        QMessageBox .information (
        self ,
        "Загрузка из подключения",
        result ["message"]
        )

    def load_ads_data_from_connection (self ):
        """Заглушечная загрузка рекламных данных из подключенного кабинета."""
        self ._load_from_connection_stub ("ads")

    def load_crm_data_from_connection (self ):
        """Заглушечная загрузка CRM-данных из подключенной системы."""
        self ._load_from_connection_stub ("crm")

    def _get_auto_refresh_slots (self ):
        schedule_map ={
        "Вручную":[],
        "Каждые 3 часа":["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00"],
        "Каждые 6 часов":["03:00","09:00","15:00","21:00"],
        "Каждые 12 часов":["09:00","21:00"],
        "Раз в день":["09:00"],
        }
        return schedule_map .get (getattr (self ,"auto_refresh_mode","Каждые 6 часов"),["03:00","09:00","15:00","21:00"])

    def _init_auto_refresh_timer (self ):
        if hasattr (self ,"auto_refresh_timer")and self .auto_refresh_timer is not None :
            try :
                self .auto_refresh_timer .stop ()
            except Exception :
                pass 
        self .auto_refresh_timer =QTimer (self )
        self .auto_refresh_timer .timeout .connect (self ._check_auto_refresh_schedule )
        self .auto_refresh_timer .start (60000 )
        QTimer .singleShot (1500 ,self ._check_auto_refresh_schedule )

    def _merge_loaded_sources_silent (self ):
        if not hasattr (self ,'ads_data')or self .ads_data is None or self .ads_data .empty :
            return False 
        if not hasattr (self ,'crm_data')or self .crm_data is None or self .crm_data .empty :
            return False 
        merged =self ._build_merged_dataframe_from_sources ()
        if merged is None or merged .empty :
            return False 
        self .data =merged .copy ()
        self .original_data =merged .copy ()
        self .chart_data =merged .copy ()
        if self .current_client in self .clients :
            self .clients [self .current_client ]["data"]=merged .copy ()
        self .update_filters_from_data ()
        self .refresh_plan_dimension_options ()
        self .update_dashboard ()
        self .refresh_data_loader_labels ()
        self ._mark_sync_time ("project")
        return True 

    def _run_auto_refresh_now (self ):
        if not self .current_project :
            return False ,"Проект не выбран" 
        ads_platforms =self ._get_connected_platforms ("ads")
        crm_platforms =self ._get_connected_platforms ("crm")
        if not ads_platforms and not crm_platforms :
            return False ,"Нет подключенных источников для автообновления" 
        messages =[]
        errors =[]
        try :
            if ads_platforms :
                platform_name ,config =ads_platforms [0 ]
                if len (ads_platforms )>1 :
                    self .log (f"Автообновление: найдено несколько рекламных подключений, используем первое: {platform_name }")
                result =self ._simulate_connector_fetch ("ads",platform_name ,config or {})
                messages .append (f"{platform_name }: {result ['rows']} строк")
                if not result .get ("ok"):
                    errors .append (str (result .get ("message","Ошибка загрузки рекламы")))
                elif int (result .get ("rows",0 )or 0 )<=0 :
                    errors .append (f"{platform_name }: источник ответил без ошибок, но не вернул ни одной строки")
            if crm_platforms :
                platform_name ,config =crm_platforms [0 ]
                if len (crm_platforms )>1 :
                    self .log (f"Автообновление: найдено несколько CRM-подключений, используем первое: {platform_name }")
                result =self ._simulate_connector_fetch ("crm",platform_name ,config or {})
                messages .append (f"{platform_name }: {result ['rows']} строк")
                if not result .get ("ok"):
                    errors .append (str (result .get ("message","Ошибка загрузки CRM")))
                elif int (result .get ("rows",0 )or 0 )<=0 :
                    errors .append (f"{platform_name }: источник ответил без ошибок, но не вернул ни одной строки")
            merged_ok =self ._merge_loaded_sources_silent ()
            if merged_ok :
                messages .append ("данные объединены")
            elif not errors :
                errors .append ("Источники ответили, но объединенные данные не были сформированы")
            self .last_auto_refresh_error =None if not errors else " | ".join (errors )
            self .update_project_status_labels ()
            if self .current_project :
                self .auto_save_project ()
            return len (errors )==0 ,"; ".join (messages ) if messages else (self .last_auto_refresh_error or "Автообновление завершено")
        except Exception as e :
            self .last_auto_refresh_error =str (e )
            self .update_project_status_labels ()
            return False ,str (e )

    def _check_auto_refresh_schedule (self ):
        if not self .current_project :
            return 
        slots =self ._get_auto_refresh_slots ()
        if not slots :
            return 
        now =datetime .now ()
        current_time =now .strftime ("%H:%M")
        if current_time not in slots :
            return 
        slot_key =now .strftime ("%Y-%m-%d %H:%M")
        if self .last_auto_refresh_slot_key ==slot_key :
            return 
        ok ,message =self ._run_auto_refresh_now ()
        self .last_auto_refresh_slot_key =slot_key 
        if ok :
            self .log (f"Автообновление выполнено: {message }")
        else :
            self .log (f"Автообновление завершилось с ошибкой: {message }")
        if self .current_project :
            self .auto_save_project ()
    def open_data_loader_dialog (self ):
        """Финальная версия окна загрузки данных с действиями по файлам и подключениям."""
        dialog =QDialog (self )
        dialog .setWindowTitle ("Загрузка данных")
        dialog .setMinimumWidth (560 )

        layout =QVBoxLayout (dialog )
        title =QLabel ("Загрузка и объединение данных")
        title .setStyleSheet ("font-size: 16px; font-weight: bold;")
        layout .addWidget (title )

        info =QLabel ("Можно загрузить данные из файлов или через подготовленные подключения.")
        info .setWordWrap (True )
        layout .addWidget (info )

        files_group =QGroupBox ("Выбранные файлы")
        files_layout =QVBoxLayout (files_group )
        self .ads_file_info_label =QLabel ()
        self .ads_file_info_label .setWordWrap (True )
        self .crm_file_info_label =QLabel ()
        self .crm_file_info_label .setWordWrap (True )
        files_layout .addWidget (self .ads_file_info_label )
        files_layout .addWidget (self .crm_file_info_label )
        layout .addWidget (files_group )

        self .data_loader_summary_label =QLabel ()
        self .data_loader_summary_label .setWordWrap (True )
        self .data_loader_summary_label .setStyleSheet (
        "padding: 8px 10px; border: 1px solid #d9e2ec; border-radius: 8px; background-color: #f8fafc;"
        )
        layout .addWidget (self .data_loader_summary_label )
        self .refresh_data_loader_labels ()

        file_actions_group =QGroupBox ("Загрузка из файлов")
        file_actions_layout =QVBoxLayout (file_actions_group )
        load_ads_btn =QPushButton ("Загрузить данные рекламы")
        load_ads_btn .clicked .connect (lambda :(self .load_ads_data (),self .refresh_data_loader_labels ()))
        file_actions_layout .addWidget (load_ads_btn )

        load_crm_btn =QPushButton ("Загрузить данные CRM")
        load_crm_btn .clicked .connect (lambda :(self .load_crm_data (),self .refresh_data_loader_labels ()))
        file_actions_layout .addWidget (load_crm_btn )
        layout .addWidget (file_actions_group )

        connection_actions_group =QGroupBox ("Загрузка из подключений")
        connection_actions_layout =QVBoxLayout (connection_actions_group )
        load_ads_connection_btn =QPushButton ("Загрузить рекламу из подключения")
        load_ads_connection_btn .clicked .connect (self .load_ads_data_from_connection )
        connection_actions_layout .addWidget (load_ads_connection_btn )

        load_crm_connection_btn =QPushButton ("Загрузить CRM из подключения")
        load_crm_connection_btn .clicked .connect (self .load_crm_data_from_connection )
        connection_actions_layout .addWidget (load_crm_connection_btn )
        layout .addWidget (connection_actions_group )

        self .merge_data_btn =QPushButton ("Объединить данные")
        self .merge_data_btn .clicked .connect (self .merge_data )
        layout .addWidget (self .merge_data_btn )

        close_btn =QPushButton ("Закрыть")
        close_btn .clicked .connect (dialog .accept )
        layout .addWidget (close_btn )

        dialog .exec ()

    def _mark_sync_time (self ,sync_kind ):
        timestamp =datetime .now ().strftime ("%d.%m.%Y %H:%M")
        if sync_kind =="ads":
            self .last_ads_sync_at =timestamp 
        elif sync_kind =="crm":
            self .last_crm_sync_at =timestamp 
        elif sync_kind =="project":
            self .last_project_refresh_at =timestamp 
        return timestamp 

    def _format_sync_label (self ,label ,value ):
        return f"{label}: {value if value else '—'}"
    def refresh_project_now (self ):
        if not self .current_project :
            QMessageBox .information (self ,"Проект не выбран","Сначала выберите или откройте проект.")
            return 
        ok ,message =self ._run_auto_refresh_now () if hasattr (self ,"_run_auto_refresh_now") else (False ,"Механизм обновления пока недоступен")
        if ok :
            QMessageBox .information (self ,"Успех",f"Обновление выполнено успешно.\n{message }")
        else :
            QMessageBox .warning (self ,"Ошибка",f"Не удалось обновить данные.\n{message }")
    def update_project_status_labels (self ):
        """Финальная безопасная сводка статусов проекта, данных и подключений."""
        active_project_text =f"Активный проект: {self .current_project if self .current_project else '—'}"

        rows_count =len (self .data )if hasattr (self ,"data")and self .data is not None else 0 
        has_ads_data =hasattr (self ,"ads_data")and self .ads_data is not None and not self .ads_data .empty 
        has_crm_data =hasattr (self ,"crm_data")and self .crm_data is not None and not self .crm_data .empty 
        has_merged =rows_count >0 

        ads_connections =self .ads_connections if hasattr (self ,"ads_connections")and isinstance (self .ads_connections ,dict )else {}
        crm_connections =self .crm_connections if hasattr (self ,"crm_connections")and isinstance (self .crm_connections ,dict )else {}

        ads_connected =sum (
        1 for config in ads_connections .values ()
        if isinstance (config ,dict )and str (config .get ("status","")).strip ().lower ()=="подключен"
        )
        crm_connected =sum (
        1 for config in crm_connections .values ()
        if isinstance (config ,dict )and str (config .get ("status","")).strip ().lower ()=="подключен"
        )
        ads_total =len (ads_connections )
        crm_total =len (crm_connections )

        if not self .current_project :
            project_status ="Статус проекта: проект не выбран"
        elif not has_ads_data and not has_crm_data and not has_merged :
            if ads_total or crm_total :
                project_status =(
                f"Статус проекта: пустой проект, настроены подключения "
                f"(реклама {ads_connected }/{ads_total }, CRM {crm_connected }/{crm_total })"
                )
            else :
                project_status ="Статус проекта: пустой проект"
        elif has_merged :
            project_status =f"Статус проекта: данные загружены, строк {rows_count }"
        else :
            project_status ="Статус проекта: проект открыт, источники загружены частично"

        ads_text ="реклама загружена"if has_ads_data else "реклама не загружена"
        crm_text ="CRM загружена"if has_crm_data else "CRM не загружена"
        merge_text =f"объединено {rows_count } строк"if has_merged else "данные не объединены"
        connection_text =(
        f"Подключения: реклама {ads_connected }/{ads_total }; CRM {crm_connected }/{crm_total }"
        if (ads_total or crm_total )
        else "Подключения: не настроены"
        )
        data_status =f"Данные: {ads_text }; {crm_text }; {merge_text }"
        sync_text ="; ".join ([
        self ._format_sync_label ("Реклама обновлена",self .last_ads_sync_at ),
        self ._format_sync_label ("CRM обновлена",self .last_crm_sync_at ),
        self ._format_sync_label ("Проект обновлен",self .last_project_refresh_at ),
        ])
        auto_refresh_slots_text =", ".join (self ._get_auto_refresh_slots ()) if hasattr (self ,"_get_auto_refresh_slots") else ""
        auto_refresh_text =f"Автообновление: {self .auto_refresh_mode }"
        if auto_refresh_slots_text :
            auto_refresh_text +=f" ({auto_refresh_slots_text })"
        if getattr (self ,"last_auto_refresh_error",None ):
            auto_refresh_text +=f"\nПоследняя ошибка автообновления: {self .last_auto_refresh_error }"

        safe_updates =[
        ("active_project_label",active_project_text ),
        ("project_status_label",project_status ),
        ("data_status_label",f"{data_status }; {connection_text }\n{sync_text }\n{auto_refresh_text }"),
        ]

        for attr_name ,text in safe_updates :
            try :
                widget =getattr (self ,attr_name ,None )
                if widget :
                    widget .setText (text )
            except RuntimeError :
                setattr (self ,attr_name ,None )

    def delete_project (self ):
        """Удаляетт выбранный или активный проект безопасно."""
        target_project =self .current_project 
        target_project_path =self .current_project_path 

        selected_item =self .project_list .currentItem ()if hasattr (self ,"project_list")and self .project_list else None 
        if selected_item :
            selected_project =self ._clean_project_list_name (selected_item .text ())
            selected_path =os .path .join (self .projects_dir ,f"{selected_project }.json")
            if os .path .exists (selected_path ):
                target_project =selected_project 
                target_project_path =selected_path 

        if not target_project or not target_project_path :
            QMessageBox .warning (self ,"Ошибка","Нет выбранного проекта для удаления.")
            return 

        reply =QMessageBox .question (
        self ,
        "Подтверждение удаления",
        f"Вы уверены, что хотите удалить проект '{target_project }'?\nЭто действие нельзя отменить.",
        QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No 
        )

        if reply !=QMessageBox .StandardButton .Yes :
            return 

        try :
            if not os .path .exists (target_project_path ):
                QMessageBox .warning (self ,"Ошибка","Файл проекта для удаления не найден.")
                return 

            deleting_current_project =self .current_project ==target_project 

            os .remove (target_project_path )

            if self .selected_project_name ==target_project :
                self .selected_project_name =None 

            if deleting_current_project :
                self .current_project =None 
                self .current_project_path =None 

            self .save_projects_index ()
            self .update_project_list ()

            if deleting_current_project :
                self ._set_empty_project_view ()
            else :
                self .update_project_status_labels ()

            QMessageBox .information (self ,"Успех","Проект удален")
        except Exception as e :
            self .log (f"Ошибка удаления проекта: {e }")
            QMessageBox .warning (self ,"Ошибка",f"Ошибка удаления проекта: {e }")

    def show_about_dialog (self ):
        app_name =str (getattr (self ,"release_config",{}).get ("app_name","ROMI Lab"))
        publisher =str (getattr (self ,"release_config",{}).get ("publisher","easyartstyle"))
        QMessageBox .information (
        self ,
        "О программе",
        f"{app_name }\nВерсия: {getattr (self ,'app_version','0.1.0' )}\nИздатель: {publisher }"
        )

    def _get_release_urls (self ):
        config =getattr (self ,"release_config",{})or {}
        owner =str (config .get ("github_owner","" )).strip ()
        repo =str (config .get ("github_repo","" )).strip ()
        if not owner or not repo :
            return None ,None 
        api_url =str (config .get ("release_api_template","https://api.github.com/repos/{owner}/{repo}/releases/latest" )).format (owner =owner ,repo =repo )
        page_url =str (config .get ("release_page_template","https://github.com/{owner}/{repo}/releases/latest" )).format (owner =owner ,repo =repo )
        return api_url ,page_url 

    def _fetch_latest_release_info (self ):
        api_url ,_ =self ._get_release_urls ()
        if not api_url :
            return None 
        request =urllib .request .Request (api_url ,headers ={"Accept":"application/vnd.github+json","User-Agent":"ROMILab-Updater"})
        with urllib .request .urlopen (request ,timeout =15 )as response :
            payload =response .read ().decode ("utf-8")
        return json .loads (payload )

    def _download_update_installer (self ,download_url ,asset_name ):
        downloads_dir =os .path .join (os .path .expanduser ("~"),"Downloads","ROMILabUpdates")
        os .makedirs (downloads_dir ,exist_ok =True )
        file_name =asset_name or os .path .basename (urllib .parse .urlparse (download_url ).path ) or "ROMILab-Setup.exe"
        target_path =os .path .join (downloads_dir ,file_name )
        request =urllib .request .Request (download_url ,headers ={"User-Agent":"ROMILab-Updater"})
        with urllib .request .urlopen (request ,timeout =60 )as response ,open (target_path ,"wb")as output_file :
            output_file .write (response .read ())
        return target_path 
    def check_for_updates_on_startup (self ,manual =False ):
        config =getattr (self ,"release_config",{})or {}
        if not bool (config .get ("update_check_enabled",True )):
            if manual :
                QMessageBox .information (self ,"Проверка обновлений","Проверка обновлений отключена в настройках релиза.")
            return 
        api_url ,page_url =self ._get_release_urls ()
        if not api_url :
            self .log ("Проверка обновлений пропущена: GitHub репозиторий еще не настроен")
            if manual :
                QMessageBox .information (self ,"Проверка обновлений","GitHub-репозиторий для обновлений еще не настроен.")
            return 
        try :
            latest_release =self ._fetch_latest_release_info ()
            if not latest_release :
                if manual :
                    QMessageBox .information (self ,"Проверка обновлений","Не удалось получить информацию о последнем релизе.")
                return 
            latest_version =normalize_version (latest_release .get ("tag_name")or latest_release .get ("name")or "")
            current_version =normalize_version (getattr (self ,"app_version","0.1.0"))
            if not is_newer_version (latest_version ,current_version ):
                self .log (f"Проверка обновлений: установлена актуальная версия {current_version }")
                if manual :
                    QMessageBox .information (self ,"Проверка обновлений",f"У вас уже установлена актуальная версия: {current_version }")
                return 
            assets =latest_release .get ("assets",[])if isinstance (latest_release ,dict )else []
            installer_asset =None 
            for asset in assets :
                asset_name =str (asset .get ("name",""))
                if asset_name .lower ().endswith ((".exe",".msi")):
                    installer_asset =asset 
                    break 
            release_notes =str (latest_release .get ("body","" )).strip ()
            message =f"Доступна новая версия приложения: {latest_version }\nТекущая версия: {current_version }"
            if release_notes :
                message +=f"\n\nЧто нового:\n{release_notes [:1200 ]}"
            if installer_asset and installer_asset .get ("browser_download_url"):
                reply =QMessageBox .question (
                self ,
                "Доступно обновление",
                message + "\n\nСкачать и открыть установщик новой версии?",
                QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No 
                )
                if reply ==QMessageBox .StandardButton .Yes :
                    downloaded_file =self ._download_update_installer (installer_asset .get ("browser_download_url"),installer_asset .get ("name","ROMILab-Setup.exe"))
                    QMessageBox .information (self ,"Обновление загружено",f"Установщик сохранен:\n{downloaded_file }")
                    try :
                        os .startfile (downloaded_file )
                    except Exception as open_error :
                        self .log (f"Не удалось открыть установщик автоматически: {open_error }")
            elif page_url :
                reply =QMessageBox .question (
                self ,
                "Доступно обновление",
                message + "\n\nНа релизе нет установщика. Открыть страницу релиза?",
                QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No 
                )
                if reply ==QMessageBox .StandardButton .Yes :
                    try :
                        os .startfile (page_url )
                    except Exception as open_error :
                        self .log (f"Не удалось открыть страницу релиза: {open_error }")
        except Exception as e :
            self .log (f"Проверка обновлений пропущена из-за ошибки: {e }")
            if manual :
                QMessageBox .warning (self ,"Проверка обновлений",f"Не удалось проверить обновления:\n{e }")
if __name__ =="__main__":
    app =QApplication (sys .argv )
    window =AnalyticsApp ()
    window .show ()
    sys .exit (app .exec ())

























