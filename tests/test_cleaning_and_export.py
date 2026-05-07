from pathlib import Path

from kakao_chat_manager.cleaning import build_dataframe, mark_duplicate_messages, mark_duplicate_url_messages, canonicalize_url
from kakao_chat_manager.exporter import export_chat_to_text
from kakao_chat_manager.parser import parse_kakao_chat_text


def _load_df_and_chat():
    sample_text = Path("tests/fixtures/sample_chat.txt").read_text(encoding="utf-8")
    parsed = parse_kakao_chat_text(sample_text)
    df = build_dataframe(parsed.messages)
    return parsed, df


def test_mark_duplicate_messages_disables_second_duplicate():
    _, df = _load_df_and_chat()
    marked = mark_duplicate_messages(df)
    duplicate_rows = marked[marked["normalized_text"] == "중복 메시지"]
    assert bool(duplicate_rows.iloc[0]["keep"]) is True
    assert bool(duplicate_rows.iloc[1]["keep"]) is False


def test_mark_duplicate_url_messages_ignores_tracking_parameters():
    first = canonicalize_url("https://example.com/article?utm_source=test&x=1")
    second = canonicalize_url("https://example.com/article?x=1&utm_medium=social")
    assert first == second


def test_export_chat_to_text_contains_day_divider_and_only_kept_messages():
    parsed, df = _load_df_and_chat()
    marked = mark_duplicate_messages(df)
    exported = export_chat_to_text(parsed, marked, include_day_dividers=True)
    assert "2026년 5월 5일 화요일" in exported
    assert exported.count("중복 메시지") == 1
