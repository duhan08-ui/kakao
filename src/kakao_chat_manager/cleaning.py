from __future__ import annotations

from dataclasses import asdict
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

from .parser import ChatMessage

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


def mark_empty_messages(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    enriched.loc[enriched["normalized_text"] == "", "keep"] = False
    return enriched
