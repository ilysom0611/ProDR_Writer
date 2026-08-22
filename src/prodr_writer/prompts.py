"""Prompt builders for each pipeline stage.

Prompts are assembled from the project input, upstream stage JSON, and the
compliance profile. All content values must be written in the configured
output language; JSON keys stay fixed for reliable parsing.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .profiles import localized

_LANGUAGE_INSTRUCTION = {
    "en": "Write ALL text values in professional business English.",
    "zh": "所有文本值请使用专业的简体中文书写。",
}

# Canonical recovery-tier design constraints applied to every profile.
TIER_CONSTRAINTS = (
    "- P0 systems: RPO=0 (synchronous replication), RTO < 30 minutes; "
    "backup/restore is forbidden as the primary protection strategy.\n"
    "- P1 systems: RPO <= 1 minute, RTO < 1 hour, hot standby architecture.\n"
    "- P2 systems: RPO <= 15 minutes, RTO < 4 hours, warm standby architecture.\n"
    "- P3 systems: RPO <= 1 hour, RTO <= 24 hours, cold standby / backup restore.\n"
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _header(title: str, language: str) -> str:
    lang_rule = _LANGUAGE_INSTRUCTION.get(language, _LANGUAGE_INSTRUCTION["en"])
    return f"## Task: {title}\n\n### Output language rule\n{lang_rule}\n\n"


def _profile_context(profile: Dict) -> str:
    parts = ["### Regulatory & compliance context (must be satisfied)\n"]
    ctx = profile.get("regulatory_context", "").strip()
    if ctx:
        parts.append(ctx + "\n")
    extra = localized(profile.get("extra_guidance"), "en").strip()
    if extra:
        parts.append(extra + "\n")
    return "\n".join(parts)


def bia_prompt(inputs: Dict, language: str) -> str:
    return (
        _header("Business Impact Analysis (BIA)", language)
        + f"### Project information\n{_dump(inputs)}\n\n"
        "Perform a business impact analysis: identify the key business systems, "
        "assign each an importance tier and RTO/RPO target, and rank recovery "
        "priority. Output STRICTLY one JSON object, no other content:\n"
        "```json\n"
        "{\n"
        '  "business_systems": [\n'
        '    {"name": "...", "tier": "P0|P1|P2|P3", "rto": "target recovery time",\n'
        '     "rpo": "target recovery point", "criticality": "...",\n'
        '     "max_downtime_impact": "..."}\n'
        "  ],\n"
        '  "overall_rto": "...",\n'
        '  "overall_rpo": "...",\n'
        '  "recovery_priority": ["system names in recovery order"],\n'
        '  "summary": "one-paragraph conclusion"\n'
        "}\n```\n"
    )


def current_state_prompt(inputs: Dict, language: str) -> str:
    return (
        _header("Current State Assessment & Gap Analysis", language)
        + f"### Project information\n{_dump(inputs)}\n\n"
        "Assess the client's current IT infrastructure and identify disaster "
        "recovery capability gaps. Output STRICTLY one JSON object:\n"
        "```json\n"
        "{\n"
        '  "current_infrastructure": {\n'
        '    "compute": "...", "storage": "...", "network": "...", "application": "..."\n'
        "  },\n"
        '  "gap_analysis": [\n'
        '    {"area": "...", "current_capability": "...", "required_capability": "...",\n'
        '     "gap": "...", "risk_level": "high|medium|low"}\n'
        "  ],\n"
        '  "summary": "overall assessment conclusion"\n'
        "}\n```\n"
    )


def strategy_prompt(inputs: Dict, bia: Any, state: Any, language: str) -> str:
    return (
        _header("Disaster Recovery Strategy Design", language)
        + f"### Project information\n{_dump(inputs)}\n\n"
        f"### BIA results\n{_dump(bia.model_dump())}\n\n"
        f"### Current state assessment\n{_dump(state.model_dump())}\n\n"
        "Design a complete DR strategy mapping each tier to a protection mode. "
        "Output STRICTLY one JSON object:\n"
        "```json\n"
        "{\n"
        '  "overall_strategy": "...",\n'
        '  "protection_tiers": [\n'
        '    {"tier": "P0|P1|P2|P3", "protection_mode": "active-active|hot standby|warm standby|cold standby",\n'
        '     "replication": "synchronous|asynchronous", "failover": "automatic|semi-automatic|manual",\n'
        '     "rationale": "..."}\n'
        "  ]\n"
        "}\n```\n"
    )


def architecture_prompt(inputs: Dict, bia: Any, state: Any, strategy: Any, profile: Dict, language: str) -> str:
    return (
        _header("Disaster Recovery Architecture Design", language)
        + f"### Project information\n{_dump(inputs)}\n\n"
        f"### BIA results\n{_dump(bia.model_dump())}\n\n"
        f"### Current state assessment\n{_dump(state.model_dump())}\n\n"
        f"### DR strategy\n{_dump(strategy.model_dump())}\n\n"
        + _profile_context(profile)
        + "\n### Tier design constraints (strict)\n"
        + TIER_CONSTRAINTS
        + "\nOutput STRICTLY one JSON object:\n"
        "```json\n"
        "{\n"
        '  "deployment_mode": "...",\n'
        '  "primary_site": {"name": "...", "location": "..."},\n'
        '  "dr_site": {"name": "...", "location": "..."},\n'
        '  "tier_definitions": {\n'
        '    "P0": {"systems": [], "recovery_strategy": "...", "rpo": "...", "rto": "...",\n'
        '           "replication": "...", "failover": "...", "description": "..."},\n'
        '    "P1": {...}, "P2": {...}, "P3": {...}\n'
        "  },\n"
        '  "network_architecture": "...",\n'
        '  "storage_architecture": "...",\n'
        '  "compute_architecture": "...",\n'
        '  "failover_automation": "...",\n'
        '  "site_separation": {"primary_location": "...", "dr_location": "...",\n'
        '                      "distance_km": "<number>", "datacenter_tier": "Tier III|Tier IV"},\n'
        '  "compliance_design": {"data_localization": "...", "cross_border_transfer": "...",\n'
        '                        "encryption": "...", "retention_years": 7},\n'
        '  "regulatory_alignment": {"rto_compliant": "...", "rpo_compliant": "...",\n'
        '                           "annual_dr_test": "...", "reporting": "..."},\n'
        '  "vendor_recommendations": {"storage": "...", "replication": "...",\n'
        '                             "dr_platform": "...", "network": "..."}\n'
        "}\n```\n"
    )


def critic_prompt(
    inputs: Dict, bia: Any, strategy: Any, architecture: Any, profile: Dict, language: str
) -> str:
    dims = []
    schema_dims = []
    for dim in profile.get("review_dimensions", []):
        name = localized(dim.get("name"), language) or dim["key"]
        dims.append(f"{len(dims) + 1}. {name} (weight {dim.get('weight', 0)}%): {dim['key']}")
        schema_dims.append(f'    "{dim["key"]}": {{"score": <0-100>, "reason": "..."}}')
    dimensions_block = "\n".join(dims) or "- Overall quality"
    schema_block = ",\n".join(schema_dims)

    return (
        _header("Architecture Review", language)
        + f"### Project information\n{_dump(inputs)}\n\n"
        f"### BIA requirements\n{_dump(bia.model_dump())}\n\n"
        f"### DR strategy\n{_dump(strategy.model_dump())}\n\n"
        f"### Architecture under review\n{_dump(architecture.model_dump())}\n\n"
        "Score the architecture on these dimensions (0-100 each):\n"
        f"{dimensions_block}\n\n"
        "The weighted overall score must reach 90 to pass. Output STRICTLY one JSON object:\n"
        "```json\n"
        "{\n"
        '  "score": <0-100 integer>,\n'
        '  "can_proceed": true|false,\n'
        "  \"dimension_scores\": {\n"
        f"{schema_block}\n"
        "  },\n"
        '  "issues": [\n'
        '    {"severity": "blocker|major|minor", "description": "...", "suggestion": "..."}\n'
        "  ],\n"
        '  "summary": "overall review opinion"\n'
        "}\n```\n"
    )


def optimizer_prompt(architecture: Any, review: Any, profile: Dict, language: str) -> str:
    issues = [issue.model_dump() for issue in review.issues]
    return (
        _header("Architecture Optimization", language)
        + f"### Current architecture\n{_dump(architecture.model_dump())}\n\n"
        f"### Review issues to fix\n{_dump(issues)}\n\n"
        "### Tier design constraints (must not be violated)\n"
        + TIER_CONSTRAINTS
        + "\nProduce an optimized architecture that resolves every blocker and major issue "
        "while keeping all previously correct content. Output STRICTLY one JSON object:\n"
        "```json\n"
        "{\n"
        '  "optimized_architecture": { <the complete corrected architecture JSON> },\n'
        '  "changes": ["change 1", "change 2"],\n'
        '  "reason": "why this resolves the issues"\n'
        "}\n```\n"
    )
