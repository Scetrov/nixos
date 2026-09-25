#!/usr/bin/env python3
"""Render the installed Build 42 in-game world map as private XYZ tiles.

World coordinates are game tiles with origin (0, 0), X right and Y down.
The installed worldmap.png is the game's tourist map: 2 world tiles per
image pixel, inset by 125 image pixels (250 world tiles) on each side.
The game world is placed at the Web Mercator equator at 1 metre per tile;
Grafana markers must use lon = X / 111319.4908 and lat ~= -Y / 111319.4908.
No copyrighted image or generated tile is stored in the source repository.
"""

import argparse
import math
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ORIGIN = 20037508.342789244
WORLD_WIDTH = 19968
WORLD_HEIGHT = 16128
WORLD_IMAGE_SIZE = (10234, 8314)
INSET = 125
TILE = 256


def tile_bounds(zoom: int) -> tuple[range, range, float]:
    resolution = 2 * ORIGIN / (TILE * 2**zoom)
    span = TILE * resolution
    start = math.floor(ORIGIN / span)
    return (
        range(start, math.floor((ORIGIN + WORLD_WIDTH) / span) + 1),
        range(start, math.floor((ORIGIN + WORLD_HEIGHT) / span) + 1),
        resolution,
    )


def render(source: Path, output: Path, min_zoom: int = 11, max_zoom: int = 17) -> int:
    with Image.open(source) as original:
        if original.size != WORLD_IMAGE_SIZE:
            raise ValueError(f"Unexpected Build 42 map dimensions: {original.size}")
        # Strip the native 250-world-tile margin to align image pixel 0,0
        # with game coordinate 0,0. Two game tiles correspond to one pixel.
        image = original.convert("RGB").crop(
            (INSET, INSET, INSET + WORLD_WIDTH // 2, INSET + WORLD_HEIGHT // 2)
        )
    count = 0
    for zoom in range(min_zoom, max_zoom + 1):
        xs, ys, resolution = tile_bounds(zoom)
        span = TILE * resolution
        for x in xs:
            for y in ys:
                left = x * span - ORIGIN
                top = y * span - ORIGIN
                right = min(WORLD_WIDTH, left + span)
                bottom = min(WORLD_HEIGHT, top + span)
                if right <= 0 or bottom <= 0 or left >= WORLD_WIDTH or top >= WORLD_HEIGHT:
                    continue
                left_clipped, top_clipped = max(0, left), max(0, top)
                # Pillow's EXTENT resampler reads source coordinates directly;
                # out-of-bounds samples become transparent on the RGBA tile.
                patch = image.transform(
                    (TILE, TILE), Image.Transform.EXTENT,
                    ((left - 0) / 2, top / 2, (left + span) / 2, (top + span) / 2),
                    resample=Image.Resampling.BILINEAR,
                ).convert("RGBA")
                if left < 0 or top < 0 or right < left + span or bottom < top + span:
                    # Blank the world outside valid map bounds instead of
                    # extending edge pixels over uncharted territory.
                    px0 = max(0, math.ceil((left_clipped - left) / resolution))
                    py0 = max(0, math.ceil((top_clipped - top) / resolution))
                    px1 = min(TILE, math.floor((right - left) / resolution))
                    py1 = min(TILE, math.floor((bottom - top) / resolution))
                    alpha = Image.new("L", (TILE, TILE))
                    if px1 > px0 and py1 > py0:
                        alpha.paste(255, (px0, py0, px1, py1))
                    patch.putalpha(alpha)
                target = output / str(zoom) / str(x) / f"{y}.webp"
                target.parent.mkdir(parents=True, exist_ok=True)
                patch.save(target, quality=82, method=4)
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-zoom", type=int, default=11)
    parser.add_argument("--max-zoom", type=int, default=17)
    args = parser.parse_args()
    if not 0 <= args.min_zoom <= args.max_zoom <= 19:
        parser.error("zoom must be between 0 and 19")
    print(f"Rendered {render(args.source, args.output, args.min_zoom, args.max_zoom)} private Build 42 map tiles")


if __name__ == "__main__":
    main()
