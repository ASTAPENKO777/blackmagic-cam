"""/luts: сторінки віддаються, каталог має запасний знімок, у розмітці немає $ і зайвих обіцянок."""
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Те саме оточення, що в test_security: app імпортується один раз на весь прогін.
sys.path.insert(0, os.path.dirname(__file__))
import test_security  # noqa: E402,F401

import pytest  # noqa: E402
import requests  # noqa: E402

import app as appmod  # noqa: E402
import luts  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    def offline(*a, **k):
        raise requests.ConnectionError("bot is down")
    monkeypatch.setattr(luts.requests, "get", offline)
    luts._cache.update(data=None, etag=None, at=0.0)  # холодний старт без бота: працює знімок
    return appmod.app.test_client()


PAGES = ["/luts", "/luts/free", "/luts/rec709-vs-log", "/luts/guide/blackmagic-camera", "/luts/guide/capcut",
         "/luts/guide/vn", "/luts/guide/lumafusion", "/luts/legal/terms", "/luts/legal/privacy",
         "/luts/legal/refund", "/luts/legal/license", "/luts/rec709_collection", "/luts/caribe"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render_from_seed_when_bot_is_down(client, path):
    assert client.get(path).status_code == 200


def test_unknown_pages_are_404(client):
    assert client.get("/luts/nope").status_code == 404
    assert client.get("/luts/guide/nope").status_code == 404
    assert client.get("/luts/legal/nope").status_code == 404


def test_no_dollar_prices_while_card_is_off(client):
    """Поки оплата карткою не підключена, на сторінках немає цін у $."""
    for path in PAGES:
        html = client.get(path).data.decode()
        assert "$" not in re.sub(r"<script.*?</script>", "", html, flags=re.S), path


def test_buttons_go_to_the_bot_with_a_start_payload(client):
    html = client.get("/luts").data.decode()
    links = re.findall(r'href="https://t\.me/(\w+)\?start=(web_site__[a-z0-9_]+)"', html)
    assert links and all(len(payload) <= 64 for _, payload in links)
    assert {"web_site__cinematic_pro_15", "web_site__starter"} <= {p for _, p in links}


def test_hero_slider_is_accessible_and_sized(client):
    html = client.get("/luts").data.decode()
    assert 'type="range"' in html and 'aria-label="Compare before and after"' in html
    assert re.search(r'<img[^>]+width="768" height="960"', html)  # место під кадр зарезервоване: CLS 0


def test_csp_allows_only_the_bot_origin(client):
    csp = client.get("/luts").headers["Content-Security-Policy"]
    assert "connect-src 'self' https://bmc-lut-bot.fly.dev" in csp and "unsafe-inline" not in csp.split("style-src")[1].split(";")[0]


def test_other_languages_are_noindex_until_translated(client):
    assert 'rel="canonical"' in client.get("/luts").data.decode()
    html = client.get("/uk/luts").data.decode()
    assert 'name="robots" content="noindex, follow"' in html and 'dir="ltr"' in html
    assert 'dir="rtl"' in client.get("/ar/luts").data.decode()


def test_sitemap_lists_luts_pages(client):
    sitemap = client.get("/sitemap.xml").data.decode()
    assert "http://test.local/luts</loc>" in sitemap and "/luts/guide/blackmagic-camera" in sitemap
    assert "/uk/luts" not in sitemap


def test_catalog_uses_bot_data_and_falls_back(monkeypatch):
    class Resp:
        status_code = 200
        headers = {"ETag": '"v1"'}
        def json(self):
            return {"bot": "x_bot", "items": [{"slug": "p", "kind": "pack", "i18n": {"en": {"title": "P"}}, "price_stars": 5,
                    "count": 1, "versions": ["Rec.709"], "looks": [], "media": [], "pairs": [], "sort": 0}]}
    monkeypatch.setattr(luts.requests, "get", lambda *a, **k: Resp())
    luts._cache.update(data=None, etag=None, at=0.0)
    with appmod.app.app_context():
        assert luts.get_catalog()["bot"] == "x_bot"
        monkeypatch.setattr(luts.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()))
        luts._cache["at"] = 0.0  # кеш прострочений, бот лежить → лишається останній вдалий каталог
        assert luts.get_catalog()["bot"] == "x_bot"
