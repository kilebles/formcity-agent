from __future__ import annotations

import json

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

_client = AsyncOpenAI(api_key=settings.openai_key.get_secret_value())

_SYSTEM_PROMPT = """Ты — внутренний ИИ-помощник компании Formula City.

ПАЙПЛАЙН ПОИСКА (строго соблюдай порядок):
1. Если пользователь явно просит зайти на сайт или упоминает URL — сразу используй parse_project_site, без поиска в Excel
2. Иначе сначала ищи данные в Excel-файлах (list_files → get_sheet_names → describe_sheet → search_in_sheet / load_sheet)
3. Если в Excel данных нет — используй parse_project_site чтобы получить информацию с официального сайта проекта
4. Если и там нет — используй search_web для поиска в интернете
5. Только после всех шагов сообщай что данных нет

Инструменты для Excel:
- list_files — узнать какие файлы доступны
- get_sheet_names — узнать листы файла
- describe_sheet — узнать структуру листа (столбцы, типы данных)
- load_sheet — загрузить весь лист
- search_in_sheet — найти строки по значению в столбце или найти пустые ячейки

Инструменты для веба:
- parse_project_site — получить информацию с официального сайта проекта (используй только если Excel не дал ответа)
- search_web — поиск в интернете через Tavily (используй только если Excel и parse_project_site не дали ответа)

Всегда сначала исследуй структуру данных перед ответом.
Отвечай на русском языке.
Если данных недостаточно — честно сообщи об этом.

ФОРМАТИРОВАНИЕ (сообщения отображаются в Telegram):
- Используй HTML-теги: <b>жирный</b>, <i>курсив</i>, <code>моноширинный</code>
- Никогда не используй markdown (**, *, `, |таблицы|) — они не работают в Telegram
- Списки записей оформляй нумерованным или маркированным списком, например:
  1. <b>Иванов И.И.</b> — апарт. 2.05, этаж 2
  2. <b>Петров П.П.</b> — апарт. 3.10, этаж 3
- Числа и итоги выделяй через <b>
- Если записей много (больше 20) — покажи первые 20 и укажи общее количество"""


_ANONYMIZED_TOOLS = {"load_sheet", "search_in_sheet"}


async def ask(user_message: str) -> str:
    """Запускает agentic loop для вопроса пользователя и возвращает ответ."""
    try:
        anonymizer = Anonymizer()
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(10):
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
                        args=str(arguments)[:120],
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
        return "Произошла ошибка при обработке запроса. Попробуйте ещё раз."
