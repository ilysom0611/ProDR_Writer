import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from prodr_writer.rules import (
    check_coverage,
    check_p0_strategy,
    check_rto_rpo,
    compute_weighted_score,
    parse_minutes,
)
from prodr_writer.schemas import (
    PASS_SCORE_THRESHOLD,
    BIAReport,
    BusinessSystem,
    DRArchitecture,
    DRStrategy,
    ProtectionTier,
    TierDefinition,
)


def test_parse_minutes():
    assert parse_minutes("≤4h") == 240
    assert parse_minutes("<30min") == 30
    assert parse_minutes("0") == 0
    assert parse_minutes("24 hours") == 1440
    assert parse_minutes("") is None
    assert parse_minutes("N/A") is None


def test_parse_minutes_ranges_and_prefixes():
    # Ranges: the upper bound is the binding promise.
    assert parse_minutes("1-2 hours") == 120
    assert parse_minutes("15–30 min") == 30  # en dash range
    assert parse_minutes("1 to 2 days") == 2880
    # Comparison prefixes: value stands.
    assert parse_minutes(">30min") == 30
    assert parse_minutes(">=4 hours") == 240
    assert parse_minutes("<=15min") == 15
    assert parse_minutes("~1 hour") == 60
    assert parse_minutes("≥5分钟") == 5
    # Qualifiers and other units.
    assert parse_minutes("2 full hours") == 120
    assert parse_minutes("half an hour") == 30
    assert parse_minutes("1 full day") == 1440
    assert parse_minutes("2d") == 2880
    assert parse_minutes(None) is None


def test_compute_weighted_score():
    weights = {"a": 20, "b": 80}
    assert compute_weighted_score({"a": 100, "b": 50}, weights) == 60
    # Dimensions absent from weights are ignored.
    assert compute_weighted_score({"a": 90, "zzz": 0}, weights) == 90
    # No overlap between scores and weights → 0.0.
    assert compute_weighted_score({"zzz": 100}, weights) == 0.0
    assert compute_weighted_score({}, weights) == 0.0


def test_tier_definitions_key_normalization():
    arch = DRArchitecture(tier_definitions={
        " p0 ": TierDefinition(systems=["x"], rto="<30min", rpo="0"),
        "tier 1": TierDefinition(systems=["y"], rto="<1h", rpo="<=1min"),
        "P2": TierDefinition(systems=["z"], rto="<4h", rpo="<=15min"),
        "3": TierDefinition(systems=["w"], rto="24h", rpo="1h"),
    })
    assert set(arch.tier_definitions.keys()) == {"P0", "P1", "P2", "P3"}


def test_tier_definitions_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        DRArchitecture(tier_definitions={
            "Tier 4": TierDefinition(systems=["x"], rto="<30min", rpo="0"),
        })


def _bia(**overrides):
    defaults = dict(name="Core Banking", tier="P0", rto="<30min", rpo="0")
    defaults.update(overrides)
    return BIAReport(business_systems=[BusinessSystem(**defaults)])


def _arch(rto="<30min", rpo="0"):
    return DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["Core Banking"], rto=rto, rpo=rpo),
    })


def test_bia_target_slower_than_tier_is_fatal():
    constraints = {"P0": {"rto_max_minutes": 30, "rpo_max_minutes": 0}}
    bia = _bia(rto="<=15 min")
    findings = check_rto_rpo(bia, _arch(rto="<30min"), constraints)
    rto_hits = [f for f in findings if f.rule_id == "RTO-LIMIT"]
    assert any(f.severity == "fatal" and "Core Banking" in f.message for f in rto_hits)


def test_bia_rpo_weaker_than_required_is_fatal():
    constraints = {}
    bia = _bia(rpo="0")
    findings = check_rto_rpo(bia, _arch(rpo="15min"), constraints)
    assert any(f.rule_id == "RPO-LIMIT" and f.severity == "fatal" for f in findings)


def test_bia_within_tier_capability_passes():
    constraints = {"P0": {"rto_max_minutes": 30, "rpo_max_minutes": 0}}
    findings = check_rto_rpo(_bia(), _arch(), constraints)
    assert not [f for f in findings if f.severity == "fatal"]


def test_unparsable_bia_target_is_warning_not_silent():
    findings = check_rto_rpo(_bia(rto="ASAP"), _arch(), {})
    assert any(f.rule_id == "RTO-PARSE" and f.severity == "warning"
               and "Core Banking" in f.message for f in findings)


def test_coverage_finds_unassigned_system():
    bia = BIAReport(business_systems=[
        BusinessSystem(name="Core Banking", tier="P0"),
        BusinessSystem(name="CRM", tier="P2"),
    ])
    arch = DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["Core Banking"], rto="<30min", rpo="0"),
    })
    findings = check_coverage(bia, arch)
    assert any(f.rule_id == "COVERAGE" and "CRM" in f.message for f in findings)


def test_coverage_normalization_matches_fuzzy_names():
    bia = BIAReport(business_systems=[
        BusinessSystem(name="Core-Banking System", tier="P0"),
        BusinessSystem(name="crm", tier="P2"),
    ])
    arch = DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["Core Banking"], rto="<30min", rpo="0"),
        "P2": TierDefinition(systems=["CRM System"], rto="<4h", rpo="<=15min"),
    })
    assert check_coverage(bia, arch) == []


def test_p0_backup_strategy_is_fatal():
    arch = DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["x"], recovery_strategy="backup and restore", rto="<30min", rpo="0"),
    })
    strategy = DRStrategy(protection_tiers=[])
    findings = check_p0_strategy(arch, strategy)
    assert any(f.severity == "fatal" for f in findings)


def test_p0_strategy_word_boundaries_avoid_false_positives():
    arch = DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["x"], recovery_strategy="Synchronous replication "
                             "with continuous data protection; no backup window needed",
                             rto="<30min", rpo="0"),
    })
    strategy = DRStrategy(protection_tiers=[
        ProtectionTier(tier="P0", protection_mode="active-active synchronous replication"),
    ])
    assert check_p0_strategy(arch, strategy) == []


def test_pass_score_threshold_exported():
    # pipeline.py recomputes review results against this shared constant.
    assert PASS_SCORE_THRESHOLD == 90


# resources/sample_run.json is the canonical copy of this fixture (this repo's
# demo payload); the duplicate under tests/fixtures/ exists because docgen tests
# resolve it relative to the package root in some environments. This tripwire
# fails when one copy is edited without the other, preventing silent drift.
def test_sample_run_fixture_stays_in_sync_with_resources_copy():
    fixture = Path(__file__).parent / "fixtures" / "sample_run.json"
    canonical = Path(__file__).parents[1] / "src" / "prodr_writer" / "resources" / "sample_run.json"
    assert fixture.read_bytes() == canonical.read_bytes()
    # Sanity: both must remain valid JSON payloads of the same document.
    assert json.loads(fixture.read_text(encoding="utf-8")) == json.loads(
        canonical.read_text(encoding="utf-8"))
