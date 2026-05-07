from pathlib import Path

from kakao_chat_manager.parser import parse_kakao_chat_text, parse_kakao_chat_bytes


def test_parse_kakao_chat_text_reads_messages_and_multiline():
    sample_text = Path("tests/fixtures/sample_chat.txt").read_text(encoding="utf-8")
    parsed = parse_kakao_chat_text(sample_text)

    assert parsed.title == "나와의 채팅"
    assert parsed.saved_at == "2026-05-06 10:30:00"
    assert len(parsed.messages) == 5
    assert parsed.messages[0].sender == "홍길동"
    assert parsed.messages[1].urls == ["https://example.com/article?utm_source=test"]
    assert parsed.messages[-1].text.endswith("셋째 줄")


def test_parse_kakao_chat_bytes_detects_encoding():
    sample_text = Path("tests/fixtures/sample_chat.txt").read_text(encoding="utf-8")
    parsed = parse_kakao_chat_bytes(sample_text.encode("utf-8-sig"))
    assert parsed.encoding == "utf-8-sig"
    assert len(parsed.messages) == 5
