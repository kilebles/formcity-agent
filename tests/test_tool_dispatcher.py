"""Тесты для app/tools/excel.py — диспетчер tool calls."""

from __future__ import annotations

import json

import polars as pl
import pytest

from app.tools.excel import TOOLS, _df_to_str, call_tool

FILE = "Сводная_Обводный 118.xlsx"
SHEET = "Уступки ВЕЛЛ"


class TestToolDefinitions:
    EXPECTED_NAMES = {"list_files", "get_sheet_names", "describe_sheet", "load_sheet", "search_in_sheet"}

    def test_all_tools_present(self):
        names = {t["function"]["name"] for t in TOOLS}
        assert names == self.EXPECTED_NAMES

    def test_each_tool_has_type_function(self):
        for t in TOOLS:
            assert t["type"] == "function"

    def test_each_tool_has_description(self):
        for t in TOOLS:
            assert t["function"].get("description", "").strip() != ""

    def test_each_tool_has_parameters_schema(self):
        for t in TOOLS:
            params = t["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_required_params_are_in_properties(self):
        for t in TOOLS:
            params = t["function"]["parameters"]
            for req in params["required"]:
                assert req in params["properties"], (
                    f"Tool '{t['function']['name']}': required param '{req}' not in properties"
                )

    def test_search_in_sheet_optional_params(self):
        tool = next(t for t in TOOLS if t["function"]["name"] == "search_in_sheet")
        params = tool["function"]["parameters"]
        assert "value" not in params["required"]
        assert "find_nulls" not in params["required"]
        assert "column" in params["required"]


class TestDfToStr:
    def test_empty_df_returns_message(self):
        df = pl.DataFrame({"a": []})
        result = _df_to_str(df)
        assert "пустой" in result.lower() or "empty" in result.lower()

    def test_non_empty_df_returns_csv(self):
        df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = _df_to_str(df)
        assert "a" in result
        assert "b" in result
        assert "1" in result

    def test_csv_has_header_row(self):
        df = pl.DataFrame({"col1": [10], "col2": [20]})
        result = _df_to_str(df)
        lines = result.strip().split("\n")
        assert "col1" in lines[0]
        assert "col2" in lines[0]


class TestCallTool:
    async def test_list_files(self):
        result = await call_tool("list_files", {})
        files = json.loads(result)
        assert isinstance(files, list)
        assert FILE in files

    async def test_list_files_idempotent(self):
        r1 = await call_tool("list_files", {})
        r2 = await call_tool("list_files", {})
        assert r1 == r2

    async def test_get_sheet_names(self):
        result = await call_tool("get_sheet_names", {"file_name": FILE})
        sheets = json.loads(result)
        assert isinstance(sheets, list)
        assert SHEET in sheets

    async def test_get_sheet_names_idempotent(self):
        r1 = await call_tool("get_sheet_names", {"file_name": FILE})
        r2 = await call_tool("get_sheet_names", {"file_name": FILE})
        assert r1 == r2

    async def test_describe_sheet(self):
        result = await call_tool("describe_sheet", {"file_name": FILE, "sheet_name": SHEET})
        meta = json.loads(result)
        assert "columns" in meta
        assert "rows" in meta
        assert meta["rows"] > 0

    async def test_describe_sheet_idempotent(self):
        r1 = await call_tool("describe_sheet", {"file_name": FILE, "sheet_name": SHEET})
        r2 = await call_tool("describe_sheet", {"file_name": FILE, "sheet_name": SHEET})
        assert r1 == r2

    async def test_load_sheet(self):
        result = await call_tool("load_sheet", {"file_name": FILE, "sheet_name": SHEET})
        assert isinstance(result, str)
        assert len(result) > 0
        assert result != "(нет строк — результат пустой)"

    async def test_load_sheet_idempotent(self):
        r1 = await call_tool("load_sheet", {"file_name": FILE, "sheet_name": SHEET})
        r2 = await call_tool("load_sheet", {"file_name": FILE, "sheet_name": SHEET})
        assert r1 == r2

    async def test_search_find_nulls(self):
        meta = json.loads(
            await call_tool("describe_sheet", {"file_name": FILE, "sheet_name": SHEET})
        )
        col = meta["columns"][0]
        result = await call_tool("search_in_sheet", {
            "file_name": FILE,
            "sheet_name": SHEET,
            "column": col,
            "find_nulls": True,
        })
        assert isinstance(result, str)

    async def test_search_find_nulls_idempotent(self):
        meta = json.loads(
            await call_tool("describe_sheet", {"file_name": FILE, "sheet_name": SHEET})
        )
        col = meta["columns"][0]
        args = {"file_name": FILE, "sheet_name": SHEET, "column": col, "find_nulls": True}
        r1 = await call_tool("search_in_sheet", args)
        r2 = await call_tool("search_in_sheet", args)
        assert r1 == r2

    async def test_search_by_value(self):
        result = await call_tool("search_in_sheet", {
            "file_name": FILE,
            "sheet_name": SHEET,
            "column": "№п/п",
            "value": "1",
        })
        assert isinstance(result, str)

    async def test_unknown_tool_returns_error_string(self):
        result = await call_tool("nonexistent_tool", {})
        assert "неизвестный" in result.lower() or "unknown" in result.lower()

    async def test_missing_file_returns_error_string(self):
        result = await call_tool("get_sheet_names", {"file_name": "нет_такого.xlsx"})
        assert "ошибка" in result.lower() or "error" in result.lower()

    async def test_invalid_column_returns_error_string(self):
        result = await call_tool("search_in_sheet", {
            "file_name": FILE,
            "sheet_name": SHEET,
            "column": "zzz_нет_такого_zzz",
            "find_nulls": True,
        })
        assert "ошибка" in result.lower() or "error" in result.lower()

    async def test_result_is_always_string(self):
        calls = [
            ("list_files", {}),
            ("get_sheet_names", {"file_name": FILE}),
            ("describe_sheet", {"file_name": FILE, "sheet_name": SHEET}),
            ("load_sheet", {"file_name": FILE, "sheet_name": SHEET}),
            ("unknown", {}),
            ("get_sheet_names", {"file_name": "несуществующий.xlsx"}),
        ]
        for name, args in calls:
            result = await call_tool(name, args)
            assert isinstance(result, str), f"call_tool('{name}') вернул не строку"
