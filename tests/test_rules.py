from prodr_writer.rules import parse_minutes
from prodr_writer.schemas import BIAReport, BusinessSystem, DRArchitecture, DRStrategy, TierDefinition
from prodr_writer.rules import check_coverage, check_p0_strategy


def test_parse_minutes():
    assert parse_minutes("≤4h") == 240
    assert parse_minutes("<30min") == 30
    assert parse_minutes("0") == 0
    assert parse_minutes("24 hours") == 1440
    assert parse_minutes("") is None
    assert parse_minutes("N/A") is None


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


def test_p0_backup_strategy_is_fatal():
    arch = DRArchitecture(tier_definitions={
        "P0": TierDefinition(systems=["x"], recovery_strategy="backup and restore", rto="<30min", rpo="0"),
    })
    strategy = DRStrategy(protection_tiers=[])
    findings = check_p0_strategy(arch, strategy)
    assert any(f.severity == "fatal" for f in findings)
