import json
import re
import unicodedata

import pandas as pd
from natural_disaster_calculation import calculate_severity


### LOAD DATA
nodes = pd.read_csv("data/nodes.csv")
edges = pd.read_csv("data/edges.csv")

# Returns filtered individual records with imputed impacts and severity.
disasters = calculate_severity(
    pd.read_excel("data/emdat.xlsx")
)

# Exclude records whose severity remains unavailable.
disasters = disasters.dropna(subset=["severity_score"]).copy()

# Filter natural disasters in the Americas
americas = [
    "Americas", "North America", "Northern America",
    "Central America", "South America", "Caribbean"
]

region_col = "Continent" if "Continent" in disasters.columns else "Region"

disasters = disasters[disasters[region_col].isin(americas)]
disasters = disasters[disasters["Disaster Group"] == "Natural"]
disasters = disasters.dropna(subset=["severity_score"]).copy()

# Identify unique disasters across countries
disasters["Event ID"] = (
    disasters["DisNo."].astype("string")
    .str.replace(r"-[A-Z]{3}$", "", regex=True)
)


### CLEAN LOCATIONS
def clean_location(value):
    if pd.isna(value):
        return ""

    value = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(
        c for c in value if not unicodedata.combining(c)
    ).strip()


disasters["location_clean"] = disasters["Location"].apply(clean_location)


### MATCH DISASTERS
def match_disasters(country, region, city):

    country = country.strip()

    if country == "United States":
        country = "United States of America"

    matches = disasters[
        disasters["Country"] == country
    ].copy()

    city = clean_location(city)
    region = clean_location(region)

    city_match = pd.Series(False, index=matches.index)
    region_match = pd.Series(False, index=matches.index)

    if city:
        pattern = (
            r"\b" + re.escape(city)
            + r"\b(?!\s+(?:do|da|de|dos|das)\b)"
        )
        city_match = matches["location_clean"].str.contains(
            pattern, na=False
        )

    if region:
        region_match = matches["location_clean"].str.contains(
            r"\b" + re.escape(region) + r"\b",
            na=False
        )

    return matches[city_match | region_match].copy()


### CALCULATE VULNERABILITY
def calculate_vulnerability(match_list, original, id_column):
    matched = pd.concat(match_list, ignore_index=True)

    # A country record may match several cities along the same route.
    matched = matched.drop_duplicates(
        subset=[id_column, "DisNo."]
    )

    # Count each event once per asset.
    # For international routes, use the highest matched country severity.
    matched = matched.groupby(
        [id_column, "Event ID"], as_index=False
    ).agg(
        severity_score=("severity_score", "max"),
        start_year=("Start Year", "min")
    )

    summary = matched.groupby(id_column).agg(
        disaster_count=("Event ID", "nunique"),
        average_severity=("severity_score", "mean"),
        first_year=("start_year", "min"),
        last_year=("start_year", "max")
    ).reset_index()

    # Keep every node or edge, including those without matches.
    summary = original[[id_column]].merge(
        summary, on=id_column, how="left"
    )

    summary["disaster_count"] = (
        summary["disaster_count"].fillna(0).astype(int)
    )
    summary["average_severity"] = (
        summary["average_severity"].fillna(0)
    )

    summary["year_range"] = (
    summary["last_year"] - summary["first_year"] + 1
    ).fillna(1).clip(lower=1)

    summary["annual_frequency"] = (
        summary["disaster_count"] / summary["year_range"]
    )

    frequency = summary["annual_frequency"]

    summary["vulnerability_score"] = (
        summary["average_severity"]
        * frequency / (1 + frequency)
    ).round(2)

    return summary


### NODE VULNERABILITY
node_matches = []

for _, node in nodes.iterrows():

    matches = match_disasters(
        node["country"], node["region"], node["city"]
    )

    matches["node_id"] = node["node_id"]
    node_matches.append(matches)

node_summary = calculate_vulnerability(
    node_matches, nodes, "node_id"
)

nodes = nodes.merge(
    node_summary[["node_id", "vulnerability_score"]],
    on="node_id", how="left"
)

nodes.to_csv("data/nodes_vulnerability.csv", index=False)

print("\nNODE VULNERABILITY")
print(node_summary.to_string(index=False))


### EDGE VULNERABILITY
edge_matches = []

for _, edge in edges.iterrows():

    for location in json.loads(edge["cities_along_route"]):

        if location.count(",") < 2:
            continue

        city, region, country = (
            part.strip() for part in location.rsplit(",", 2)
        )

        matches = match_disasters(country, region, city)

        matches["edge_id"] = edge["edge_id"]
        edge_matches.append(matches)

# Handle edges without usable city entries
if not edge_matches:
    edge_matches = [
        disasters.iloc[0:0].assign(edge_id=pd.Series(dtype="object"))
    ]

edge_summary = calculate_vulnerability(
    edge_matches, edges, "edge_id"
)

edges = edges.merge(
    edge_summary[["edge_id", "vulnerability_score"]],
    on="edge_id", how="left"
)

edges.to_csv("data/edges_vulnerability.csv", index=False)

print("\nEDGE VULNERABILITY")
print(edge_summary.to_string(index=False))
