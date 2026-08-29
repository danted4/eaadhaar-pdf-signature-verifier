#!/usr/bin/env python3
"""Headless stamp validation against PDF baseline and color checks."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

from PIL import Image

ROOT = Path(__file__).parent


def run_node_render() -> None:
    subprocess.run(
        ["node", "--input-type=module", "-e", NODE_RENDER],
        cwd=ROOT,
        check=True,
    )


NODE_RENDER = r"""
import { createCanvas } from 'canvas';
import { drawStamp, FORM_W, FORM_H } from './stamp-render.js';
import fs from 'fs';
const s = 16;
for (const [valid, name] of [[true,'stamp-valid.png'],[false,'our_invalid.png']]) {
  const c = createCanvas(FORM_W*s, FORM_H*s);
  drawStamp(c.getContext('2d'), s, valid);
  fs.writeFileSync(name, c.toBuffer('image/png'));
}
"""


def similarity(a: Image.Image, b: Image.Image) -> tuple[float, float]:
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.NEAREST)
    total = close = 0
    pixels = a.size[0] * a.size[1]
    for y in range(a.size[1]):
        for x in range(a.size[0]):
            pa = a.getpixel((x, y))
            pb = b.getpixel((x, y))
            d = sum(abs(pa[i] - pb[i]) for i in range(3))
            total += d
            if d < 35:
                close += 1
    return close / pixels * 100, (1 - total / (pixels * 3 * 255)) * 100


def analyze_valid(img: Image.Image) -> dict:
    greens: list[tuple[int, int, int]] = []
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if g > 70 and g > r + 12 and g > b + 8:
                greens.append((r, g, b))
    if not greens:
        return {"green_pixels": 0}
    from collections import Counter

    top = Counter(greens).most_common(3)
    xs = [x for y in range(img.size[1]) for x in range(img.size[0]) if img.getpixel((x, y))[1] > 70 and img.getpixel((x, y))[1] > img.getpixel((x, y))[0] + 12]
    ys = [y for y in range(img.size[1]) for x in range(img.size[0]) if img.getpixel((x, y))[1] > 70 and img.getpixel((x, y))[1] > img.getpixel((x, y))[0] + 12]
    return {
        "green_pixels": len(greens),
        "top_colors": [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top],
        "bbox_pt": (round(min(xs) / 16, 1), round(min(ys) / 16, 1), round(max(xs) / 16, 1), round(max(ys) / 16, 1)),
    }


def main() -> int:
    run_node_render()
    baseline = Image.open(ROOT / "baseline_invalid.png").convert("RGB")
    invalid = Image.open(ROOT / "our_invalid.png").convert("RGB")
    valid = Image.open(ROOT / "stamp-valid.png").convert("RGB")

    close_pct, sim_pct = similarity(baseline, invalid)
    print(f"INVALID vs PDF baseline:")
    print(f"  similarity:   {sim_pct:.1f}%")
    print(f"  close pixels: {close_pct:.1f}%")

    info = analyze_valid(valid)
    print(f"\nVALID stamp:")
    for k, v in info.items():
        print(f"  {k}: {v}")

    ok = sim_pct >= 95 and info.get("green_pixels", 0) > 500
    if info.get("top_colors") and info["top_colors"][0] not in ("#00a651", "#00a650", "#00a652", "#01a651"):
        print(f"  WARN: dominant green {info['top_colors'][0]} (target #00a651)")

    print(f"\n{'PASS' if ok else 'REVIEW'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
