from __future__ import annotations

import json

import httpx
from loguru import logger
from openai import AsyncOpenAI

from app.config import settings
from app.services.anonymizer import Anonymizer
from app.tools import excel as excel_tools
from app.tools import web as web_tools

TOOLS = excel_tools.TOOLS + web_tools.TOOLS
_EXCEL_TOOL_NAMES = {t["function"]["name"] for t in excel_tools.TOOLS}


async def call_tool(name: str, arguments: dict) -> str:
    if name in _EXCEL_TOOL_NAMES:
        return await excel_tools.call_tool(name, arguments)
    return await web_tools.call_tool(name, arguments)

def _build_proxy_url() -> str | None:
    if not settings.proxy:
        return None
    host, port, user, password = settings.proxy.split(":")
    return f"http://{user}:{password}@{host}:{port}"


_client = AsyncOpenAI(
    api_key=settings.openai_key.get_secret_value(),
    http_client=httpx.AsyncClient(proxy=_build_proxy_url()) if settings.proxy else None,
)

_SYSTEM_PROMPT = """Ты — внутренний ИИ-помощник компании Formula City.

ФОРМАТИРОВАНИЕ ОТВЕТОВ (соблюдай ВСЕГДА):
- Отвечай plain text без какого-либо форматирования
- ЗАПРЕЩЕНО: **жирный**, *курсив*, `код`, # заголовки, |таблицы|, --- разделители, HTML-теги
- Списки: только нумерованные (1. 2. 3.) или с дефисом (- )
- Если записей больше 20 — показывай первые 20 и указывай общее количество

ПАЙПЛАЙН ПОИСКА (строго соблюдай порядок):
1. Если пользователь явно просит зайти на сайт или упоминает URL — сразу используй parse_project_site, без поиска в Excel
2. Иначе сначала ищи данные в Excel-файлах (list_files → get_sheet_names → describe_sheet → search_in_sheet / count_values / load_sheet)
3. Если в Excel данных нет — используй parse_project_site чтобы получить информацию с официального сайта проекта
4. Если и там нет — используй search_web для поиска в интернете
5. Только после всех шагов сообщай что данных нет

Инструменты для Excel:
- list_files — узнать какие файлы доступны
- get_sheet_names — узнать листы файла
- describe_sheet — узнать структуру листа (столбцы, типы данных, примеры значений)
- load_sheet — загрузить весь лист (для просмотра данных)
- search_in_sheet — найти строки по значению в столбце, найти пустые ячейки, или отфильтровать по диапазону дат (date_from/date_to в формате 'YYYY' или 'YYYY-MM-DD')
- count_values — ПРЕДПОЧТИТЕЛЬНЫЙ инструмент для любых подсчётов: сколько продано, сколько апартаментов, сколько сделок и т.п.

Инструменты для веба:
- parse_project_site — получить информацию с официального сайта проекта (используй только если Excel не дал ответа)
- search_web — поиск в интернете через Tavily (используй только если Excel и parse_project_site не дали ответа)

МАППИНГ ПРОЕКТОВ → ФАЙЛЫ (обязательно):
- "Well", "Well Апарт-отель", "Велл Обводный", "Обводный" без уточнения → "Сводная_Обводный 118.xlsx"
- "Well Московский", "Велл Московский", "ВМ" → "Сводная_Велл Московский.xlsx"
- "Евгеньевский", "ЖК Евгеньевский" → "ЖК Евгеньевский.xlsx"
- Если не уверен в файле — сначала вызови list_files

ПОДСКАЗКИ ПО ДАННЫМ:
- Продажи апартаментов (сделки, ДДУ) — листы "Апартаменты (проект)" в файлах "Сводная_*.xlsx", столбец "Дата ДДУ"
- Уступки (переуступки прав) — лист "Уступки ВЕЛЛ" в "Сводная_Обводный 118.xlsx"
- Количество апартаментов в проекте ≠ количество строк в листе; используй count_values с distinct=true по столбцу с номером апартамента

ПРАВИЛА РАБОТЫ С ПЕРИОДАМИ:
- Если пользователь НЕ указал период — ищи за ВСЁ время (не передавай date_from/date_to)
- Если указан месяц (например "декабрь 2025") — используй date_from="2025-12-01" и date_to="2025-12-31"
- Если указан год (например "2022") — используй date_from="2022" и date_to="2022"
- Никогда не применяй произвольный период по умолчанию

ПРАВИЛА ОТВЕТА ПРИ ОТСУТСТВИИ ДАННЫХ:
- Если count_values вернул non_null_count=0 и есть поля data_min_date/data_max_date — сообщи пользователю что данные в файле охватывают только период от data_min_date до data_max_date, и запрошенный период в них не входит
- Пример: "В файле данные только по декабрь 2023. За декабрь 2025 сведений нет — возможно, файл не обновлён."
- Никогда не выдавай просто "0 сделок" без объяснения причины если запрошенный период выходит за пределы данных

ПРАВИЛА ПОДСЧЁТА:
- "Сколько продано", "сколько сделок" → count_values по столбцу "Дата ДДУ" (non-null = продана)
- "Сколько апартаментов в проекте" → count_values с distinct=true по столбцу с номером апартамента
- НЕ используй поле "rows" из describe_sheet как количество апартаментов или сделок — это общее число строк, включая непроданные

ВАЖНО: при поиске по конкретному проекту проверяй ОБА релевантных файла если не уверен.

Всегда сначала исследуй структуру данных перед ответом (describe_sheet).
Отвечай на русском языке.
Если данных недостаточно — честно сообщи об этом.

Пример оформления списка сделок:
1. Иванов И.И. — апарт. 2.05, этаж 2, дата ДДУ: 2025-12-10
2. Петров П.П. — апарт. 3.10, этаж 3, дата ДДУ: 2025-12-15"""


_MAX_ITERATIONS = 15
_ANONYMIZED_TOOLS = {"load_sheet", "search_in_sheet"}


async def ask(user_message: str, history: list[dict] | None = None) -> str:
    """Запускает agentic loop для вопроса пользователя и возвращает ответ."""
    try:
        anonymizer = Anonymizer()
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": user_message},
        ]

        for iteration in range(_MAX_ITERATIONS):
            response = await _client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0,
            )
            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return anonymizer.deanonymize(choice.message.content or "")

            if choice.finish_reason == "tool_calls":
                tool_calls = choice.message.tool_calls

                messages.append({
                    "role": "assistant",
                    "content": choice.message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    name = tc.function.name
                    arguments = json.loads(tc.function.arguments)
                    logger.info(
                        "Tool call [{i}]: {name}({args})",
                        i=iteration,
                        name=name,
                        args=str(arguments),
                    )
                    result = await call_tool(name, arguments)
                    if name in _ANONYMIZED_TOOLS:
                        result = anonymizer.anonymize_csv(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                continue

            return anonymizer.deanonymize(choice.message.content or "")

        return "Превышен лимит итераций. Попробуйте переформулировать вопрос."

    except Exception as exc:
        logger.exception("AI service error: {exc}", exc=exc)
        msg = str(exc)
        if "insufficient_quota" in msg or "quota" in msg.lower():
            return "⚠️ Исчерпан лимит OpenAI API. Пополните баланс на platform.openai.com."
        if "rate_limit" in msg.lower():
            return "⚠️ Превышен лимит запросов к OpenAI. Подождите немного и попробуйте снова."
        if "unsupported_country" in msg or "request_forbidden" in msg:
            return "⚠️ OpenAI недоступен с текущего IP. Проверьте настройки прокси."
        return "Произошла ошибка при обработке запроса. Попробуйте ещё раз."
