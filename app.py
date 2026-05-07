from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import lru_cache
from hashlib import md5
from html import escape
from math import ceil
from pathlib import Path
import re
from typing import Iterable, Optional
from collections.abc import Mapping
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup

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
KO_DAY_DIVIDER_PATTERN = re.compile(r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s+[월화수목금토일]요일$")
DOT_DAY_DIVIDER_PATTERN = re.compile(r"^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*[월화수목금토일]요일$")
SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
FILTER_LABELS = {
    "all": "전체 메시지",
}
SCREENSHOT_BASE_URL = "https://image.thum.io/get/width/1200/crop/900/noanimate/"
FALLBACK_SCREENSHOT_BASE_URL = "https://s.wordpress.com/mshots/v1/"


@dataclass
class ChatMessage:
    row_id: int
    dt: datetime
    sender: str
    text: str
    urls: list[str] = field(default_factory=list)


@dataclass
class ParsedChat:
    title: str
    header_lines: list[str]
    messages: list[ChatMessage]
    saved_at: Optional[str] = None
    message_format: str = "ko"
    encoding: str = "utf-8-sig"


@dataclass
class ParseCandidate:
    dt: datetime
    sender: str
    text: str
    message_format: str


@dataclass
class URLPreview:
    requested_url: str
    final_url: str
    domain: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    image: str = ""
    status_code: Optional[int] = None
    content_type: str = ""
    error: str = ""


@dataclass
class PreviewRecord:
    row_id: int
    dt: datetime
    sender: str
    text: str
    url: str


def decode_chat_bytes(file_bytes: bytes) -> tuple[str, str]:
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return file_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace"), "utf-8"


def _convert_hour(ampm: str, hour: int) -> int:
    upper_ampm = ampm.upper()
    if ampm == "오전" or upper_ampm == "AM":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def _extract_urls(text: str) -> list[str]:
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
    header_lines: list[str] = []
    messages: list[ChatMessage] = []
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


def parse_kakao_chat_bytes(file_bytes: bytes) -> ParsedChat:
    text, encoding = decode_chat_bytes(file_bytes)
    parsed = parse_kakao_chat_text(text)
    parsed.encoding = encoding
    return parsed


def normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_QUERY_KEYS]
    normalized = parsed._replace(
        scheme=(parsed.scheme or "https").lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(query_pairs, doseq=True),
        fragment="",
    )
    normalized_url = urlunparse(normalized)
    if normalized_url.endswith("/") and parsed.path not in ("", "/"):
        normalized_url = normalized_url[:-1]
    return normalized_url


def build_dataframe(messages: Iterable[ChatMessage]) -> pd.DataFrame:
    records = []
    for message in messages:
        record = asdict(message)
        record["keep"] = True
        records.append(record)
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "row_id",
                "dt",
                "sender",
                "text",
                "urls",
                "keep",
                "normalized_text",
                "url_list",
                "canonical_url_list",
                "is_duplicate_text",
                "is_duplicate_url",
                "is_url_message",
                "url_count",
            ]
        )
    return enrich_dataframe(df)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    enriched = df.copy()
    if "keep" not in enriched.columns:
        enriched["keep"] = True
    enriched["text"] = enriched["text"].fillna("")
    enriched["sender"] = enriched["sender"].fillna("")
    if "urls" not in enriched.columns:
        enriched["urls"] = [[] for _ in range(len(enriched))]
    enriched["urls"] = enriched["urls"].apply(lambda value: value if isinstance(value, list) else [])
    enriched["normalized_text"] = enriched["text"].map(normalize_text)
    enriched["url_list"] = enriched["urls"].apply(lambda value: value if isinstance(value, list) else [])
    enriched["canonical_url_list"] = enriched["url_list"].apply(lambda items: [canonicalize_url(item) for item in items])
    enriched["is_url_message"] = enriched["url_list"].map(bool)
    enriched["url_count"] = enriched["url_list"].map(len)

    duplicate_sizes = enriched.groupby("normalized_text")["row_id"].transform("size")
    enriched["is_duplicate_text"] = (enriched["normalized_text"] != "") & (duplicate_sizes > 1)

    url_signature = enriched["canonical_url_list"].map(lambda items: " | ".join(items))
    url_sizes = url_signature.groupby(url_signature).transform("size") if len(url_signature) else pd.Series(dtype=int)
    enriched["is_duplicate_url"] = enriched["is_url_message"] & (url_signature != "") & (url_sizes > 1)
    return enriched


def _mark_repeated(df: pd.DataFrame, signature_column: str) -> pd.DataFrame:
    updated = df.copy()
    seen = set()
    for idx, row in updated.sort_values("row_id").iterrows():
        signature = row[signature_column]
        if not signature:
            continue
        if signature in seen:
            updated.at[idx, "keep"] = False
        else:
            seen.add(signature)
    return updated


def mark_duplicate_messages(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    return enrich_dataframe(_mark_repeated(enriched, "normalized_text"))


def mark_duplicate_url_messages(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    signature_df = enriched.copy()
    signature_df["url_signature"] = signature_df["canonical_url_list"].map(lambda items: " | ".join(items))
    marked = _mark_repeated(signature_df, "url_signature")
    return enrich_dataframe(marked.drop(columns=["url_signature"]))


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


@lru_cache(maxsize=256)
def fetch_url_preview(url: str, timeout: int = 5) -> URLPreview:
    domain = urlparse(url).netloc
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        content_type = response.headers.get("Content-Type", "")
        final_url = response.url
        preview = URLPreview(
            requested_url=url,
            final_url=final_url,
            domain=urlparse(final_url).netloc or domain,
            status_code=response.status_code,
            content_type=content_type,
        )
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return preview

        html = response.text[:300000]
        soup = BeautifulSoup(html, "html.parser")

        def pick(*selectors: tuple[str, dict]) -> str:
            for tag_name, attrs in selectors:
                tag = soup.find(tag_name, attrs=attrs)
                if not tag:
                    continue
                if tag_name == "meta":
                    value = tag.get("content", "")
                else:
                    value = tag.get_text(" ", strip=True)
                if value:
                    return value.strip()
            return ""

        preview.title = pick(
            ("meta", {"property": "og:title"}),
            ("meta", {"name": "twitter:title"}),
            ("title", {}),
        )
        preview.description = pick(
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "description"}),
            ("meta", {"name": "twitter:description"}),
        )
        preview.site_name = pick(("meta", {"property": "og:site_name"}),)
        image_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
        if image_tag:
            preview.image = image_tag.get("content", "").strip()
        return preview
    except requests.RequestException as exc:
        return URLPreview(
            requested_url=url,
            final_url=url,
            domain=domain,
            error=str(exc),
        )


def _normalize_screenshot_target_url(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = f"https://{candidate.lstrip('/')}"
        parsed = urlparse(candidate)

    safe_path = quote(unquote(parsed.path), safe="/:@%+-._~")
    safe_query = quote(unquote(parsed.query), safe="=&%/:+;,@-._~")
    normalized = parsed._replace(
        scheme=(parsed.scheme or "https").lower(),
        netloc=parsed.netloc.lower(),
        path=safe_path,
        query=safe_query,
        fragment="",
    )
    return urlunparse(normalized)


def build_screenshot_url(url: str) -> str:
    normalized_url = _normalize_screenshot_target_url(url)
    return f"{SCREENSHOT_BASE_URL}{normalized_url}" if normalized_url else ""


def build_fallback_screenshot_url(url: str) -> str:
    normalized_url = _normalize_screenshot_target_url(url)
    if not normalized_url:
        return ""
    return f"{FALLBACK_SCREENSHOT_BASE_URL}{quote(normalized_url, safe='')}?w=1200"


def render_screenshot_preview(url: str, height: int = 520) -> None:
    primary_url = build_fallback_screenshot_url(url)
    # primary_url (WordPress MShots)가 Generating Preview... 문구를 표시할 때가 있으므로
    # thum.io를 기본으로 사용하고 WordPress를 백업으로 전환합니다.
    fallback_url = build_screenshot_url(url)
    
    if not fallback_url:
        st.info("스크린샷용 URL을 만들 수 없습니다.")
        return

    fallback_id = f"shot-fallback-{md5(url.encode('utf-8')).hexdigest()[:10]}"
    html = f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:#f8fafc;">
      <img
        src="{escape(fallback_url, quote=True)}"
        alt="열린 페이지 스크린샷 미리보기"
        referrerpolicy="no-referrer"
        loading="lazy"
        style="display:block;width:100%;height:auto;min-height:360px;background:#f8fafc;object-fit:cover;"
        onerror="if (this.dataset.fallback !== '1') {{ this.dataset.fallback = '1'; this.src = '{escape(primary_url, quote=True)}'; return; }} this.style.display = 'none'; document.getElementById('{fallback_id}').style.display = 'block';"
      />
      <div id="{fallback_id}" style="display:none;padding:16px;font-size:14px;line-height:1.6;color:#475569;">
        스크린샷을 불러오지 못했습니다.<br/>
        <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">원본 페이지를 새 탭에서 열기</a>
      </div>
    </div>
    """
    components.html(html, height=height, scrolling=False)


def build_url_preview_records(df: pd.DataFrame) -> list[PreviewRecord]:
    records: list[PreviewRecord] = []
    if df.empty:
        return records
    url_rows = df[df["is_url_message"] & df["keep"]].sort_values(["dt", "row_id"])
    for _, row in url_rows.iterrows():
        for url in row["url_list"]:
            records.append(
                PreviewRecord(
                    row_id=int(row["row_id"]),
                    dt=row["dt"],
                    sender=str(row["sender"]),
                    text=str(row["text"]),
                    url=url,
                )
            )
    return records


def paginate_records(records: list[PreviewRecord], page: int, page_size: int = 10) -> tuple[list[PreviewRecord], int, int]:
    total_records = len(records)
    total_pages = max(1, ceil(total_records / page_size)) if total_records else 1
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size
    return records[start:end], current_page, total_pages


def _reset_chat_editor_state() -> None:
    if "chat_editor" in st.session_state:
        del st.session_state["chat_editor"]



def _sanitize_chat_editor_state() -> None:
    editor_state = st.session_state.get("chat_editor")
    if editor_state is None:
        _reset_chat_editor_state()
        return
    if not isinstance(editor_state, Mapping):
        _reset_chat_editor_state()



def _set_view_mode(mode: str) -> None:
    st.session_state.view_mode = mode
    _reset_chat_editor_state()


def _reset_url_preview_page() -> None:
    st.session_state.url_preview_page = 1


def _sync_editor_changes(base_df: pd.DataFrame, edited_view: pd.DataFrame) -> pd.DataFrame:
    if edited_view is None or edited_view.empty:
        return enrich_dataframe(base_df)
    updated = base_df.copy().set_index("row_id")
    for _, row in edited_view.iterrows():
        row_id = int(row["row_id"])
        if row_id not in updated.index:
            continue
        delete_value = bool(row.get("delete", False))
        text_value = str(row.get("text", ""))
        updated.at[row_id, "keep"] = not delete_value
        updated.at[row_id, "text"] = text_value
        updated.at[row_id, "urls"] = _extract_urls(text_value)
    updated = updated.reset_index()
    return enrich_dataframe(updated)


def _apply_filters(base_df: pd.DataFrame, search_keyword: str, sender_filter: list[str], view_mode: str) -> pd.DataFrame:
    view_df = base_df.copy()
    if search_keyword:
        view_df = view_df[view_df["text"].str.contains(search_keyword, case=False, na=False)]
    if sender_filter:
        view_df = view_df[view_df["sender"].isin(sender_filter)]
    if view_mode == "duplicate_text":
        view_df = view_df[view_df["is_duplicate_text"]]
    elif view_mode == "url_only":
        view_df = view_df[view_df["is_url_message"]]
    return view_df


def render_app() -> None:
    st.set_page_config(
        page_title="카카오톡 나와의 채팅 정리기",
        page_icon="💬",
        layout="wide",
    )

    st.title("💬 카카오톡 나와의 채팅 정리기")
    st.caption(
        "TXT 내보내기 파일을 올리면 메시지 수정, 삭제 체크, 중복 메시지 필터, URL 페이지 미리보기, 수정본 재다운로드까지 한 번에 할 수 있습니다."
    )

    uploaded_file = st.file_uploader("카카오톡 TXT 파일 업로드", type=["txt"])
    if not uploaded_file:
        st.info("카카오톡에서 내보낸 TXT 파일을 업로드해 주세요.")
        return

    file_bytes = uploaded_file.getvalue()
    file_fingerprint = md5(file_bytes).hexdigest()
    if st.session_state.get("file_fingerprint") != file_fingerprint:
        parsed_chat = parse_kakao_chat_bytes(file_bytes)
        st.session_state.file_fingerprint = file_fingerprint
        st.session_state.parsed_chat = parsed_chat
        st.session_state.chat_df = build_dataframe(parsed_chat.messages)
        st.session_state.include_day_dividers = True
        st.session_state.preview_cache = {}
        st.session_state.view_mode = "all"
        st.session_state.url_preview_page = 1
        _reset_chat_editor_state()

    parsed_chat = st.session_state.parsed_chat
    base_df = st.session_state.chat_df
    st.session_state.setdefault("view_mode", "all")
    st.session_state.setdefault("url_preview_page", 1)
    st.session_state.setdefault("preview_cache", {})

    with st.sidebar:
        st.subheader("정리 옵션")
        if st.button("전체 복구", use_container_width=True):
            reset_df = st.session_state.chat_df.copy()
            reset_df["keep"] = True
            st.session_state.chat_df = enrich_dataframe(reset_df)
            st.rerun()

        st.divider()
        search_keyword = st.text_input("메시지 검색")
        sender_options = sorted(base_df["sender"].dropna().unique().tolist())
        sender_filter = st.multiselect("보낸 사람 필터", options=sender_options, default=sender_options)
        st.session_state.include_day_dividers = st.checkbox(
            "다운로드 시 날짜 구분선 포함",
            value=st.session_state.get("include_day_dividers", True),
        )

    metrics = st.columns(3)
    metrics[0].metric("전체 메시지", len(base_df))
    metrics[1].metric("삭제 예정", int((~base_df["keep"]).sum()))
    metrics[2].metric("URL 메시지", int(base_df["is_url_message"].sum()))

    st.subheader("채팅 목록")
    st.caption("삭제를 체크하면 다운로드 파일에서 제외됩니다. 메시지 내용은 직접 수정할 수 있습니다.")

    # 메시지 분류
    photo_pattern = re.compile(r'사진|image|photo|사진을|사진을 보냈|사진을 받음', re.IGNORECASE)
    
    # 시트 분류 (삭제되지 않은 메시지만 표시)
    text_df = base_df[(base_df["url_count"] == 0) & (~base_df["text"].str.contains(photo_pattern, na=False)) & (base_df["keep"] == True)].copy()
    url_df = base_df[(base_df["url_count"] > 0) & (base_df["keep"] == True)].copy()
    photo_df = base_df[(base_df["text"].str.contains(photo_pattern, na=False)) & (base_df["keep"] == True)].copy()

    def render_sheet(sheet_name: str, df: pd.DataFrame, session_key: str) -> None:
        """시트를 렌더링하고 삭제 버튼 처리"""
        if df.empty:
            st.markdown(f"### 📋 {sheet_name}")
            st.info("해당 메시지가 없습니다.")
            return

        st.markdown(f"### 📋 {sheet_name} ({len(df)}개)")
        
        # 데이터 표시
        display_df = df[["row_id", "dt", "text"]].copy()
        display_df["delete"] = False
        display_df = display_df.rename(
            columns={
                "dt": "시간",
                "text": "메시지 내용",
                "delete": "삭제",
            }
        )
        display_df = display_df.set_index("row_id")

        edited = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            disabled=["시간"],
            column_config={
                "삭제": st.column_config.CheckboxColumn("삭제", help="체크하면 다운로드 파일에서 제외됩니다."),
                "메시지 내용": st.column_config.TextColumn("메시지 내용", width="large"),
            },
            key=f"editor_{session_key}",
        )

        # 삭제 버튼 - 체크된 항목이 있을 때만 활성화
        checked_ids = [idx for idx, row in edited.iterrows() if row.get("삭제", False)]
        if checked_ids:
            if st.button(f"🗑️ 선택 항목 삭제 ({len(checked_ids)}개)", key=f"delete_btn_{session_key}", use_container_width=True):
                delete_df = st.session_state.chat_df.copy()
                delete_df.loc[delete_df["row_id"].isin(checked_ids), "keep"] = False
                st.session_state.chat_df = enrich_dataframe(delete_df)
                # URL 미리보기 페이지가 초과되면 첫 페이지로 리셋
                preview_records = build_url_preview_records(st.session_state.chat_df)
                total_pages = max(1, ceil(len(preview_records) / 10))
                current_page = st.session_state.get("url_preview_page", 1)
                if current_page > total_pages:
                    st.session_state.url_preview_page = 1
                st.rerun()

    # 3개의 시트 렌더링 (텍스트 메시지 → 사진 → URL 메시지 순서)
    with st.expander("📝 텍스트 메시지", expanded=True):
        render_sheet("텍스트 메시지", text_df, "text")

    with st.expander("📷 사진", expanded=True):
        render_sheet("사진", photo_df, "photo")

    with st.expander("🔗 URL 메시지", expanded=True):
        render_sheet("URL 메시지", url_df, "url")

    st.subheader("URL 미리 보기")
    preview_records = build_url_preview_records(base_df)
    if not preview_records:
        st.info("현재 유지 상태인 URL 메시지가 없습니다.")
    else:
        page_records, current_page, total_pages = paginate_records(
            preview_records,
            page=st.session_state.get("url_preview_page", 1),
            page_size=10,
        )
        st.session_state.url_preview_page = current_page

        # 상단 페이지 네비게이션
        st.markdown(f"**📄 총 {len(preview_records)}개 URL · {total_pages}페이지**")
        nav_cols = st.columns([1, 1] + [1] * min(total_pages, 10) + [2] if total_pages <= 10 else st.columns([1, 1, 3]))
        if nav_cols[0].button("◀ 이전", key="nav_prev_top", disabled=current_page <= 1, use_container_width=True):
            st.session_state.url_preview_page = current_page - 1
            st.rerun()
        if nav_cols[1].button("다음 ▶", key="nav_next_top", disabled=current_page >= total_pages, use_container_width=True):
            st.session_state.url_preview_page = current_page + 1
            st.rerun()
        
        if total_pages > 10:
            selected_page_top = st.selectbox(
                "페이지 이동",
                options=list(range(1, total_pages + 1)),
                index=current_page - 1,
                key="nav_select_top"
            )
            if selected_page_top != current_page:
                st.session_state.url_preview_page = selected_page_top
                st.rerun()
        elif total_pages > 1:
            for i, p in enumerate(range(1, total_pages + 1)):
                if i + 2 < len(nav_cols):
                    if nav_cols[i + 2].button(str(p), key=f"nav_page_top_{p}", use_container_width=True, type="primary" if p == current_page else "secondary"):
                        st.session_state.url_preview_page = p
                        st.rerun()

        if st.button("현재 페이지 메타데이터 불러오기", use_container_width=True):
            preview_cache = st.session_state.get("preview_cache", {})
            for record in page_records:
                if record.url in preview_cache:
                    continue
                preview_cache[record.url] = fetch_url_preview(record.url)
            st.session_state.preview_cache = preview_cache
            st.rerun()

        preview_cache = st.session_state.get("preview_cache", {})
        for idx, record in enumerate(page_records):
            preview = preview_cache.get(record.url)
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{record.dt} · {record.sender}**")
                    st.write(record.text)
                    st.code(record.url, language=None)
                    btn_cols = st.columns([1, 1])
                    if btn_cols[0].link_button("원본 URL 열기", record.url, use_container_width=True):
                        pass
                    if btn_cols[1].button(f"🗑️ 삭제", key=f"del_url_{current_page}_{idx}", use_container_width=True):
                        # 해당 row_id의 메시지 삭제
                        delete_df = st.session_state.chat_df.copy()
                        delete_df.loc[delete_df["row_id"] == record.row_id, "keep"] = False
                        st.session_state.chat_df = enrich_dataframe(delete_df)
                        # 삭제 후 URL 미리보기 목록 동기화를 위해 페이지 상태 확인
                        preview_records_after = build_url_preview_records(st.session_state.chat_df)
                        total_pages_after = max(1, ceil(len(preview_records_after) / 10))
                        if current_page > total_pages_after:
                            st.session_state.url_preview_page = 1
                        st.rerun()
                    if preview:
                        st.markdown(f"**도메인:** `{preview.domain or '-'}`")
                        st.markdown(f"**제목:** {preview.title or '-'}")
                        st.markdown(f"**설명:** {preview.description or '-'}")
                        if preview.error:
                            st.warning(f"메타데이터를 가져오지 못했습니다: {preview.error}")
                    else:
                        st.info("현재 페이지 메타데이터 불러오기를 누르면 제목/설명을 확인할 수 있습니다.")
                with col2:
                    render_screenshot_preview(record.url, height=400)

        # 하단 페이지 네비게이션 추가
        if total_pages > 1:
            st.divider()
            nav_cols_bottom = st.columns([1, 1] + [1] * min(total_pages, 10) + [2] if total_pages <= 10 else st.columns([1, 1, 3]))
            if nav_cols_bottom[0].button("◀ 이전", key="nav_prev_bottom", disabled=current_page <= 1, use_container_width=True):
                st.session_state.url_preview_page = current_page - 1
                st.rerun()
            if nav_cols_bottom[1].button("다음 ▶", key="nav_next_bottom", disabled=current_page >= total_pages, use_container_width=True):
                st.session_state.url_preview_page = current_page + 1
                st.rerun()
            
            if total_pages > 10:
                selected_page_bottom = st.selectbox(
                    "페이지 이동",
                    options=list(range(1, total_pages + 1)),
                    index=current_page - 1,
                    key="nav_select_bottom"
                )
                if selected_page_bottom != current_page:
                    st.session_state.url_preview_page = selected_page_bottom
                    st.rerun()
            elif total_pages > 1:
                for i, p in enumerate(range(1, total_pages + 1)):
                    if i + 2 < len(nav_cols_bottom):
                        if nav_cols_bottom[i + 2].button(str(p), key=f"nav_page_bottom_{p}", use_container_width=True, type="primary" if p == current_page else "secondary"):
                            st.session_state.url_preview_page = p
                            st.rerun()


    export_text = export_chat_to_text(
        parsed_chat,
        base_df,
        include_day_dividers=st.session_state.get("include_day_dividers", True),
    )

    st.subheader("다운로드")
    st.download_button(
        label="수정된 TXT 다운로드",
        data=export_text.encode(parsed_chat.encoding or "utf-8-sig", errors="replace"),
        file_name=uploaded_file.name.replace(".txt", "_cleaned.txt"),
        mime="text/plain",
        use_container_width=True,
    )

    with st.expander("파일 정보"):
        st.write(
            {
                "대화방 제목": parsed_chat.title,
                "저장한 날짜": parsed_chat.saved_at,
                "추정 인코딩": parsed_chat.encoding,
                "메시지 수": len(parsed_chat.messages),
            }
        )


if __name__ == "__main__":
    render_app()
