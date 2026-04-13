"""
LLM evaluation runner.

Usage:
    uv run python -m tests.evals.runner              # все кейсы
    uv run python -m tests.evals.runner --tags excel # только excel
    uv run python -m tests.evals.runner --tags web   # только web
    uv run python -m tests.evals.runner --id excel_null_search_01
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.services.ai import ask
from tests.evals.cases.excel_cases import EXCEL_CASES, EvalCase
from tests.evals.cases.web_cases import WEB_CASES
from tests.evals.judge import judge

ALL_CASES: list[EvalCase] = EXCEL_CASES + WEB_CASES

RESULTS_DIR = Path(__file__).parent / "results"


def _filter_cases(cases: list[EvalCase], tags: list[str], id_: str | None) -> list[EvalCase]:
    if id_:
        return [c for c in cases if c.id == id_]
    if tags:
        return [c for c in cases if any(t in c.tags for t in tags)]
    return cases


async def _run_case(case: EvalCase) -> dict:
    start = time.monotonic()
    try:
        answer = await ask(case.question)
    except Exception as exc:
        answer = f"[ERROR] {exc}"

    duration_ms = int((time.monotonic() - start) * 1000)

    passed, reason = await judge(case.question, answer, case.checks)

    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {case.id} ({duration_ms}ms)")
    if not passed:
        print(f"         reason: {reason}")

    return {
        "id": case.id,
        "tags": case.tags,
        "question": case.question,
        "answer": answer,
        "checks": case.checks,
        "passed": passed,
        "reason": reason,
        "duration_ms": duration_ms,
    }


async def _run_idempotency(case: EvalCase) -> list[dict]:
    """Для idempotency-кейсов запускает вопрос дважды и сравнивает результаты."""
    print(f"  [IDEMPOTENCY] {case.id} — запуск 1/2")
    r1 = await _run_case(case)
    print(f"  [IDEMPOTENCY] {case.id} — запуск 2/2")
    r2 = await _run_case(case)

    both_passed = r1["passed"] and r2["passed"]
    return [
        {**r1, "id": f"{case.id}_run1", "idempotency_passed": both_passed},
        {**r2, "id": f"{case.id}_run2", "idempotency_passed": both_passed},
    ]


async def main(tags: list[str], id_: str | None) -> None:
    cases = _filter_cases(ALL_CASES, tags, id_)
    if not cases:
        print("Нет кейсов по заданным фильтрам.")
        return

    print(f"\nЗапуск {len(cases)} eval-кейсов...\n")
    results: list[dict] = []

    for case in cases:
        if "idempotency" in case.tags:
            results.extend(await _run_idempotency(case))
        else:
            results.append(await _run_case(case))

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = total - passed

    print(f"\nИтого: {passed}/{total} прошло, {failed} упало")

    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
    output = {
        "run_at": run_at,
        "model": settings.openai_model,
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_at}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Результаты сохранены: {out_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Запуск LLM evals")
    parser.add_argument("--tags", nargs="+", default=[], help="Фильтр по тегам (excel, web, ...)")
    parser.add_argument("--id", dest="id_", default=None, help="Запустить конкретный кейс по ID")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(tags=args.tags, id_=args.id_))
