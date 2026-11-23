#!/usr/bin/env python3
"""Make Voron 2.4r2 Z drive base plates with a tab on each inner edge.

The base plate ([a]_z_drive_baseplate_a/b_x2.stl) sits under each Z drive and carries the
rubber foot. Two of its edges face outwards (the frame's outer faces); the other two face into
the printer, where the side skirt and the front or rear skirt end. These versions add a tab of
3, 4 or 5 mm to each inner edge, only where a skirt ends, so the plate reaches out to the skirt
ends.
Everything else (the outer edges, the rest of the inner edges, the big rounded corner between
them, the holes, the nut pocket and the foot seat) is exactly as Voron made it.

Where the tabs are, in Voron's print orientation (drive side down on the bed):
- On the inner edge with the slot (low x), the tab covers the 19 mm next to the outer edge.
  The side skirt's inner face is 20 mm from that outer edge and the bottom panel's cut-out
  20.4 mm, so the tab stops 1 mm short of the skirt and keeps Voron's clearance of about
  1.4 mm to the panel. The panel therefore still fits without trimming.
- On the other inner edge (low y on A, high y on B), the tab covers the 18 mm next to the
  outer edge; the front or rear skirt's inner face is 19 mm away and the panel 19.4 mm.
- Each tab is the full 7 mm plate thickness and reaches the full size out. The slot is carried
  straight out through its tab, keeping Voron's 2 mm rounded mouth corners. The tab's free
  corner is rounded to 2 mm; the inside corner where it meets Voron's edge is left sharp.
- Every new edge, including the tab ends, has Voron's edge shape: a 0.4 mm chamfer on the bed
  side and a 1 mm round on the floor side.

How a tab is made: Voron's plate is cut by a line a few millimetres in from the edge, along the
tab only, and the strip outside the cut is moved out by the tab size. The gap is filled with
the plate's own cross-section at the cut, so the moved edge (slot, mouth corners, outer
corner and Voron's raised top near the edge) is Voron's own shape. In the two places where
Voron's top rises above 7 mm near the edge (beside the slot, and along the other edge
towards the outer corner), the tab therefore keeps Voron's height there, up to about 7.4 mm.
The edge between the tab and Voron's untouched edge is rebuilt from Voron's own edge-shape rows: a mitred inside corner, the tab end, the 2 mm round and the
moved edge. The flat bed and top faces are triangulated again from their outlines. The
script builds the mesh directly rather than with a boolean union, so every edge is shared by
exactly two triangles and none has zero area; it checks that, and that nothing of Voron's
plate was removed or added outside the tabs, before writing each file.

A and B are each made from Voron's own file. B is a mirror image of A, so B is handled in a
mirrored frame (its y flipped) and turned back on output.

Usage (from the repository root):
    python3 CAD/fetch_voron_originals.py
    uv run --with numpy==2.5.5 --with manifold3d==3.5.5 python -I CAD/make_baseplates.py [VORON_STL_DIR] [OUT_DIR] [--sizes 3,4,5]
VORON_STL_DIR defaults to CAD/voron_originals (filled by fetch_voron_originals.py, which
downloads Voron's two base plate files at a fixed commit and checks their SHA-256). OUT_DIR
defaults to the repository's STLs folder. Sizes may be 0.5 to 10 mm; below 2 mm the tab's
free corner is rounded to the tab size instead of 2 mm.

Derived from Voron Design's [a]_z_drive_baseplate_a_x2.stl and _b_x2.stl
(github.com/VoronDesign/Voron-2, GPL-3.0). Modifications copyright (C) 2026 ChanceTheHacker,
also under the GNU General Public License v3.0; see LICENSE in the repository root.
"""
import math
import struct
from pathlib import Path

import manifold3d as m3
import numpy as np

SIZES = (3, 4, 5)
THICK = 7.0          # plate thickness along the inner edges
SLOT_TAB = 19.0      # tab on the slotted inner edge: length from the outer edge
OTHER_TAB = 18.0     # tab on the other inner edge: length from the outer edge
END_R = 2.0          # rounding of the tab's free corner
ARC_SEG = 12         # segments in that quarter circle
REC = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])

# Positions in a frame where the plate's corner between its inner edges is at x = y = 0 (for
# B, y is mirrored so both plates read the same). Voron's straight edges carry rows of
# vertices for the edge shape; the rebuilt part of each edge runs between two of them.
SLOT_ROWS = (19.5, 26.5)       # slotted edge: end of the big corner, start of the slot's mouth
OTHER_ROWS = (19.5, 28.655)    # other edge: end of the big corner, start of the raised top
OTHER_LOW_ROW = 41.0           # where its chamfer and flat face end (start of the outer corner)
# The cut lines, kept at least 0.15 mm from Voron's vertices: for the slotted edge 3.25 mm in;
# for the other edge 1.15 mm in, passing under the nut pocket, then stepping out to 3.3 mm to
# clear the outer corner before it meets the outer edge.
SLOT_CUT = 3.25
OTHER_CUT = ((0.0, 1.15), (41.5, 1.15), (42.6, 3.3), (60.0, 3.3))

PLATES = {
    'a': {'src': '[a]_z_drive_baseplate_a_x2.stl', 'mirror': False},
    'b': {'src': '[a]_z_drive_baseplate_b_x2.stl', 'mirror': True},
}


def load(path):
    b = Path(path).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    return np.frombuffer(b[84:84 + n * 50], dtype=REC)['v'].reshape(-1, 3, 3).astype(np.float64)


def save(path, tris, label):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1
    rec = np.zeros(len(tris), dtype=REC)
    rec['n'] = n / ln[:, None]
    rec['v'] = tris.reshape(-1, 9)
    with open(path, 'wb') as f:
        f.write(label.encode()[:80].ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        f.write(rec.tobytes())


def weld(tris):
    """Vertices and faces, joining corners at exactly the same single-precision position."""
    v, inv = np.unique(tris.astype(np.float32).reshape(-1, 3), axis=0, return_inverse=True)
    return v, inv.reshape(-1, 3)


def to_manifold(tris):
    v, f = weld(tris)
    return m3.Manifold(m3.Mesh(vert_properties=v, tri_verts=f.astype(np.uint32)))


def other_cut(x):
    return np.interp(x, *zip(*OTHER_CUT))


class Build:
    """Voron's plate in the shared frame, with the tabs added by mesh surgery."""

    def __init__(self, tris, mirror):
        self.mirror = mirror
        v, f = np.unique(tris.reshape(-1, 3), axis=0, return_inverse=True)
        f = f.reshape(-1, 3)
        self.lo, self.hi = v.min(0), v.max(0)
        p = v - [self.lo[0], self.lo[1], 0]
        if mirror:
            p[:, 1] = self.hi[1] - v[:, 1]
            f = f[:, ::-1]
        self.P = [q for q in p]          # positions; new points are appended
        self.F = f
        self.size = self.hi - self.lo

    def add(self, q):
        self.P.append(np.asarray(q, dtype=np.float64))
        return len(self.P) - 1

    def to_world(self, tris):
        out = tris.copy()
        out[..., 0] += self.lo[0]
        if self.mirror:
            out[..., 1] = self.hi[1] - out[..., 1]
            out = out[:, ::-1]
        else:
            out[..., 1] += self.lo[1]
        return out

    def find(self, along_axis, at, points, tol=2e-3):
        """Vertex indices of the edge-shape row at `at` along the edge (inset, height pairs)."""
        P = np.array(self.P)
        out = []
        for inset, z in points:
            m = ((abs(P[:, along_axis] - at) < tol) & (abs(P[:, 1 - along_axis] - inset) < tol)
                 & (abs(P[:, 2] - z) < tol))
            hit = np.flatnonzero(m)
            if len(hit) != 1:
                raise SystemExit(f'edge row at {at:.3f} not found in Voron\'s mesh ({len(hit)} matches)')
            out.append(int(hit[0]))
        return out


def extend(tris, d, mirror):
    """Voron's plate with the two tabs, d mm out. Returns triangles in Voron's coordinates."""
    b = Build(tris, mirror)
    P0 = np.array(b.P)
    F = b.F
    tri = P0[F]
    ext = b.size

    # Voron's edge shape, read from the slotted edge's row where the big corner ends.
    m = (abs(P0[:, 1] - SLOT_ROWS[0]) < 2e-3) & (P0[:, 0] < 1 + 2e-3)
    shape = sorted(((q[0], q[2]) for q in P0[m]), key=lambda s: s[1])
    if (len(shape) != 13 or abs(shape[0][0] - 0.4) > 1e-3 or abs(shape[0][1]) > 1e-6
            or abs(shape[-1][0] - 1) > 1e-3 or abs(shape[-1][1] - THICK) > 1e-3):
        raise SystemExit("Voron's edge shape is not where expected")

    # Faces to be rebuilt: the flat bed and top faces, and the two stretches of edge being rebuilt.
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nz = n[:, 2] / np.linalg.norm(n, axis=1)
    zs = tri[:, :, 2]
    cap = (abs(nz) > 0.999) & (np.all(abs(zs) < 5e-3, axis=1) | np.all(abs(zs - THICK) < 5e-3, axis=1))
    eps = 1e-3

    def zone(along, a0, a1, inset_max, zmax=99.0):
        u, v = tri[:, :, along], tri[:, :, 1 - along]
        return (np.all((u > a0 - eps) & (u < a1 + eps) & (v < inset_max + eps) & (zs < zmax + eps), axis=1)
                & (u.max(1) - u.min(1) > eps))
    slot_zone = zone(1, *SLOT_ROWS, 1.0)
    other_zone = zone(0, *OTHER_ROWS, 1.0) | zone(0, OTHER_ROWS[0], OTHER_LOW_ROW, 0.4, 6.2)
    keep = ~(cap | slot_zone | other_zone)

    # The two moved regions: (test on a triangle's corners, signed distance to the cut, shift).
    slot_end = ext[1] - SLOT_TAB             # tab end along the slotted edge
    other_end = ext[0] - OTHER_TAB
    slot_from = (slot_end + END_R + SLOT_ROWS[1]) / 2
    other_from = (other_end + END_R + OTHER_ROWS[1]) / 2
    regions = [
        (lambda q: q[..., 1] > slot_from, lambda q: q[..., 0] - SLOT_CUT, np.array([-d, 0, 0])),
        (lambda q: q[..., 0] > other_from, lambda q: q[..., 1] - other_cut(q[..., 0]), np.array([0, -d, 0])),
    ]
    moved = [dict(), dict()]          # original vertex -> moved copy, per region
    crossing = {}                     # (region, edge) -> (static copy, moved copy)

    def mv(r, i):
        if i not in moved[r]:
            moved[r][i] = b.add(b.P[i] + regions[r][2])
        return moved[r][i]

    def cross(r, i, j):
        key = (r, min(i, j), max(i, j))
        if key not in crossing:
            f = regions[r][1]
            a, c = b.P[key[1]], b.P[key[2]]
            fa = f(a)
            lo_t, hi_t = 0.0, 1.0
            for _ in range(80):
                t = (lo_t + hi_t) / 2
                if (f(a + t * (c - a)) < 0) == (fa < 0):
                    lo_t = t
                else:
                    hi_t = t
            q = a + (lo_t + hi_t) / 2 * (c - a)
            s = b.add(q)
            crossing[key] = (s, b.add(q + regions[r][2]))
        return crossing[key]

    out = []
    for t in F[keep]:
        q = P0[t]
        placed = False
        for r, (inside, f, shift) in enumerate(regions):
            ins = inside(q)
            if not ins.any():
                continue
            fv = f(q)
            if not ins.all():
                if np.any(ins & (fv < 0)):
                    raise SystemExit('a triangle straddles the end of a moved region')
                continue
            if np.any(abs(fv) < 0.02):
                raise SystemExit('a cut line passes too close to one of Voron\'s vertices')
            neg = fv < 0
            if not neg.any():
                continue
            if neg.all():
                out.append([mv(r, i) for i in t])
            elif neg.any():
                # Split along the cut: the lone corner's piece and the other two corners' piece.
                k = int(np.flatnonzero(neg == (neg.sum() == 1))[0])
                a, bb, c = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
                p, s = cross(r, a, bb), cross(r, a, c)     # each (static, moved)
                lone_moved = bool(neg[k])
                side = 1 if lone_moved else 0
                out.append([mv(r, a) if lone_moved else a, p[side], s[side]])
                o = 0 if lone_moved else 1
                B_ = mv(r, bb) if not lone_moved else bb
                C_ = mv(r, c) if not lone_moved else c
                # Two-corner piece: quad p, bb, c, s; split along the shorter diagonal.
                if np.linalg.norm(b.P[p[0]] - b.P[c]) <= np.linalg.norm(b.P[bb] - b.P[s[0]]):
                    out += [[p[o], B_, C_], [p[o], C_, s[o]]]
                else:
                    out += [[p[o], B_, s[o]], [B_, C_, s[o]]]
                # Fill the gap: the static piece holds the cut edge in one direction.
                e0, e1 = (p, s) if not lone_moved else (s, p)     # static directed edge e0 -> e1
                out += [[e1[0], e0[0], e0[1]], [e1[0], e0[1], e1[1]]]
            placed = True
            break
        if not placed:
            out.append(list(t))

    # Rebuild each edge stretch from Voron's edge-shape rows.
    def sweep(along, start_row, end_rows, tab_end):
        """Edge shape from Voron's row at start_row, mitred at the tab end, round the free
        corner and along the moved edge to Voron's (moved) rows. Coordinates (along, inset, z)."""
        def xyz(u, v, z):
            return (v, u, z) if along == 1 else (u, v, z)
        r = 0 if along == 1 else 1
        stations = [b.find(along, start_row, shape)]
        stations.append([b.add(xyz(tab_end + i, i, z)) for i, z in shape])           # mitre
        # The free corner's round: END_R, or the tab size when the tab is shorter than that. Rows of
        # the edge shape set in further than the radius meet in a sharp corner instead.
        rad = min(END_R, d)
        cu, cv = tab_end + rad, -d + rad
        for k in range(ARC_SEG + 1):
            a = math.pi * (1 + 0.5 * k / ARC_SEG)
            row = []
            for j, (i, z) in enumerate(shape):
                if i >= rad:
                    u, v = tab_end + i, -d + i
                elif k == 0:
                    u, v = tab_end + i, cv
                elif k == ARC_SEG:
                    u, v = cu, -d + i
                else:
                    u, v = cu + (rad - i) * math.cos(a), cv + (rad - i) * math.sin(a)
                q = np.array(xyz(u, v, z))
                prev = stations[-1][j]
                row.append(prev if np.linalg.norm(b.P[prev] - q) < 1e-9 else b.add(q))
            stations.append(row)
        last = []
        for k, (at, ks) in enumerate(end_rows):
            last.append({kk: mv(r, i) for kk, i in zip(ks, b.find(along, at, [shape[kk] for kk in ks]))})
        faces = []
        for A, B_ in zip(stations, stations[1:]):
            for k in range(len(shape) - 1):
                faces += [[A[k], B_[k], A[k + 1]], [A[k + 1], B_[k], B_[k + 1]]]
        return stations[-1], last, faces, along == 1

    def emit(faces, flip):
        faces = [f for f in faces if len(set(f)) == 3]      # drop the halves of collapsed quads
        out.extend([f[::-1] for f in faces] if flip else faces)

    # Slotted edge: every row point of Voron's mouth-corner row exists.
    allk = list(range(len(shape)))
    end, (last,), faces, flip = sweep(1, SLOT_ROWS[0], [(SLOT_ROWS[1], allk)], slot_end)
    for k in range(len(shape) - 1):
        faces += [[end[k], last[k], end[k + 1]], [end[k + 1], last[k], last[k + 1]]]
    emit(faces, flip)

    # Other edge: the round reaches Voron's row at the raised top; the chamfer and the flat face
    # run on to the outer corner's row, and the flat face takes in the raised top's foot.
    up = allk[2:]
    end, (last, low), faces, flip = sweep(0, OTHER_ROWS[0], [(OTHER_ROWS[1], up), (OTHER_LOW_ROW, [0, 1])],
                                          other_end)
    for k in up[:-1]:
        faces += [[end[k], last[k], end[k + 1]], [end[k + 1], last[k], last[k + 1]]]
    faces += [[end[0], low[0], end[1]], [end[1], low[0], low[1]]]                       # chamfer
    foot = b.find(0, OTHER_ROWS[1], [(0.0, 6.123)], tol=2e-3)[0]
    top41 = b.find(0, OTHER_LOW_ROW, [(0.0, 6.123)], tol=2e-3)[0]
    f_, t41, r0 = mv(1, foot), mv(1, top41), last[2]
    faces += [[r0, end[2], end[1]], [r0, end[1], low[1]], [r0, low[1], t41], [r0, t41, f_]]
    emit(faces, flip)

    # Flat bed and top faces, triangulated again from the open outlines left by everything else.
    P = np.array(b.P)
    out = np.array(out, dtype=np.int64)
    directed = np.concatenate([out[:, [0, 1]], out[:, [1, 2]], out[:, [2, 0]]])
    _, cnt = np.unique(directed, axis=0, return_counts=True)
    if cnt.max() > 1:
        raise SystemExit('an edge is used twice in the same direction')
    have = set(map(tuple, directed.tolist()))
    open_edges = [(i, j) for i, j in directed.tolist() if (j, i) not in have]
    caps, done = [], set()
    for level, up_facing in ((0.0, False), (THICK, True)):
        es = [(i, j) for i, j in open_edges if abs(P[i, 2] - level) < 5e-3 and abs(P[j, 2] - level) < 5e-3]
        nxt = {}
        for i, j in es:
            a, c = (j, i) if up_facing else (i, j)       # outline wound anticlockwise seen from above
            if a in nxt:
                raise SystemExit('the outline of a flat face branches')
            nxt[a] = c
        loops, seen = [], set()
        for s in sorted(nxt):
            if s in seen:
                continue
            loop, c = [], s
            while c not in seen:
                seen.add(c)
                loop.append(c)
                c = nxt[c]
            if c != s:
                raise SystemExit('the outline of a flat face does not close')
            loops.append(loop)
        idx = np.concatenate(loops)
        t = m3.triangulate([P[lp][:, :2] for lp in loops])
        t = idx[np.asarray(t)]
        caps.append(t if up_facing else t[:, ::-1])
        done.update(es)
    open_edges = [e for e in open_edges if e not in done]
    if open_edges:
        raise SystemExit(f'{len(open_edges)} edges are left open off the flat faces')
    out = np.concatenate([out] + caps)
    return b.to_world(P[out])


def check(name, voron, tris, d, mirror):
    """Confirm the file is a clean closed solid, Voron's plate is intact and only the tabs were added."""
    v, f = weld(tris)
    t32 = v[f].astype(np.float64)
    area = 0.5 * np.linalg.norm(np.cross(t32[:, 1] - t32[:, 0], t32[:, 2] - t32[:, 0]), axis=1)
    directed = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    und = np.sort(directed, axis=1)
    _, ucnt = np.unique(und, axis=0, return_counts=True)
    _, dcnt = np.unique(directed, axis=0, return_counts=True)
    clean = bool(ucnt.min() == 2 and ucnt.max() == 2 and dcnt.max() == 1 and area.min() > 1e-6)
    solid = to_manifold(tris)
    plate = to_manifold(voron)
    closed = solid.status() == m3.Error.NoError
    parts = len(solid.decompose())

    # Shared frame: x from Voron's inner edge, y from the other inner edge (mirrored on B).
    lo, hi = voron.reshape(-1, 3).min(0), voron.reshape(-1, 3).max(0)

    def frame(p):
        q = p.reshape(-1, 3) - [lo[0], 0, 0]
        q[:, 1] = hi[1] - q[:, 1] if mirror else q[:, 1] - lo[1]
        return q
    q, size = frame(v.astype(np.float64)), hi - lo
    slot_end, other_end = size[1] - SLOT_TAB, size[0] - OTHER_TAB
    out_x, out_y = q[:, 0] < -1e-4, q[:, 1] < -1e-4
    slot_span = (q[out_x, 1].min(), q[out_x, 1].max())
    other_span = (q[out_y, 0].min(), q[out_y, 0].max())
    edges_ok = (abs(q[:, 0].min() + d) < 1e-4 and abs(q[:, 1].min() + d) < 1e-4
                and abs(q[:, 0].max() - size[0]) < 1e-4 and abs(q[:, 1].max() - size[1]) < 1e-4
                and slot_span[0] > slot_end - 1e-4 and other_span[0] > other_end - 1e-4
                and abs(q[out_x, 0].min() + d) < 1e-4 and abs(q[out_y, 1].min() + d) < 1e-4)

    # Added material may only lie in the tabs and the strip they were joined along.
    def box(x0, x1, y0, y1):
        ya, yb = (hi[1] - y1, hi[1] - y0) if mirror else (lo[1] + y0, lo[1] + y1)
        return m3.Manifold.cube((x1 - x0, yb - ya, 20)).translate((lo[0] + x0, ya, -5))
    allowed = (box(-d - 1, SLOT_CUT + 0.01, slot_end, size[1] + 1)
               + box(other_end, size[0] + 1, -d - 1, max(c for _, c in OTHER_CUT) + 0.01))
    removed = (plate - solid).volume()
    added = solid - plate
    stray = (added - allowed).volume()
    ok = clean and closed and parts == 1 and solid.genus() == plate.genus() and removed < 1e-3 \
        and stray < 1e-3 and edges_ok
    print(f'{name} +{d} mm: {len(f)} triangles, smallest {area.min():.4f} mm2, every edge shared by two '
          f'triangles in opposite directions {clean}, closed solid {closed}, pieces {parts}, genus '
          f'{solid.genus()} (Voron {plate.genus()}), volume {solid.volume() / 1000:.3f} cm3 (Voron '
          f'{plate.volume() / 1000:.3f}), Voron material removed {removed:.5f} mm3, added outside the tabs '
          f'{stray:.5f} mm3, outer edges unmoved and tabs {d} mm out {edges_ok}; slotted-edge tab '
          f'{size[1] - slot_span[0]:.2f} mm long from the outer edge (panel clearance '
          f'{slot_span[0] - (size[1] - 20.4):.2f} mm), other tab {size[0] - other_span[0]:.2f} mm '
          f'(panel clearance {other_span[0] - (size[0] - 19.4):.2f} mm)')
    if not ok:
        raise SystemExit(f'{name} +{d} mm failed its check')


if __name__ == '__main__':
    import argparse
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description='Make Voron 2.4r2 Z drive base plates with a tab on each inner edge.')
    ap.add_argument('src', nargs='?', type=Path, default=here / 'voron_originals',
                    help="folder holding Voron's [a]_z_drive_baseplate_a_x2.stl and _b_x2.stl")
    ap.add_argument('out', nargs='?', type=Path, default=here.parent / 'STLs')
    ap.add_argument('--sizes', default='3,4,5',
                    help='how far the tabs reach out, in millimetres, comma separated (default 3,4,5)')
    args = ap.parse_args()
    SIZES = tuple(float(x) if '.' in x else int(x) for x in args.sizes.split(','))
    if any(not 0.5 <= d <= 10 for d in SIZES):
        ap.error('sizes must be between 0.5 and 10 mm')
    src, out = args.src, args.out
    out.mkdir(parents=True, exist_ok=True)
    for key, cfg in PLATES.items():
        voron = load(src / cfg['src'])
        voron[:, :, 2] -= voron[:, :, 2].min()     # Voron's A file sits 217.57 mm up; put both on the bed
        for d in SIZES:
            tris = extend(voron, d, cfg['mirror'])
            check(key.upper(), voron, tris, d, cfg['mirror'])
            save(out / f'[a]_z_drive_baseplate_{key}_plus{d}mm_x2.stl', tris.astype(np.float32),
                 f'Voron 2.4r2 Z drive base plate {key.upper()}, inner-edge tabs +{d} mm')
