# Noblis aluminum supply-chain data dictionary

Version: 2026-10-19.

## Scope and joins

The baseline data consist of two UTF-8 CSV files:

- data/nodes.csv: 10 records and 16 columns.
- data/edges.csv: 9 records and 13 columns.

Each edge is directed. From and To reference nodes.node_id; edge_id identifies the transportation connection itself.

The network follows Juruti bauxite mining through Alumar receiving, refining and smelting, assumed export and receiving terminals, Arconic Davenport Works, AMI Metals Fort Worth, and Lockheed Martin Fort Worth.

This is an illustrative supply-chain scenario combining documented connections, historical relationships, and assumptions. It is not a verified end-to-end shipment chain.

## Facility and connection assumptions

- N006 represents an assumed aluminum export terminal at the real Port of Itaqui. The exact terminal and modeled shipment are unverified.
- N007 represents an assumed aluminum receiving terminal at the real Port of New Orleans. The exact terminal and modeled shipment are unverified.
- N009 is an identified AMI Metals facility in Fort Worth. Its receiving and processing role in this chain is provisional.
- E008 has a historical Arconic–AMI company relationship, but the represented shipment to AMI Fort Worth is unverified.
- E009 aggregates possible intermediate component manufacturing between AMI Metals and Lockheed Martin. These manufacturers are not separate nodes.

E009's approximate 20 km distance is an endpoint proxy. Unknown intermediate manufacturing locations and transportation legs are not included.

## Missing data and geographic conventions

- Blank baseline cells mean unknown or unverified, never zero.
- Facility coordinates and annual capacities are currently blank.
- Coordinates, if added, use WGS84 (EPSG:4326).
- Distances are reported approximations or scenario estimates. Read notes for their evidence and limitations.
- Route geometry is not stored in the current edge file.
- All current route_status values are unknown.
- cities_along_route provides candidate locations for disaster matching, not verified stops or physical route geometry.
- Waterway lists use approximate 50-mile vicinity screening. Road lists use selected corridor locations rather than an equivalent calculated buffer.
- Source URLs may provide contextual evidence. Read notes and status fields before treating a connection as confirmed.
- Sources represent different periods; the network is not a synchronized operating snapshot.

## Node fields

| Column | Type | Definition |
|---|---|---|
| node_id | string | Required unique node identifier, such as N001. |
| node_name | string | Facility name or explicitly labeled scenario location. |
| company | string | Owner or operator; blank if unidentified. |
| node_type | category | mine, port, refinery, smelter, plate_mill, processor, or final_assembly. |
| country | string | Facility or scenario country. |
| region | string | State or province; currently also used as an alternative disaster-matching term. |
| city | string | Facility municipality or assumed endpoint city. |
| latitude | decimal | WGS84 latitude in decimal degrees; currently blank. |
| longitude | decimal | WGS84 longitude in decimal degrees; currently blank. |
| input_material | string | Material received or resource extracted. |
| output_material | string | Material produced or handled. |
| annual_capacity | decimal | Annual facility nameplate capacity; currently blank. Not actual production or ownership share. |
| capacity_unit | string | Material-specific annual unit; required when capacity is populated. |
| verification_status | category | Facility identity or placement status; does not verify downstream supply connections. |
| source_url | string | Supporting URLs separated by a space, pipe, and space. |
| notes | string | Evidence, assumptions, source periods, and limitations. |

## Edge fields

| Column | Type | Definition |
|---|---|---|
| edge_id | string | Required unique transportation-leg identifier, such as E001. |
| From | string | Origin node_id. |
| To | string | Destination node_id. |
| countries_visited | string | Semicolon-separated countries or territories associated with the proposed corridor. Does not establish verified border crossings, territorial-water entry, or port calls. Not used directly in scoring. |
| material | string | Material transported or represented. E009 aggregates processing stages rather than one unchanged shipment. |
| transport_mode | category | rail, ship, truck, conveyor, or internal_transfer. Assumptions appear in notes. |
| carrier | string | Transportation operator, if identified. |
| distance_km | decimal | Reported approximate or estimated distance in kilometres. Not used in the current vulnerability calculation. |
| connection_status | category | Evidence supporting the represented supply connection. |
| route_status | category | Evidence supporting the geographic path, separate from connection evidence. |
| source_url | string | Supporting URLs separated by a space, pipe, and space. |
| notes | string | Connection assumptions, distance evidence, route-list methods, missing locations, and qualifications. |
| cities_along_route | JSON array stored as text | Location strings formatted as "City, Region, Country", used for disaster matching. May include towns and communities. |

The current edge schema excludes the earlier route_geometry, transit_days, transfer_delay_days, and annual_flow_tonnes fields.

### Route-list parsing

cities_along_route is parsed with json.loads. Each entry is split from the right into city, region, and country. Entries with fewer than two commas are skipped.

Lists are not complete municipal inventories or verified port-call lists. E009 includes Fort Worth but omits unidentified intermediate manufacturing locations.

## Status definitions

### Node verification_status

| Value | Meaning |
|---|---|
| confirmed_facility | Facility identity and locality are documented. Does not establish precise coordinates or modeled shipments. |
| approximate_location | Geographic placement is explicitly approximate. |
| unidentified_placeholder | The specific facility or terminal remains unidentified. |

### Edge connection_status

| Value | Meaning |
|---|---|
| confirmed | The represented supply connection is documented, subject to notes. |
| historical | An older relationship supports the connection, but current operation or the exact receiving site is unresolved. |
| assumed | A scenario connection lacks sufficient direct evidence. |
| unknown | The connection remains unresolved without an assigned scenario assumption. |

Current connection classifications:

| Edge | Connection | Status |
|---|---|---|
| E001 | Juruti Mine → Juruti Port | confirmed |
| E002 | Juruti Port → Alumar Receiving Port | confirmed |
| E003 | Alumar Receiving Port → Alumar Refinery | confirmed |
| E004 | Alumar Refinery → Alumar Smelter | confirmed |
| E005 | Alumar Smelter → assumed Itaqui terminal | assumed |
| E006 | assumed Itaqui terminal → assumed New Orleans terminal | assumed |
| E007 | assumed New Orleans terminal → Arconic Davenport Works | assumed |
| E008 | Arconic Davenport Works → AMI Metals Fort Worth | historical |
| E009 | AMI Metals Fort Worth → Lockheed Martin Fort Worth | assumed |

### Edge route_status

| Value | Meaning |
|---|---|
| observed | A sourced physical path or tracked voyage is available. |
| modeled | An explicitly constructed geographic route is established. |
| unknown | The physical path remains unverified. Currently applies to every edge. |

Connection status describes evidence for the supply relationship. It does not establish whether the physical transportation path is verified.

## Disaster severity calculation

natural_disaster_calculation.py accepts an EM-DAT DataFrame or Excel path and returns:

| Column | Definition |
|---|---|
| Disaster Type | Retained natural-disaster category. |
| severity_score | Disaster-type severity, rounded to two decimal places. |

Severity calibration retains natural disasters in the Americas with Start Year from 2000 through 2025, inclusive. Disaster types with fewer than five distinct events are excluded.

The geographic filter uses Continent when available, otherwise Region.

### Event identification

Event ID is derived from DisNo. by removing a trailing hyphen and three-letter country code.

Country-level impact records belonging to the same event and disaster type are summed. Entirely missing impact totals remain missing. Average deaths and average affected are calculated separately by disaster type, excluding missing values.

### Severity formulas

For each retained disaster type:

Death score =
100 × ln(1 + average event deaths)
    / ln(1 + highest average event deaths across retained types)

Affected score =
100 × ln(1 + average event affected)
    / ln(1 + highest average event affected across retained types)

Severity =
0.70 × death score + 0.30 × affected score

Each measure uses its own maximum. The logarithm reduces the influence of extreme impact values.

All matched events of the same disaster type receive the same severity. Severity is therefore type-level rather than event-specific.

## Disaster matching

main.py attaches severity by Disaster Type, retains natural disasters in the Americas, and excludes records without a usable severity score.

Severity calibration uses 2000–2025, but the matching step currently uses the full available historical dataset without that year restriction.

Matching follows these steps:

1. Convert United States to United States of America.
2. Restrict disaster records to the specified country.
3. Lowercase city, region, and disaster Location text and remove diacritics.
4. Search Location for a whole-word match to either city or region.

Nodes use their own country, region, and city fields. Edges use the locations in cities_along_route.

Each Event ID is counted once per node or edge, even if multiple route locations match it.

The implemented matching is not city-only: a region match can include disasters without an explicit mention of the intended city. Region is an alternative search term rather than an additional geographic restriction.

## Vulnerability calculation

Nodes and edges use the same formula.

For each asset:

disaster_count = number of distinct matched events

year_range = max(1, last matched Start Year − first matched Start Year)

annual_frequency = disaster_count / year_range

average_severity = mean severity across distinct matched events

vulnerability_score =
average_severity × annual_frequency / (1 + annual_frequency)

Scores are rounded to two decimal places.

The year-range calculation does not add 1. Each asset uses its own matched first-to-last year span rather than a shared observation period.

As frequency increases, the score approaches the asset's average severity.

The current calculation does not:
- Use distance or transit time.
- Calculate exposure per 100 km.
- Rescale scores relative to the network maximum.
- Estimate disruption probability, downtime, or production loss.

### Summary fields

| Field | Definition |
|---|---|
| node_id / edge_id | Asset identifier. |
| disaster_count | Number of distinct matched events. |
| average_severity | Mean severity across distinct matched events. |
| first_year | Earliest matched Start Year. |
| last_year | Latest matched Start Year. |
| year_range | Last year minus first year, with a minimum of 1. |
| annual_frequency | disaster_count / year_range. |
| vulnerability_score | average_severity × annual_frequency / (1 + annual_frequency). |

For assets without matches, the implementation assigns disaster_count, average_severity, annual_frequency, and vulnerability_score values of zero. year_range is 1, while first_year and last_year remain missing.

These zeros indicate no usable matched records, not demonstrated absence of hazard.

## Output files

| File | Contents |
|---|---|
| data/nodes_vulnerability.csv | Original 16 node columns plus vulnerability_score; 10 records. |
| data/edges_vulnerability.csv | Original 13 edge columns plus vulnerability_score; 9 records. |
| vulnerability_table.svg | Combined node-and-edge ranking generated by simple_vulnerability_table_svg.py. |

main.py prints detailed summaries to the console. It does not export full summary tables or complete event-match inventories.

The SVG table sorts all assets by descending vulnerability score. Its Connection status column displays edge connection_status; nodes display N/A.

Score colors use the combined distribution:
- Low: score at or below the one-third quantile.
- Medium: above the one-third quantile and at or below the two-thirds quantile.
- High: above the two-thirds quantile.

These categories are relative to the current assets, not externally validated risk thresholds. Connection status is displayed separately and does not modify the score.

## Interpretation and limitations

Scores describe historical disaster exposure under the implemented matching and frequency assumptions.

- Region matching can include disasters beyond the intended city or corridor.
- Road and waterway location lists have different geographic coverage.
- Offshore events may be missed.
- Reporting completeness varies across locations and periods.
- Asset-specific year spans affect frequency comparisons.
- Calibration and matching use different time windows.
- Nearby disaster records do not establish actual facility or shipment disruption.
- Assets sharing locations may receive identical scores.
- Unknown intermediate manufacturers and alternative suppliers are absent.

Use the ranking as an initial screening tool. Production-loss and downstream disruption simulation require additional information about operations, material flows, conversion ratios, alternatives, and recovery times.
