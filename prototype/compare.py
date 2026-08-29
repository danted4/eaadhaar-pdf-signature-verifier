#!/usr/bin/env python3
"""Compare our stamp render against PDF baseline (invalid state layout check)."""

from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).parent
BASE = ROOT / "baseline_invalid.png"


def diff_stats(a: Path, b: Path) -> dict:
    im_a = Image.open(a).convert("RGB")
    im_b = Image.open(b).convert("RGB")
    if im_a.size != im_b.size:
        im_b = im_b.resize(im_a.size, Image.Resampling.NEAREST)
    diff = ImageChops.difference(im_a, im_b)
    stat = ImageStat.Stat(diff)
    return {
        "size": im_a.size,
        "mean_rgb": [round(x, 2) for x in stat.mean],
        "rms": round(stat.rms[0], 2),
    }


if __name__ == "__main__":
    ours = ROOT / "stamp-valid.png"
    if not ours.exists():
        print("Export stamp-valid.png from stamp-lab.html first")
        raise SystemExit(1)
    if not BASE.exists():
        print("Missing baseline_invalid.png")
        raise SystemExit(1)
    stats = diff_stats(BASE, ours)
    print("Diff vs PDF baseline (invalid):", stats)
    print("Note: valid stamp should NOT match invalid baseline — use visual overlay in lab.")
