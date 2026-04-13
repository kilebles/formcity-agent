"""Тесты для app/services/excel.py и app/schemas/excel.py."""

from __future__ import annotations

import polars as pl
import pytest

from app.schemas.excel import SHEET_SCHEMAS
from app.services.excel import (
    _deduplicate_columns,
    _find_column,
    _normalize_col,
    describe_sheet,
    get_sheet_names,
    list_files,
    load_sheet,
    search_in_sheet,
)

FILE = "Сводная_Обводный 118.xlsx"
SHEET = "Уступки ВЕЛЛ"


class TestNormalization:
    def test_normalize_strips_whitespace(self):
        assert _normalize_col("  Имя  ") == "Имя"

    def test_normalize_collapses_spaces(self):
        assert _normalize_col("Дата  регистрации") == "Дата регистрации"

    def test_normalize_none(self):
        assert _normalize_col(None) == "unnamed"

    def test_deduplicate_unique(self):
        assert _deduplicate_columns(["a", "b", "c"]) == ["a", "b", "c"]

    def test_deduplicate_duplicates(self):
        result = _deduplicate_columns(["a", "a", "a"])
        assert result == ["a", "a_1", "a_2"]

    def test_deduplicate_mixed(self):
        result = _deduplicate_columns(["x", "y", "x"])
        assert result == ["x", "y", "x_1"]


class TestListFiles:
    def test_returns_list(self):
        files = list_files()
        assert isinstance(files, list)
        assert len(files) > 0

    def test_all_xlsx(self):
        for f in list_files():
            assert f.endswith(".xlsx")

    def test_idempotent(self):
        assert list_files() == list_files()

    def test_known_file_present(self):
        assert FILE in list_files()


class TestGetSheetNames:
    def test_returns_list(self):
        sheets = get_sheet_names(FILE)
        assert isinstance(sheets, list)
        assert len(sheets) > 0

    def test_known_sheet_present(self):
        assert SHEET in get_sheet_names(FILE)

    def test_idempotent(self):
        assert get_sheet_names(FILE) == get_sheet_names(FILE)

    def test_missing_file_raises(self):
        with pytest.raises(Exception):
            get_sheet_names("несуществующий.xlsx")


class TestLoadSheet:
    def test_returns_dataframe(self):
        df = load_sheet(FILE, SHEET)
        assert isinstance(df, pl.DataFrame)

    def test_not_empty(self):
        df = load_sheet(FILE, SHEET)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_no_fully_null_rows(self):
        df = load_sheet(FILE, SHEET)
        fully_null = df.filter(pl.all_horizontal(pl.all().is_null()))
        assert len(fully_null) == 0

    def test_idempotent_same_object(self):
        df1 = load_sheet(FILE, SHEET)
        df2 = load_sheet(FILE, SHEET)
        assert df1 is df2

    def test_idempotent_equal_content(self):
        df1 = load_sheet(FILE, SHEET)
        df2 = load_sheet(FILE, SHEET)
        assert df1.equals(df2)

    def test_column_names_normalized(self):
        df = load_sheet(FILE, SHEET)
        for col in df.columns:
            assert col == col.strip()
            assert "  " not in col

    def test_missing_sheet_raises(self):
        with pytest.raises(Exception):
            load_sheet(FILE, "НесуществующийЛист")

    def test_header_row_applied(self):
        header_row = SHEET_SCHEMAS.get(FILE, {}).get(SHEET, 0)
        df = load_sheet(FILE, SHEET)
        if header_row > 0:
            assert not any(str(c).startswith("column_") for c in df.columns)


class TestDescribeSheet:
    def test_returns_dict_with_keys(self):
        meta = describe_sheet(FILE, SHEET)
        assert "file" in meta
        assert "sheet" in meta
        assert "rows" in meta
        assert "columns" in meta
        assert "dtypes" in meta
        assert "null_counts" in meta

    def test_matches_load_sheet(self):
        df = load_sheet(FILE, SHEET)
        meta = describe_sheet(FILE, SHEET)
        assert meta["rows"] == len(df)
        assert meta["columns"] == df.columns

    def test_null_counts_non_negative(self):
        meta = describe_sheet(FILE, SHEET)
        for col, count in meta["null_counts"].items():
            assert count >= 0

    def test_idempotent(self):
        m1 = describe_sheet(FILE, SHEET)
        m2 = describe_sheet(FILE, SHEET)
        assert m1 == m2


class TestFindColumn:
    def test_exact_match(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        assert _find_column(df, col) == col

    def test_case_insensitive(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        assert _find_column(df, col.upper()) == col

    def test_partial_match(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        if len(col) > 3:
            assert _find_column(df, col[:3]) == col

    def test_no_match_returns_none(self):
        df = load_sheet(FILE, SHEET)
        assert _find_column(df, "zzz_нет_такого_столбца_zzz") is None


class TestSearchInSheet:
    def test_find_nulls_returns_dataframe(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        result = search_in_sheet(FILE, SHEET, col, find_nulls=True)
        assert isinstance(result, pl.DataFrame)

    def test_find_nulls_idempotent(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        r1 = search_in_sheet(FILE, SHEET, col, find_nulls=True)
        r2 = search_in_sheet(FILE, SHEET, col, find_nulls=True)
        assert r1.equals(r2)

    def test_find_nulls_consistent_with_load_sheet(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        nulls_via_search = search_in_sheet(FILE, SHEET, col, find_nulls=True)
        nulls_via_polars = df.filter(pl.col(col).is_null())
        assert len(nulls_via_search) == len(nulls_via_polars)

    def test_search_value_subset_of_full_sheet(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        first_val = df[col].drop_nulls().cast(pl.Utf8).head(1).to_list()
        if not first_val:
            pytest.skip("No non-null values in first column")
        query = str(first_val[0])[:3]
        result = search_in_sheet(FILE, SHEET, col, value=query)
        assert len(result) <= len(df)

    def test_search_value_idempotent(self):
        df = load_sheet(FILE, SHEET)
        col = df.columns[0]
        first_val = df[col].drop_nulls().cast(pl.Utf8).head(1).to_list()
        if not first_val:
            pytest.skip("No non-null values in first column")
        query = str(first_val[0])[:3]
        r1 = search_in_sheet(FILE, SHEET, col, value=query)
        r2 = search_in_sheet(FILE, SHEET, col, value=query)
        assert r1.equals(r2)

    def test_invalid_column_raises(self):
        with pytest.raises(ValueError, match="не найден"):
            search_in_sheet(FILE, SHEET, "zzz_нет_такого_zzz")


class TestSheetsSchemas:
    def test_all_schema_files_exist(self):
        available = list_files()
        for file_name in SHEET_SCHEMAS:
            assert file_name in available, f"{file_name} из SHEET_SCHEMAS не найден в common/"

    def test_all_schema_sheets_exist(self):
        for file_name, sheets in SHEET_SCHEMAS.items():
            available_sheets = get_sheet_names(file_name)
            for sheet_name in sheets:
                assert sheet_name in available_sheets, (
                    f"Лист '{sheet_name}' из SHEET_SCHEMAS не найден в {file_name}"
                )

    def test_header_rows_non_negative(self):
        for file_name, sheets in SHEET_SCHEMAS.items():
            for sheet_name, header_row in sheets.items():
                assert header_row >= 0, (
                    f"header_row < 0 для {file_name}/{sheet_name}"
                )
