from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tavily import AsyncTavilyClient

from app.config import settings

PROJECT_SITES: dict[str, str] = {
    "well московский": "https://well-apart-msk.ru",
    "well-apart-msk": "https://well-apart-msk.ru",
    "well обводный": "https://well-apart.ru",
    "well-apart.ru": "https://well-apart.ru",
    "well-apart": "https://well-apart.ru",
    "обводный 118": "https://well-apart.ru",
    "well": "https://well-apart.ru",
    "евгеньевский": "https://evg-spb.ru",
    "king & sons": "https://kingsons.ru",
    "stories": "https://storiesmoscow.ru",
    "первая линия": "https://hcresort.ru",
    "formcity": "https://formcity.ru",
}

_MAX_TEXT_LENGTH = 5000
_TIMEOUT = 15.0


async def fetch_page(url: str) -> str:
    """Загружает страницу по URL и возвращает чистый текст без HTML-тегов."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:_MAX_TEXT_LENGTH]


async def parse_project_site(project: str) -> str:
    """Возвращает текстовое содержимое сайта проекта по его названию."""
    key = project.lower().strip()
    sorted_sites = sorted(PROJECT_SITES.items(), key=lambda x: -len(x[0]))
    url = next(
        (v for k, v in sorted_sites if k in key),
        next(
            (v for k, v in sorted_sites if key in k),
            PROJECT_SITES["formcity"],
        ),
    )
    logger.info("Parsing site for project '{project}': {url}", project=project, url=url)
    try:
        text = await fetch_page(url)
        return f"[Источник: {url}]\n\n{text}"
    except Exception as exc:
        logger.warning("Failed to parse {url}: {exc}", url=url, exc=exc)
        return f"Не удалось получить данные с сайта {url}: {exc}"


async def search_web(query: str) -> str:
    """Ищет информацию в интернете через Tavily. Используется как последний fallback."""
    if not settings.tavily_key:
        return "Веб-поиск недоступен: TAVILY_KEY не настроен."
    client = AsyncTavilyClient(api_key=settings.tavily_key.get_secret_value())
    logger.info("Tavily search: {query}", query=query)
    try:
        response = await client.search(query, max_results=5, search_depth="basic")
        results = response.get("results", [])
        if not results:
            return "Поиск не дал результатов."
        parts = []
        for r in results:
            parts.append(f"[{r.get('title', '')}]({r.get('url', '')})\n{r.get('content', '')[:500]}")
        return "\n\n---\n\n".join(parts)
    except Exception as exc:
        logger.warning("Tavily search failed: {exc}", exc=exc)
        return f"Ошибка веб-поиска: {exc}"
