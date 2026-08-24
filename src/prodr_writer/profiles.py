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


def _validate(data: Any, name: str, path: Path) -> None:
    """Validate the profile structure so bad files fail at load time with a
    clear message instead of a KeyError deep inside prompt building mid-run."""
    if not isinstance(data, dict):
        raise ValueError(f"Profile '{name}' ({path}): top level must be a mapping")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError(f"Profile '{name}' ({path}): missing 'name' key")

    dimensions = data.get("review_dimensions")
    if not isinstance(dimensions, list):
        raise ValueError(f"Profile '{name}': 'review_dimensions' must be a list")
    total_weight = 0.0
    for i, dim in enumerate(dimensions):
        label = f"review_dimensions[{i}]"
        if not isinstance(dim, dict):
            raise ValueError(f"Profile '{name}': {label} must be a mapping")
        key = dim.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"Profile '{name}': {label}.key must be a non-empty string")
        weight = dim.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise ValueError(f"Profile '{name}': {label}.weight must be a number "
                             f"(got {weight!r})")
        total_weight += float(weight)
    if dimensions and abs(total_weight - 100.0) > 1.0:
        raise ValueError(f"Profile '{name}': review dimension weights sum to "
                         f"{total_weight:g}, expected 100 (±1)")

    constraints = data.get("constraints")
    if not isinstance(constraints, dict):
        raise ValueError(f"Profile '{name}': 'constraints' must be a mapping (may be empty)")


def load_profile(name: str) -> Dict[str, Any]:
    path = _resolve(name)
    if path is None:
        raise FileNotFoundError(
            f"Profile '{name}' not found. Built-in: "
            + ", ".join(p.stem for p in BUILTIN_DIR.glob("*.yaml"))
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate(data, name, path)
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
