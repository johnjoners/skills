---
name: official-parcel-gis-evidence
description: Use when verifying a parcel or address, or pulling flood, soil, elevation, or public well-index evidence from official GIS and government sources. Retains each query and response as evidence.
license: MIT
compatibility: Needs HTTP access to public GIS services (ArcGIS REST, FEMA NFHL, USDA Soil Data Access, USGS EPQS). Works with any agent that can fetch URLs and write files.
---

# Official parcel GIS evidence

Use this when a claim about a property has to be traceable to an official record. Every value in the output needs a source, a timestamp, and the exact request that produced it. If a query fails, record the failure. A missing result is a finding.

## Before querying

1. Read the project's evidence and privacy rules. They decide what may be stored.
2. Decide the fields you need before the first request. Owner names and mailing addresses are out of scope unless the project says otherwise. Whitelist the output fields, and never request owner fields "to be safe."
3. Pull the layer metadata first: append `?f=pjson` to the layer URL. Read the field types. ArcGIS returns HTTP 400 for a quoted value on an integer field, so `SITE_NUM = 123` works and `SITE_NUM = '123'` fails.

## Workflow

1. **Parcel.** Query the county or state parcel layer by address fields with `outFields` set to the whitelist. Use `returnGeometry=true&outSR=4326` only when you need the polygon for later steps.
2. **Address check.** Match on the returned address fields, not on the query. An adjacent parcel with a blank address is a separate feature. It does not establish that two parcels share title or ownership.
3. **Area.** Keep the published geometry area separate from the assessor's acreage. Convert square meters to acres only after checking the native CRS, and label the result as a GIS calculation.
4. **Flood.** Query layer 20 (Flood Hazard Zones) of `https://hazards.fema.gov/arcgis/rest/services/FIRMette/NFHLREST_FIRMette/MapServer/20/query`. Pass the parcel polygon as the geometry with `geometryType=esriGeometryPolygon`, not a centroid. The layer returns `FLD_ZONE` and `SFHA_TF`. Keep every zone the polygon touches, not just the dominant one. Layer 28 is High Water Marks, not flood zones. Take the overlapping FIRM panels from layer 1 and select by the jurisdiction identifier.
5. **Soil.** POST to `https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest` with a JSON body `{"query": "<SQL>", "format": "JSON+COLUMNNAME"}`. For a point, get the map unit keys first with `SELECT ... FROM muaggatt WHERE mukey IN (SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('POINT(<lon> <lat>)'))`. Longitude comes first in the WKT. The response is a `Table` array whose first row is the column names. The physical fields include `slopegraddcp`, `slopegradwta`, `brockdepmin`, and `drclasswettest`. State-level snapshots may name these differently. Take the units from the current USDA TablesAndColumnsReport PDF, `muaggatt` page, not from memory.
6. **Elevation.** Query USGS EPQS at `https://epqs.nationalmap.gov/v1/json?x=<lon>&y=<lat>&units=Feet`. Label each value as a DEM sample at a point. It is not a wellhead elevation and not a parcel-wide maximum or minimum.
7. **Well index.** For large state well-index XML files, test HTTP Range support first (`curl -I` and look for `Accept-Ranges: bytes`). If Range works, pull only the counties you need. Records in those files are often ordered by county, so you can stop early. Count records with missing sections or coordinates before reading zero spatial matches as "no wells." An index record in the same township does not match a construction record. Do not retrieve linked original forms when you cannot store their identities safely.

## Fetching source documents

- Fetch the complete PDF before you extract text. A truncated download of a linearized or incrementally updated PDF can still parse and return stale pages. Compare the saved byte count with the `Content-Length` header and reject a mismatch.
- Record the capture date for every fetch.

## Evidence record

Write one JSON file per property. Each fact has its source.

```json
{
  "property": {"address": "...", "parcel_id": "...", "source": {"url": "...", "params": {...}, "captured": "2026-01-15T10:00:00Z", "http_status": 200}},
  "facts": [
    {"field": "flood_zone", "value": "X", "source_ref": "nfhl-q1", "note": "polygon intersects zone X; also AE sliver"},
    {"field": "slope_pct_weighted", "value": 4, "source_ref": "sda-q2", "unit": "percent"}
  ],
  "failed_queries": [{"name": "well-index", "reason": "HTTP 503", "captured": "..."}],
  "transfer_limits": ["GIS calculation, not survey"]
}
```

- No owner attributes anywhere in the file. Grep for the whitelisted-out field names before you save.
- Keep failed queries. A reviewer needs to see what was tried.
- If another tool assigns citation numbers, return the facts as JSON without numbers and let that tool number them.

## Validation before handoff

- The JSON parses, and every `source_ref` resolves to a stored query.
- Every flood or soil value has its units written next to it.
- Every elevation is labeled as a DEM sample.
- Every derived number says it is a derived number.
- The file contains no owner names or mailing addresses.

## Common failures

- A quoted integer filter returns HTTP 400. Check the field type in the metadata.
- A centroid query misses a flood zone that the polygon crosses.
- A truncated PDF yields plausible but stale text. Check the byte count.
- A zero-match spatial query may be a coverage gap in the data. Count what was actually searched.
