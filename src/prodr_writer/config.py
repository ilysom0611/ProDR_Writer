"""Application configuration: LLM endpoint, output language, compliance profile.

Precedence: CLI arguments > environment variables > config file (~/.prodr/config.yaml).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from rich.console import Console

console = Console()

CONFIG_DIR = Path.home() / ".prodr"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

ENV_API_KEY = "PRODR_API_KEY"
ENV_BASE_URL = "PRODR_BASE_URL"
ENV_MODEL = "PRODR_MODEL"

# LLM fields that must be numeric; used to coerce file values and overrides.
_NUMERIC_LLM_FIELDS = {"temperature": float, "max_tokens": int, "request_timeout": int}


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    request_timeout: int = 300

    def is_complete(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    language: str = "en"  # en | zh
    profile: str = "generic-enterprise"
    output_dir: str = "outputs"

    @classmethod
    def load(cls, overrides: Optional[Dict[str, Any]] = None) -> "AppConfig":
        """Load config with precedence CLI > env > file > defaults."""
        file_cfg: Dict[str, Any] = {}
        if CONFIG_FILE.exists():
            try:
                file_cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                console.print(f"[yellow]Warning: ignoring malformed config file: {exc}[/yellow]")

        llm_file = file_cfg.get("llm", {}) or {}

        def _coerce(key: str, default: Any, cast: type) -> Any:
            """Cast an optional config value; warn and fall back on bad types."""
            raw = llm_file.get(key)
            if raw is None:
                return default
            try:
                return cast(raw)
            except (TypeError, ValueError):
                console.print(f"[yellow]Warning: invalid llm.{key} value {raw!r}; "
                              f"using default {default}[/yellow]")
                return default

        llm = LLMConfig(
            base_url=os.environ.get(ENV_BASE_URL, str(llm_file.get("base_url", "") or "")),
            api_key=os.environ.get(ENV_API_KEY, str(llm_file.get("api_key", "") or "")),
            model=os.environ.get(ENV_MODEL, str(llm_file.get("model", "") or "")),
            temperature=_coerce("temperature", 0.3, float),
            max_tokens=_coerce("max_tokens", 8192, int),
            request_timeout=_coerce("request_timeout", 300, int),
        )
        cfg = cls(
            llm=llm,
            language=str(file_cfg.get("language", "en")),
            profile=str(file_cfg.get("profile", "generic-enterprise")),
            output_dir=str(file_cfg.get("output_dir", "outputs")),
        )

        llm_fields = {f.name for f in fields(LLMConfig)}
        app_fields = {f.name for f in fields(AppConfig) if f.name != "llm"}
        for key, value in (overrides or {}).items():
            if value is None:
                continue
            if key.startswith("llm_"):
                field_name = key[4:]
                if field_name in llm_fields:
                    cast = _NUMERIC_LLM_FIELDS.get(field_name)
                    try:
                        value = cast(value) if cast else value
                    except (TypeError, ValueError):
                        console.print(f"[yellow]Warning: invalid value {value!r} for "
                                      f"'{key}'; keeping current setting[/yellow]")
                        continue
                    setattr(cfg.llm, field_name, value)
                else:
                    console.print(f"[yellow]Warning: ignoring unknown LLM override '{key}'[/yellow]")
            elif key in app_fields:
                setattr(cfg, key, value)
            else:
                console.print(f"[yellow]Warning: ignoring unknown config override '{key}'[/yellow]")
        return cfg

    def save(self) -> Path:
        """Persist to ~/.prodr/config.yaml with restrictive permissions."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "llm": {
                "base_url": self.llm.base_url,
                "api_key": self.llm.api_key,
                "model": self.llm.model,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
                "request_timeout": self.llm.request_timeout,
            },
            "language": self.language,
            "profile": self.profile,
            "output_dir": self.output_dir,
        }
        CONFIG_FILE.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass  # Windows may not support POSIX perms
        return CONFIG_FILE

    def missing(self) -> list[str]:
        items = []
        if not self.llm.base_url:
            items.append("base_url")
        if not self.llm.api_key:
            items.append("api_key")
        if not self.llm.model:
            items.append("model")
        return items


def test_connection(cfg: AppConfig) -> tuple[bool, str]:
    """Minimal chat round-trip against the configured OpenAI-compatible endpoint."""
    missing = [name for name, value in (
        ("base_url", cfg.llm.base_url), ("api_key", cfg.llm.api_key), ("model", cfg.llm.model),
    ) if not value]
    if missing:
        return False, f"Incomplete LLM configuration, missing: {', '.join(missing)}"
    try:
        import litellm

        response = litellm.completion(
            model=_normalized_model(cfg.llm.model),
            api_base=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=8,
            timeout=30,
        )
        text = (response.choices[0].message.content or "").strip()
        return True, f"Model responded: {text[:80]}"
    except Exception as exc:  # noqa: BLE001 - report any provider error verbatim
        return False, f"{type(exc).__name__}: {exc}"


def _normalized_model(model: str) -> str:
    """LiteLLM needs an explicit provider prefix for custom endpoints.

    A bare name like 'MiniMax-M2.5' is ambiguous; route it through the
    OpenAI-compatible provider which honors base_url.
    """
    if "/" in model:
        return model
    return f"openai/{model}"
