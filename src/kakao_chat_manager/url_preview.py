from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


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
