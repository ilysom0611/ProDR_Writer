"""Rule engine: consistency checks over validated stage models.

Findings are surfaced in the console and written into the document's
Validation chapter, so bidders see real review results instead of hardcoded
"passed" claims.
"""
from __future__ import annotations

import re
from typing import List, Optional

from .profiles import localized
from .schemas import BIAReport, DRArchitecture, DRStrategy, Finding, ProjectInput, ValidationReport

_DURATION_RE = re.compile(r"[<>≤>=~\s]*(\d+(?:\.\d+)?)\s*(min(?:ute)?s?|分钟|hours?|小时|h|d|天)?", re.IGNORECASE)
_UNIT_MINUTES = {"min": 1, "mins": 1, "minute": 1, "minutes": 1, "分钟": 1,
                 "h": 60, "hour": 60, "hours": 60, "小时": 60,
                 "d": 1440, "天": 1440}


def parse_minutes(value: str) -> Optional[float]:
    """Parse '≤4h', '<30min', '0', '24 hours' → minutes. None when unparseable."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("n/a", "na", "-"):
        return None
    match = _DURATION_RE.search(text)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "min").lower()
    return number * _UNIT_MINUTES.get(unit, 1)


def check_rto_rpo(bia: BIAReport, arch: DRArchitecture, constraints: dict) -> List[Finding]:
    findings = []
    for tier_key, tier in arch.tier_definitions.items():
        rto = parse_minutes(tier.rto)
        rpo = parse_minutes(tier.rpo)
        limit = constraints.get(tier_key, {})
        rto_max = limit.get("rto_max_minutes")
        rpo_max = limit.get("rpo_max_minutes")
        if rto is None:
            findings.append(Finding(rule_id="RTO-PARSE", severity="warning",
                                    message=f"Tier {tier_key}: RTO '{tier.rto}' is not machine-readable."))
        elif rto_max is not None and rto > rto_max:
            findings.append(Finding(rule_id="RTO-LIMIT", severity="fatal",
                                    message=f"Tier {tier_key} RTO {tier.rto} ({rto:.0f} min) exceeds the "
                                            f"profile limit of {rto_max} min."))
        if rpo is None:
            findings.append(Finding(rule_id="RPO-PARSE", severity="warning",
                                    message=f"Tier {tier_key}: RPO '{tier.rpo}' is not machine-readable."))
        elif rpo_max is not None and rpo > rpo_max:
            findings.append(Finding(rule_id="RPO-LIMIT", severity="fatal",
                                    message=f"Tier {tier_key} RPO {tier.rpo} ({rpo:.0f} min) exceeds the "
                                            f"profile limit of {rpo_max} min."))
    return findings


def check_coverage(bia: BIAReport, arch: DRArchitecture) -> List[Finding]:
    findings = []
    assigned = set()
    for tier in arch.tier_definitions.values():
        assigned.update(tier.systems)
    for system in bia.business_systems:
        if system.name not in assigned:
            findings.append(Finding(rule_id="COVERAGE", severity="major",
                                    message=f"Business system '{system.name}' (tier {system.tier}) is not "
                                            f"assigned to any tier in the architecture."))
    return findings


def check_p0_strategy(arch: DRArchitecture, strategy: DRStrategy) -> List[Finding]:
    findings = []
    forbidden = ("backup", "restore", "备份", "恢复")
    p0 = arch.tier_definitions.get("P0")
    if p0 and any(word in (p0.recovery_strategy or "").lower() for word in forbidden):
        findings.append(Finding(rule_id="P0-STRATEGY", severity="fatal",
                                message="P0 tier uses backup/restore as its recovery strategy; "
                                        "synchronous replication is required (RPO=0)."))
    for tier in strategy.protection_tiers:
        if tier.tier == "P0" and any(word in tier.protection_mode.lower() for word in forbidden):
            findings.append(Finding(rule_id="P0-STRATEGY", severity="fatal",
                                    message=f"P0 protection mode '{tier.protection_mode}' violates the "
                                            f"no-backup-as-primary constraint."))
    return findings


def check_completeness(arch: DRArchitecture) -> List[Finding]:
    findings = []
    required_sections = {
        "network_architecture": arch.network_architecture,
        "storage_architecture": arch.storage_architecture,
        "compute_architecture": arch.compute_architecture,
        "failover_automation": arch.failover_automation,
    }
    for name, value in required_sections.items():
        if not (value or "").strip():
            findings.append(Finding(rule_id="COMPLETENESS", severity="warning",
                                    message=f"Architecture section '{name}' is empty."))
    return findings


def check_budget(inputs: ProjectInput) -> List[Finding]:
    if not (inputs.budget or "").strip():
        return [Finding(rule_id="BUDGET", severity="warning",
                        message="No budget range was provided; cost alignment cannot be verified.")]
    return []


def validate_run(inputs: ProjectInput, bia: BIAReport, strategy: DRStrategy,
                 arch: DRArchitecture, profile: dict) -> ValidationReport:
    constraints = profile.get("constraints", {})
    findings: List[Finding] = []
    findings += check_rto_rpo(bia, arch, constraints)
    findings += check_coverage(bia, arch)
    findings += check_p0_strategy(arch, strategy)
    findings += check_completeness(arch)
    findings += check_budget(inputs)
    passed = not any(f.severity == "fatal" for f in findings)
    return ValidationReport(findings=findings, passed=passed)
