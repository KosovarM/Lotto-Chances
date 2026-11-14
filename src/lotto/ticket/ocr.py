"""Local OCR for receipt photos (RapidOCR / ONNX Runtime, nothing leaves the machine).

The OCR packages are optional: install them with ``pip install -e ".[ocr]"``.
"""

from __future__ import annotations

import io
import math
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from lotto.ticket.models import Token

if TYPE_CHECKING:
    from PIL.Image import Image

# Longest image side handed to the OCR engine. Phone photos (4000 px) are
# shrunk to this: faster, and the receipt text stays far above the size
# the recognizer needs. 1400 px: all eval variants pass, ~2x faster than 2000.
MAX_SIDE = 1400
MAX_PIXELS = 40_000_000  # refuse decompression bombs


class OcrUnavailable(RuntimeError):
    """The optional OCR dependencies are not installed."""


class BadImage(ValueError):
    """The upload is not a readable image."""


@lru_cache(maxsize=1)
def _engine() -> Any:
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise OcrUnavailable(
            'OCR is not installed. Run: pip install -e ".[ocr]"'
        ) from exc
    return RapidOCR(params={"Global.log_level": "error"})


def load_image(data: bytes) -> Image:
    """Decode an upload, apply the phone's EXIF rotation, shrink to MAX_SIDE."""
    try:
        from PIL import Image as PILImage, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise OcrUnavailable('Pillow is not installed. Run: pip install -e ".[ocr]"') from exc

    PILImage.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = PILImage.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception as exc:  # Pillow raises many types for broken files
        raise BadImage("Not a readable image") from exc

    scale = MAX_SIDE / max(img.size)
    if scale < 1:
        img = img.resize(
            (round(img.width * scale), round(img.height * scale)),
            PILImage.Resampling.LANCZOS,
        )
    return img


def read_tokens(img: Image) -> list[Token]:
    """Run text detection + recognition and return positioned tokens."""
    import numpy as np

    # Flags passed explicitly: the engine remembers the last call's flags.
    result = _engine()(np.asarray(img), use_det=True, use_cls=True, use_rec=True)
    if not hasattr(result, "boxes"):
        return []
    if result.boxes is None:
        return []
    tokens: list[Token] = []
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        (tlx, tly), (trx, try_) = box[0], box[1]
        angle = math.degrees(math.atan2(float(try_) - float(tly), float(trx) - float(tlx)))
        tokens.append(
            Token(
                text=str(text).strip(),
                x0=min(xs),
                y0=min(ys),
                x1=max(xs),
                y1=max(ys),
                score=float(score),
                angle=angle,
            )
        )
    return tokens


def recognize_crop(img: Image, box: tuple[float, float, float, float]) -> tuple[str, float]:
    """Recognize the text in one region (no detection step).

    Used for receipt cells the full-page pass missed or merged.
    """
    import numpy as np

    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return "", 0.0
    crop = np.asarray(img.crop((x0, y0, x1, y1)))
    result = _engine()(crop, use_det=False, use_cls=False, use_rec=True)
    txts = list(getattr(result, "txts", None) or [])
    scores = list(getattr(result, "scores", None) or [])
    if not txts:
        return "", 0.0
    return str(txts[0]).strip(), float(scores[0])
