# Alpine, TX &mdash; Fire Hydrant Map

A single-file, offline-capable, installable map of fire hydrants in Alpine,
TX, with street-routed nearest-hydrant search and continuous GPS tracking.
Built for the Alpine Fire Department.

**Live site:** https://mdoucleff.github.io/alpine-hydrant-map/

## What it does

- **Plots every hydrant and storage tank** from the city's KMZ, colored by
  status as recorded there:
  - **Good** (red)
  - **Not Working** (black)
  - **Low Pressure** (yellow)
  - **Storage Supply Tank** (purple &mdash; the pump-house tank, the Training
    Center tank/hydrant, and the Double Diamond tanks)
- **Street basemap** drawn from TIGER/Line road centerlines (no map-tile
  service required, so it works with no network at all once loaded).
- **Nearest-hydrant search**: tap any spot on the map, and the three closest
  hydrants are found by routing along the actual street network (not
  straight-line distance), with the route drawn and each hydrant's distance,
  compass direction, and nearest cross streets shown. Hydrants marked *Not
  Working* are skipped; storage tanks are included.
- **Continuous GPS tracking**: on load (or on pressing "My location"), the
  map follows your position and the nearest-hydrant list updates live as you
  move &mdash; no need to re-tap while driving. Manually panning the map
  pauses auto-recentering (the list keeps updating) until "My location" is
  pressed again; tapping the map or pressing "Clear" pauses GPS updates
  entirely until then.
- **Installable / offline (PWA)**: a service worker (`sw.js`) caches the page
  after the first online visit, so it keeps working with no signal after
  that. The page's manifest is built at runtime from the page's own URL
  (`location.href`), so `start_url` always matches wherever it's actually
  hosted &mdash; renaming the file or moving it to a different path/host
  doesn't break the installed shortcut.
- Light/dark theme follows the system setting; street labels appear as you
  zoom in.

## Files

| File | Purpose |
|---|---|
| `index.html` | The map, as served at the site root by GitHub Pages. |
| `alpine-hydrant-map.html` | Identical content to `index.html`; kept under its descriptive name for local use / handing off the file directly. |
| `sw.js` | Service worker: network-first with a cached fallback, so the page keeps working offline after one successful visit. |
| `alpine-hydrant-map.webmanifest` | Static manifest kept for reference only &mdash; the page builds its actual manifest at runtime (see above), so this file isn't linked from the page. |
| `hydrant-icon.png` | Home-screen / install icon. |
| `Alpine Hydrants_9_23_26_Update.kmz` | Source of hydrant/tank locations and status. |
| `tl_2024_48043_roads.zip` | U.S. Census Bureau TIGER/Line 2024 road centerlines for Brewster County &mdash; the map's street basemap and its routing graph. |
| `build/` | The build pipeline that turns the KMZ + roads zip into `index.html` (see “Updating the map” below). |

Reference only &mdash; not surveyed. Hydrant status and locations should be
confirmed against city records before operational use.

## Updating the map

`index.html` / `alpine-hydrant-map.html` are generated files: Leaflet, the
hydrant data (from the KMZ), and the TIGER roads are all inlined into one
HTML document by the build scripts in `build/`. Regenerating and publishing
is two commands:

```
python3 build/parse_sources.py   # KMZ + roads.zip -> build/cache/*.json,*.pkl
python3 build/build_map.py       # cache + build/template.html -> alpine-hydrant-map.html, index.html
git add -A && git commit -m "update map" && git push
```

`build/parse_sources.py` reads `Alpine Hydrants_9_23_26_Update.kmz` and
`tl_2024_48043_roads.zip` straight out of their zip archives (nothing needs
to be pre-extracted) and writes a small cache under `build/cache/` (not
committed &mdash; regenerate it any time). `build/build_map.py` reads that
cache plus `build/template.html` and the vendored Leaflet build in
`build/vendor/`, and writes the final page. GitHub Pages republishes
automatically within about a minute of the push.

**Changing the hydrant data:** replace the KMZ with an updated export and
regenerate.

**Changing the streets:** TIGER/Line road files are published annually by
the Census Bureau; download the current year's `tl_<year>_48043_roads.zip`
for Brewster County, update the filename in `build/parse_sources.py` if it
changed, and regenerate.

**Changing the map's behavior/UI:** edit `build/template.html` (plain HTML
+ CSS + JS, with `/*HYDRANTS*/` / `/*ROADS*/` / `/*ROADNAMES*/` /
`/*LEAFLET_CSS*/` / `/*LEAFLET_JS*/` as the four spots `build_map.py` fills
in) and regenerate.
