"""Application configuration: LLM endpoint, output language, compliance profile.

Precedence: CLI arguments > environment variables > config file (~/.prodr/config.yaml).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
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
        llm = LLMConfig(
            base_url=os.environ.get(ENV_BASE_URL, llm_file.get("base_url", "")),
            api_key=os.environ.get(ENV_API_KEY, llm_file.get("api_key", "")),
            model=os.environ.get(ENV_MODEL, llm_file.get("model", "")),
            temperature=float(llm_file.get("temperature", 0.3)),
            max_tokens=int(llm_file.get("max_tokens", 8192)),
            request_timeout=int(llm_file.get("request_timeout", 300)),
        )
        cfg = cls(
            llm=llm,
            language=str(file_cfg.get("language", "en")),
            profile=str(file_cfg.get("profile", "generic-enterprise")),
            output_dir=str(file_cfg.get("output_dir", "outputs")),
        )

        for key, value in (overrides or {}).items():
            if value is None:
                continue
            if key.startswith("llm_"):
                setattr(cfg.llm, key[4:], value)
            else:
                setattr(cfg, key, value)
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
    if cfg.llm.missing():
        return False, f"Incomplete LLM configuration, missing: {', '.join(cfg.missing())}"
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
