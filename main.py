import json
import pandas as pd
from natural_disaster_calculation import calculate_severity
import re
import unicodedata

# Load data
nodes = pd.read_csv("data/nodes.csv")
edges = pd.read_csv("data/edges.csv")
edges_original = edges.copy()
disasters = pd.read_excel("data/emdat.xlsx")

# Calculate severity for each retained disaster type
severity = calculate_severity(disasters)

# Attach severity to disaster records
disasters = disasters.merge(
    severity,
    on="Disaster Type",
    how="left",
    validate="many_to_one"
)

# Filter to Western Hemisphere
americas = [
    "Americas", "North America", "Northern America",
    "Central America", "South America", "Caribbean"
]

if "Continent" in disasters.columns:
    disasters = disasters[disasters["Continent"].isin(americas)]
else:
    disasters = disasters[disasters["Region"].isin(americas)]

# Filter natural disasters
disasters = disasters[disasters["Disaster Group"] == "Natural"]

# Remove disasters without a severity score
disasters = disasters.dropna(subset=["severity_score"])


#CLEAN LOCATIONS AND MATCH
# Standardize location names
def clean_location(text):
    if pd.isna(text):
        return ""

    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))

    return text


disasters["location_clean"] = disasters["Location"].apply(clean_location)

# Match disasters to nodes
node_matches = []

for index, node in nodes.iterrows():

    country = node["country"]
    region = clean_location(node["region"])
    city = clean_location(node["city"])

    # Match EM-DAT country naming
    if country == "United States":
        country = "United States of America"

    # First filter by country
    matches = disasters[disasters["Country"] == country].copy()

    # Check for the region or city in the disaster location
    region_pattern = r"\b" + re.escape(region) + r"\b"
    city_pattern = r"\b" + re.escape(city) + r"\b"

    region_match = matches["location_clean"].str.contains(region_pattern)
    city_match = matches["location_clean"].str.contains(city_pattern)

    matches = matches[region_match | city_match].copy()

    # Identify the node associated with each matched disaster
    matches["node_id"] = node["node_id"]

    node_matches.append(matches)

    print(node["node_id"], "-", len(matches), "matching disasters")

# Combine results
node_disasters = pd.concat(node_matches, ignore_index=True)

###CALCULATE DISASTER FREQUENCIES
# Group disasters by node
node_summary = node_disasters.groupby("node_id").agg(
    disaster_count=("DisNo.", "nunique"),
    average_severity=("severity_score", "mean"),
    first_year=("Start Year", "min"),
    last_year=("Start Year", "max")
).reset_index()

# Include all nodes, even those without matching disasters
node_summary = nodes[["node_id"]].merge(
    node_summary,
    on="node_id",
    how="left"
)

# Replace missing disaster counts with zero
node_summary["disaster_count"] = node_summary["disaster_count"].fillna(0)

# Calculate year range for each node
node_summary["year_range"] = (
    node_summary["last_year"] - node_summary["first_year"]
)

# Avoid division by zero when disasters occur in only one year
node_summary["year_range"] = node_summary["year_range"].fillna(1)
node_summary["year_range"] = node_summary["year_range"].clip(lower=1)

# Calculate disaster frequency
node_summary["annual_frequency"] = (
    node_summary["disaster_count"] / node_summary["year_range"]
)

# Display results
print("\nNODE DISASTER SUMMARY")
print(node_summary.to_string(index=False))


###CALCULATE VULNERABILITY SCORE FOR NODES
# Replace missing severity values with zero
node_summary["average_severity"] = node_summary["average_severity"].fillna(0)

# Calculate vulnerability
node_summary["vulnerability_score"] = (
    node_summary["average_severity"] *
    node_summary["annual_frequency"] /
    (1 + node_summary["annual_frequency"])
)

# Round scores to 2 decimal places
node_summary["vulnerability_score"] = node_summary["vulnerability_score"].round(2)

# Display results
print("\nNODE VULNERABILITY SCORES")
print(node_summary.to_string(index=False))


#MERGE VULNERABILITY SCORE TO DATASET
# Merge vulnerability scores with original nodes
nodes = nodes.merge(
    node_summary[["node_id", "vulnerability_score"]],
    on="node_id",
    how="left"
)

# Save updated nodes to CSV
nodes.to_csv("nodes_vulnerability.csv", index=False)

# Display results
print("\nFINAL NODE VULNERABILITY SCORES")
print(nodes[["node_id", "vulnerability_score"]].to_string(index=False))






###EDGES
# Convert city lists from JSON strings into Python lists
edges["cities_along_route"] = edges["cities_along_route"].apply(json.loads)

# Display cities along each edge
for index, edge in edges.iterrows():

    edge_id = edge["edge_id"]
    cities = edge["cities_along_route"]

###MATCH CITIES ONTO EDGES
# Match disasters to edges
edge_matches = []

for index, edge in edges.iterrows():

    for location in edge["cities_along_route"]:

        # Separate city, region, and country
        parts = location.split(",")

        if len(parts) < 3:
            continue

        city = clean_location(parts[0].strip())
        region = clean_location(parts[-2].strip())
        country = parts[-1].strip()

        # Match EM-DAT country naming
        if country == "United States":
            country = "United States of America"

        # Filter disasters by country
        matches = disasters[disasters["Country"] == country].copy()

        # Match city and region
        city_pattern = r"\b" + re.escape(city) + r"\b"
        region_pattern = r"\b" + re.escape(region) + r"\b"

        city_match = matches["location_clean"].str.contains(city_pattern, na=False)
        region_match = matches["location_clean"].str.contains(region_pattern, na=False)

        matches = matches[city_match | region_match].copy()

        # Assign disaster to edge
        matches["edge_id"] = edge["edge_id"]

        edge_matches.append(matches)

# Combine all matching disasters
if edge_matches:
    edge_disasters = pd.concat(edge_matches, ignore_index=True)
else:
    edge_disasters = pd.DataFrame(
        columns=list(disasters.columns) + ["edge_id"]
    )

# Identify unique disaster events
edge_disasters["Event ID"] = (
    edge_disasters["DisNo."]
    .astype("string")
    .str.replace(r"-[A-Z]{3}$", "", regex=True)
)

# Remove duplicate disasters for the same edge
edge_disasters = edge_disasters.drop_duplicates(
    subset=["edge_id", "Event ID"]
)

# Display matches for each edge
print("\nEDGE DISASTER MATCHES")

for edge_id in edges["edge_id"]:
    count = len(edge_disasters[edge_disasters["edge_id"] == edge_id])
    print(edge_id, "-", count, "matching disasters")


### CALCULATE EDGE DISASTER FREQUENCIES

# Group disasters by edge
edge_summary = edge_disasters.groupby("edge_id").agg(
    disaster_count=("Event ID", "nunique"),
    average_severity=("severity_score", "mean"),
    first_year=("Start Year", "min"),
    last_year=("Start Year", "max")
).reset_index()

# Include all edges
edge_summary = edges[["edge_id"]].merge(
    edge_summary,
    on="edge_id",
    how="left"
)

# Replace missing values
edge_summary["disaster_count"] = edge_summary["disaster_count"].fillna(0)
edge_summary["average_severity"] = edge_summary["average_severity"].fillna(0)

# Calculate year range
edge_summary["year_range"] = (
    edge_summary["last_year"] - edge_summary["first_year"]
)

# Prevent division by zero
edge_summary["year_range"] = edge_summary["year_range"].fillna(1)
edge_summary["year_range"] = edge_summary["year_range"].clip(lower=1)

# Calculate annual disaster frequency
edge_summary["annual_frequency"] = (
    edge_summary["disaster_count"] / edge_summary["year_range"]
)

### CALCULATE EDGE VULNERABILITY

# Calculate vulnerability
edge_summary["vulnerability_score"] = (
    edge_summary["average_severity"] *
    edge_summary["annual_frequency"] /
    (1 + edge_summary["annual_frequency"])
)

# Round scores
edge_summary["vulnerability_score"] = (
    edge_summary["vulnerability_score"].round(2)
)

print("\nEDGE VULNERABILITY SCORES")
print(edge_summary.to_string(index=False))


### MERGE VULNERABILITY SCORES TO EDGES

# Merge scores with original edges
edges = edges_original.merge(
    edge_summary[["edge_id", "vulnerability_score"]],
    on="edge_id",
    how="left"
)

# Save results
edges.to_csv("edges_vulnerability.csv", index=False)

# Display results
print("\nFINAL EDGE VULNERABILITY SCORES")
print(edges[["edge_id", "vulnerability_score"]].to_string(index=False))