from __future__ import annotations

from app.services import web as web_svc

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Ищет информацию в интернете через Tavily. "
                "Используй только если данных нет ни в Excel-файлах, ни на сайте проекта."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на русском или английском.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_project_site",
            "description": (
                "Получает информацию о проекте с официального сайта компании. "
                "Используй только если данных нет в Excel-файлах. "
                "Доступные проекты: Well, Well Московский, Евгеньевский, "
                "King & Sons, Stories, Первая линия. "
                "Если проект не указан — используй 'formcity'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Название проекта на русском или английском.",
                    },
                },
                "required": ["project"],
            },
        },
    },
]


async def call_tool(name: str, arguments: dict) -> str:
    """Выполняет web tool call и возвращает результат строкой. Никогда не бросает исключений."""
    try:
        if name == "parse_project_site":
            return await web_svc.parse_project_site(arguments["project"])
        if name == "search_web":
            return await web_svc.search_web(arguments["query"])
        return f"Неизвестный инструмент: {name}"
    except Exception as exc:
        return f"Ошибка выполнения инструмента '{name}': {exc}"
