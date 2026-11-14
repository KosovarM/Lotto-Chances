"""Photo -> TicketScan: OCR plus the receipt parser, with rotation handling."""

from __future__ import annotations

from lotto.ticket import ocr
from lotto.ticket.models import TicketScan
from lotto.ticket.parse import _skew_degrees, parse_ticket

# Above this tilt the image itself is straightened and read again; below it
# the parser's coordinate correction is enough.
RE_READ_SKEW_DEGREES = 4.0


def _score(scan: TicketScan) -> int:
    """How much usable content a parse found (for picking a rotation)."""
    return sum(1 for t in scan.tips for c in t.cells if c.value is not None)


def scan_image(data: bytes) -> TicketScan:
    """Read a receipt photo. Raises ocr.BadImage / ocr.OcrUnavailable."""
    img = ocr.load_image(data)
    best: TicketScan | None = None
    # Upright first; a sideways or upside-down photo is retried turned.
    for turn in (0, 90, 270, 180):
        candidate = img.rotate(turn, expand=True) if turn else img
        tokens = ocr.read_tokens(candidate)
        skew = _skew_degrees(tokens)
        if abs(skew) > RE_READ_SKEW_DEGREES:
            candidate = candidate.rotate(skew, expand=True, fillcolor=(255, 255, 255))
            tokens = ocr.read_tokens(candidate)
        page = candidate
        scan = parse_ticket(tokens, read_crop=lambda box: ocr.recognize_crop(page, box))
        if best is None or _score(scan) > _score(best):
            best = scan
        if scan.tips and _score(scan) >= 6 * len(scan.tips) * 0.8:
            break
    assert best is not None
    return best
