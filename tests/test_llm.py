import pytest
from pydantic import BaseModel

from prodr_writer.llm import extract_json, run_stage


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


# ---------------------------------------------------------------------------
# run_stage retry behaviour
# ---------------------------------------------------------------------------

class _Out(BaseModel):
    score: int


class _FakeResult:
    def __init__(self, raw: str):
        self.raw = raw


@pytest.fixture()
def _no_backoff_sleep(monkeypatch):
    from prodr_writer import llm

    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)


def _patch_crew(monkeypatch, behaviours):
    """Patch llm.Crew so each kickoff() pops the next behaviour (str or Exception)."""
    from prodr_writer import llm

    calls = {"n": 0}
    steps = list(behaviours)

    class _FakeCrew:
        def __init__(self, agents=None, tasks=None, **kwargs):
            pass

        def kickoff(self):
            calls["n"] += 1
            step = steps.pop(0)
            if isinstance(step, Exception):
                raise step
            return _FakeResult(step)

    monkeypatch.setattr(llm, "Crew", _FakeCrew)
    monkeypatch.setattr(llm, "Task", lambda **kwargs: object())
    return calls


def test_run_stage_retries_transient_error(monkeypatch, _no_backoff_sleep):
    calls = _patch_crew(monkeypatch, [
        ConnectionError("connection reset by peer"),
        '{"score": 90}',
    ])
    out = run_stage(agent=None, description="d", expected_output="e",
                    schema=_Out, stage_name="s")
    assert out.score == 90
    assert calls["n"] == 2


def test_run_stage_auth_error_aborts_fast(monkeypatch, _no_backoff_sleep):
    calls = _patch_crew(monkeypatch, [
        RuntimeError("Authentication failed: 401 Unauthorized, invalid api key"),
        '{"score": 90}',  # must never be consumed
    ])
    with pytest.raises(RuntimeError, match="401"):
        run_stage(agent=None, description="d", expected_output="e",
                  schema=_Out, stage_name="s")
    assert calls["n"] == 1
