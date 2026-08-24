"""Resume-cache fingerprinting — changed inputs must never reuse a stale run."""
from dataclasses import dataclass
from pathlib import Path

import json

from prodr_writer.config import AppConfig
from prodr_writer.pipeline import Pipeline
from prodr_writer.schemas import ProjectInput


def _Cfg(output_dir: str, profile: str = "generic-enterprise") -> AppConfig:
    # Real AppConfig: Pipeline.__init__ builds an LLM from it (offline).
    return AppConfig(output_dir=output_dir, profile=profile)


def _inputs(**kw) -> ProjectInput:
    return ProjectInput(project_name="Acme DR", **kw)


def test_same_inputs_resume_same_run(tmp_path: Path):
    pipe = Pipeline(_Cfg(output_dir=str(tmp_path)))
    run1 = pipe._prepare_run_dir(_inputs())
    run2 = pipe._prepare_run_dir(_inputs())
    assert run1 == run2  # identical inputs resume into the same run dir


def test_changed_inputs_start_fresh_run(tmp_path: Path):
    """Regression (H3): editing client/language/etc. used to silently resume
    the old run and regenerate a stale document."""
    pipe = Pipeline(_Cfg(output_dir=str(tmp_path)))
    run1 = pipe._prepare_run_dir(_inputs(client_name="Old Name"))
    (run1 / "bia.json").write_text("{}", encoding="utf-8")  # make it resumable
    run2 = pipe._prepare_run_dir(_inputs(client_name="New Name"))
    assert run1 != run2
    # fingerprint recorded in the new dir matches its own inputs
    fp = json.loads((run2 / ".inputs.json").read_text(encoding="utf-8"))["fingerprint"]
    assert fp == Pipeline._inputs_fingerprint(_inputs(client_name="New Name"),
                                              "generic-enterprise")


def test_profile_change_starts_fresh_run(tmp_path: Path):
    """The configured profile drives prompts/scoring, so switching it must
    never resume an existing run even with identical inputs."""
    pipe = Pipeline(_Cfg(output_dir=str(tmp_path), profile="generic-enterprise"))
    run1 = pipe._prepare_run_dir(_inputs())
    (run1 / "bia.json").write_text("{}", encoding="utf-8")
    run2 = Pipeline(_Cfg(output_dir=str(tmp_path),
                         profile="generic-enterprise"))._prepare_run_dir(_inputs())
    assert run1 == run2  # matching profile still resumes
    run3 = Pipeline(_Cfg(output_dir=str(tmp_path),
                         profile="thailand-oic"))._prepare_run_dir(_inputs())
    assert run1 != run3  # different configured profile must not reuse
