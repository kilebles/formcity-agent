from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.config import settings

_client = AsyncOpenAI(api_key=settings.openai_key.get_secret_value())

_JUDGE_SYSTEM = (
    "Ты — беспристрастный судья качества ответов AI-ассистента. "
    "Оценивай строго по указанным критериям. "
    "Отвечай только валидным JSON без пояснений вне JSON."
)


async def judge(question: str, answer: str, checks: list[str]) -> tuple[bool, str]:
    """Оценивает ответ бота по списку критериев. Возвращает (passed, reason)."""
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(checks))
    prompt = (
        f"Вопрос пользователя:\n{question}\n\n"
        f"Ответ бота:\n{answer}\n\n"
        f"Критерии (все должны выполняться):\n{numbered}\n\n"
        'Ответь JSON: {"passed": true или false, "reason": "краткое объяснение"}'
    )

    response = await _client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return bool(data.get("passed", False)), str(data.get("reason", ""))
