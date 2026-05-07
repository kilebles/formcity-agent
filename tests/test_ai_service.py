"""Тесты для app/services/ai.py — agentic loop с мокнутым OpenAI."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai import ask


def _make_stop_response(content: str):
    choice = SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(content=content, tool_calls=None),
    )
    return SimpleNamespace(choices=[choice])


def _make_tool_call_response(tool_name: str, arguments: str, call_id: str = "call_1"):
    tc = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=tool_name, arguments=arguments),
    )
    choice = SimpleNamespace(
        finish_reason="tool_calls",
        message=SimpleNamespace(content=None, tool_calls=[tc]),
    )
    return SimpleNamespace(choices=[choice])


class TestAskBasic:
    async def test_returns_string(self):
        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=_make_stop_response("Привет!")
            )
            result = await ask("Привет")
        assert isinstance(result, str)
        assert result == "Привет!"

    async def test_empty_content_returns_empty_string(self):
        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=_make_stop_response("")
            )
            result = await ask("вопрос")
        assert result == ""

    async def test_openai_error_returns_error_string(self):
        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("network error")
            )
            result = await ask("вопрос")
        assert isinstance(result, str)
        assert len(result) > 0


class TestAskToolCalling:
    async def test_single_tool_call_then_stop(self):
        tool_result = '["file1.xlsx"]'

        responses = [
            _make_tool_call_response("list_files", "{}"),
            _make_stop_response("Доступны файлы: file1.xlsx"),
        ]

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value=tool_result)),
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=responses)
            result = await ask("какие файлы есть?")

        assert result == "Доступны файлы: file1.xlsx"

    async def test_tool_called_with_correct_name(self):
        tool_result = '["file1.xlsx"]'
        responses = [
            _make_tool_call_response("list_files", "{}"),
            _make_stop_response("ок"),
        ]

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value=tool_result)) as mock_tool,
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=responses)
            await ask("список файлов")

        mock_tool.assert_called_once_with("list_files", {})

    async def test_tool_result_appended_as_tool_message(self):
        tool_result = '["a.xlsx"]'
        captured_messages = []

        async def fake_create(**kwargs):
            captured_messages.append(list(kwargs["messages"]))
            if len(captured_messages) == 1:
                return _make_tool_call_response("list_files", "{}", call_id="c1")
            return _make_stop_response("ок")

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value=tool_result)),
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
            await ask("файлы")

        second_call_messages = captured_messages[1]
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["content"] == tool_result
        assert tool_messages[0]["tool_call_id"] == "c1"

    async def test_multiple_tool_calls_in_sequence(self):
        responses = [
            _make_tool_call_response("list_files", "{}", "c1"),
            _make_tool_call_response("get_sheet_names", '{"file_name":"a.xlsx"}', "c2"),
            _make_stop_response("готово"),
        ]

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value="[]")) as mock_tool,
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=responses)
            result = await ask("вопрос")

        assert result == "готово"
        assert mock_tool.call_count == 2

    async def test_tool_error_doesnt_crash_loop(self):
        responses = [
            _make_tool_call_response("list_files", "{}"),
            _make_stop_response("не нашёл"),
        ]

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value="Ошибка: файл не найден")),
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=responses)
            result = await ask("вопрос")

        assert isinstance(result, str)
        assert result == "не нашёл"


class TestAskIterationLimit:
    async def test_stops_after_max_iterations(self):
        infinite_tool_response = _make_tool_call_response("list_files", "{}")

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value="[]")),
        ):
            mock_client.chat.completions.create = AsyncMock(
                return_value=infinite_tool_response
            )
            result = await ask("бесконечный вопрос")

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_api_called_at_most_max_iterations(self):
        from app.services.ai import _MAX_ITERATIONS
        infinite_tool_response = _make_tool_call_response("list_files", "{}")

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value="[]")),
        ):
            mock_client.chat.completions.create = AsyncMock(
                return_value=infinite_tool_response
            )
            await ask("бесконечный вопрос")

        assert mock_client.chat.completions.create.call_count <= _MAX_ITERATIONS


class TestAskMessageStructure:
    async def test_first_call_has_system_and_user_messages(self):
        captured = {}

        async def fake_create(**kwargs):
            captured["messages"] = list(kwargs["messages"])
            return _make_stop_response("ок")

        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
            await ask("мой вопрос")

        messages = captured["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "мой вопрос"

    async def test_tools_passed_to_api(self):
        captured = {}

        async def fake_create(**kwargs):
            captured["tools"] = kwargs.get("tools")
            return _make_stop_response("ок")

        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
            await ask("вопрос")

        assert captured["tools"] is not None
        from app.services.ai import TOOLS
        assert len(captured["tools"]) == len(TOOLS)

    async def test_correct_model_used(self):
        captured = {}

        async def fake_create(**kwargs):
            captured["model"] = kwargs.get("model")
            return _make_stop_response("ок")

        with patch("app.services.ai._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
            await ask("вопрос")

        from app.config import settings
        assert captured["model"] == settings.openai_model

    async def test_temperature_zero_for_determinism(self):
        captured_calls = []

        async def fake_create(**kwargs):
            captured_calls.append(kwargs)
            if len(captured_calls) == 1:
                return _make_tool_call_response("list_files", "{}")
            return _make_stop_response("ок")

        with (
            patch("app.services.ai._client") as mock_client,
            patch("app.services.ai.call_tool", new=AsyncMock(return_value="[]")),
        ):
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
            await ask("вопрос")

        for call_kwargs in captured_calls:
            assert call_kwargs.get("temperature") == 0, (
                f"temperature должен быть 0, получено: {call_kwargs.get('temperature')}"
            )
