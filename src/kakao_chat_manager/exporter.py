from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pandas as pd

from .parser import ParsedChat

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def _format_ampm(dt: datetime, style: str) -> tuple[str, int]:
    hour = dt.hour
    if style == "dot":
        ampm = "AM" if hour < 12 else "PM"
    else:
        ampm = "오전" if hour < 12 else "오후"
    twelve_hour = hour % 12
    if twelve_hour == 0:
        twelve_hour = 12
    return ampm, twelve_hour


def format_message_datetime(dt: datetime, style: str = "ko") -> str:
    ampm, hour = _format_ampm(dt, style)
    if style == "dot":
        return f"{dt.year}. {dt.month}. {dt.day}. {ampm} {hour}:{dt.minute:02d}"
    return f"{dt.year}년 {dt.month}월 {dt.day}일 {ampm} {hour}:{dt.minute:02d}"


def format_day_divider(dt: datetime, style: str = "ko") -> str:
    weekday = WEEKDAY_LABELS[dt.weekday()]
    if style == "dot":
        return f"{dt.year}. {dt.month}. {dt.day}. {weekday}요일"
    return f"{dt.year}년 {dt.month}월 {dt.day}일 {weekday}요일"


def _format_message_line(dt: datetime, sender: str, text: str, style: str) -> str:
    lines = (text or "").splitlines() or [""]
    head = f"{format_message_datetime(dt, style)}, {sender} : {lines[0]}"
    if len(lines) == 1:
        return head
    return "\n".join([head, *lines[1:]])


def export_chat_to_text(parsed_chat: ParsedChat, df: pd.DataFrame, include_day_dividers: bool = True) -> str:
    style = parsed_chat.message_format or "ko"
    lines = list(parsed_chat.header_lines)
    if lines and lines[-1].strip() != "":
        lines.append("")

    kept = df[df["keep"]].sort_values("row_id")
    last_date = None
    for _, row in kept.iterrows():
        dt = row["dt"]
        current_date = dt.date()
        if include_day_dividers and last_date != current_date:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(format_day_divider(dt, style))
        lines.append(_format_message_line(dt, row["sender"], row["text"], style))
        last_date = current_date

    return "\n".join(lines).strip() + "\n"
