# Hydrant Map — Design Doc

## Problem / Goal
Alpine's only hydrant location record appears to be a physical sheet kept at the
City Water Department (309 W. Sul Ross Ave), listing hydrants by cross streets.
No digital hydrant layer exists — confirmed there's nothing in OpenStreetMap, no
city GIS portal, and no county GIS layer covering hydrants. Goal: turn a
photographed copy of that sheet into an accurate, browsable map.

## Non-goals
- Not field-surveying/GPS-pinning hydrants directly — v1 is a photo → map pipeline only.
- Not building a live/public-facing map — v1 is a static snapshot of one photographed sheet.
- Not validating hydrant condition, flow rate, or color coding — location only.

## Input
One or more photos of the hydrant sheet. Expected: rows of hydrant ID (maybe) +
a location description, typically cross streets (e.g. "5th & Sul Ross") or a
street + block ("600 blk Ave E"). Actual column layout, handwritten vs. typed,
and whether IDs exist are unknown until we see it.

## Pipeline

1. **Capture**
   Photograph the sheet at high resolution, flat lighting, one page per image,
   in sequential order.

2. **Extraction (image → structured text)**
   Read each photo directly and transcribe rows into a table: `hydrant_id`
   (if present), `raw_location_text`, `notes`. For long or handwritten sheets,
   work in batches and cross-check row counts against the photo to catch
   skipped or merged rows.
   → `data/hydrants_raw.csv`, with `source_image` / `source_row` columns so
   every entry stays traceable back to the photo.

3. **Normalization**
   Parse `raw_location_text` into a cross-street pair (`street_a`, `street_b`)
   or a street + block, resolving abbreviations/aliases against the canonical
   Alpine street list already compiled for this project (e.g. "Ave E" →
   "East Avenue E", "Ft Davis" → "Fort Davis Avenue"). Anything that doesn't
   cleanly match two known streets is flagged `needs_review`, not guessed.
   → `data/hydrants_normalized.csv`

4. **Geocoding (cross-street → lat/lon)**
   Pull Alpine street centerline geometry from OpenStreetMap (same Overpass
   source used for the street-name doc) and compute the intersection point of
   each cross-street pair. Where a street name matches multiple segments,
   prefer the segment nearest downtown on the first pass and flag ambiguous
   cases. Block-address entries get interpolated along the named way,
   marked lower precision.
   → `data/hydrants_geocoded.geojson`, one Point feature per hydrant, with a
   `precision` field: `intersection` | `interpolated` | `unresolved`.

5. **Review pass (required, not optional)**
   Everything flagged `needs_review` or `unresolved` goes into a short list
   for manual resolution — either by re-reading the photo or dropping a pin
   by hand. OCR + intersection-matching on a small town's imperfect street
   grid *will* misfire sometimes, and wrong hydrant data is actively harmful
   if anyone relies on it in an emergency — it doesn't ship unresolved.

6. **Map output**
   Single-file HTML map (Leaflet + OSM basemap): one marker per resolved
   hydrant, popup with hydrant ID and the original raw location text (so the
   source sheet is always one click away), distinct marker styling for
   lower-precision (`interpolated`) points. Optional street-name filter/search.

## Data layout
```
fire-projects/hydrant-map/
  DESIGN.md
  photos/                     # original sheet photos, numbered in order
  data/
    hydrants_raw.csv          # verbatim transcription — source of truth for what the sheet said
    hydrants_normalized.csv   # + resolved street names, review flags
    hydrants_geocoded.geojson # + lat/lon, precision
  map.html                    # rendered output (Artifact + local copy)
```
Keeping raw → normalized → geocoded as separate files (never overwritten in
place) means every hydrant's final map position traces back to the exact text
on the photographed sheet, and the geocoding logic can be rerun later without
re-transcribing anything.

## Known risks / open questions
- **Legibility** — if the sheet is handwritten, transcription accuracy is
  bounded by photo quality; ambiguous entries get flagged for the user rather
  than guessed.
- **Street name drift** — the sheet may use informal or outdated names not in
  OSM. Cross-referencing against the street list catches most but not all of this.
- **Ambiguous/missing intersections** — streets that don't actually meet in
  OSM's data (unmapped segments, grid gaps) need manual pinning.
- **No independent accuracy check** — this map's accuracy is bounded by (a)
  how accurate the sheet itself is and (b) how cleanly cross-streets resolve.
  It should be labeled as *derived from a photographed reference sheet*, not
  surveyed/authoritative data — especially if it's ever handed to the fire
  department for operational use.

## Milestones
1. Photograph the sheet → `photos/`
2. Transcribe → `hydrants_raw.csv`, sanity-check row count against the photo
3. Normalize street names, flag unresolved
4. Geocode, flag unresolved/low-confidence
5. User resolves flagged rows
6. Render map, review

## Next step
Photograph the sheet and drop the image(s) into `photos/` — that starts step 2.
