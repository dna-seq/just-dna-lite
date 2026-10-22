"""Render the manuscript's worked annotation from its recorded report extract."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manuscript = root / "docs" / "manuscript" / "v0.5"
    evidence = json.loads(
        (manuscript / "supplementary" / "S13_worked_report_row.json").read_text()
    )
    row = evidence["row"]
    figure, axes = plt.subplots(figsize=(8.6, 6.4))
    figure.patch.set_facecolor("white")
    axes.set(xlim=(0, 1), ylim=(0, 1))
    axes.axis("off")
    ink, muted, accent = "#183342", "#526574", "#137b82"
    axes.text(0.025, 0.97, "From a called genotype to its source studies",
              fontsize=16, weight="bold", color=ink, va="top")
    axes.text(0.025, 0.905, "Fields extracted from an existing Longevity Variants report",
              fontsize=11, color=muted)

    def panel(x: float, y: float, width: float, height: float) -> None:
        axes.add_patch(FancyBboxPatch(
            (x, y), width, height, boxstyle="round,pad=0.014,rounding_size=0.008",
            facecolor="#f4f8fa", edgecolor="#cdd9df", linewidth=1,
        ))

    panel(0.025, 0.54, 0.35, 0.30)
    axes.text(0.045, 0.795, "CALLED GENOTYPE", fontsize=10, weight="bold", color=accent)
    axes.text(0.045, 0.72, f"{row['gene']}   {row['rsid']}", fontsize=14, weight="bold", color=ink)
    axes.text(0.045, 0.64, f"{row['genotype']}   ·   {row['genotype_evidence']}", fontsize=20, color=ink)
    axes.text(0.045, 0.575, "Anton Kulaga's public genome\nGRCh38", fontsize=10.5, color=muted)

    panel(0.025, 0.11, 0.35, 0.355)
    axes.text(0.045, 0.42, "REPORT ANNOTATION", fontsize=10, weight="bold", color=accent)
    axes.text(0.045, 0.36, "Category: insulin signalling", fontsize=12, color=ink)
    axes.text(0.045, 0.30, f"Displayed direction: {row['displayed_direction']}", fontsize=12, color=ink)
    axes.text(0.045, 0.24, f"Curation weight: {row['weight']}", fontsize=12, color=ink)
    axes.text(0.045, 0.17, "A curation weight does not quantify\na change in lifespan.",
              fontsize=10.5, color=muted, linespacing=1.45)
    axes.add_patch(FancyArrowPatch((0.20, 0.53), (0.20, 0.48), arrowstyle="-|>",
                                  mutation_scale=17, color=accent, linewidth=1.5))
    axes.add_patch(FancyArrowPatch((0.39, 0.64), (0.44, 0.64), arrowstyle="-|>",
                                  mutation_scale=17, color=accent, linewidth=1.5))

    panel(0.465, 0.11, 0.51, 0.73)
    axes.text(0.485, 0.795, "LINKED STUDY RECORDS", fontsize=10, weight="bold", color=accent)
    axes.text(0.485, 0.73, "Recorded population", fontsize=10.5, color=muted)
    axes.text(0.86, 0.73, "PubMed ID", fontsize=10.5, color=muted, ha="center")
    labels = {
        "Italian (Southern)": "Southern Italian",
        "Chinese (Han)": "Han Chinese",
        "American of Japanese origin": "Japanese-American",
        "Danish": "Danish",
    }
    for index, study in enumerate(evidence["studies"]):
        y = 0.67 - index * 0.066
        axes.text(0.485, y, labels[study["population"]], fontsize=12, color=ink)
        axes.text(0.86, y, study["pmid"], fontsize=12, color=accent, ha="center")
        axes.plot([0.485, 0.955], [y - 0.021, y - 0.021], color="#dce5e9", linewidth=0.7)
    axes.text(0.485, 0.305, "Excerpt of the stored Danish-study conclusion", fontsize=10.5, color=muted)
    conclusion = row["conclusion"].split(" FOXO3A was ")[-1]
    conclusion = "FOXO3A was " + conclusion
    axes.text(0.485, 0.26, textwrap.fill(conclusion, width=44), fontsize=10,
              color=ink, va="top", linespacing=1.5)
    axes.text(0.025, 0.035, "Recorded report content; extracted fields and provenance: Supplementary S13.",
              fontsize=9, color=muted)
    figure.subplots_adjust(left=0.015, right=0.995, top=0.99, bottom=0.01)
    destination = manuscript / "figures"
    destination.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "svg"):
        figure.savefig(destination / f"figure-2-worked-annotation.{extension}",
                       dpi=220, facecolor="white")
    plt.close(figure)


if __name__ == "__main__":
    main()
