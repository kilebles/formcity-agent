from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final

import polars as pl
from loguru import logger

from app.schemas.excel import SHEET_SCHEMAS

COMMON_DIR: Final[Path] = Path(__file__).parent.parent.parent / "common"


def _normalize_col(name: str | None) -> str:
    if name is None:
        return "unnamed"
    name = str(name).strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _deduplicate_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            result.append(col)
    return result


def _read_sheet(file_path: Path, sheet_name: str, header_row: int) -> pl.DataFrame:
    import fastexcel
    reader = fastexcel.read_excel(str(file_path))
    sheet = reader.load_sheet(sheet_name, header_row=header_row)
    df = sheet.to_polars()

    normalized = _deduplicate_columns([_normalize_col(c) for c in df.columns])
    df = df.rename(dict(zip(df.columns, normalized)))
    df = df.filter(~pl.all_horizontal(pl.all().is_null()))

    logger.debug(
        "Loaded sheet '{sheet}' from '{file}': {rows} rows × {cols} cols",
        sheet=sheet_name,
        file=file_path.name,
        rows=len(df),
        cols=len(df.columns),
    )
    return df


@lru_cache(maxsize=128)
def load_sheet(file_name: str, sheet_name: str) -> pl.DataFrame:
    """Загружает лист из файла в common/. Результат кешируется."""
    file_path = COMMON_DIR / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    header_row = SHEET_SCHEMAS.get(file_name, {}).get(sheet_name, 0)
    logger.info(
        "Loading '{sheet}' from '{file}' (header_row={row})",
        sheet=sheet_name,
        file=file_name,
        row=header_row,
    )
    return _read_sheet(file_path, sheet_name, header_row)


def get_sheet_names(file_name: str) -> list[str]:
    """Возвращает список листов в файле."""
    import fastexcel  # noqa: PLC0415
    file_path = COMMON_DIR / file_name
    reader = fastexcel.read_excel(str(file_path))
    return reader.sheet_names


def list_files() -> list[str]:
    """Список всех xlsx-файлов в common/."""
    return [f.name for f in sorted(COMMON_DIR.glob("*.xlsx"))]


def search_in_sheet(
    file_name: str,
    sheet_name: str,
    column: str,
    *,
    value: str | None = None,
    find_nulls: bool = False,
) -> pl.DataFrame:
    """
    Поиск в конкретном листе.

    - find_nulls=True → строки где column пустой
    - value=... → строки где column содержит value (регистронезависимо)
    """
    df = load_sheet(file_name, sheet_name)

    col_match = _find_column(df, column)
    if col_match is None:
        available = ", ".join(df.columns)
        raise ValueError(
            f"Столбец '{column}' не найден в {file_name}/{sheet_name}. "
            f"Доступные: {available}"
        )

    if find_nulls:
        result = df.filter(pl.col(col_match).is_null())
        logger.info(
            "Nulls in '{col}' of {file}/{sheet}: {n} rows",
            col=col_match, file=file_name, sheet=sheet_name, n=len(result),
        )
        return result

    if value is not None:
        result = df.filter(
            pl.col(col_match).cast(pl.Utf8).str.to_lowercase().str.contains(
                value.lower(), literal=True
            )
        )
        logger.info(
            "Search '{val}' in '{col}' of {file}/{sheet}: {n} rows",
            val=value, col=col_match, file=file_name, sheet=sheet_name, n=len(result),
        )
        return result

    return df


def _find_column(df: pl.DataFrame, name: str) -> str | None:
    name_lower = name.strip().lower()
    for col in df.columns:
        if col.lower() == name_lower:
            return col
    for col in df.columns:
        if name_lower in col.lower():
            return col
    return None


def describe_sheet(file_name: str, sheet_name: str) -> dict:
    """Возвращает мета-информацию о листе для LLM-контекста."""
    df = load_sheet(file_name, sheet_name)
    return {
        "file": file_name,
        "sheet": sheet_name,
        "rows": len(df),
        "columns": df.columns,
        "dtypes": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
        "null_counts": {col: df[col].null_count() for col in df.columns},
    }
