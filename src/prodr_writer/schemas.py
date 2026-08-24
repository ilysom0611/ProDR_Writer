"""Pydantic data models for every pipeline stage.

Every agent output is validated against these models; a stage that fails
validation is retried with the validation errors fed back to the LLM.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Minimum weighted review score for a stage to pass. Single source of truth:
# prompts.py quotes it in the review task and pipeline.py recomputes with it.
PASS_SCORE_THRESHOLD = 90


class _Strict(BaseModel):
    # extra="ignore": garbage extras from LLM responses must not silently flow
    # into documents. DRArchitecture declares the requested optional blocks
    # explicitly instead of relying on permissive extras.
    model_config = ConfigDict(extra="ignore")


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
    # Per-dimension scores keyed by the profile's review dimension keys,
    # values 0-100. Used by the pipeline to recompute the weighted score
    # (see rules.compute_weighted_score) instead of trusting self-reported totals.
    dimension_scores: Dict[str, float] = {}
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
        return bool(score is not None and score >= PASS_SCORE_THRESHOLD)


class OptimizerResult(_Strict):
    optimized_architecture: Dict[str, object]
    changes: List[str] = []
    reason: str = ""


def _stringify(v):
    """Render structured LLM output (dict/list) as readable text for str fields."""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


class DRArchitecture(_Strict):
    deployment_mode: str = ""
    primary_site: SiteInfo = SiteInfo()
    dr_site: SiteInfo = SiteInfo()
    tier_definitions: Dict[str, TierDefinition] = {}
    network_architecture: str = ""
    storage_architecture: str = ""
    compute_architecture: str = ""
    failover_automation: str = ""
    site_separation: Optional[str] = Field(
        default=None,
        description="Physical separation between primary and DR sites: locations, "
                    "distance, and datacenter tiers.",
    )
    compliance_design: Optional[str] = Field(
        default=None,
        description="How the design satisfies data-localization, cross-border-transfer, "
                    "encryption and retention obligations.",
    )
    regulatory_alignment: Optional[str] = Field(
        default=None,
        description="Evidence that RTO/RPO targets are met plus annual DR testing "
                    "and regulator reporting arrangements.",
    )
    vendor_recommendations: Dict[str, str] = {}

    @field_validator("site_separation", "compliance_design", "regulatory_alignment",
                     mode="before")
    @classmethod
    def _flatten_structured_block(cls, v):
        # The architecture prompt requests these as JSON objects; accept either
        # the object form or plain prose by serializing structures to text.
        if v is None:
            return None
        return _stringify(v)

    @field_validator("tier_definitions", mode="before")
    @classmethod
    def _normalize_tier_keys(cls, v):
        """Normalize LLM-emitted tier keys ('p0', 'Tier 0', ' p1 ') to P0-P3.

        Anything outside P0-P3 raises so the validation-retry loop regenerates
        instead of rules.py silently skipping RTO/RPO checks for unknown keys.
        """
        if not isinstance(v, dict):
            return v
        normalized: Dict[str, object] = {}  # values validated as TierDefinition after this
        for key, value in v.items():
            text = str(key).strip().upper()
            if text.startswith("TIER"):
                text = text[4:].strip()
            if text in {"0", "1", "2", "3"}:
                text = f"P{text}"
            if text not in {"P0", "P1", "P2", "P3"}:
                raise ValueError(
                    f"tier_definitions keys must be P0-P3 (got {key!r}); "
                    "rename the tier to one of P0, P1, P2, P3."
                )
            normalized[text] = value
        return normalized


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
