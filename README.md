# formcity-bot

Telegram-бот на aiogram 3 с OpenAI GPT-4o для анализа внутренних данных компании Formula City.

## Запуск

```bash
uv run python main.py
```

Требуется `.env`:

```
BOT_TOKEN=...
OPENAI_KEY=...
OPENAI_MODEL=gpt-4o
TAVILY_KEY=...
```

## Юнит-тесты

Проверяют корректность кода: сервисы, инструменты, agentic loop (с моками OpenAI).

```bash
uv run pytest
```

## LLM Evals

Evaluation-тесты проверяют качество ответов бота: реальные вопросы прогоняются через живой LLM, ответы оцениваются по смысловым критериям.

Результаты сохраняются в `tests/evals/results/` в формате JSON.

### Запуск

```bash
# Все кейсы
uv run python -m tests.evals.runner

# Только Excel-кейсы (поиск, агрегация, пустые ячейки)
uv run python -m tests.evals.runner --tags excel

# Только веб-кейсы (парсинг сайтов + Tavily)
uv run python -m tests.evals.runner --tags web

# Только idempotency-кейсы
uv run python -m tests.evals.runner --tags idempotency

# Конкретный кейс по ID
uv run python -m tests.evals.runner --id excel_null_search_01
```

### Кейсы

| Тег | Что проверяет |
|---|---|
| `excel` | Поиск и агрегация данных из xlsx-файлов |
| `web` | Парсинг сайтов проектов и веб-поиск через Tavily |
| `null_search` | Поиск пустых ячеек в таблицах |
| `search` | Поиск конкретных значений (квартира, клиент, цена) |
| `aggregation` | Подсчёт строк, сумм, статистики |
| `idempotency` | Один и тот же вопрос дважды — ответы должны совпадать по смыслу |

### Формат результатов

Каждый запуск сохраняет `tests/evals/results/YYYY-MM-DDTHH-MM.json`:

```json
{
  "run_at": "2026-04-12T14-30",
  "model": "gpt-4o",
  "total": 12,
  "passed": 11,
  "failed": 1,
  "results": [
    {
      "id": "excel_null_search_01",
      "passed": true,
      "reason": "Ответ содержит список строк с пустыми ячейками",
      "duration_ms": 4200
    }
  ]
}
```
