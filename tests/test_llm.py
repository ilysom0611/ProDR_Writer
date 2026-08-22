import pytest

from prodr_writer.llm import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_in_fence():
    text = "Here is the result:\n```json\n{\"score\": 92}\n```\nDone."
    assert extract_json(text) == {"score": 92}


def test_think_tags_and_prose():
    text = "<think>reasoning...</think> Result: {\"ok\": true, \"note\": \"brace } inside string\"} trailing"
    assert extract_json(text) == {"ok": True, "note": "brace } inside string"}


def test_nested_braces():
    text = "prefix {\"a\": {\"b\": [1, 2]}, \"c\": \"}\"} suffix"
    assert extract_json(text) == {"a": {"b": [1, 2]}, "c": "}"}


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json("no structured content here")
