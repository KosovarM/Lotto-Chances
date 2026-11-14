"""Read a Lotto 6aus49 receipt (Spielquittung) from a photo and check it.

Pipeline: ``ocr.read_tokens`` (image -> positioned text) -> ``parse.parse_ticket``
(text -> tips, Superzahl, draw dates) -> ``prizes.evaluate_ticket``
(tips + official results -> prize classes and payouts).
"""
