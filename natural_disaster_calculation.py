from pathlib import Path

import numpy as np
import pandas as pd

DAMAGE_WEIGHT = 0.75
DEATH_WEIGHT = 0.25


DATA_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "combined_disasters.csv"
)

DAMAGE = "Total Damage, Adjusted ('000 US$)"


def prepare_data(data):
    if isinstance(data, (str, Path)):
        if Path(data).suffix.lower() == ".csv":
            data = pd.read_csv(data, low_memory=False)
        else:
            data = pd.read_excel(data)

    data = data.copy()

    if "Source" not in data.columns:
        data["Source"] = "EM-DAT"

    region = "Continent" if "Continent" in data.columns else "Region"

    americas = [
        "Americas",
        "North America",
        "Northern America",
        "Central America",
        "South America",
        "Caribbean",
    ]

    data = data[
        data[region].isin(americas)
        & data["Disaster Group"].eq("Natural")
        & data["Start Year"].between(2000, 2025)
    ].copy()

    for column in ["Total Deaths", "Total Affected", DAMAGE]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data["Event ID"] = (
        data["DisNo."]
        .astype("string")
        .str.replace(r"-[A-Z]{3}$", "", regex=True)
    )

    # Keep disaster types with at least five distinct source records/events.
    counts = data.groupby("Disaster Type")["Event ID"].nunique()
    supported_types = counts[counts >= 5].index

    return data[
        data["Disaster Type"].isin(supported_types)
    ].copy()


def impute_impacts(data):
    data = data.copy()

    data["period"] = data["Start Year"] // 5 * 5

    groups = [
        ["Disaster Type", "Country", "period"],
        ["Disaster Type", "Country"],
        ["Disaster Type", "period"],
        ["Disaster Type"],
    ]

    impacts = {
        DAMAGE: "damage",
        "Total Deaths": "deaths",
        "Total Affected": "affected",
    }

    for column, name in impacts.items():
        filled_column = f"{name}_imputed"
        data[filled_column] = data[column]

        for grouping in groups:
            # Atlas and EM-DAT never supply donors to one another.
            # Donors always come from the original reported column.
            grouped = data.groupby(
                ["Source"] + grouping
            )[column]

            medians = grouped.transform("median")
            counts = grouped.transform("count")

            data[filled_column] = data[filled_column].fillna(
                medians.where(counts >= 3)
            )

        data[f"{name}_was_imputed"] = (
            data[column].isna()
            & data[filled_column].notna()
        )

    return data


def normalize_log(values):
    values = pd.to_numeric(values, errors="coerce")

    if (values.dropna() < 0).any():
        raise ValueError(
            "Impact values cannot be negative."
        )

    maximum = values.max()

    if pd.isna(maximum) or maximum <= 0:
        return values * 0

    return 100 * np.log1p(values) / np.log1p(maximum)

def calculate_damage_score(data):
    data = data.copy()

    # EM-DAT-compatible damage is in thousands of USD.
    # Convert to USD before applying your existing log formula.
    data["damage_score"] = normalize_log(
        data["damage_imputed"] * 1000
    )

    return data

def calculate_severity(
    data=DATA_FILE,
    damage_weight=DAMAGE_WEIGHT,
    death_weight=DEATH_WEIGHT,
):
    # Check that weights are valid
    if not 0 <= damage_weight <= 1:
        raise ValueError("damage_weight must be between 0 and 1")

    if not 0 <= death_weight <= 1:
        raise ValueError("death_weight must be between 0 and 1")

    humanitarian_weight = 1 - damage_weight
    affected_weight = 1 - death_weight

    # Existing preprocessing
    data = prepare_data(data)
    data = impute_impacts(data)
    data = calculate_damage_score(data)

    # Normalize humanitarian impacts
    data["death_score"] = normalize_log(
        data["deaths_imputed"]
    )

    data["affected_score"] = normalize_log(
        data["affected_imputed"]
    )

    # Calculate humanitarian severity
    data["humanitarian_score"] = (
        death_weight * data["death_score"]
        + affected_weight * data["affected_score"]
    )

    # Calculate overall severity
    data["severity_score"] = (
        damage_weight * data["damage_score"]
        + humanitarian_weight * data["humanitarian_score"]
    )

    return data

if __name__ == "__main__":
    results = calculate_severity()

    columns = [
        "DisNo.",
        "Source",
        "Disaster Type",
        "Country",
        "Start Year",
        "damage_was_imputed",
        "death_score",
        "affected_score",
        "damage_score",
        "severity_score",
    ]

    print(
        results[columns]
        .head(10)
        .round(2)
        .to_string(index=False)
    )