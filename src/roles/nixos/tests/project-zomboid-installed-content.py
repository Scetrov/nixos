#!/usr/bin/env python3
"""Validate the co-op starter-item contract against installed Build 42 media."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
items = ("Bag_DuffelBag", "CannedChili", "TinOpener", "WaterBottle", "HandAxe")
content = "\n".join(path.read_text(errors="replace") for path in (root / "media/scripts/generated/items").rglob("*.txt"))
for item in items:
    assert f"item {item}\n" in content, f"missing Base.{item}"
water_start = content.index("item WaterBottle\n")
water = content[water_start : content.index("\n    item ", water_start + 1)]
assert "PickRandomFluid = true" in water and "fluid = Water:1.0" in water
assert "fluid = CarbonatedWater:1.0" in water, "water bottle no longer needs live potability validation"
print("PASS: five Build 42 starter IDs present; WaterBottle randomizes its initial fluid")
