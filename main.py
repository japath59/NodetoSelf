import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from full_dataset import clean_text, state_key
from natural_disaster_calculation import calculate_severity


DATA = Path(__file__).resolve().parent / "data"


def clean_location(value):
    if pd.isna(value):
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value).lower(),
    )

    return "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    ).strip()


def match_disasters(disasters, country, region, city):
    country = country.strip()

    if country == "United States":
        country = "United States of America"

    matches = disasters[
        disasters["Country"].eq(country)
    ].copy()

    # Atlas identifies municipalities.
    # Match both the exact municipality and its state.
    if country == "Brazil":
        return matches[
            matches["Municipality Key"].eq(clean_text(city))
            & matches["State Key"].eq(state_key(region))
        ].copy()

    # Preserve the original matching method for other countries.
    city = clean_location(city)
    region = clean_location(region)

    city_match = pd.Series(False, index=matches.index)
    region_match = pd.Series(False, index=matches.index)

    if city:
        pattern = (
            r"\b"
            + re.escape(city)
            + r"\b(?!\s+(?:do|da|de|dos|das)\b)"
        )

        city_match = matches["location_clean"].str.contains(
            pattern,
            na=False,
        )

    if region:
        region_match = matches["location_clean"].str.contains(
            r"\b" + re.escape(region) + r"\b",
            na=False,
        )

    return matches[city_match | region_match].copy()


def calculate_vulnerability(match_list, original, id_column):
    matched = pd.concat(match_list, ignore_index=True)

    # Avoid counting the same source record several times per asset.
    matched = matched.drop_duplicates(
        subset=[id_column, "DisNo."]
    )

    # EM-DAT country records sharing an event ID count once.
    # Atlas IDs identify individual municipal records.
    matched = matched.groupby(
        [id_column, "Event ID"],
        as_index=False,
    ).agg(
        severity_score=("severity_score", "max"),
        start_year=("Start Year", "min"),
    )

    summary = matched.groupby(id_column).agg(
        disaster_count=("Event ID", "nunique"),
        average_severity=("severity_score", "mean"),
        first_year=("start_year", "min"),
        last_year=("start_year", "max"),
    ).reset_index()

    # Retain assets even when no scored records match.
    summary = original[[id_column]].merge(
        summary,
        on=id_column,
        how="left",
    )

    summary["disaster_count"] = (
        summary["disaster_count"]
        .fillna(0)
        .astype(int)
    )

    summary["average_severity"] = (
        summary["average_severity"].fillna(0)
    )

    summary["year_range"] = (
        summary["last_year"]
        - summary["first_year"]
        + 1
    ).fillna(1).clip(lower=1)

    summary["annual_frequency"] = (
        summary["disaster_count"]
        / summary["year_range"]
    )

    frequency = summary["annual_frequency"]

    summary["vulnerability_score"] = (
        summary["average_severity"]
        * frequency
        / (1 + frequency)
    ).round(2)

    return summary


def calculate_node_vulnerability(nodes, disasters):
    node_matches = []

    for _, node in nodes.iterrows():
        matches = match_disasters(
            disasters,
            node["country"],
            node["region"],
            node["city"],
        )

        matches["node_id"] = node["node_id"]
        node_matches.append(matches)

    if not node_matches:
        node_matches = [
            disasters.iloc[0:0].assign(
                node_id=pd.Series(dtype="object")
            )
        ]

    return calculate_vulnerability(
        node_matches,
        nodes,
        "node_id",
    )


def calculate_edge_vulnerability(edges, disasters):
    edge_matches = []

    for _, edge in edges.iterrows():
        locations = json.loads(edge["cities_along_route"])

        for location in locations:
            if location.count(",") < 2:
                continue

            city, region, country = (
                part.strip()
                for part in location.rsplit(",", 2)
            )

            matches = match_disasters(
                disasters,
                country,
                region,
                city,
            )

            matches["edge_id"] = edge["edge_id"]
            edge_matches.append(matches)

    if not edge_matches:
        edge_matches = [
            disasters.iloc[0:0].assign(
                edge_id=pd.Series(dtype="object")
            )
        ]

    return calculate_vulnerability(
        edge_matches,
        edges,
        "edge_id",
    )


def main():
    nodes = pd.read_csv(DATA / "nodes.csv")
    edges = pd.read_csv(DATA / "edges.csv")

    disasters = calculate_severity(
        DATA / "combined_disasters.csv"
    )

    # Save individual scores, including unresolved missing values.
    disasters.to_csv(
        DATA / "scored_disasters.csv",
        index=False,
    )

    # Only records with a usable severity enter vulnerability calculations.
    disasters = disasters.dropna(
        subset=["severity_score"]
    ).copy()

    disasters["location_clean"] = (
        disasters["Location"].apply(clean_location)
    )

    node_summary = calculate_node_vulnerability(
        nodes,
        disasters,
    )

    edge_summary = calculate_edge_vulnerability(
        edges,
        disasters,
    )

    nodes = nodes.merge(
        node_summary[["node_id", "vulnerability_score"]],
        on="node_id",
        how="left",
    )

    edges = edges.merge(
        edge_summary[["edge_id", "vulnerability_score"]],
        on="edge_id",
        how="left",
    )

    nodes.to_csv(
        DATA / "nodes_vulnerability.csv",
        index=False,
    )

    edges.to_csv(
        DATA / "edges_vulnerability.csv",
        index=False,
    )

    node_summary.to_csv(
        DATA / "node_summary.csv",
        index=False,
    )

    edge_summary.to_csv(
        DATA / "edge_summary.csv",
        index=False,
    )

    print("\nNODE VULNERABILITY")
    print(node_summary.to_string(index=False))

    print("\nEDGE VULNERABILITY")
    print(edge_summary.to_string(index=False))


if __name__ == "__main__":
    main()