from datetime import date, datetime
from pathlib import Path

import pytest

from lotto import results
from lotto.results import DrawResult, ResultUnavailable, draw_has_happened, parse_westlotto_xml
from lotto.ticket.prizes import (
    check_ticket,
    draw_dates,
    evaluate_draw,
    prize_class,
    trailing_matches,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _final() -> DrawResult:
    raw = (FIXTURES / "westlotto_2026-11-11.xml").read_bytes()
    return parse_westlotto_xml(raw, date(2026, 11, 11))


def test_parse_final_result():
    r = _final()
    assert r.numbers == (11, 20, 21, 23, 31, 49)
    assert r.superzahl == 8
    assert r.spiel77 == "1122310" and r.super6 == "852773"
    assert r.quotes_final
    assert r.quotes[2] == 1_146_356.10
    assert r.quotes[9] == 6.00
    assert r.jackpot_unclaimed
    assert r.super6_quotes[1] == 100_000.00


def test_parse_result_without_payouts_yet():
    raw = (FIXTURES / "westlotto_2026-11-14_pending.xml").read_bytes()
    r = parse_westlotto_xml(raw, date(2026, 11, 14))
    assert r.numbers == (11, 15, 17, 32, 39, 49)
    assert r.superzahl == 3
    assert not r.quotes_final


def test_service_answering_another_date_is_rejected():
    raw = (FIXTURES / "westlotto_2026-11-11.xml").read_bytes()
    with pytest.raises(ResultUnavailable):
        parse_westlotto_xml(raw, date(2026, 11, 7))


def test_garbage_response_is_rejected():
    with pytest.raises(ResultUnavailable):
        parse_westlotto_xml(b"<html>oops", date(2026, 11, 11))


def test_draw_has_happened():
    sat = date(2026, 11, 14)
    assert not draw_has_happened(sat, datetime(2026, 11, 14, 19, 0))
    assert draw_has_happened(sat, datetime(2026, 11, 14, 20, 0))
    assert draw_has_happened(sat, datetime(2026, 11, 15, 8, 0))
    assert not draw_has_happened(sat, datetime(2026, 11, 13, 23, 0))


@pytest.mark.parametrize(
    "hits,sz,expected",
    [(6, True, 1), (6, False, 2), (5, True, 3), (5, False, 4), (4, True, 5),
     (4, False, 6), (3, True, 7), (3, False, 8), (2, True, 9), (2, False, None),
     (1, True, None), (0, False, None)],
)
def test_prize_classes(hits, sz, expected):
    assert prize_class(hits, sz) == expected


def test_trailing_matches():
    assert trailing_matches("1234567", "9994567") == 4
    assert trailing_matches("1234567", "1234568") == 0
    assert trailing_matches("1234567", "1234567") == 7


def test_draw_dates():
    assert draw_dates(date(2026, 11, 14), (5,), 1) == [date(2026, 11, 14)]
    assert draw_dates(date(2026, 11, 11), (2, 5), 2) == [
        date(2026, 11, 11), date(2026, 11, 14), date(2026, 11, 18), date(2026, 11, 21)
    ]


def test_evaluate_draw_against_real_payouts():
    r = _final()  # 11 20 21 23 31 49, SZ 8
    tips = [
        (1, (11, 20, 21, 23, 31, 2)),   # 5 hits
        (2, (11, 20, 1, 2, 3, 4)),      # 2 hits, SZ hit -> class 9
        (3, (11, 1, 2, 3, 4, 5)),       # nothing
    ]
    out = evaluate_draw(tips, 8, r)
    assert [t.prize_class for t in out.tips] == [3, 9, None]
    assert out.tips[0].payout == 12_418.80
    assert out.total == pytest.approx(12_418.80 + 6.00)


def test_evaluate_draw_spiel77_super6():
    r = _final()  # spiel77 1122310, super6 852773
    out = evaluate_draw([], 0, r, losnummer="9992773", spiel77=True, super6=True)
    assert out.spiel77_class is None  # last digit 3 vs 0
    assert out.super6_class == 3  # 2773 -> 4 end digits
    assert out.super6_payout == 666.00


def test_class9_without_published_payouts_uses_fixed_amount():
    r = DrawResult(draw_date=date(2026, 11, 14), numbers=(1, 2, 3, 4, 5, 6), superzahl=3)
    out = evaluate_draw([(1, (1, 2, 10, 11, 12, 13)), (2, (1, 2, 3, 10, 11, 12))], 3, r)
    assert out.tips[0].payout == 6.00
    assert out.tips[1].prize_class == 7 and out.tips[1].payout is None
    assert out.has_unpriced_win


def test_check_ticket_marks_future_draws_pending():
    def fake(day):
        if day == date(2026, 11, 11):
            return _final()
        raise ResultUnavailable("not yet")

    out = check_ticket([(1, (11, 20, 21, 1, 2, 3))], 0, date(2026, 11, 11), (2, 5), 1, get_result=fake)
    assert [o.draw_date for o in out] == [date(2026, 11, 11), date(2026, 11, 14)]
    assert out[0].tips[0].prize_class == 8
    assert out[1].result is None


def test_get_result_caches_only_final_payouts(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    final = (FIXTURES / "westlotto_2026-11-11.xml").read_bytes()
    pending = (FIXTURES / "westlotto_2026-11-14_pending.xml").read_bytes()
    monkeypatch.setattr(results, "_download", lambda day: final if day.day == 11 else pending)
    now = datetime(2026, 11, 15, 12, 0)

    assert results.get_result(date(2026, 11, 11), now=now).quotes_final
    assert (tmp_path / "2026-11-11.json").exists()
    assert results.get_result(date(2026, 11, 14), now=now).superzahl == 3
    assert not (tmp_path / "2026-11-14.json").exists()

    monkeypatch.setattr(results, "_download", lambda day: (_ for _ in ()).throw(OSError("offline")))
    assert results.get_result(date(2026, 11, 11), now=now).quotes[9] == 6.00  # from cache


def test_get_result_future_draw():
    with pytest.raises(ResultUnavailable):
        results.get_result(date(2026, 11, 18), now=datetime(2026, 11, 15, 12, 0))
