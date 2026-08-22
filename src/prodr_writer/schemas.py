"""Pydantic data models for every pipeline stage.

Every agent output is validated against these models; a stage that fails
validation is retried with the validation errors fed back to the LLM.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="allow")  # keep LLM-added fields instead of dropping them


class ProjectInput(_Strict):
    """User-supplied project parameters (CLI / interactive)."""

    project_name: str
    client_name: str = ""
    vendor_name: str = ""
    industry: str = "general"
    overall_rto: str = ""
    overall_rpo: str = ""
    budget: str = ""
    language: str = "en"
    profile: str = "generic-enterprise"


class BusinessSystem(_Strict):
    name: str
    tier: str = Field(pattern=r"^P[0-3]$")
    rto: str = ""
    rpo: str = ""
    criticality: str = ""
    max_downtime_impact: str = ""


class BIAReport(_Strict):
    business_systems: List[BusinessSystem]
    overall_rto: str = ""
    overall_rpo: str = ""
    recovery_priority: List[str] = []
    summary: str = ""


class GapItem(_Strict):
    area: str
    current_capability: str = ""
    required_capability: str = ""
    gap: str = ""
    risk_level: str = ""


class CurrentStateReport(_Strict):
    current_infrastructure: Dict[str, str] = {}
    gap_analysis: List[GapItem] = []
    summary: str = ""


class ProtectionTier(_Strict):
    tier: str = Field(pattern=r"^P[0-3]$")
    protection_mode: str = ""
    replication: str = ""
    failover: str = ""
    rationale: str = ""


class DRStrategy(_Strict):
    overall_strategy: str = ""
    protection_tiers: List[ProtectionTier] = []


class SiteInfo(_Strict):
    name: str = ""
    location: str = ""


class TierDefinition(_Strict):
    systems: List[str] = []
    recovery_strategy: str = ""
    rpo: str = ""
    rto: str = ""
    replication: str = ""
    failover: str = ""
    description: str = ""


class ReviewIssue(_Strict):
    severity: str = "major"  # blocker | major | minor
    description: str = ""
    suggestion: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v):
        """Map Chinese severities emitted by LLMs onto the canonical set."""
        table = {"阻塞": "blocker", "严重": "major", "一般": "minor"}
        return table.get(str(v).strip(), v)


class ReviewResult(_Strict):
    score: int
    can_proceed: bool = False
    dimension_scores: Dict[str, Dict[str, object]] = {}
    issues: List[ReviewIssue] = []
    summary: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _coerce_score(cls, v):
        try:
            return int(float(str(v).strip().replace("%", "")))
        except (TypeError, ValueError):
            raise ValueError(f"score must be a number 0-100, got {v!r}")

    @field_validator("can_proceed", mode="before")
    @classmethod
    def _derive_can_proceed(cls, v, info):
        # Some models omit it or emit a string; derive from score when unusable.
        if isinstance(v, bool):
            return v
        if isinstance(v, str) and v.strip().lower() in ("true", "false"):
            return v.strip().lower() == "true"
        score = info.data.get("score")
        return bool(score is not None and score >= 90)


class OptimizerResult(_Strict):
    optimized_architecture: Dict[str, object]
    changes: List[str] = []
    reason: str = ""


class DRArchitecture(_Strict):
    deployment_mode: str = ""
    primary_site: SiteInfo = SiteInfo()
    dr_site: SiteInfo = SiteInfo()
    tier_definitions: Dict[str, TierDefinition] = {}
    network_architecture: str = ""
    storage_architecture: str = ""
    compute_architecture: str = ""
    failover_automation: str = ""
    # Profile-specific blocks (e.g. datacenter_thailand, pdpa_compliance) are
    # kept verbatim under `profile_data` via extra="allow".
    vendor_recommendations: Dict[str, str] = {}


class Finding(_Strict):
    rule_id: str
    severity: str = "warning"  # fatal | warning | info
    message: str = ""


class ValidationReport(_Strict):
    findings: List[Finding] = []
    passed: bool = True


STAGE_SCHEMAS = {
    "bia": BIAReport,
    "current_state": CurrentStateReport,
    "strategy": DRStrategy,
    "architecture": DRArchitecture,
    "review": ReviewResult,
    "optimizer": OptimizerResult,
}
