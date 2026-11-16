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
import luts_content  # noqa: E402
import luts_text  # noqa: E402


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


def test_sliders_live_in_pack_blocks_not_in_the_hero(client):
    """Герой — профіль автора без повзунка. Повзунок LUT OFF / LUT ON стоїть на 36% у кожному пак-блоці головної й на сторінках паків."""
    home = client.get("/luts").data.decode()
    hero = home[home.index('<section class="hero">'):home.index("</section>", home.index('<section class="hero">'))]
    assert "data-ba" not in hero
    assert home.count("data-ba") == 3 and home.count('value="36"') == 3 and "LUT OFF" in home
    page = client.get("/luts/rec709_collection").data.decode()
    assert 'type="range"' in page and 'aria-label="Compare before and after"' in page and 'value="36"' in page
    assert re.search(r'<img[^>]+width="768" height="960"', page)  # місце під кадр зарезервоване: CLS 0


def test_single_look_with_its_own_photo_gets_a_slider(client):
    import luts_media

    assert luts_media.PAIRS, "пари для окремих LUT мають бути згенеровані"
    slug = next(iter(luts_media.PAIRS))
    page = client.get(f"/luts/{slug}").data.decode()
    assert 'type="range"' in page
    pair = luts_media.PAIRS[slug]
    for width in pair["widths"]:
        assert os.path.exists(os.path.join(ROOT, f"static/luts/img/pairs/{pair['name']}-after-{width}.webp"))


def test_hero_is_a_bio_without_dashes(client):
    html = client.get("/luts").data.decode()
    plain = html.replace("\u00a0", " ")
    assert "Hi, I&#39;m\u00a0Mykhailo." in html and "Almost two years" in plain and "The shot is finished before you hit record." in plain
    assert 'href="https://t.me/blackmagicamera"' in html  # слово «channel» у біографії веде в канал
    assert 'class="portrait"' in html


def test_no_long_dashes_in_visible_site_text():
    """Довгі тире — ознака машинного тексту. У текстах сайту (усі мови) їх немає."""
    import json
    import luts_content

    texts = [json.dumps(luts_text.EN, ensure_ascii=False), json.dumps(luts_content.GUIDES, ensure_ascii=False),
             json.dumps(luts_content.LEGAL, ensure_ascii=False), json.dumps(luts_content.COMPARE, ensure_ascii=False)]
    texts += [open(os.path.join(ROOT, "luts_i18n", f"{code}.json"), encoding="utf-8").read() for code in luts_text.LUT_LANGS[1:]]
    for text in texts:
        assert "—" not in text and "–" not in text


def test_csp_allows_only_the_bot_origin(client):
    csp = client.get("/luts").headers["Content-Security-Policy"]
    assert "connect-src 'self' https://bmc-lut-bot.fly.dev" in csp and "unsafe-inline" not in csp.split("style-src")[1].split(";")[0]


def test_every_language_is_indexable_with_hreflang_and_rtl(client):
    html = client.get("/uk/luts").data.decode()
    assert 'rel="canonical" href="http://test.local/uk/luts"' in html and 'name="robots"' not in html
    assert html.count('hreflang="') >= 9 and 'hreflang="x-default" href="http://test.local/luts"' in html
    assert 'dir="ltr"' in html and 'lang="uk"' in html
    for code in ("ar", "fa"):
        assert 'dir="rtl"' in client.get(f"/{code}/luts").data.decode()
    assert client.get("/de/luts").status_code == 404


def test_sitemap_lists_every_language_with_alternates(client):
    sitemap = client.get("/sitemap.xml").data.decode()
    assert "http://test.local/luts</loc>" in sitemap and "/luts/guide/blackmagic-camera" in sitemap
    for code in luts_text.LUT_LANGS[1:]:
        assert f"http://test.local/{code}/luts</loc>" in sitemap
        assert f'hreflang="{code}" href="http://test.local/{code}/luts"' in sitemap


LANGS = luts_text.LUT_LANGS[1:]


def _ph(text):
    return sorted(re.findall(r"\{\w+\}", text))


@pytest.mark.parametrize("lang", LANGS)
def test_translation_is_complete_and_keeps_placeholders(lang):
    tr = luts_text.load(lang)
    assert set(tr["ui"]) <= set(luts_text.EN), "ключ перекладу, якого немає в англійській"
    missing = set(luts_text.EN) - set(tr["ui"]) - {"not_found", "guide_h", "guides", "updated", "free_look", "only_in_pack",
                                                   "versions", "buy_tg", "lang_label", "before", "after", "kicker"}
    assert not missing, f"{lang}: немає перекладу для {sorted(missing)}"
    for key, value in tr["ui"].items():
        base = luts_text.EN[key]
        if isinstance(base, str):
            assert _ph(value) == _ph(base), f"{lang}.{key}: плейсхолдери"
        else:
            assert len(value) == len(base), f"{lang}.{key}: кількість елементів"
    assert set(tr["packs"]) == set(luts_content.PACK_COPY)
    for name, guide in luts_content.GUIDES.items():
        assert len(tr["guides"][name]["steps"]) == len(guide["steps"]), f"{lang}: кроки {name}"
    assert len(tr["compare"]["blocks"]) == len(luts_content.COMPARE["blocks"])
    for name, page in luts_content.LEGAL.items():
        assert len(tr["legal"][name]["body"]) == len(page["body"]), f"{lang}: legal {name}"


@pytest.mark.parametrize("lang", LANGS)
def test_translated_pages_render_in_their_language_without_dollars(client, lang):
    for path in ("", "/free", "/rec709_collection", "/guide/capcut", "/rec709-vs-log", "/legal/terms"):
        resp = client.get(f"/{lang}/luts{path}")
        assert resp.status_code == 200, path
        html = re.sub(r"<script.*?</script>", "", resp.data.decode(), flags=re.S)
        assert "$" not in html and f'lang="{lang}"' in html
    home = client.get(f"/{lang}/luts").data.decode()
    import html as htmllib

    assert luts_text.load(lang)["ui"]["h1"] in htmllib.unescape(home).replace("\u00a0", " ")
    assert luts_text.load(lang)["ui"]["cta_all"] in home


def test_language_switcher_keeps_the_page(client):
    html = client.get("/ru/luts/guide/capcut").data.decode()
    assert 'href="/uk/luts/guide/capcut"' in html and 'href="/luts/guide/capcut"' in html


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


def test_static_assets_are_versioned(client):
    """/static отдається з immutable на рік: без ?v=<хеш> браузер навічно тримає стару копію після змін."""
    html = client.get("/luts").data.decode()
    for ref in re.findall(r'(?:href|src)="(/static/luts/(?:css|js)/[^"]+)"', html):
        assert "?v=" in ref, ref
    assert re.search(r'portrait-768\.webp\?v=', html)


def test_only_bot_media_on_the_site(client):
    """Відео й фото на сайті — копії медіа з бота (static/luts/media/<хеш>), а не окремий матеріал; усе існує на диску."""
    import luts_media

    html = client.get("/luts").data.decode()
    refs = set(re.findall(r'(?:data-src|src|poster)="(/static/luts/media/[^"]+)"', html))
    assert refs, "портфоліо з відео бота має бути на головній"
    for ref in refs:
        assert os.path.exists(os.path.join(ROOT, ref.lstrip("/"))), ref
    assert not os.path.exists(os.path.join(ROOT, "static/luts/video")), "кліпи не з бота прибрано"
    for entry in luts_media.MEDIA.values():
        base = os.path.join(ROOT, "static/luts/media", entry["key"])
        assert os.path.exists(base + (".mp4" if entry["video"] else ".webp"))


def test_video_keeps_the_bot_aspect_ratio(client):
    html = client.get("/luts").data.decode()
    sizes = {(int(w), int(h)) for w, h in re.findall(r'<video[^>]*width="(\d+)" height="(\d+)"', html)}
    assert sizes and all(abs(w / h - r) < 0.02 for w, h in sizes for r in [w / h]), sizes
    assert any(h > w for w, h in sizes) and any(w > h for w, h in sizes)  # вертикальні й горизонтальні — як у боті


def test_name_stays_next_to_i_in_ukrainian_heading(client):
    """«я Михайло» не розривається переносом: між ними нерозривний пробіл."""
    import html as htmllib

    html = htmllib.unescape(client.get("/uk/luts").data.decode())
    assert "Привіт, я\u00a0Михайло." in html
    assert "Одразу навчився знімати" in html and "Я одразу навчився" not in html


def test_packs_are_big_alternating_rows_with_collage_and_telegram_style_message(client):
    html = client.get("/luts").data.decode()
    rows = re.findall(r'<article class="pack-row( flip)?">', html)
    assert rows == ["", " flip", ""]  # перший: колаж ліворуч, другий навпаки
    assert html.count('class="collage-lead"') == 3 and html.count('class="msg"') == 3
    # у стилі картки бота: «13 LUTs / Rec.709», пронумерований моноширинний список, ціна, «≈ N ⭐ per LUT»
    assert re.search(r"<b>13 LUTs / Rec\.709</b>", html) and 'class="msg-code"' in html and "1. Era" in html
    assert "per LUT" in html and html.count("Buy in Telegram") >= 3
    assert 'href="/luts/cinematic_pro_15"' not in html  # пак не відкривається окремою сторінкою: усе на головній


def test_inside_list_matches_the_bot_format():
    import luts

    eight = luts.numbered_block([f"Look {i}" for i in range(1, 9)], "en")
    assert eight.splitlines()[0].startswith("1. Look 1") and "5. Look 5" in eight.splitlines()[0]   # дві колонки, як у боті
    assert luts.numbered_block(["A", "B", "C"], "en") == "1. A\n2. B\n3. C"
    assert "\n" in luts.numbered_block([f"Look {i}" for i in range(1, 9)], "ar") and "  " not in luts.numbered_block([f"L{i}" for i in range(1, 9)], "ar")  # RTL: одна колонка


def test_single_looks_are_simple_cards_without_buy_buttons(client):
    html = client.get("/luts").data.decode()
    block = html[html.index('<div class="singles">'):html.index("</section>", html.index('<div class="singles">'))]
    assert block.count('class="single"') >= 8 and "Buy" not in block and "single-price" in block
