"""Measure how well the receipt reader does on real photos and harder variants.

Ground truth lives next to each photo:  data/tickets/<name>.jpg + <name>.truth.json
(data/tickets/ is git-ignored: receipts carry a Losnummer and are bearer slips).

Every photo is also degraded on purpose (tilt, sideways, blur, low resolution,
heavy JPEG, dim light, perspective) to see where reading breaks.

    .venv/Scripts/python.exe scripts/eval_ticket_ocr.py [--quick]

Pass = every number, the Superzahl and the first draw date read correctly.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import date
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lotto.ticket.scan import scan_image  # noqa: E402


def _jpeg(img: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _perspective(img: Image.Image, k: float) -> Image.Image:
    w, h = img.size
    d = k * w
    # top edge narrower than the bottom: phone held at an angle
    coeffs = _find_coeffs([(d, 0), (w - d, 0), (w, h), (0, h)], [(0, 0), (w, 0), (w, h), (0, h)])
    return img.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)


def _find_coeffs(src, dst):
    import numpy as np

    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(rows, dtype=float)
    b = np.array(src, dtype=float).reshape(8)
    return np.linalg.solve(a, b).tolist()


VARIANTS = {
    "original": lambda im: _jpeg(im),
    "tilt +3": lambda im: _jpeg(im.rotate(3, expand=True, fillcolor=(20, 20, 20))),
    "tilt -6": lambda im: _jpeg(im.rotate(-6, expand=True, fillcolor=(20, 20, 20))),
    "tilt +12": lambda im: _jpeg(im.rotate(12, expand=True, fillcolor=(20, 20, 20))),
    "sideways": lambda im: _jpeg(im.rotate(90, expand=True)),
    "upside down": lambda im: _jpeg(im.rotate(180)),
    "1/3 resolution": lambda im: _jpeg(im.resize((im.width // 3, im.height // 3))),
    "1/4 resolution": lambda im: _jpeg(im.resize((im.width // 4, im.height // 4))),
    "jpeg q15": lambda im: _jpeg(im, quality=15),
    "blur r4": lambda im: _jpeg(im.filter(ImageFilter.GaussianBlur(4))),
    "dim + low contrast": lambda im: _jpeg(
        ImageEnhance.Contrast(ImageEnhance.Brightness(im).enhance(0.45)).enhance(0.6)
    ),
    "perspective": lambda im: _jpeg(_perspective(im, 0.08)),
}
QUICK = ("original", "tilt -6", "sideways", "1/4 resolution", "blur r4")


def _check(scan, truth: dict) -> tuple[int, int, list[str]]:
    errors: list[str] = []
    want = [tuple(t) for t in truth["tips"]]
    got = {t.index: [c.value for c in t.cells] for t in scan.tips}
    correct = 0
    for i, tip in enumerate(want, start=1):
        g = got.get(i, [None] * 6)
        for j, v in enumerate(tip):
            if j < len(g) and g[j] == v:
                correct += 1
            else:
                errors.append(f"tip {i} pos {j + 1}: {g[j] if j < len(g) else None} != {v}")
    if len(got) != len(want):
        errors.append(f"{len(got)} tips found, expected {len(want)}")
    if scan.superzahl != truth["superzahl"]:
        errors.append(f"superzahl {scan.superzahl} != {truth['superzahl']}")
    if scan.first_draw != date.fromisoformat(truth["first_draw"]):
        errors.append(f"draw date {scan.first_draw} != {truth['first_draw']}")
    return correct, 6 * len(want), errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--dir", type=Path, default=ROOT / "data" / "tickets")
    args = ap.parse_args()

    photos = sorted(p for p in args.dir.glob("*.jpg") if p.with_suffix(".truth.json").exists())
    if not photos:
        print(f"No photos with ground truth in {args.dir}")
        return 1

    passed = total = 0
    cells_ok = cells_all = 0
    for photo in photos:
        truth = json.loads(photo.with_suffix(".truth.json").read_text(encoding="utf-8"))
        base = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
        print(f"\n{photo.name}")
        for name, make in VARIANTS.items():
            if args.quick and name not in QUICK:
                continue
            t0 = time.perf_counter()
            scan = scan_image(make(base))
            secs = time.perf_counter() - t0
            ok, n, errors = _check(scan, truth)
            flagged = sum(c.suspicious for t in scan.tips for c in t.cells)
            total += 1
            passed += not errors
            cells_ok += ok
            cells_all += n
            status = "PASS" if not errors else "FAIL"
            print(f"  {status} {name:20s} {ok:3d}/{n} cells  flagged={flagged:2d}  {secs:5.1f}s")
            for e in errors[:6]:
                print(f"         {e}")
    print(f"\n{passed}/{total} variants fully correct, {cells_ok}/{cells_all} cells "
          f"({100 * cells_ok / max(cells_all, 1):.1f}%)")
    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
