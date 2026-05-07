from pathlib import Path

from app import (
    _normalize_screenshot_target_url,
    build_dataframe,
    build_fallback_screenshot_url,
    build_screenshot_url,
    build_url_preview_records,
    paginate_records,
    parse_kakao_chat_text,
)


def _load_df():
    sample_text = Path("tests/fixtures/sample_chat.txt").read_text(encoding="utf-8")
    parsed = parse_kakao_chat_text(sample_text)
    return build_dataframe(parsed.messages)


def test_build_url_preview_records_collects_url_messages():
    df = _load_df()
    records = build_url_preview_records(df)
    assert len(records) == 1
    assert records[0].url == "https://example.com/article?utm_source=test"
    assert records[0].sender == "홍길동"


def test_paginate_records_limits_items_per_page():
    df = _load_df()
    records = build_url_preview_records(df) * 12
    page_records, current_page, total_pages = paginate_records(records, page=2, page_size=10)
    assert len(page_records) == 2
    assert current_page == 2
    assert total_pages == 2


def test_normalize_screenshot_target_url_preserves_scheme_and_encodes_spaces():
    normalized = _normalize_screenshot_target_url("https://example.com/hello world?a=1&b=2")
    assert normalized == "https://example.com/hello%20world?a=1&b=2"


def test_build_screenshot_url_contains_unescaped_target_scheme():
    screenshot_url = build_screenshot_url("https://example.com/hello world?a=1&b=2")
    assert screenshot_url.startswith("https://image.thum.io/get/")
    assert screenshot_url.endswith("https://example.com/hello%20world?a=1&b=2")


def test_build_fallback_screenshot_url_contains_encoded_target_url():
    screenshot_url = build_fallback_screenshot_url("https://example.com/hello world?a=1&b=2")
    assert screenshot_url.startswith("https://s.wordpress.com/mshots/v1/")
    assert "https%3A%2F%2Fexample.com%2Fhello%2520world%3Fa%3D1%26b%3D2" in screenshot_url
    assert screenshot_url.endswith("?w=1200")
