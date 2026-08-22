"""Compliance profile loading.

Profiles are YAML data files under src/prodr_writer/profiles/ (custom ones may
be placed in ~/.prodr/profiles/). They inject regulatory context into prompts
and drive the rule engine and document compliance chapter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

BUILTIN_DIR = Path(__file__).parent / "profiles"
USER_DIR = Path.home() / ".prodr" / "profiles"


def load_profile(name: str) -> Dict[str, Any]:
    path = _resolve(name)
    if path is None:
        raise FileNotFoundError(
            f"Profile '{name}' not found. Built-in: "
            + ", ".join(p.stem for p in BUILTIN_DIR.glob("*.yaml"))
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Profile file {path} is not a valid profile")
    return data


def _resolve(name: str) -> Optional[Path]:
    for directory in (USER_DIR, BUILTIN_DIR):
        candidate = directory / f"{name}.yaml"
        if candidate.exists():
            return candidate
    return None


def localized(value: Any, language: str) -> str:
    """Return the string for `language` from an {en, zh} mapping or plain str."""
    if isinstance(value, dict):
        return str(value.get(language) or value.get("en") or "")
    return "" if value is None else str(value)


def list_profiles() -> list[str]:
    names = set()
    for directory in (BUILTIN_DIR, USER_DIR):
        if directory.exists():
            names.update(p.stem for p in directory.glob("*.yaml"))
    return sorted(names)
