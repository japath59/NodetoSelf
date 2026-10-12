# Noblis aluminum supply-chain data dictionary

Version: 2026-10-11, revision 3 (America/New_York).

## Scope and joins

Two UTF-8, comma-delimited CSV files: nodes_updated.csv has 10 records and 16 columns; edges_updated.csv has 9 records and 15 columns. Each edge is directed from its origin facility to its destination facility. `From` and `To` reference `nodes.node_id`; `edge_id` identifies the transportation leg itself. Edge IDs cannot serve as facility endpoints in this node-edge schema.

This is a research scaffold with documented upstream links and hypothetical downstream links, not a verified end-to-end shipment chain. Three node rows are unidentified placeholders (N006, N007, N009). AMI is a known company but its specific handling facility is not identified.

## Aggregated downstream edge

E009 connects AMI Metals (N009) to Lockheed Martin Fort Worth (N010). It includes possible intermediate component manufacturers, which are not separate nodes. Nodes are numbered consecutively N001-N010 and edges E001-E009. No new columns were added.

This is an assumed aggregated supply connection, not a verified direct truck shipment. Intermediate manufacturing, handling, routes and transportation changes remain unknown. Their facility-level exposure and disruption effects cannot be evaluated separately in this simplified network. Any future distance or transit time must cover all included transportation legs; manufacturing lead time must be modeled separately from transit and transfer delay. Do not interpret the aggregated material label as conservation of mass across manufacturing.

## Missing data and geospatial conventions

- Blank cells mean unknown or not yet verified, never zero. Configure the CSV reader to parse numeric columns as nullable numbers.
- All coordinates, route geometries, capacities, annual flows and travel/transfer times are currently blank because no verified values were established in the working chain. Do not substitute city centres for facility coordinates without explicitly labeling that approximation.
- Coordinates use WGS84 (EPSG:4326). WKT uses longitude first, latitude second. Reproject to a suitable distance-preserving CRS or use geodesic methods for distances and buffers.
- E001 distance is the reported approximate railway length. E002 uses 2000 km solely as a provisional midpoint of the earlier unvalidated 1800-2200 km estimate. Replace it after tracing a navigable route. Other distances are blank.
- A known mode or source-destination connection does not establish route geometry: every route_status is currently unknown.
- A source URL can be contextual. Always read notes and connection_status before treating an edge as evidence. Historical agreements do not prove current shipments.
- Capacity years and edge data years were removed as requested; when future numeric data are entered, retain source dates in notes. Removed inventory and recovery fields are not included.
- Source material combines different years. This file is not a synchronized operating snapshot.

## Nodes fields

| Column | Type | Definition and rules |
|---|---|---|
| node_id | string | Required unique primary key, e.g. N001. |
| node_name | string | Facility name or explicit placeholder label. |
| company | string | Owner or operator; blank if unknown. |
| node_type | category | mine, port, refinery, smelter, plate_mill, processor, component_manufacturer, final_assembly. |
| country | string | Country name; blank if unknown. |
| region | string | State or province; blank if unknown. |
| city | string | City or municipality; blank if unknown. |
| latitude | decimal | WGS84 (EPSG:4326) latitude in decimal degrees, -90 to 90. Blank until facility position is verified. |
| longitude | decimal | WGS84 (EPSG:4326) longitude in decimal degrees, -180 to 180. Blank until facility position is verified. |
| input_material | string | Material received; mine input may describe the in-ground resource. |
| output_material | string | Material produced or handled; ports do not chemically transform the material. |
| annual_capacity | decimal | Nonnegative annual facility nameplate capacity, not actual production or Alcoa ownership share. Blank when not established. |
| capacity_unit | string | Material-specific annual unit, e.g. metric tonnes of alumina/year or aircraft/year. Required when capacity is populated. |
| verification_status | category | confirmed_facility, approximate_location, unidentified_placeholder. Confirms node identity only, not downstream supply. |
| source_url | string | Supporting URL(s), separated by a space-pipe-space. Notes distinguish direct evidence from contextual evidence. |
| notes | string | Evidence limits, assumptions, source dates and other qualifications. |

## Edges fields

| Column | Type | Definition and rules |
|---|---|---|
| edge_id | string | Required unique primary key, e.g. E001. |
| From | string | Required origin node_id from nodes_updated.csv; not an edge ID. |
| To | string | Required destination node_id from nodes_updated.csv; not an edge ID. |
| material | string | Material transported on this leg. For aggregated E009, the label describes plate becoming components across hidden processing stages; it is not a single unchanged shipment. |
| transport_mode | category | rail, ship, truck, conveyor, internal_transfer, unknown. Assumed modes must be identified in notes. |
| carrier | string | Transportation operator, if established; blank otherwise. |
| route_geometry | WKT string | Route LINESTRING in WGS84 (EPSG:4326), ordered longitude latitude from origin to destination. Blank until traced or explicitly modeled. |
| distance_km | decimal | Nonnegative route distance in kilometres. Estimates must be explained in notes. Not straight-line distance. |
| transit_days | decimal | Nonnegative travel time in days, excluding transfer_delay_days; fractional days allowed. |
| transfer_delay_days | decimal | Nonnegative loading/unloading/terminal delay assigned to this leg. Count each delay once. |
| annual_flow_tonnes | decimal | Annual material flow on this edge in metric tonnes/year, not facility capacity. State evidence period in notes if filled. |
| connection_status | category | confirmed, historical, assumed, unknown. Refers to the exact facility-to-facility connection represented. |
| route_status | category | observed, modeled, unknown. Describes geographic path evidence, separately from transport-mode evidence. |
| source_url | string | Supporting URL(s), separated by a space-pipe-space. Contextual sources do not verify an assumed edge. |
| notes | string | Assumptions, source periods, distance ranges and qualifications. |

## Status definitions

Node verification_status: confirmed_facility means the facility identity and locality are documented, not that precise coordinates are available. approximate_location is reserved for explicitly approximate geographic placement. unidentified_placeholder means the specific site is unknown.

Edge connection_status: confirmed means the represented supply connection is documented; historical means an older agreement supports it but current operation is not established; assumed means a proposed scenario leg with insufficient direct evidence; unknown is reserved for unresolved links with no assigned scenario assumption. E008 is historical at the company relationship level, with its receiving site still unresolved.

Edge route_status: observed requires a sourced physical path or tracked voyage; modeled means an explicitly constructed route geometry; unknown means no path geometry is established.

## Use in disruption analysis

Join edges.From and edges.To to nodes.node_id. Overlay only located facilities and traced or modeled routes with hazard footprints. Keep scenarios containing assumed edges separate from a confirmed-only network. Do not infer robust chokepoint rankings from this single illustrative chain: missing alternatives can make every leg appear critical.

Hazard exposure, downtime, capacity loss and risk scores are scenario outputs and are not included in these baseline CSVs. Quantitative production-loss simulation requires additional flow and conversion information, especially because tonnes of bauxite, alumina, metal and plate are not interchangeable.
