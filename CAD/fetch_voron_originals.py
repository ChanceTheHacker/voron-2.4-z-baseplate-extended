#!/usr/bin/env python3
"""Download the Voron Design originals this mod is made from, and check them.

The files come from github.com/VoronDesign/Voron-2 at a fixed commit, so a
rebuild always starts from exactly the same meshes. Each download is checked
against its SHA-256 before it is saved.

Usage (from the repository root):
    python3 CAD/fetch_voron_originals.py [DEST_DIR]
DEST_DIR defaults to CAD/voron_originals.

Copyright (C) 2026 ChanceTheHacker. Licensed under the GNU General Public
License v3.0; see LICENSE in the repository root.
"""
import hashlib
import sys
import urllib.parse
import urllib.request
from pathlib import Path

COMMIT = '7b32e405f0719881cca782500c822e01e3b16bf2'
BASE = f'https://raw.githubusercontent.com/VoronDesign/Voron-2/{COMMIT}/STLs/Z_Drive/'
FILES = {
    '[a]_z_drive_baseplate_a_x2.stl':
        'f368fe689562dfc31adda88f450a80cf839795fbe80951f6927cdb2c56979bb0',
    '[a]_z_drive_baseplate_b_x2.stl':
        'f791f01457ee5a39fb2af0dab971b02535e5921b436fcb9ae0e25e1f9f95c93f',
}


def main():
    default = Path(__file__).resolve().parent / 'voron_originals'
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    dest.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        with urllib.request.urlopen(BASE + urllib.parse.quote(name), timeout=60) as response:
            data = response.read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SystemExit(f'{name}: SHA-256 {actual} does not match {expected}')
        (dest / name).write_bytes(data)
        print(f'{name}: downloaded and checked')


if __name__ == '__main__':
    main()
