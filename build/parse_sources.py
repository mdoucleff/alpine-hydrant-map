#!/usr/bin/env python3
"""Parse the two source files into a small intermediate cache that
build_map.py assembles into the final HTML.

Inputs (in the repo root, one directory up from this script):
  Alpine Hydrants_9_23_26_Update.kmz   -- hydrant/tank points + status
  tl_2024_48043_roads.zip              -- TIGER/Line 2024 road centerlines,
                                           Brewster County

Outputs (written to build/cache/, not committed -- regenerate any time):
  pts.json    -- one dict per KMZ point: name, folder, style, lat, lon
  roads.pkl   -- (shapes, records) pair straight off the shapefile

Both source files are plain zip archives; nothing here needs anything
beyond the Python standard library.
"""
import re, struct, json, pickle, zipfile, collections, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path(__file__).resolve().parent / 'cache'
CACHE.mkdir(exist_ok=True)

KMZ = ROOT / 'Alpine Hydrants_9_23_26_Update.kmz'
ROADS_ZIP = ROOT / 'tl_2024_48043_roads.zip'


def parse_kmz(path):
    with zipfile.ZipFile(path) as z:
        kml = z.read('doc.kml').decode('utf-8')
    stack, out = [], []
    for m in re.finditer(
        r'<Folder[^>]*>\s*<name>([^<]*)</name>|</Folder>|<Placemark[^>]*>.*?</Placemark>',
        kml, re.S,
    ):
        s = m.group(0)
        if s.startswith('<Folder'):
            stack.append(m.group(1))
        elif s == '</Folder>':
            stack.pop()
        else:
            name = re.search(r'<name>([^<]*)</name>', s).group(1)
            style = re.search(r'<styleUrl>#([^<]*)', s).group(1)
            coords = re.search(r'<coordinates>\s*([^<]*)', s).group(1).strip().split(',')
            out.append(dict(name=name, folder=stack[-1], style=style,
                             lon=float(coords[0]), lat=float(coords[1])))
    return out


def parse_shapefile(zpath):
    with zipfile.ZipFile(zpath) as z:
        base = 'tl_2024_48043_roads'
        shp = z.read(base + '.shp')
        dbf = z.read(base + '.dbf')

    nrec, hl, rl = struct.unpack('<xxxxIHH', dbf[:12])
    fields, o = [], 32
    while dbf[o] != 0x0D:
        fields.append((dbf[o:o + 11].split(b'\0')[0].decode(), dbf[o + 16]))
        o += 32
    recs = []
    for i in range(nrec):
        r = dbf[hl + i * rl: hl + (i + 1) * rl]
        p, row = 1, {}
        for name, length in fields:
            row[name] = r[p:p + length].decode('latin1').strip()
            p += length
        recs.append(row)

    o, shapes = 100, []
    while o < len(shp):
        _, content_len = struct.unpack('>ii', shp[o:o + 8])
        b = o + 8
        shape_type = struct.unpack('<i', shp[b:b + 4])[0]
        if shape_type == 3:  # PolyLine
            npart, npts = struct.unpack('<ii', shp[b + 36:b + 44])
            parts = list(struct.unpack('<%di' % npart, shp[b + 44:b + 44 + 4 * npart])) + [npts]
            po = b + 44 + 4 * npart
            xy = struct.unpack('<%dd' % (2 * npts), shp[po:po + 16 * npts])
            shapes.append([[(xy[2 * k], xy[2 * k + 1]) for k in range(parts[j], parts[j + 1])]
                            for j in range(npart)])
        else:
            shapes.append([])
        o = b + content_len * 2
    return shapes, recs


def main():
    pts = parse_kmz(KMZ)
    print(f'{len(pts)} KMZ points')
    print(collections.Counter((p['folder'], p['style']) for p in pts))
    json.dump(pts, open(CACHE / 'pts.json', 'w'))

    shapes, recs = parse_shapefile(ROADS_ZIP)
    print(f'{len(recs)} road records')
    print(collections.Counter(r['MTFCC'] for r in recs))
    pickle.dump((shapes, recs), open(CACHE / 'roads.pkl', 'wb'))


if __name__ == '__main__':
    main()
