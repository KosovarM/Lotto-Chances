"""Official results of one draw: numbers, Superzahl, Spiel 77 / Super 6 and payouts.

Source: WestLotto's public info service (the XML behind westlotto.de's
"Gewinnzahlen und Quoten" page). It is not a documented API, so every
response is validated and results are cached once the payouts are final.
If it is unreachable, the numbers come from the draw-history CSV and the
payouts are reported as unknown.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from lotto.fetch import DATA_DIR

SERVICE_URL = (
    "https://www.westlotto.de/wlinfo/WL_InfoService"
    "?gruppe=ZahlenUndQuoten&spielart=LOTTO&historie=ja&datum={day}"
)
RESULTS_DIR = DATA_DIR / "results"
USER_AGENT = "lotto-chances/0.2 (+https://github.com/KosovarM/Lotto-Chances)"
# Draws are at ~19:25 on Saturdays and ~18:25 on Wednesdays; numbers are
# online a few minutes later.
DRAW_DONE_AT = {2: time(18, 45), 5: time(19, 45)}


@dataclass
class DrawResult:
    draw_date: date
    numbers: tuple[int, ...]
    superzahl: int | None
    spiel77: str | None = None
    super6: str | None = None
    # prize class -> payout in EUR (None = not published yet)
    quotes: dict[int, float | None] = field(default_factory=dict)
    spiel77_quotes: dict[int, float | None] = field(default_factory=dict)
    super6_quotes: dict[int, float | None] = field(default_factory=dict)
    jackpot_unclaimed: bool = False  # class 1 had no winner
    source: str = "westlotto"

    @property
    def quotes_final(self) -> bool:
        return len(self.quotes) == 9 and all(v is not None for v in self.quotes.values())


class ResultUnavailable(RuntimeError):
    """The draw has not happened yet or no source has it."""


def draw_has_happened(day: date, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if day < now.date():
        return True
    if day > now.date():
        return False
    return now.time() >= DRAW_DONE_AT.get(day.weekday(), time(20, 0))


def _euro(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d[\d.]*,\d{2})\s*EUR", text)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def _classes(node: ET.Element | None) -> dict[int, float | None]:
    out: dict[int, float | None] = {}
    if node is None:
        return out
    for k in node.findall("klasse"):
        num = (k.findtext("gewinnklasse") or "").strip()
        if num.isdigit():
            out[int(num)] = _euro(k.findtext("quote"))
    return out


def parse_westlotto_xml(raw: bytes, expected: date) -> DrawResult:
    """Parse one WestLotto response; raise ResultUnavailable if it is not that draw."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ResultUnavailable("unreadable response") from exc
    day_text = (root.findtext("daten/datum") or "").strip()
    try:
        day = datetime.strptime(day_text, "%d.%m.%Y").date()
    except ValueError as exc:
        raise ResultUnavailable("response has no draw date") from exc
    if day != expected:
        # The service answers unknown dates with the latest draw.
        raise ResultUnavailable(f"no result for {expected} yet")

    main = root.find("ziehung/hauptlotterie")
    nums = tuple(
        sorted(int(z.text) for z in (main.findall("zahlen_sortiert/zahl") if main is not None else [])
               if z.text and z.text.strip().isdigit())
    )
    if len(nums) != 6 or len(set(nums)) != 6 or not all(1 <= n <= 49 for n in nums):
        raise ResultUnavailable("response has no valid numbers")
    sz_text = (main.findtext("superzahl") or "").strip() if main is not None else ""

    quoten = root.find("quoten")
    main_q = quoten.find("hauptlotterie") if quoten is not None else None
    quotes = _classes(main_q)
    jackpot = False
    if main_q is not None:
        for k in main_q.findall("klasse"):
            if (k.findtext("gewinnklasse") or "").strip() == "1":
                jackpot = "jackpot" in (k.findtext("anzahl") or "").lower()

    return DrawResult(
        draw_date=day,
        numbers=nums,
        superzahl=int(sz_text) if sz_text.isdigit() else None,
        spiel77=(root.findtext("ziehung/spiel77") or "").strip() or None,
        super6=(root.findtext("ziehung/super6") or "").strip() or None,
        quotes=quotes,
        spiel77_quotes=_classes(quoten.find("spiel77") if quoten is not None else None),
        super6_quotes=_classes(quoten.find("super6") if quoten is not None else None),
        jackpot_unclaimed=jackpot,
    )


def _cache_path(day: date) -> Path:
    return RESULTS_DIR / f"{day.isoformat()}.json"


def _load_cached(day: date) -> DrawResult | None:
    path = _cache_path(day)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["draw_date"] = date.fromisoformat(raw["draw_date"])
    raw["numbers"] = tuple(raw["numbers"])
    for key in ("quotes", "spiel77_quotes", "super6_quotes"):
        raw[key] = {int(k): v for k, v in raw[key].items()}
    return DrawResult(**raw)


def _store(result: DrawResult) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["draw_date"] = result.draw_date.isoformat()
    _cache_path(result.draw_date).write_text(json.dumps(payload, indent=1), encoding="utf-8")


def _download(day: date) -> bytes:
    req = Request(SERVICE_URL.format(day=day.strftime("%d.%m.%Y")), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as resp:
        return resp.read()


def _from_history(day: date) -> DrawResult | None:
    from lotto.fetch import fetch_all_draws

    for d in reversed(fetch_all_draws()):
        if d.draw_date == day:
            return DrawResult(draw_date=day, numbers=d.numbers, superzahl=d.superzahl, source="history")
        if d.draw_date < day:
            break
    return None


def get_result(day: date, *, now: datetime | None = None) -> DrawResult:
    """Result for one draw day. Raises ResultUnavailable when there is none (yet)."""
    if not draw_has_happened(day, now):
        raise ResultUnavailable(f"draw on {day} has not happened yet")
    cached = _load_cached(day)
    if cached is not None:
        return cached
    try:
        result = parse_westlotto_xml(_download(day), day)
    except (URLError, OSError, ResultUnavailable):
        fallback = _from_history(day)
        if fallback is None:
            raise ResultUnavailable(f"no result for {day} available") from None
        return fallback
    if result.quotes_final:
        _store(result)
    return result
