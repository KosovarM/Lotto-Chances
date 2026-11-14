from datetime import date
from pathlib import Path

import pytest

from lotto.results import ResultUnavailable, parse_westlotto_xml
from lotto.ticket import prizes
from lotto.ticket.models import Cell, Tip, TicketScan
from lotto.web.app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(monkeypatch):
    final = parse_westlotto_xml((FIXTURES / "westlotto_2026-11-11.xml").read_bytes(), date(2026, 11, 11))

    def fake_result(day):
        if day == final.draw_date:
            return final
        raise ResultUnavailable("pending")

    monkeypatch.setattr(prizes, "fetch_result", fake_result)
    return create_app().test_client()


def _form(**over):
    data = {f"n_1_{j}": str(v) for j, v in enumerate((11, 20, 21, 23, 1, 2), start=1)}
    data.update({"superzahl": "8", "first_draw": "2026-11-11", "weeks": "1", "wed": "1"})
    data.update(over)
    return data


def test_ticket_tab_renders_with_disclaimer(client):
    html = client.get("/?tab=ticket&lang=de").get_data(as_text=True)
    assert "Lottoschein prüfen" in html
    assert 'type="file"' in html and 'accept="image/*"' in html
    assert "Jede Ziehung ist unabhängig" in html


def test_manual_check_shows_win(client):
    html = client.post("/ticket?lang=en", data=_form()).get_data(as_text=True)
    # 4 hits + Superzahl -> class 5 = 180.30 EUR on 11.11.2026
    assert "180,30 €" in html
    assert "Each draw is independent" in html


def test_missing_date_asks_for_it(client):
    html = client.post("/ticket?lang=de", data=_form(first_draw="")).get_data(as_text=True)
    assert "Ziehungsdatum konnte nicht gelesen werden" in html
    assert "result-summary" not in html


def test_invalid_tip_is_marked(client):
    html = client.post("/ticket?lang=en", data=_form(n_1_2="11")).get_data(as_text=True)
    assert "six different numbers" in html
    assert "row-bad" in html


def test_future_draw_is_pending(client):
    html = client.post("/ticket?lang=en", data=_form(first_draw="2026-11-14", wed="", sat="1")).get_data(as_text=True)
    assert "has not taken place yet" in html


def test_photo_upload_uses_scanner(client, monkeypatch):
    scan = TicketScan(
        tips=[Tip(1, [Cell(v) for v in (11, 20, 21, 23, 1, 2)])],
        superzahl=8,
        draw_weekdays=(2,),
        weeks=1,
        first_draw=date(2026, 11, 11),
    )
    import lotto.ticket.scan as scan_mod

    monkeypatch.setattr(scan_mod, "scan_image", lambda data: scan)
    resp = client.post(
        "/ticket?lang=en",
        data={"photo": (Path(__file__).open("rb"), "receipt.jpg")},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "Recognised data" in html
    assert "180,30 €" in html


def test_unreadable_upload(client):
    import io

    resp = client.post(
        "/ticket?lang=en",
        data={"photo": (io.BytesIO(b"not an image"), "x.jpg")},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "could not be read as an image" in html or "not installed" in html
