# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```bash
uv run python main.py
```

Requires `.env` with:
```
BOT_TOKEN=...
OPENAI_KEY=...
OPENAI_MODEL=gpt-4o  # optional, default gpt-4o
```

## Architecture

Telegram-бот на aiogram 3 с OpenAI и чтением Excel через polars + fastexcel.

- `main.py` — точка входа, запускает `app/main.py`
- `app/main.py` — инициализация Bot/Dispatcher, polling
- `app/config.py` — настройки через pydantic-settings из `.env`
- `app/logger.py` — loguru + перехват стандартного logging; логи пишутся в `logs/bot.log`
- `app/bot/commands.py` — список команд бота (BOT_COMMANDS)
- `app/bot/router.py` — главный Router, подключает все sub-роутеры
- `app/bot/handlers/` — обработчики сообщений/команд; каждый файл экспортирует `router`
- `app/services/excel.py` — чтение xlsx из `common/` через fastexcel + polars, LRU-кеш
- `app/schemas/excel.py` — SHEET_SCHEMAS (header_row для каждого листа) и DASHBOARD_SHEETS
- `app/tools/` — инструменты для LLM (function calling)
- `common/` — xlsx-файлы с данными (не трогать руками)

## Conventions

- Комментарии в коде не писать. Докстринги на публичных функциях — OK.
- Новый handler = новый файл в `app/bot/handlers/`, регистрируется в `app/bot/router.py`.
- Схемы Excel (header_row) добавлять в `app/schemas/excel.py`, не в сервис.
- Зависимости управляются через `uv`.
