#!/usr/bin/env python3
"""Assemble alpine-hydrant-map.html (and index.html) from:
  - build/cache/pts.json, roads.pkl   (run parse_sources.py first)
  - alpine-rail.geojson               (Alpine-area TIGER/Line railroads)
  - build/vendor/leaflet.css, leaflet.js
  - build/template.html

Run from anywhere; paths below are all relative to this script.
"""
import csv, json, pickle, math, re, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / 'cache'
CORRECTIONS_CSV = ROOT / 'hydrant-corrections.csv'


def load_rail():
    """Flatten alpine-rail.geojson into the same [lon,lat,lon,lat,...]-per-
    part shape the road data uses, for embedding and for drawing."""
    gj = json.load(open(ROOT / 'alpine-rail.geojson'))
    parts = []
    for feat in gj['features']:
        for part in feat['geometry']['coordinates']:
            flat = []
            for x, y in part:
                flat += [round(x, 6), round(y, 6)]
            parts.append(flat)
    return parts

COLOR_BY_STYLE = {
    'IconStyle30': 'red',      # Good
    'IconStyle322': 'black',   # Not Working
    'IconStyle331': 'yellow',  # Low Pressure
    'IconStyle3137': 'purple', # Storage Supply Tank
    'IconStyle60': 'purple',
    'IconStyle70': 'purple',
    'IconStyle20': 'purple',
}

# Road classes eligible to be the "nearest street" shown in a hydrant's
# popup, and eligible for on-map street labels.
STREET_CLASSES = ('S1100', 'S1200', 'S1400', 'S1630', 'S1640', 'S1730', 'S1780')


def load_hydrants():
    pts = json.load(open(CACHE / 'pts.json'))
    H = []
    for p in pts:
        name = p['name'].strip()
        is_tank = bool(re.search(r'tank|storage', name, re.I)) and name != 'Storage Tank Hydrant'
        H.append(dict(n=name, c=COLOR_BY_STYLE[p['style']], t=1 if is_tank else 0,
                      y=round(p['lat'], 6), x=round(p['lon'], 6)))
    return H


# Status names as written in the popup/legend (build/template.html's CAT
# object) -> the internal single-letter-ish color code. Keep in sync with
# that object if the labels there ever change.
STATUS_TO_COLOR = {
    'good': 'red',
    'not working': 'black',
    'low pressure': 'yellow',
    'storage supply tank': 'purple',
    'unknown': 'brown',
}


def load_corrections():
    """Read hydrant-corrections.csv (add/remove rows for fixing entries the
    KMZ has wrong, or adding ones it's missing entirely). Returns [] if the
    file doesn't exist -- it's optional, not everyone will need it."""
    if not CORRECTIONS_CSV.exists():
        return []
    rows = []
    with open(CORRECTIONS_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            action = (row.get('action') or '').strip().lower()
            if action:
                rows.append(row)
    return rows


def apply_corrections(H, rows):
    """Apply hydrant-corrections.csv rows to H in place-ish (returns a new
    list). 'remove' rows drop a matching KMZ entry by name (optionally
    disambiguated by lat/lon, for the rare case of two KMZ points sharing a
    name -- H151 duplicates itself, for one); 'add' rows append a brand new
    hydrant in the same shape load_hydrants() produces, so it gets full
    nearest-street/corner treatment downstream exactly like a KMZ one."""
    removed = added = 0
    for row in rows:
        action = row['action'].strip().lower()
        name = (row.get('name') or '').strip()

        if action == 'remove':
            matches = [i for i, h in enumerate(H) if h['n'] == name]
            if not matches:
                print(f'  correction: "remove {name}" -- no KMZ hydrant with that name, skipped')
                continue
            if len(matches) > 1:
                lat, lon = (row.get('lat') or '').strip(), (row.get('lon') or '').strip()
                if lat and lon:
                    lat, lon = float(lat), float(lon)
                    matches = [min(matches, key=lambda i: math.hypot(H[i]['x'] - lon, H[i]['y'] - lat))]
                else:
                    print(f'  correction: "remove {name}" is ambiguous ({len(matches)} KMZ hydrants share '
                          f'that name) and no lat/lon was given to tell them apart -- skipped, none removed')
                    continue
            del H[matches[0]]
            removed += 1

        elif action == 'add':
            status = (row.get('status') or '').strip().lower()
            color = STATUS_TO_COLOR.get(status)
            if not color:
                print(f'  correction: "add {name}" has unrecognized status "{row.get("status")}" '
                      f'(expected one of: {", ".join(v.title() for v in STATUS_TO_COLOR)}) -- skipped')
                continue
            try:
                lat, lon = float(row['lat']), float(row['lon'])
            except (KeyError, ValueError):
                print(f'  correction: "add {name}" has no valid lat/lon -- skipped')
                continue
            tank_field = (row.get('tank') or '').strip().lower()
            is_tank = tank_field in ('yes', 'y', 'true', '1') if tank_field else (color == 'purple')
            H.append(dict(n=name or f'Added-{len(H)+1}', c=color, t=1 if is_tank else 0,
                          y=round(lat, 6), x=round(lon, 6)))
            added += 1

        else:
            print(f'  correction: unrecognized action "{row["action"]}" for "{name}" -- skipped')

    if removed or added:
        print(f'corrections applied: {added} added, {removed} removed (from {CORRECTIONS_CSV.name})')
    return H


def dist_point_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def point_on_segment(px, py, ax, ay, bx, by):
    """The actual closest point ON the segment (not just the distance to it)."""
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return (ax + t * dx, ay + t * dy)


def closest_approach(seg_a, seg_b):
    """Distance and midpoint between two 2-point segments (a1,a2) and (b1,b2),
    each a ((x,y),(x,y)) pair in the same units as the returned point."""
    a1, a2 = seg_a
    b1, b2 = seg_b
    dax, day = a2[0] - a1[0], a2[1] - a1[1]
    dbx, dby = b2[0] - b1[0], b2[1] - b1[1]
    den = dax * dby - day * dbx
    if abs(den) > 1e-9:
        t = ((b1[0] - a1[0]) * dby - (b1[1] - a1[1]) * dbx) / den
        u = ((b1[0] - a1[0]) * day - (b1[1] - a1[1]) * dax) / den
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0, (a1[0] + t * dax, a1[1] + t * day)
    d1 = dist_point_to_segment(a1[0], a1[1], b1[0], b1[1], b2[0], b2[1])
    d2 = dist_point_to_segment(a2[0], a2[1], b1[0], b1[1], b2[0], b2[1])
    d3 = dist_point_to_segment(b1[0], b1[1], a1[0], a1[1], a2[0], a2[1])
    d4 = dist_point_to_segment(b2[0], b2[1], a1[0], a1[1], a2[0], a2[1])
    best = min((d1, a1), (d2, a2), (d3, b1), (d4, b2), key=lambda z: z[0])
    return best


def build_roads_and_streets(H):
    shapes, recs = pickle.load(open(CACHE / 'roads.pkl', 'rb'))

    minx = min(h['x'] for h in H) - .012
    maxx = max(h['x'] for h in H) + .012
    miny = min(h['y'] for h in H) - .012
    maxy = max(h['y'] for h in H) + .012

    names, name_idx, R = [], {}, []
    for shape, rec in zip(shapes, recs):
        for part in shape:
            if not any(minx <= x <= maxx and miny <= y <= maxy for x, y in part):
                continue
            nm = rec['FULLNAME']
            if nm and nm not in name_idx:
                name_idx[nm] = len(names)
                names.append(nm)
            flat = []
            for x, y in part:
                flat += [round(x, 5), round(y, 5)]
            R.append([name_idx.get(nm, -1), rec['MTFCC'], flat])
    print('road parts', len(R), 'names', len(names))

    # nearest named streets per hydrant, for popups.
    # Reference latitude is fixed at Alpine's own (not the mean over all H),
    # since a few outliers (Double Diamond, the Training Center) sit well
    # outside town and would skew a computed mean.
    REF_LAT = 30.36
    kx = 111320 * math.cos(math.radians(REF_LAT))
    ky = 110574
    segs = [(nm, flat) for nm, cls, flat in R if nm >= 0 and cls in STREET_CLASSES]

    # All points per street name, for deciding whether a street continues
    # through a junction or dead-ends into it (a T), used below.
    by_name_pts = {}
    for nm, f in segs:
        pts = by_name_pts.setdefault(nm, [])
        for i in range(0, len(f), 2):
            pts.append((f[i] * kx, f[i + 1] * ky))

    THROUGH_M = 25  # metres a street must extend past the junction, on BOTH sides, to count as "through" rather than a dead-end there

    def continues_through(nm, junction, direction):
        jx, jy = junction
        dx, dy = direction
        max_pos = max_neg = 0.0
        for px, py in by_name_pts.get(nm, ()):
            t = (px - jx) * dx + (py - jy) * dy
            if t > max_pos:
                max_pos = t
            elif t < max_neg:
                max_neg = t
        return max_pos >= THROUGH_M and -max_neg >= THROUGH_M

    def unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        return (dx / L, dy / L)

    def side_of(direction, ns, ew):
        # `direction` is the THROUGH street's own bearing. The meaningful
        # single side-descriptor is the axis that street does NOT run
        # along: an east-west street is described by which side (N/S)
        # you're on, a north-south one by E/W.
        return ns if abs(direction[0]) > abs(direction[1]) else ew

    for h in H:
        best = {}  # name -> (dist, closest-segment-a, closest-segment-b), all in projected units
        hx, hy = h['x'] * kx, h['y'] * ky
        for nm, f in segs:
            # cheap pre-filter: skip streets nowhere near this hydrant's longitude
            if abs(f[0] - h['x']) > .01 and abs(f[-2] - h['x']) > .01 and \
               not any(abs(f[i] - h['x']) < .003 for i in range(0, len(f), 2)):
                continue
            for i in range(0, len(f) - 2, 2):
                ax, ay, bx, by = f[i] * kx, f[i + 1] * ky, f[i + 2] * kx, f[i + 3] * ky
                d = dist_point_to_segment(hx, hy, ax, ay, bx, by)
                if d < best.get(nm, (1e9,))[0]:
                    best[nm] = (d, (ax, ay), (bx, by))
        top = sorted(best.items(), key=lambda a: a[1][0])[:3]
        h['s'] = [[names[k], round(v[0])] for k, v in top]

        # Which corner of the intersection the hydrant sits on, only when
        # the two nearest streets are both close enough that this is
        # genuinely one intersection, not just two separately-nearby
        # streets (a hydrant mid-block gets no direction hint at all).
        # A real 4-way gets a corner (NE/NW/SE/SW); a T -- one street
        # dead-ends into the other right there -- gets a single side
        # (N/S/E/W) relative to whichever street actually continues
        # through, which is the only distinction that means anything at
        # a T (there's no far corner on the dead-end side to be "at").
        h['corner'] = ''
        if len(top) >= 2:
            (nameA, (dA, segA1, segA2)), (nameB, (dB, segB1, segB2)) = top[0], top[1]
            if dA <= 70 and dB <= 70:
                gap, (ix, iy) = closest_approach((segA1, segA2), (segB1, segB2))
                # `gap` alone isn't enough: streets that run concurrent for
                # a stretch (Alpine's US 67/90/118 are the same physical
                # road under multiple route numbers for long stretches)
                # have a near-zero gap almost everywhere along that whole
                # stretch, not just where the hydrant actually is -- so a
                # "shared" point can still land nowhere near this hydrant.
                # A real corner/T has the hydrant right there, within a
                # handful of metres of the actual curb corner, not half a
                # block away, so that distance is the tighter of the two
                # checks and does the real work here.
                if gap <= 20 and math.hypot(ix - hx, iy - hy) <= 25:
                    ns = 'N' if hy >= iy else 'S'
                    ew = 'E' if hx >= ix else 'W'
                    dirA, dirB = unit(segA1, segA2), unit(segB1, segB2)
                    throughA = continues_through(nameA, (ix, iy), dirA)
                    throughB = continues_through(nameB, (ix, iy), dirB)
                    if throughA and not throughB:
                        h['corner'] = side_of(dirA, ns, ew)
                    elif throughB and not throughA:
                        h['corner'] = side_of(dirB, ns, ew)
                    else:  # both through (a real 4-way) or neither (rare) -- full corner either way
                        h['corner'] = ns + ew

        # Not near any intersection (mid-block, or the only nearby street
        # has nothing else close enough to cross it): still worth saying
        # which side of that one street the hydrant is on -- but only if
        # that one street is actually close. Some hydrants have nothing
        # but unnamed local roads nearby (real roads, sometimes just a
        # few metres away, but with no FULLNAME in TIGER to call them by),
        # and without this check top[0] would silently be some named
        # highway hundreds of metres off, with a side label that implies
        # it's nearby when it isn't.
        if not h['corner'] and top and top[0][1][0] <= 70:
            _, (dA, segA1, segA2) = top[0]
            px, py = point_on_segment(hx, hy, segA1[0], segA1[1], segA2[0], segA2[1])
            ns = 'N' if hy >= py else 'S'
            ew = 'E' if hx >= px else 'W'
            h['corner'] = side_of(unit(segA1, segA2), ns, ew)

    return R, names


def main():
    H = load_hydrants()
    H = apply_corrections(H, load_corrections())
    R, names = build_roads_and_streets(H)
    RAIL = load_rail()
    print('rail parts', len(RAIL))

    css = (HERE / 'vendor' / 'leaflet.css').read_text(encoding='utf-8')
    js = (HERE / 'vendor' / 'leaflet.js').read_text(encoding='utf-8')
    tpl = (HERE / 'template.html').read_text(encoding='utf-8')

    out = (tpl
           .replace('/*LEAFLET_CSS*/', css)
           .replace('/*LEAFLET_JS*/', js)
           .replace('/*HYDRANTS*/', json.dumps(H, separators=(',', ':')))
           .replace('/*ROADNAMES*/', json.dumps(names, separators=(',', ':')))
           .replace('/*ROADS*/', json.dumps(R, separators=(',', ':')))
           .replace('/*RAIL*/', json.dumps(RAIL, separators=(',', ':'))))

    (ROOT / 'alpine-hydrant-map.html').write_text(out, encoding='utf-8')
    (ROOT / 'index.html').write_text(out, encoding='utf-8')  # what GitHub Pages actually serves
    print(len(out) // 1024, 'KB ->  alpine-hydrant-map.html, index.html')


if __name__ == '__main__':
    main()
