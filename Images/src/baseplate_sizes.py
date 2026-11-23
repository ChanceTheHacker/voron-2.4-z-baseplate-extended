#!/usr/bin/env python3
"""Draw Images/baseplate_sizes.png: plates A and B from the floor side, with their tabs.

The plate outlines are slices of the real STL files, so the picture always matches the files.
The skirt ends and the bottom panel are drawn as Voron's 2.4r2 assembly places them relative to
Voron's plate (the side skirt 20 mm deep and flush with the plate's outer edge, the front and
rear skirts 20 mm deep and 1 mm proud of it, and the panel's edges 0.4 mm inside the skirts,
with a cut-out 2 mm outside Voron's plate), except that each skirt end is drawn GAP mm from
the plate's inner edge instead of Voron's 2 mm: the printer these plates are for, where the
5 mm tab just reaches the skirt.
"From the floor side" is looking down on the plate as it is printed (lip up), which is
how it looks with the printer turned upside down. Each plate is turned so that its two
inner edges are at the top and on the right.

Usage (from anywhere):
    uv run --with numpy --with manifold3d --with matplotlib python -I baseplate_sizes.py \
        VORON_STL_DIR STL_DIR OUT_PNG
VORON_STL_DIR is Voron-2/STLs/Z_Drive from github.com/VoronDesign/Voron-2.
STL_DIR is this repo's STLs folder. Needs the Noto Sans font installed.
"""
import struct
import sys
from pathlib import Path

import manifold3d as m3
import matplotlib
import numpy as np

matplotlib.use('Agg')
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

FONT = 'Noto Sans'
BACKGROUND = '#f6f8fa'
INK = '#1f2328'
MUTED = '#59636e'
VORON_FILL = '#d5dae0'
VORON_LINE = '#3d444d'
SIZES = [(3, '#0072b2'), (4, '#009e73'), (5, '#d55e00')]   # colour-blind-safe blue, green, vermilion
REC = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])
BODY_Z = 3.5     # slice through the plate's full outline
HOLES_Z = 6.5    # slice near the floor-side face: the holes as seen from the floor

SKIRT_FILL = '#e6e1d8'
SKIRT_LINE = '#8c7f6c'
PANEL_FILL = '#e9eef5'
PANEL_LINE = '#6e7781'
STUB = 9.0       # how much of each skirt and of the panel to draw, in mm
GAP = 5.0        # skirt end to Voron's plate edge as drawn (Voron's assembly has 2 mm)

PLATES = [  # letter, Voron file, turn (degrees, anticlockwise) to put the inner edges top and right,
            # corners, direction from the outer y edge towards the inner y edge in the file
    ('A', '[a]_z_drive_baseplate_a_x2.stl', 180, 'front-left and rear-right corners', -1),
    ('B', '[a]_z_drive_baseplate_b_x2.stl', -90, 'front-right and rear-left corners', +1),
]


def load(path):
    b = Path(path).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    v = np.frombuffer(b[84:84 + n * 50], dtype=REC)['v'].reshape(-1, 3).astype(np.float64)
    v[:, 2] -= v[:, 2].min()      # Voron's A file sits 217.57 mm up
    u, inv = np.unique(np.round(v, 4), axis=0, return_inverse=True)
    solid = m3.Manifold(m3.Mesh(vert_properties=u.astype(np.float32),
                                tri_verts=inv.reshape(-1, 3).astype(np.uint32)))
    if solid.status() != m3.Error.NoError:
        raise SystemExit(f'{path} is not a closed solid')
    return solid


def area(p):
    return 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])


def rings(solid, z):
    """Polygons of the slice at height z, largest first, each closed."""
    polys = sorted((np.asarray(p) for p in solid.slice(z).to_polygons()), key=lambda p: -abs(area(p)))
    return [np.vstack([p, p[:1]]) for p in polys]


def surroundings(voron, sy):
    """The two skirt ends and the bottom panel near one plate, in the file's coordinates.

    The low-x inner edge (the one with the slot) faces a side skirt; the other inner edge
    (low y on A, high y on B) faces the front or rear skirt."""
    x0, y0, _, x1, y1, _ = voron.bounding_box()
    oy, iy = (y1, y0) if sy < 0 else (y0, y1)          # outer and inner y edges
    def box(xa, xb, ya, yb):
        return m3.CrossSection.square((abs(xb - xa), abs(yb - ya))).translate((min(xa, xb), min(ya, yb)))
    side = box(x0 - GAP - STUB, x0 - GAP, oy, oy + sy * 20)
    front = box(x1 + 1, x1 - 19, iy + sy * GAP, iy + sy * (GAP + STUB))
    outline = voron.slice(BODY_Z)
    panel = box(x0 - GAP - STUB, x1 - 19.4, oy + sy * 20.4, iy + sy * (GAP + STUB))
    panel = panel - outline.offset(2.0, m3.JoinType.Round, circular_segments=96)
    return side, front, panel


def draw_region(ax, cs, tf, fill, line, hatch=None, dashed=False, z=1):
    for p in cs.to_polygons():
        p = tf(np.vstack([p, p[:1]]))
        ax.fill(p[:, 0], p[:, 1], facecolor=fill, edgecolor=line, hatch=hatch, lw=0, zorder=z)
        ax.plot(p[:, 0], p[:, 1], color=line, lw=1.6, ls=(0, (4, 3)) if dashed else '-', zorder=z + 0.5)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    voron_dir, stl_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    fm.findfont(fm.FontProperties(family=FONT), fallback_to_default=False)
    plt.rcParams.update({'font.family': FONT, 'text.color': INK})

    w_in, h_in, mm_per_in = 16, 9.2, 11.0
    fig = plt.figure(figsize=(w_in, h_in), dpi=100, facecolor=BACKGROUND)
    ax = fig.add_axes((0, 0, 1, 1))
    half_w, half_h = w_in * mm_per_in / 2, h_in * mm_per_in / 2
    ax.set_xlim(-half_w, half_w)
    ax.set_ylim(-half_h - 8, half_h - 8)
    ax.set_aspect('equal')
    ax.axis('off')

    fig.text(0.5, 0.925, 'Z drive base plates, seen from the floor side', ha='center',
             fontsize=30, weight='bold')
    fig.text(0.5, 0.865, "As they look with the printer upside down. Voron's plate is filled; the coloured "
             'lines are the 3, 4 and 5 mm tabs.', ha='center', fontsize=20, color=MUTED)

    label = dict(fontsize=19, color=MUTED, ha='center', va='center')
    titles, tops = [], []
    for i, (letter, name, turn, corners, sy) in enumerate(PLATES):
        voron = load(voron_dir / name)
        lo = np.array(voron.bounding_box()[:2])
        hi = np.array(voron.bounding_box()[3:5])
        centre = (lo + hi) / 2
        t = np.radians(turn)
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
        place = np.array([(-1 if i == 0 else 1) * 40.0, -20.5])

        def tf(p):
            return (p[:, :2] - centre) @ rot.T + place

        place[1] -= tf(rings(voron, BODY_Z)[0])[:, 1].min() - (place[1] - 21.5)   # same bottom line for A and B

        side, front, panel = surroundings(voron, sy)
        draw_region(ax, panel, tf, PANEL_FILL, PANEL_LINE, dashed=True, z=1)
        for skirt in (side, front):
            draw_region(ax, skirt, tf, SKIRT_FILL, SKIRT_LINE, hatch='///', z=1)
        top = max(tf(np.asarray(q))[:, 1].max() for cs in (side, front, panel) for q in cs.to_polygons())

        key = name.replace('_x2.stl', '')
        outlines = []
        for mm, colour in SIZES:
            ring = tf(rings(load(stl_dir / f'{key}_plus{mm}mm_x2.stl'), BODY_Z)[0])
            outlines.append(ring)
        for (mm, colour), ring in reversed(list(zip(SIZES, outlines))):
            ax.plot(ring[:, 0], ring[:, 1], color=colour, lw=3.2, solid_joinstyle='round', zorder=2 + mm)
        body = tf(rings(voron, BODY_Z)[0])
        ax.fill(body[:, 0], body[:, 1], color=VORON_FILL, zorder=10)
        ax.plot(body[:, 0], body[:, 1], color=VORON_LINE, lw=2.2, solid_joinstyle='round', zorder=12)
        for hole in rings(voron, HOLES_Z)[1:]:
            hole = tf(hole)
            ax.fill(hole[:, 0], hole[:, 1], color=BACKGROUND, zorder=12)
            ax.plot(hole[:, 0], hole[:, 1], color=VORON_LINE, lw=1.6, zorder=13)

        # Edge labels from the largest outline: inner edges at the top and right.
        big = outlines[-1]
        bx1, by1 = big.max(0)
        vx0, vy0 = body.min(0)
        mx, my = (vx0 + bx1) / 2, (vy0 + by1) / 2
        ax.text(vx0 - 2.6, my, 'outer edge, unchanged', rotation=90, **label)
        ax.text(mx, vy0 - 2.6, 'outer edge, unchanged', **label)
        tops.append(max(top, by1))
        titles.append((mx, letter, corners))

    top = max(tops)                      # one title line for both plates
    for mx, letter, corners in titles:
        ax.text(mx, top + 6.6, f'Plate {letter}', fontsize=25, weight='bold', ha='center', va='baseline')
        ax.text(mx, top + 3.0, corners, fontsize=20, ha='center', va='baseline')

    # Legend across the bottom.
    entries = ([("Voron's plate", None)] + [(f'{mm} mm tab', c) for mm, c in SIZES]
               + [(f'skirt end, {GAP:g} mm gap', 'skirt'), ('bottom panel', 'panel')])
    widths = [27.0, 20.0, 20.0, 20.0, 35.0, 24.0]
    x = -sum(widths) / 2
    y = -half_h - 8 + 5.5
    for (text, colour), w in zip(entries, widths):
        if colour is None:
            ax.add_patch(plt.Rectangle((x, y - 1.0), 3.2, 2.0, facecolor=VORON_FILL, edgecolor=VORON_LINE, lw=1.6))
        elif colour == 'skirt':
            ax.add_patch(plt.Rectangle((x, y - 1.0), 3.2, 2.0, facecolor=SKIRT_FILL, edgecolor=SKIRT_LINE,
                                       hatch='///', lw=1.6))
        elif colour == 'panel':
            ax.add_patch(plt.Rectangle((x, y - 1.0), 3.2, 2.0, facecolor=PANEL_FILL, edgecolor=PANEL_LINE,
                                       ls=(0, (2, 1.5)), lw=1.6))
        else:
            ax.plot([x, x + 3.2], [y, y], color=colour, lw=5, solid_capstyle='butt')
        ax.text(x + 4.4, y, text, fontsize=20, va='center')
        x += w

    fig.savefig(out, dpi=100, facecolor=BACKGROUND)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
