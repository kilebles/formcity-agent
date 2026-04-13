from __future__ import annotations

from tests.evals.cases.excel_cases import EvalCase

WEB_CASES: list[EvalCase] = [
    EvalCase(
        id="web_project_info_01",
        question="Расскажи о проекте King & Sons — что это за объект?",
        checks=[
            "Ответ упоминает Москву или Moscow",
            "Ответ упоминает апартаменты, квартиры или жилой комплекс",
            'Ответ не говорит "данных нет" или "не удалось получить"',
        ],
        tags=["web", "parse"],
    ),
    EvalCase(
        id="web_well_msk_01",
        question=(
            "Зайди на сайт Well Московский (well-apart-msk.ru) и скажи "
            "сколько там всего номеров в апарт-отеле?"
        ),
        checks=[
            "Ответ упоминает число 552",
        ],
        tags=["web", "parse"],
    ),
    EvalCase(
        id="web_search_01",
        question="Что такое ДДУ в строительстве?",
        checks=[
            "Ответ объясняет что ДДУ — это Договор долевого участия",
            "Ответ написан на русском языке",
            "Ответ содержательный (более одного предложения)",
        ],
        tags=["web", "search"],
    ),
    EvalCase(
        id="web_idempotency_01",
        question="Расскажи о проекте King & Sons — что это за объект?",
        checks=[
            "Ответ упоминает King & Sons",
            "Ответ упоминает Москву или жилой комплекс",
        ],
        tags=["web", "idempotency"],
    ),
]
