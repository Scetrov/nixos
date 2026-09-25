#!/usr/bin/env python3
"""Verify Build 42 world-tile -> private XYZ tile registration without game data."""

import importlib.util
import math
from pathlib import Path
import sys
import tempfile

from PIL import Image, ImageDraw


spec = importlib.util.spec_from_file_location("map_tiles", Path(__file__).resolve().parents[1] / "files/etc/nixos/modules/project-zomboid-map-tiles.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Same pixels-per-world-tile and inset as the game, on a 512-tile synthetic world.
module.WORLD_WIDTH = module.WORLD_HEIGHT = 512
module.INSET = 5
module.WORLD_IMAGE_SIZE = (266, 266)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = root / "worldmap.png"
    image = Image.new("RGB", module.WORLD_IMAGE_SIZE, "#1b2530")
    # World coordinate (400, 300) lands at pixel (205, 155) with inset 5.
    ImageDraw.Draw(image).rectangle((202, 152, 208, 158), fill=(240, 20, 20))
    image.save(source)
    assert module.render(source, root / "tiles", min_zoom=17, max_zoom=17) > 0
    span = module.TILE * 2 * module.ORIGIN / (module.TILE * 2**17)
    x, y = 400, 300
    tx = math.floor((module.ORIGIN + x) / span)
    ty = math.floor((module.ORIGIN + y) / span)
    path = root / "tiles" / "17" / str(tx) / f"{ty}.webp"
    with Image.open(path) as tile:
        px = round(((module.ORIGIN + x) / span - tx) * module.TILE)
        py = round(((module.ORIGIN + y) / span - ty) * module.TILE)
        red, green, blue, alpha = tile.getpixel((px, py))
        assert red > green * 2 and red > blue * 2 and alpha == 255, "player/world landmark does not align with tile"
    try:
        module.render(root / "tiles" / "17" / str(tx) / f"{ty}.webp", root / "bad", 17, 17)
    except ValueError:
        pass
    else:
        raise AssertionError("renderer accepted a non-B42 map asset")
print("PASS: in-game world X/Y map alignment, authenticated tile pyramid dimensions")
