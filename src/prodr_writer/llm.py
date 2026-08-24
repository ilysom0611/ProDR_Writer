"""LLM layer: CrewAI agent/LLM factory, JSON extraction, validated stage calls."""
from __future__ import annotations

import json
import re
import time
from typing import Dict, Optional, Type, TypeVar

from crewai import Agent, Crew, Task
from crewai.llm import LLM
from pydantic import BaseModel, ValidationError
from rich.console import Console

from .config import AppConfig, _normalized_model

console = Console()

T = TypeVar("T", bound=BaseModel)


def build_llm(cfg: AppConfig) -> LLM:
    """Construct a CrewAI LLM bound to the user's OpenAI-compatible endpoint."""
    return LLM(
        model=_normalized_model(cfg.llm.model),
        base_url=cfg.llm.base_url,
        api_key=cfg.llm.api_key,
        temperature=cfg.llm.temperature,
        max_tokens=cfg.llm.max_tokens,
        timeout=cfg.llm.request_timeout,
    )


def make_agent(llm: LLM, role: str, goal: str, backstory: str) -> Agent:
    return Agent(role=role, goal=goal, backstory=backstory, llm=llm, verbose=False)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Dict:
    """Best-effort extraction of a JSON object from an LLM response.

    Handles <think> blocks, markdown fences, and leading/trailing prose.
    Raises ValueError when no JSON object can be recovered.
    """
    text = _THINK_RE.sub("", text or "").strip()

    candidates: list[str] = []
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    candidates.append(text)

    for candidate in candidates:
        obj = _balanced_json(candidate)
        if obj is not None:
            return obj
    raise ValueError("No JSON object found in LLM output")


def _balanced_json(text: str) -> Optional[Dict]:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break  # try next '{'
            # continue scanning
        start = text.find("{", start + 1)
    return None


# ---------------------------------------------------------------------------
# Validated stage call
# ---------------------------------------------------------------------------

_AUTH_MARKERS = ("auth", "401", "api key", "api_key", "unauthorized")


def _is_auth_error(exc: Exception) -> bool:
    """Detect non-transient credential failures so we don't burn retries on them.

    litellm raises provider-specific exception types, so besides checking for
    AuthenticationError (when importable) we also match the usual markers in
    the error text (e.g. '401', 'invalid api key').
    """
    try:
        import litellm

        if isinstance(exc, litellm.AuthenticationError):
            return True
    except Exception:  # noqa: BLE001 — litellm may not expose the type
        pass
    message = str(exc).lower()
    return any(marker in message for marker in _AUTH_MARKERS)


def run_stage(
    agent: Agent,
    description: str,
    expected_output: str,
    schema: Type[T],
    stage_name: str,
    max_retries: int = 2,
    notify=None,
) -> T:
    """Run a single-agent Crew and validate its JSON against `schema`.

    On parse/validation failure the validation errors are appended to the
    prompt and the stage is retried, instead of silently defaulting fields.
    Transient API/network errors from kickoff() are also retried with
    exponential backoff; authentication failures re-raise immediately since
    retrying with the same credentials cannot succeed.

    `notify` (optional) receives {"type": "retry", ...} events so web UIs can
    show that a stage is being retried rather than silently hanging.
    """

    def _announce(reason: str) -> None:
        if notify:
            notify({"type": "retry", "stage": stage_name, "reason": reason})

    error_feedback = ""
    for attempt in range(1, max_retries + 2):
        desc = description + error_feedback
        task = Task(description=desc, agent=agent, expected_output=expected_output)
        try:
            result = Crew(agents=[agent], tasks=[task]).kickoff()
        except Exception as exc:  # noqa: BLE001 — litellm raises many types
            if _is_auth_error(exc):
                raise
            console.print(
                f"[yellow]  [{stage_name}] attempt {attempt}: {type(exc).__name__} "
                f"from provider, retrying...[/yellow]"
            )
            _announce(f"{type(exc).__name__} from provider — retrying")
            if attempt > max_retries:
                raise RuntimeError(
                    f"Stage '{stage_name}' failed after {max_retries + 1} attempts "
                    f"due to provider errors: {type(exc).__name__}: {exc}"
                ) from exc
            time.sleep(min(2 ** attempt, 30))  # exponential backoff, capped
            continue
        raw = getattr(result, "raw", str(result))
        try:
            data = extract_json(raw)
            return schema.model_validate(data)
        except (ValueError, ValidationError) as exc:
            console.print(
                f"[yellow]  [{stage_name}] attempt {attempt}: invalid output "
                f"({type(exc).__name__}), retrying with feedback...[/yellow]"
            )
            _announce("invalid model output — retrying with feedback")
            error_feedback = (
                "\n\n### IMPORTANT: your previous output was invalid.\n"
                f"Error:\n{str(exc)[:1500]}\n"
                "Return ONLY corrected, complete JSON matching the required schema."
            )
    raise RuntimeError(
        f"Stage '{stage_name}' failed to produce valid JSON after {max_retries + 1} attempts"
    )
