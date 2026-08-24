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

# Range expression: "<lo>-<hi> <unit>" / "<lo> to <hi> <unit>". The upper bound
# wins — it is the binding promise to the customer ("1-2 hours" → 2h).
_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*"
    r"(?:(?:full|half)\s*)?(min(?:ute)?s?|分钟|hours?|小时|h|days?|d|天)?",
    re.IGNORECASE,
)
# One number+unit pair; compounds like "1h30m" / "2 days 4 hours" are summed.
_PAIR_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:(?:full|half)\s*)?(min(?:ute)?s?|分钟|hours?|小时|h|days?|d|天|m)",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
_UNIT_MINUTES = {"min": 1, "mins": 1, "minute": 1, "minutes": 1, "分钟": 1, "m": 1,
                 "h": 60, "hour": 60, "hours": 60, "小时": 60,
                 "d": 1440, "day": 1440, "days": 1440, "天": 1440}


def _unit_minutes(unit: str) -> float:
    text = unit.lower().strip()
    # '2 full hours' / '1 full day': the qualifier does not change the unit.
    text = re.sub(r"^(?:full|half)\s+", "", text)
    return _UNIT_MINUTES.get(text, 0.0)


def parse_minutes(value: str) -> Optional[float]:
    """Parse a human duration expression into minutes; None when unparseable.

    Handles '≤4h', '<30min', '>30min', '>=2 hours', '~1 hour',
    '24 hours', '1 full day', 'half an hour', compounds like '1h30m'
    and '2 days 4 hours', and ranges like '1-2 hours' (upper bound taken).

    A bare number WITHOUT a unit returns None instead of guessing minutes:
    '3 business days' must never silently become 3 minutes — that would hide
    real RTO/RPO violations from the Validation chapter.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("n/a", "na", "-"):
        return None
    # Comparison prefixes do not change the value ('>30min' means 30 min or worse).
    text = re.sub(r"^[><≥≤~=]+\s*", "", text).strip()
    lowered = text.lower()
    if lowered in ("half an hour", "half hour"):
        return 30.0
    if _BARE_NUMBER_RE.match(text):
        # Unit-less zero is unambiguous; any other bare number is not.
        return 0.0 if float(text) == 0 else None
    range_match = _RANGE_RE.search(text)
    if range_match and range_match.group(3):
        return float(range_match.group(2)) * _unit_minutes(range_match.group(3))
    pairs = list(_PAIR_RE.finditer(text))
    if pairs:
        return sum(float(num) * _unit_minutes(unit)
                   for num, unit in ((m.group(1), m.group(2)) for m in pairs))
    return None


def compute_weighted_score(dimension_scores: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted mean of dimension scores, scaled to 100. Dimensions absent from weights are ignored; returns 0.0 if nothing overlaps."""
    total_weight = 0.0
    weighted_sum = 0.0
    for key, score in (dimension_scores or {}).items():
        weight = (weights or {}).get(key)
        if weight is None:
            continue
        try:
            weighted_sum += float(score) * float(weight)
            total_weight += float(weight)
        except (TypeError, ValueError):
            continue
    if total_weight <= 0:
        return 0.0
    return weighted_sum / total_weight


def check_rto_rpo(bia: BIAReport, arch: DRArchitecture, constraints: dict) -> List[Finding]:
    """Check tier capability against profile limits AND the BIA's stated targets."""
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

    # Compare each BIA system's required targets against what its assigned
    # tier in the architecture can actually deliver.
    for system in bia.business_systems:
        tier = arch.tier_definitions.get(system.tier)
        if tier is None:
            continue  # missing assignment is reported by check_coverage
        need_rto = parse_minutes(system.rto)
        need_rpo = parse_minutes(system.rpo)
        can_rto = parse_minutes(tier.rto)
        can_rpo = parse_minutes(tier.rpo)
        if need_rto is None and str(system.rto or "").strip():
            findings.append(Finding(rule_id="RTO-PARSE", severity="warning",
                                    message=f"System '{system.name}': BIA RTO target "
                                            f"'{system.rto}' is not machine-readable; skipped."))
        elif need_rto is not None and can_rto is None:
            findings.append(Finding(rule_id="RTO-PARSE", severity="warning",
                                    message=f"System '{system.name}' (tier {system.tier}): architecture "
                                            f"RTO '{tier.rto}' is not machine-readable; cannot verify the "
                                            f"BIA target of {need_rto:.0f} min."))
        elif need_rto is not None and can_rto is not None and can_rto > need_rto:
            findings.append(Finding(rule_id="RTO-LIMIT", severity="fatal",
                                    message=f"System '{system.name}' needs RTO {system.rto} "
                                            f"({need_rto:.0f} min) but tier {system.tier} only delivers "
                                            f"{tier.rto} ({can_rto:.0f} min)."))
        if need_rpo is None and str(system.rpo or "").strip():
            findings.append(Finding(rule_id="RPO-PARSE", severity="warning",
                                    message=f"System '{system.name}': BIA RPO target "
                                            f"'{system.rpo}' is not machine-readable; skipped."))
        elif need_rpo is not None and can_rpo is None:
            findings.append(Finding(rule_id="RPO-PARSE", severity="warning",
                                    message=f"System '{system.name}' (tier {system.tier}): architecture "
                                            f"RPO '{tier.rpo}' is not machine-readable; cannot verify the "
                                            f"BIA target of {need_rpo:.0f} min."))
        elif need_rpo is not None and can_rpo is not None and can_rpo > need_rpo:
            findings.append(Finding(rule_id="RPO-LIMIT", severity="fatal",
                                    message=f"System '{system.name}' needs RPO {system.rpo} "
                                            f"({need_rpo:.0f} min) but tier {system.tier} only delivers "
                                            f"{tier.rpo} ({can_rpo:.0f} min)."))
    return findings


_PUNCT_RE = re.compile(r"[^\w一-鿿]+", re.UNICODE)


def _normalize_name(name: str) -> str:
    """Normalize a system name for fuzzy cross-document matching.

    Casefold, strip punctuation and collapse whitespace so 'Core-Banking '
    matches 'core banking'. Chinese names keep their characters (\\u4e00-\\u9fff).
    """
    return _PUNCT_RE.sub(" ", str(name).casefold()).strip()


def _names_match(candidate: str, assigned_names: set[str]) -> bool:
    """True when a normalized name matches, or one normalized name contains the other.

    Heuristic: LLMs routinely shorten names ('CRM System' → 'CRM'); containment
    after normalization treats those as covered. Remaining limitation: generic
    single-word names ('System') could over-match longer names.
    """
    norm = _normalize_name(candidate)
    if not norm:
        return True  # nothing to match on; do not flag empty names
    for other in assigned_names:
        if norm == other or norm in other or other in norm:
            return True
    return False


def check_coverage(bia: BIAReport, arch: DRArchitecture) -> List[Finding]:
    findings = []
    assigned_raw = []
    for tier_key, tier in arch.tier_definitions.items():
        assigned_raw.extend(tier.systems)
    # Normalize once; both sides come from independent LLM outputs whose
    # exact strings rarely agree.
    assigned = {_normalize_name(name) for name in assigned_raw}
    for system in bia.business_systems:
        if not _names_match(system.name, assigned):
            findings.append(Finding(rule_id="COVERAGE", severity="major",
                                    message=f"Business system '{system.name}' (tier {system.tier}) is not "
                                            f"assigned to any tier in the architecture."))
    return findings


# Forbidden backup/restore-family terms with a small synonym set each,
# matched on word boundaries so substrings inside unrelated words no longer
# trigger the check.
_FORBIDDEN_P0_TERMS = {
    "backup": ["backups", "back-up", "back-ups"],
    "restore": ["restoring", "restored", "restoration"],
    "备份": [],
    "恢复": [],
}


def _forbidden_p0_pattern() -> re.Pattern:
    """Word-boundary regex for ASCII terms; CJK terms have no word boundaries."""
    parts = []
    for term, synonyms in _FORBIDDEN_P0_TERMS.items():
        if term.isascii():
            parts.append(rf"\b(?:{term}|{'|'.join(synonyms)})\b" if synonyms else rf"\b{term}\b")
        else:
            parts.append(re.escape(term))
    return re.compile("|".join(parts), re.IGNORECASE)


_FORBIDDEN_P0_RE = _forbidden_p0_pattern()


# Negation cues that flip a hit into a non-finding ("no backup window",
# "without restore points", "无需备份"). Checked in the ~20 chars before a match.
_NEGATION_RE = re.compile(r"(?:\b(?:no|not|without|non|avoid\w*)\b|[无非避免不需禁])\s*$", re.IGNORECASE)


def check_p0_strategy(arch: DRArchitecture, strategy: DRStrategy) -> List[Finding]:
    """Reject backup/restore as the P0 primary protection strategy.

    Lexical, boundary-aware matching only, with a narrow negation window
    ("no backup window needed" is not a violation). Semantic paraphrases that
    avoid the backup/restore vocabulary entirely cannot be caught here.
    """
    findings = []

    def forbidden_hit(text: str) -> bool:
        for m in _FORBIDDEN_P0_RE.finditer(text or ""):
            prefix = text[max(0, m.start() - 20):m.start()]
            if not _NEGATION_RE.search(prefix):
                return True
        return False

    p0 = arch.tier_definitions.get("P0")
    if p0 and forbidden_hit(p0.recovery_strategy):
        findings.append(Finding(rule_id="P0-STRATEGY", severity="fatal",
                                message="P0 tier uses backup/restore as its recovery strategy; "
                                        "synchronous replication is required (RPO=0)."))
    for tier in strategy.protection_tiers:
        if tier.tier == "P0" and forbidden_hit(tier.protection_mode):
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
