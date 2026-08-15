import pytest

from publisher import sanitize_token, bill_subject, build_event


def test_sanitize_token_replaces_separators_with_underscore():
    assert sanitize_token("123/1") == "123_1"
    assert sanitize_token("123 (VIII)") == "123_(VIII)"


def test_sanitize_token_collapses_and_trims_underscores():
    assert sanitize_token(" 123 / 1 ") == "123_1"


def test_sanitize_token_empty_becomes_unknown():
    assert sanitize_token("  ") == "unknown"


def test_bill_subject():
    assert bill_subject("VIII", "123/1") == "pmr.vspmr.bill.new.VIII.123_1"


def test_bill_subject_custom_prefix():
    assert bill_subject("VIII", "5", prefix="pmr.test") == "pmr.test.bill.new.VIII.5"


def test_build_event_maps_fields_and_absolutizes_url():
    entry = {
        "_id": "ignored",
        "number": "123/1",
        "conv": "VIII",
        "name": "О бюджете",
        "url": "/legislation/bills/viii-soziv/123-1",
        "author": "Иванов И.И.",
        "committee": "Комитет по бюджету",
        "text": "ignored too",
    }
    event = build_event(entry, published_at="2026-08-15T10:00:00Z")
    assert event == {
        "number": "123/1",
        "conv": "VIII",
        "name": "О бюджете",
        "url": "https://vspmr.org/legislation/bills/viii-soziv/123-1",
        "author": "Иванов И.И.",
        "committee": "Комитет по бюджету",
        "publishedAt": "2026-08-15T10:00:00Z",
    }


def test_build_event_omits_missing_optional_fields():
    entry = {"number": "5", "conv": "VIII", "name": "X", "url": "/x"}
    event = build_event(entry, published_at="2026-08-15T10:00:00Z")
    assert "author" not in event
    assert "committee" not in event
