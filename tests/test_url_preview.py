from kakao_chat_manager.url_preview import fetch_url_preview


class DummyResponse:
    def __init__(self):
        self.url = "https://example.com/article"
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.text = """
        <html>
          <head>
            <title>Fallback Title</title>
            <meta property=\"og:title\" content=\"테스트 제목\" />
            <meta property=\"og:description\" content=\"설명입니다\" />
            <meta property=\"og:site_name\" content=\"Example Site\" />
            <meta property=\"og:image\" content=\"https://example.com/image.png\" />
          </head>
        </html>
        """


def test_fetch_url_preview_extracts_metadata(monkeypatch):
    fetch_url_preview.cache_clear()

    def fake_get(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("requests.get", fake_get)
    preview = fetch_url_preview("https://example.com/article")

    assert preview.title == "테스트 제목"
    assert preview.description == "설명입니다"
    assert preview.site_name == "Example Site"
    assert preview.image == "https://example.com/image.png"
    assert preview.status_code == 200
