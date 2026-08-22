"""Generation pipeline: staged agent calls with persisted artifacts.

Each stage writes its validated output to <run_dir>/<stage>.json, so a run is
inspectable and resumable. The critic/optimizer loop feeds the optimized
architecture back into the next review round (the original v1 never did).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from rich.console import Console

from . import prompts
from .config import AppConfig
from .llm import build_llm, make_agent, run_stage
from .profiles import load_profile
from .rules import validate_run
from .schemas import (
    BIAReport,
    CurrentStateReport,
    DRArchitecture,
    DRStrategy,
    OptimizerResult,
    ProjectInput,
    ReviewResult,
)

NotifyFn = Optional[Callable[[dict], None]]

console = Console()

MAX_REVIEW_ROUNDS = 3
PASS_SCORE = 90


def slugify(name: str) -> str:
    """Filesystem-safe slug for project names on Windows and POSIX."""
    slug = re.sub(r'[\\/:*?"<>|]+', "-", name)
    slug = re.sub(r"\s+", "-", slug)[:80].strip(". ")  # re-strip after truncation
    return slug or "project"


class Pipeline:
    def __init__(self, cfg: AppConfig, notify: NotifyFn = None):
        self.cfg = cfg
        self.notify = notify or (lambda event: None)
        self.profile = load_profile(cfg.profile)
        self.llm = build_llm(cfg)
        self.analyst = make_agent(
            self.llm,
            role="Business Impact Analyst",
            goal="Produce accurate BIA and current-state assessments as structured JSON",
            backstory="A senior business continuity consultant specialising in impact analysis.",
        )
        self.architect = make_agent(
            self.llm,
            role="DR Solution Architect",
            goal="Design compliant, cost-effective disaster recovery strategies and architectures",
            backstory="A principal architect with 15 years of enterprise DR and replication design experience.",
        )
        self.critic = make_agent(
            self.llm,
            role="Independent Architecture Reviewer",
            goal="Score architecture proposals strictly against the review dimensions",
            backstory="A demanding QA reviewer who never passes a non-compliant design.",
        )
        self.optimizer = make_agent(
            self.llm,
            role="Architecture Optimization Specialist",
            goal="Fix every review issue without regressing correct content",
            backstory="An expert who turns review findings into concrete architectural corrections.",
        )

    # ------------------------------------------------------------------
    def run(self, inputs: ProjectInput) -> Tuple[Path, dict]:
        """Execute all stages; returns (run_dir, summary). Raises on failure."""
        run_dir = Path(self.cfg.output_dir) / f"{slugify(inputs.project_name)}_{time.strftime('%Y%m%d_%H%M%S')}"
        run_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[bold]Run directory:[/bold] {run_dir}")

        bia = self._stage(run_dir, "bia", "BIA analysis", 1,
                          lambda: self._bia(inputs))
        state = self._stage(run_dir, "current_state", "current state assessment", 2,
                            lambda: self._current_state(inputs))
        strategy = self._stage(run_dir, "strategy", "DR strategy", 3,
                               lambda: self._strategy(inputs, bia, state))
        architecture, review, rounds = self._review_loop(inputs, bia, state, strategy, run_dir)
        validation = validate_run(inputs, bia, strategy, architecture, self.profile)

        artifacts = {
            "input": inputs.model_dump(),
            "profile": self.cfg.profile,
            "language": self.cfg.language,
            "bia": bia.model_dump(),
            "current_state": state.model_dump(),
            "strategy": strategy.model_dump(),
            "architecture": architecture.model_dump(),
            "review": review.model_dump() if review else None,
            "review_rounds": rounds,
            "validation": validation.model_dump(),
            "status": "success",
        }
        summary_path = run_dir / "run.json"
        summary_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")

        fatal = [f for f in validation.findings if f.severity == "fatal"]
        if fatal:
            console.print("[red]Validation reported fatal findings — see the Validation chapter "
                          "of the document and fix before submission.[/red]")

        docx_path = self._build_document(run_dir, artifacts)
        return run_dir, {
            "docx": str(docx_path),
            "review_rounds": rounds,
            "score": review.score if review else None,
            "fatal_findings": len(fatal),
            "warnings": sum(1 for f in validation.findings if f.severity == "warning"),
        }

    # ------------------------------------------------------------------
    def _stage(self, run_dir: Path, stage: str, label: str, number: int, fn):
        console.print(f"[bold cyan]Step {number}/6: {label}...[/bold cyan]")
        self.notify({"type": "stage", "stage": stage, "number": number, "label": label, "status": "running"})
        result = fn()
        path = run_dir / f"{stage}.json"
        path.write_text(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.notify({"type": "stage", "stage": stage, "number": number, "label": label, "status": "done"})
        return result

    def _bia(self, inputs: ProjectInput) -> BIAReport:
        return run_stage(self.analyst, prompts.bia_prompt(inputs.model_dump(), self.cfg.language),
                         "JSON BIA report", BIAReport, "bia")

    def _current_state(self, inputs: ProjectInput) -> CurrentStateReport:
        return run_stage(self.analyst, prompts.current_state_prompt(inputs.model_dump(), self.cfg.language),
                         "JSON current state assessment", CurrentStateReport, "current_state")

    def _strategy(self, inputs: ProjectInput, bia: BIAReport, state: CurrentStateReport) -> DRStrategy:
        return run_stage(self.architect, prompts.strategy_prompt(inputs.model_dump(), bia, state, self.cfg.language),
                         "JSON DR strategy", DRStrategy, "strategy")

    def _review_loop(
        self, inputs: ProjectInput, bia: BIAReport, state: CurrentStateReport,
        strategy: DRStrategy, run_dir: Path,
    ) -> Tuple[DRArchitecture, Optional[ReviewResult], int]:
        console.print(f"[bold cyan]Step 4/6: architecture & review loop...[/bold cyan]")
        arch = run_stage(
            self.architect,
            prompts.architecture_prompt(inputs.model_dump(), bia, state, strategy, self.profile, self.cfg.language),
            "JSON DR architecture", DRArchitecture, "architecture",
        )
        review: Optional[ReviewResult] = None
        rounds = 0
        for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
            rounds = round_num
            console.print(f"  [dim]--- Review round {round_num}/{MAX_REVIEW_ROUNDS} ---[/dim]")
            review = run_stage(
                self.critic,
                prompts.critic_prompt(inputs.model_dump(), bia, strategy, arch, self.profile, self.cfg.language),
                "JSON review result", ReviewResult, f"review-{round_num}",
            )
            console.print(f"  → score [bold]{review.score}[/bold]/100 "
                          + ("[green]passed[/green]" if review.can_proceed else "[yellow]needs optimization[/yellow]"))
            self.notify({"type": "review", "round": round_num, "score": review.score,
                         "passed": review.can_proceed})
            if review.can_proceed or round_num >= MAX_REVIEW_ROUNDS:
                break
            self.notify({"type": "stage", "stage": "optimizer", "number": 4,
                         "label": f"optimizing architecture (round {round_num})", "status": "running"})
            optimized = run_stage(
                self.optimizer,
                prompts.optimizer_prompt(arch, review, self.profile, self.cfg.language),
                "JSON optimization result", OptimizerResult, f"optimize-{round_num}",
            )
            arch = DRArchitecture.model_validate(optimized.optimized_architecture)  # fed into next round
            self.notify({"type": "stage", "stage": "optimizer", "number": 4,
                         "label": f"optimizing architecture (round {round_num})", "status": "done",
                         "changes": optimized.changes})
        (run_dir / "architecture.json").write_text(json.dumps(arch.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        if review:
            (run_dir / "review.json").write_text(json.dumps(review.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return arch, review, rounds

    def _build_document(self, run_dir: Path, artifacts: dict) -> Path:
        from .docgen.builder import build_document  # deferred: heavy imports

        console.print(f"[bold cyan]Step 5/6: compliance rule check done; Step 6/6: building document...[/bold cyan]")
        self.notify({"type": "stage", "stage": "document", "number": 6, "label": "building document", "status": "running"})
        docx_path = build_document(artifacts, run_dir)
        self.notify({"type": "stage", "stage": "document", "number": 6, "label": "building document",
                     "status": "done", "docx": str(docx_path)})
        console.print(f"[green]Document written:[/green] {docx_path}")
        return docx_path


# ---------------------------------------------------------------------------
# Demo mode — full document from bundled sample data, no LLM required
# ---------------------------------------------------------------------------

def run_demo(cfg: AppConfig, notify: NotifyFn = None) -> Tuple[Path, dict]:
    """Build a complete proposal from the bundled sample run (no API calls).

    Useful for trying the tool and for smoke-testing installs.
    """
    import json as _json

    from .schemas import ProjectInput

    sample_path = Path(__file__).parent / "resources" / "sample_run.json"
    data = _json.loads(sample_path.read_text(encoding="utf-8"))
    inputs = ProjectInput.model_validate(data["input"])
    inputs = inputs.model_copy(update={"language": cfg.language, "profile": cfg.profile})
    data["input"] = inputs.model_dump()
    data["language"] = cfg.language
    data["profile"] = cfg.profile

    profile = load_profile(cfg.profile)
    bia = BIAReport.model_validate(data["bia"])
    strategy = DRStrategy.model_validate(data["strategy"])
    arch = DRArchitecture.model_validate(data["architecture"])

    run_dir = Path(cfg.output_dir) / f"demo_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_run(inputs, bia, strategy, arch, profile)
    data["validation"] = validation.model_dump()

    from .docgen.builder import build_document

    if notify:
        notify({"type": "stage", "stage": "document", "number": 6, "label": "building demo document", "status": "running"})
    docx_path = build_document(data, run_dir)
    if notify:
        notify({"type": "stage", "stage": "document", "number": 6, "label": "building demo document",
                "status": "done", "docx": str(docx_path)})
    (run_dir / "run.json").write_text(_json.dumps({**data, "status": "demo"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir, {"docx": str(docx_path), "review_rounds": data.get("review_rounds"),
                     "score": (data.get("review") or {}).get("score"),
                     "fatal_findings": sum(1 for f in validation.findings if f.severity == "fatal"),
                     "warnings": sum(1 for f in validation.findings if f.severity == "warning")}
