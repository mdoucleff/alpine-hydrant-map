# Alpine, TX &mdash; Fire Hydrant Map

A single-file, offline-capable map of fire hydrants in Alpine, TX, with
nearest-hydrant search and live GPS tracking. Built for the Alpine Fire
Department.

**Live site:** served from this repo via GitHub Pages, at the repo's Pages
URL (see the repo's "About" section once Pages is enabled).

## Files

- `index.html` / `alpine-hydrant-map.html` &mdash; the map itself (identical
  content; `index.html` is what GitHub Pages serves at the site root).
- `sw.js` &mdash; service worker. Caches the page on first (online) visit so
  it keeps working with no signal after that.
- `alpine-hydrant-map.webmanifest` &mdash; static manifest kept for
  reference; the page actually builds its manifest at runtime (as a Blob
  URL) so `start_url` always matches wherever the page is actually served
  from, regardless of filename or subpath.
- `hydrant-icon.png` &mdash; home-screen / install icon.
- `Alpine Hydrants_9_23_26_Update.kmz` &mdash; source hydrant locations and
  status (Good / Not Working / Low Pressure / Storage Supply Tank).
- `tl_2024_48043_roads.zip` &mdash; U.S. Census Bureau TIGER/Line 2024 road
  centerlines for Brewster County, used as the map's street basemap and for
  nearest-hydrant routing.
- `DESIGN.md` &mdash; project design notes.

## Updating the map

The page is a generated, self-contained HTML file (Leaflet + the hydrant
data + the TIGER roads, all inlined). After regenerating
`alpine-hydrant-map.html`, copy it over `index.html` as well, then commit
and push:

```
cp alpine-hydrant-map.html index.html
git add -A && git commit -m "update map" && git push
```

GitHub Pages republishes automatically within about a minute.

Reference only &mdash; not surveyed. Hydrant status and locations should be
confirmed against city records before operational use.
