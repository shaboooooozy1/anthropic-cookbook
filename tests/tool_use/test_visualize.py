from __future__ import annotations

from tool_use.utils.visualize import format_json, parse_content_block, parse_response


def test_parse_content_block_text() -> None:
    content = parse_content_block("hello")

    assert content.type == "text"
    assert content.data["text"] == "hello"


def test_parse_content_block_dict() -> None:
    content = parse_content_block({"type": "tool_use", "name": "example"})

    assert content.type == "tool_use"
    assert content.data["name"] == "example"


def test_parse_response_dict() -> None:
    response = {
        "role": "assistant",
        "content": [{"type": "text", "text": "hi"}],
        "model": "claude-sonnet-4-6",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 3, "output_tokens": 7},
    }

    parsed = parse_response(response)

    assert parsed.role == "assistant"
    assert parsed.model == "claude-sonnet-4-6"
    assert parsed.stop_reason == "end_turn"
    assert parsed.usage["input_tokens"] == 3
    assert parsed.content[0].type == "text"


def test_format_json_truncates() -> None:
    data = {"text": "x" * 200}

    formatted = format_json(data, max_length=50)

    assert "truncated" in formatted
