"""Render Images/overview.png: Voron's base plate A in grey, then plate A at +3, +4 and +5 mm.

All four sit as printed (lip up), lined up on their outer corner, so the tabs on the two
inner edges (the edges facing the camera) can be compared by eye.

Usage (from anywhere):
    blender -b --factory-startup -P render_overview.py -- VORON_STL_DIR STL_DIR OUT_PNG
VORON_STL_DIR is Voron-2/STLs/Z_Drive from github.com/VoronDesign/Voron-2.
STL_DIR is this repo's STLs folder.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio  # noqa: E402

OUTER_CORNER = (92.47, 47.79)   # corner between plate A's two outer edges, in every file
SPACING = 60.0                  # mm between outer corners

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 3:
        raise SystemExit(__doc__)
    voron_dir, stl_dir, out = Path(args[0]), Path(args[1]), Path(args[2])
    studio.reset()
    grey = studio.part_material(studio.VORON_GREY, 'voron')
    green = studio.part_material(studio.MOD_GREEN, 'mod')
    parts = [(voron_dir / '[a]_z_drive_baseplate_a_x2.stl', grey)]
    parts += [(stl_dir / f'[a]_z_drive_baseplate_a_plus{mm}mm_x2.stl', green) for mm in (3, 4, 5)]
    for i, (path, mat) in enumerate(parts):
        obj = studio.load_stl(path)
        studio.paint(obj, mat)
        studio.place(obj, x=i * SPACING, origin=OUTER_CORNER)
    studio.lighting()
    studio.camera_three_quarter(1600, 640, azimuth=-14, elevation=42)
    studio.render(out)
