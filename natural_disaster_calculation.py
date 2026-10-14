"""Calculate disaster-type severity for natural disasters in the Americas.

Uses 2000–2025, excludes types with fewer than five distinct events, and
preserves the notebook's 70% deaths / 30% affected severity weighting.
Missing impact values remain missing rather than being treated as zero.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def calculate_severity(data="data/emdat.xlsx"):
    """Return only Disaster Type and severity_score.

    data can be an EM-DAT DataFrame or an Excel file path. The five-entry
    threshold counts distinct events after filtering and combining countries.
    Normalization uses only the retained disaster types.
    """
    if isinstance(data, (str, Path)):
        data = pd.read_excel(data)

    region_col = "Continent" if "Continent" in data.columns else "Region"
    americas = [
        "Americas", "North America", "Northern America",
        "Central America", "South America", "Caribbean",
    ]

    data = data[
        data[region_col].isin(americas)
        & (data["Disaster Group"] == "Natural")
        & data["Start Year"].between(2000, 2025)
    ].copy()

    for column in ["Total Deaths", "Total Affected"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    # Combine country-level impacts for the same disaster event.
    data["Event ID"] = (
        data["DisNo."].astype("string")
        .str.replace(r"-[A-Z]{3}$", "", regex=True)
    )
    events = data.groupby(
        ["Event ID", "Disaster Type"], as_index=False
    ).agg(
        deaths=("Total Deaths", lambda values: values.sum(min_count=1)),
        affected=("Total Affected", lambda values: values.sum(min_count=1)),
    )

    summary = events.groupby("Disaster Type", as_index=False).agg(
        event_count=("Event ID", "nunique"),
        avg_deaths=("deaths", "mean"),
        avg_affected=("affected", "mean"),
    )
    summary = summary.loc[summary["event_count"] >= 5].copy()

    def normalize_log(values):
        maximum = values.max()
        if pd.isna(maximum) or maximum <= 0:
            return values * 0
        return np.log1p(values) / np.log1p(maximum) * 100

    summary["severity_score"] = (
        0.70 * normalize_log(summary["avg_deaths"])
        + 0.30 * normalize_log(summary["avg_affected"])
    )

    return (
        summary.sort_values("event_count", ascending=False)
        [["Disaster Type", "severity_score"]]
        .round(2)
        .reset_index(drop=True)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", nargs="?", default="data/emdat.xlsx")
    args = parser.parse_args()
    print(calculate_severity(args.input_file).to_string(index=False))
