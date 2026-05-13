from __future__ import annotations

import asyncio
import json

import polars as pl
from loguru import logger

from app.services import excel as excel_svc

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "Возвращает список всех доступных Excel-файлов (.xlsx). "
                "Используй это первым, чтобы узнать какие данные доступны."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sheet_names",
            "description": "Возвращает список листов в указанном Excel-файле.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Имя файла из list_files.",
                    },
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_sheet",
            "description": (
                "Возвращает метаданные листа: количество строк, названия столбцов, "
                "типы данных и количество пустых значений. "
                "Используй перед load_sheet или search_in_sheet, чтобы узнать точные имена столбцов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
                "required": ["file_name", "sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_sheet",
            "description": (
                "Загружает весь лист и возвращает содержимое в формате CSV. "
                "Для больших листов предпочитай search_in_sheet с фильтрацией."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
                "required": ["file_name", "sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_sheet",
            "description": (
                "Ищет строки в листе по значению в столбце. "
                "Укажи value для поиска подстроки (регистронезависимо), "
                "или find_nulls=true чтобы найти пустые ячейки в столбце. "
                "Для фильтрации по году или периоду используй date_from и/или date_to "
                "(формат 'YYYY' или 'YYYY-MM-DD'). "
                "Параметры value и date_from/date_to можно комбинировать: например искать по ФИО клиента и одновременно фильтровать по году сделки. "
                "Если фильтр по дате нужно применить к другому столбцу (не column), укажи date_column. "
                "Например: column='ФИО Клиента', value='Иванов', date_column='Дата ДДУ', date_from='2024', date_to='2024'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "column": {
                        "type": "string",
                        "description": "Имя столбца для поиска по value или find_nulls (используй describe_sheet чтобы узнать точные названия).",
                    },
                    "value": {
                        "type": "string",
                        "description": "Подстрока для поиска в column. Можно комбинировать с date_from/date_to.",
                    },
                    "find_nulls": {
                        "type": "boolean",
                        "description": "Если true — вернуть строки где столбец пустой.",
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Столбец с датой для фильтрации, если он отличается от column. Например 'Дата ДДУ' или 'Дата Договора уступки'.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Начало диапазона дат. Формат: YYYY или YYYY-MM-DD. Например '2022' или '2022-01-01'.",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Конец диапазона дат. Формат: YYYY или YYYY-MM-DD. Например '2022' или '2022-12-31'.",
                    },
                },
                "required": ["file_name", "sheet_name", "column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sum_column",
            "description": (
                "Суммирует числовой столбец листа (например, площадь в кв.м., сумму сделки). "
                "Используй когда пользователь спрашивает 'сколько квадратных метров', "
                "'какая общая площадь', 'сумма продаж' и т.п. "
                "date_column — столбец с датой для фильтрации (например, 'Дата ДДУ'). "
                "date_from/date_to — опциональный фильтр по диапазону дат (формат YYYY или YYYY-MM-DD)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "column": {
                        "type": "string",
                        "description": "Числовой столбец для суммирования (используй describe_sheet чтобы узнать точные названия).",
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Столбец с датой для фильтрации (например, 'Дата ДДУ'). Обязателен если указываешь date_from/date_to.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Начало диапазона дат. Формат: YYYY или YYYY-MM-DD.",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Конец диапазона дат. Формат: YYYY или YYYY-MM-DD.",
                    },
                },
                "required": ["file_name", "sheet_name", "column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_values",
            "description": (
                "Считает количество значений в столбце. "
                "Используй для вопросов 'сколько продано', 'сколько апартаментов', "
                "'сколько уникальных' и подобных агрегаций. "
                "distinct=true — количество уникальных значений (например, уникальных номеров апартаментов). "
                "distinct=false (по умолчанию) — количество непустых строк. "
                "date_from/date_to — опциональный фильтр по диапазону дат (формат YYYY или YYYY-MM-DD); "
                "при использовании ОБЯЗАТЕЛЬНО передавай date_column — столбец с датой. "
                "Если период не указан пользователем — НЕ передавай date_from/date_to."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "column": {
                        "type": "string",
                        "description": "Имя столбца для подсчёта (используй describe_sheet чтобы узнать точные названия).",
                    },
                    "distinct": {
                        "type": "boolean",
                        "description": "Если true — считать уникальные значения. Используй для подсчёта уникальных объектов (апартаментов, клиентов и т.п.).",
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Столбец с датой для фильтрации (например, 'Дата ДДУ'). Обязателен если указываешь date_from/date_to.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Начало диапазона дат. Формат: YYYY или YYYY-MM-DD. Передавай ТОЛЬКО если пользователь указал период.",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Конец диапазона дат. Формат: YYYY или YYYY-MM-DD. Передавай ТОЛЬКО если пользователь указал период.",
                    },
                },
                "required": ["file_name", "sheet_name", "column"],
            },
        },
    },
]


_MAX_ROWS = 200
_MAX_CHARS = 80_000


def _df_to_str(df: pl.DataFrame) -> str:
    if df.is_empty():
        return "(нет строк — результат пустой)"
    total = len(df)
    truncated = total > _MAX_ROWS
    out_df = df.head(_MAX_ROWS) if truncated else df
    csv = out_df.write_csv()
    if len(csv) > _MAX_CHARS:
        csv = csv[:_MAX_CHARS] + "\n[...обрезано]"
    header = f"[Всего строк: {total}]" + (f" [Показаны первые {_MAX_ROWS}]" if truncated else "")
    return f"{header}\n{csv}"


async def call_tool(name: str, arguments: dict) -> str:
    """Выполняет tool call и возвращает результат строкой. Никогда не бросает исключений."""
    try:
        if name == "list_files":
            result = await asyncio.to_thread(excel_svc.list_files)
            return json.dumps(result, ensure_ascii=False)

        elif name == "get_sheet_names":
            result = await asyncio.to_thread(
                excel_svc.get_sheet_names, arguments["file_name"]
            )
            return json.dumps(result, ensure_ascii=False)

        elif name == "describe_sheet":
            result = await asyncio.to_thread(
                excel_svc.describe_sheet,
                arguments["file_name"],
                arguments["sheet_name"],
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        elif name == "load_sheet":
            df = await asyncio.to_thread(
                excel_svc.load_sheet,
                arguments["file_name"],
                arguments["sheet_name"],
            )
            return _df_to_str(df)

        elif name == "search_in_sheet":
            df = await asyncio.to_thread(
                excel_svc.search_in_sheet,
                arguments["file_name"],
                arguments["sheet_name"],
                arguments["column"],
                value=arguments.get("value"),
                find_nulls=bool(arguments.get("find_nulls", False)),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                date_column=arguments.get("date_column"),
            )
            return _df_to_str(df)

        elif name == "sum_column":
            result = await asyncio.to_thread(
                excel_svc.sum_column,
                arguments["file_name"],
                arguments["sheet_name"],
                arguments["column"],
                date_column=arguments.get("date_column"),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        elif name == "count_values":
            result = await asyncio.to_thread(
                excel_svc.count_values,
                arguments["file_name"],
                arguments["sheet_name"],
                arguments["column"],
                distinct=bool(arguments.get("distinct", False)),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                date_column=arguments.get("date_column"),
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        else:
            return f"Неизвестный инструмент: {name}"

    except Exception as exc:
        logger.warning("Tool '{name}' failed: {exc}", name=name, exc=exc)
        return f"Ошибка выполнения инструмента '{name}': {exc}"
