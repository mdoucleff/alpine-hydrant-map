#!/usr/bin/env python3
"""Assemble alpine-hydrant-map.html (and index.html) from:
  - build/cache/pts.json, roads.pkl   (run parse_sources.py first)
  - build/vendor/leaflet.css, leaflet.js
  - build/template.html

Run from anywhere; paths below are all relative to this script.
"""
import json, pickle, math, re, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / 'cache'

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


def dist_point_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


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
    for h in H:
        best = {}
        for nm, f in segs:
            # cheap pre-filter: skip streets nowhere near this hydrant's longitude
            if abs(f[0] - h['x']) > .01 and abs(f[-2] - h['x']) > .01 and \
               not any(abs(f[i] - h['x']) < .003 for i in range(0, len(f), 2)):
                continue
            for i in range(0, len(f) - 2, 2):
                d = dist_point_to_segment(h['x'] * kx, h['y'] * ky,
                                           f[i] * kx, f[i + 1] * ky, f[i + 2] * kx, f[i + 3] * ky)
                if d < best.get(nm, 1e9):
                    best[nm] = d
        top = sorted(best.items(), key=lambda a: a[1])[:3]
        h['s'] = [[names[k], round(d)] for k, d in top]

    return R, names


def main():
    H = load_hydrants()
    R, names = build_roads_and_streets(H)

    css = (HERE / 'vendor' / 'leaflet.css').read_text(encoding='utf-8')
    js = (HERE / 'vendor' / 'leaflet.js').read_text(encoding='utf-8')
    tpl = (HERE / 'template.html').read_text(encoding='utf-8')

    out = (tpl
           .replace('/*LEAFLET_CSS*/', css)
           .replace('/*LEAFLET_JS*/', js)
           .replace('/*HYDRANTS*/', json.dumps(H, separators=(',', ':')))
           .replace('/*ROADNAMES*/', json.dumps(names, separators=(',', ':')))
           .replace('/*ROADS*/', json.dumps(R, separators=(',', ':'))))

    (ROOT / 'alpine-hydrant-map.html').write_text(out, encoding='utf-8')
    (ROOT / 'index.html').write_text(out, encoding='utf-8')  # what GitHub Pages actually serves
    print(len(out) // 1024, 'KB ->  alpine-hydrant-map.html, index.html')


if __name__ == '__main__':
    main()
