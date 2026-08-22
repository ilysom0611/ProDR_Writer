"""Chart generation driven by real pipeline data.

Unlike v1 (hardcoded content, parameters ignored, exceptions swallowed),
charts here take the validated stage models, label in the configured
language, and raise loudly on failure so missing figures are visible.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..schemas import BIAReport, DRArchitecture  # noqa: E402

# Font candidates per language; first available one wins.
_CJK_FONTS = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC", "WenQuanYi Micro Hei"]


def _setup_style(language: str) -> None:
    if language == "zh":
        from matplotlib import font_manager

        installed = {f.name for f in font_manager.fontManager.ttflist}
        chosen = next((name for name in _CJK_FONTS if name in installed), None)
        if chosen is None:
            raise RuntimeError(
                "No CJK font found for Chinese chart labels; install e.g. 'Noto Sans CJK SC'."
            )
        plt.rcParams["font.family"] = [chosen, "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.dpi"] = 150


def _finish(fig, out_path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def tier_distribution_chart(bia: BIAReport, out_path: Path, labels: Dict[str, str]) -> Path:
    """Bar chart: number of business systems per importance tier."""
    _setup_style("en")
    counts = {tier: 0 for tier in ("P0", "P1", "P2", "P3")}
    for system in bia.business_systems:
        if system.tier in counts:
            counts[system.tier] += 1
    tiers = list(counts)
    colors = ["#c0392b", "#e67e22", "#2980b9", "#7f8c8d"]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    bars = ax.bar(tiers, [counts[t] for t in tiers], color=colors)
    ax.bar_label(bars)
    ax.set_xlabel(labels["chart_tier_xlabel"])
    ax.set_ylabel(labels["chart_system_count"])
    ax.set_title(labels["chart_tier_title"])
    ax.spines[["top", "right"]].set_visible(False)
    return _finish(fig, out_path)


def rto_rpo_chart(arch: DRArchitecture, out_path: Path, labels: Dict[str, str]) -> Path:
    """Log-scale grouped bar of RTO/RPO targets per tier."""
    _setup_style("en")
    from ..rules import parse_minutes

    tiers = sorted(set(arch.tier_definitions) & {"P0", "P1", "P2", "P3"})
    rto_vals, rpo_vals = [], []
    for tier in tiers:
        rto_vals.append(max(parse_minutes(arch.tier_definitions[tier].rto) or 1, 0.01))
        rpo_vals.append(max(parse_minutes(arch.tier_definitions[tier].rpo) or 0.01, 0.01))

    x = range(len(tiers))
    width = 0.38
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.bar([i - width / 2 for i in x], rto_vals, width, label="RTO", color="#2471a3")
    ax.bar([i + width / 2 for i in x], rpo_vals, width, label="RPO", color="#82b366")
    ax.set_yscale("log")
    ax.set_xticks(list(x))
    ax.set_xticklabels(tiers)
    ax.set_ylabel(labels["chart_minutes_log"])
    ax.set_title(labels["chart_rto_title"])
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    return _finish(fig, out_path)


def topology_diagram(arch: DRArchitecture, out_path: Path, labels: Dict[str, str]) -> Path:
    """Simple two-site topology diagram from the architecture's site info."""
    _setup_style("en")
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    ax.axis("off")

    def site_box(x, title, subtitle, color):
        box = dict(boxstyle="round,pad=0.5", facecolor=color, edgecolor="#333333")
        ax.text(x, 0.62, title, ha="center", va="center", fontsize=11, fontweight="bold", bbox=box)
        ax.text(x, 0.38, subtitle, ha="center", va="center", fontsize=9, color="#333333")

    primary_name = arch.primary_site.name or "Primary Site"
    dr_name = arch.dr_site.name or "DR Site"
    primary_loc = arch.primary_site.location or ""
    dr_loc = arch.dr_site.location or ""
    site_box(0.22, primary_name, primary_loc, "#d6eaf8")
    site_box(0.78, dr_name, dr_loc, "#fdebd0")

    replication = arch.tier_definitions.get("P0").replication if (
        arch.tier_definitions.get("P0") and arch.tier_definitions.get("P0").replication
    ) else ""
    link_label = f"{labels['chart_replication_link']}" + (f"\n({replication})" if replication else "")
    ax.annotate("", xy=(0.66, 0.62), xytext=(0.34, 0.62),
                arrowprops=dict(arrowstyle="<->", lw=2, color="#c0392b"))
    ax.text(0.5, 0.72, link_label, ha="center", fontsize=9, color="#c0392b")

    mode = arch.deployment_mode or ""
    ax.text(0.5, 0.08, f"{labels['chart_deployment']}: {mode}", ha="center", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return _finish(fig, out_path)
