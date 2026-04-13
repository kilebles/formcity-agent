from __future__ import annotations

import csv
import io


class Anonymizer:
    """Заменяет PII-значения в CSV на псевдонимы и восстанавливает их в тексте ответа."""

    _COLUMN_RULES: dict[str, str] = {
        "фио клиента": "Клиент",
        "фио агента": "Агент",
        "наименование агента": "Агент",
        "фио": "Клиент",
        "телефон": "Телефон",
    }

    _PHONE_PLACEHOLDER = "+7-XXX-XXX-XX-XX"

    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._reverse: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def _pii_prefix(self, col: str) -> str | None:
        col_lower = col.lower()
        for kw, prefix in sorted(self._COLUMN_RULES.items(), key=lambda x: -len(x[0])):
            if kw in col_lower:
                return prefix
        return None

    def _alias(self, prefix: str, value: str) -> str:
        if prefix == "Телефон":
            return self._PHONE_PLACEHOLDER
        if value in self._reverse:
            return self._reverse[value]
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        alias = f"{prefix}_{n}"
        self._map[alias] = value
        self._reverse[value] = alias
        return alias

    def anonymize_csv(self, text: str) -> str:
        """Анонимизирует CSV: заменяет значения PII-столбцов на псевдонимы."""
        if not text or text.startswith("("):
            return text

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return text

        header = rows[0]
        pii: dict[int, str] = {
            i: prefix
            for i, col in enumerate(header)
            if (prefix := self._pii_prefix(col)) is not None
        }

        if not pii:
            return text

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(header)
        for row in rows[1:]:
            new_row = list(row)
            for idx, prefix in pii.items():
                if idx < len(new_row) and new_row[idx]:
                    new_row[idx] = self._alias(prefix, new_row[idx])
            writer.writerow(new_row)

        return out.getvalue()

    def deanonymize(self, text: str) -> str:
        """Заменяет псевдонимы в тексте ответа обратно на реальные значения."""
        for alias, real in self._map.items():
            text = text.replace(alias, real)
        return text
