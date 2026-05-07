from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import List, Optional

URL_PATTERN = re.compile(r'https?://[^\s<>\]\\)"\']+')

KO_MESSAGE_PATTERN = re.compile(
    r"^(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일\s+"
    r"(?P<ampm>오전|오후)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}),\s*"
    r"(?P<sender>.+?)\s*:\s*(?P<text>.*)$"
)

DOT_MESSAGE_PATTERN = re.compile(
    r"^(?P<year>\d{4})\.\s*(?P<month>\d{1,2})\.\s*(?P<day>\d{1,2})\.\s*"
    r"(?P<ampm>오전|오후|AM|PM)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}),\s*"
    r"(?P<sender>.+?)\s*:\s*(?P<text>.*)$"
)

KO_DAY_DIVIDER_PATTERN = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s+[월화수목금토일]요일$"
)
DOT_DAY_DIVIDER_PATTERN = re.compile(
    r"^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*[월화수목금토일]요일$"
)

SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]


@dataclass
class ChatMessage:
    row_id: int
    dt: datetime
    sender: str
    text: str
    urls: List[str] = field(default_factory=list)


@dataclass
class ParsedChat:
    title: str
    header_lines: List[str]
    messages: List[ChatMessage]
    saved_at: Optional[str] = None
    message_format: str = "ko"
    encoding: str = "utf-8-sig"


@dataclass
class ParseCandidate:
    dt: datetime
    sender: str
    text: str
    message_format: str


def decode_chat_bytes(file_bytes: bytes) -> tuple[str, str]:
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return file_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace"), "utf-8"


def parse_kakao_chat_bytes(file_bytes: bytes) -> ParsedChat:
    text, encoding = decode_chat_bytes(file_bytes)
    parsed = parse_kakao_chat_text(text)
    parsed.encoding = encoding
    return parsed


def _convert_hour(ampm: str, hour: int) -> int:
    upper_ampm = ampm.upper()
    if ampm == "오전" or upper_ampm == "AM":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def _extract_urls(text: str) -> List[str]:
    matches = []
    for raw in URL_PATTERN.findall(text or ""):
        matches.append(raw.rstrip('.,!?:;)'))
    return matches


def _parse_message_line(line: str) -> Optional[ParseCandidate]:
    for pattern, fmt in ((KO_MESSAGE_PATTERN, "ko"), (DOT_MESSAGE_PATTERN, "dot")):
        match = pattern.match(line)
        if not match:
            continue
        data = match.groupdict()
        hour = _convert_hour(data["ampm"], int(data["hour"]))
        dt = datetime(
            int(data["year"]),
            int(data["month"]),
            int(data["day"]),
            hour,
            int(data["minute"]),
        )
        return ParseCandidate(
            dt=dt,
            sender=data["sender"].strip(),
            text=data["text"],
            message_format=fmt,
        )
    return None


def _is_day_divider(line: str) -> bool:
    return bool(KO_DAY_DIVIDER_PATTERN.match(line) or DOT_DAY_DIVIDER_PATTERN.match(line))


def parse_kakao_chat_text(text: str) -> ParsedChat:
    lines = text.splitlines()
    header_lines: List[str] = []
    messages: List[ChatMessage] = []
    title = "카카오톡 대화"
    saved_at: Optional[str] = None
    message_format = "ko"

    cursor = 0
    while cursor < len(lines):
        line = lines[cursor].rstrip("\n")
        if _parse_message_line(line) or _is_day_divider(line):
            break
        header_lines.append(line)
        cursor += 1

    for header_line in header_lines:
        stripped = header_line.strip()
        if stripped and title == "카카오톡 대화":
            title = stripped
        if "저장한 날짜" in stripped:
            saved_at = stripped.split(":", 1)[-1].strip()

    current_message: Optional[ChatMessage] = None
    for line in lines[cursor:]:
        raw_line = line.rstrip("\n")
        candidate = _parse_message_line(raw_line)
        if candidate:
            message_format = candidate.message_format
            current_message = ChatMessage(
                row_id=len(messages),
                dt=candidate.dt,
                sender=candidate.sender,
                text=candidate.text,
                urls=_extract_urls(candidate.text),
            )
            messages.append(current_message)
            continue

        if _is_day_divider(raw_line) or not raw_line.strip():
            continue

        if current_message is None:
            header_lines.append(raw_line)
            continue

        current_message.text = f"{current_message.text}\n{raw_line}".strip("\n")
        current_message.urls = _extract_urls(current_message.text)

    return ParsedChat(
        title=title,
        header_lines=header_lines,
        messages=messages,
        saved_at=saved_at,
        message_format=message_format,
    )
