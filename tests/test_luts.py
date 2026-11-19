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
import time  # noqa: E402

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
    luts._posts.update(at=-luts.POSTS_TTL, data=None)
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
    assert hero.count("data-ba") == 0  # у героєві слайдера немає
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
    assert '<span class="h1-l">Hi,</span><span class="h1-l">I&#39;m\u00a0Mykhailo.</span>' in html and "Almost two years" in plain
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
                                                   "versions", "buy_tg", "lang_label", "before", "after", "kicker", "brand_short"}
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

    h1 = re.search(r"<h1>(.*?)</h1>", home, flags=re.S).group(1)
    h1 = htmllib.unescape(re.sub(r"</span><span[^>]*>", " ", re.sub(r"^<span[^>]*>|</span>$", "", h1))).replace("\u00a0", " ")
    ui = luts_text.load(lang)["ui"]
    assert h1 == ui["kicker"] + " " + ui["h1"]   # SEO: ключова фраза в H1 над привітанням
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
    assert '<span class="h1-l">Привіт,</span><span class="h1-l">я\u00a0Михайло.</span>' in html
    assert "Одразу навчився знімати" in html and "Я одразу навчився" not in html


def test_packs_are_calm_alternating_rows_with_collage(client):
    html = client.get("/luts").data.decode()
    rows = re.findall(r'<article class="pack-row( flip)?">', html)
    assert rows == ["", " flip", ""]  # перший: колаж ліворуч, другий навпаки
    assert html.count('class="collage-big"') == 3 and html.count('class="pack-text"') == 3 and html.count('class="collage-tiles') >= 2
    # склад у тому ж форматі, що в картці бота: «13 LUTs / Rec.709», нумерований моноширинний список, ціна, «≈ N ⭐ per LUT»
    assert "13 LUTs · Rec.709" in html and 'class="pack-chips"' in html and "<li>Era</li>" in html and 'class="pack-code"' not in html   # назви LUT чіпами, без «коду»
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


def test_only_the_top_bar_spans_the_whole_screen():
    """На широких моніторах лінії й смуги не тягнуться до країв екрана: повна ширина лише в верхньому меню."""
    css = open(os.path.join(ROOT, "static/luts/css/luts.css"), encoding="utf-8").read()
    for selector in (".band", ".foot", ".hero", ".strip"):
        for rule in re.findall(re.escape(selector) + r" \{([^}]*)\}", css):
            if selector == ".strip":
                assert "max-width" in rule or "border" not in rule
            else:
                assert "border" not in rule, f"{selector}: {rule}"


def test_bio_names_the_account_and_the_audience_without_the_word_channel(client):
    plain = client.get("/luts").data.decode().replace("\u00a0", " ")
    assert ">@blackmagicamera</a>, followed by more than 6 500 people, and shoot everything on iPhone" in plain
    assert "channel @blackmagicamera" not in plain


def test_members_are_rounded_down_so_the_claim_is_always_true():
    import luts

    assert luts.members_label(6540) == "6\u00a0500" and luts.members_label(6499) == "6\u00a0000" and luts.members_label(12999) == "12\u00a0500"
    assert luts.members_label(900) is None and luts.members_label(None) is None  # мало чи невідомо: число не показуємо


def test_bio_without_member_count_falls_back(client, monkeypatch):
    """Бот не віддав кількість підписників: біографія без числа, а не з порожнім місцем."""
    with appmod.app.app_context():
        seed = luts._seed()
    monkeypatch.setattr(luts, "get_catalog", lambda: {**seed, "channel_members": None})
    plain = client.get("/luts").data.decode().replace("\u00a0", " ")
    assert "I run <a" in plain and "followed by" not in plain


def test_hero_is_the_blackmagic_camera_screen_with_proof_badges(client):
    html = client.get("/luts").data.decode()
    hero = html[html.index('<section class="hero">'):html.index("</section>", html.index('<section class="hero">'))]
    assert 'class="phone"' not in hero and 'vf-focus' not in hero   # без айфона й без рамки фокусу на голові
    for gone in ("Internal Storage", 'class="dots', 'class="xh', 'class="tabs"', 'class="ctrl"'):   # прибрано на прохання власника
        assert gone not in hero, gone
    for part in ('class="vfinder"', 'class="hud-top"', "00:00:00:00", "Rec.709", 'class="hc c-hist"'):
        assert part in hero, part
    assert "Microphone iPhone" not in hero and 'c-mic' not in hero   # прибрано: нічого не продає
    assert 'hud-row' not in hero and 'b-fl' not in hero   # рядок параметрів і спалах прибрано: лягали на голову
    assert 'c-exp' not in hero and '<span class="tc-box"><span class="rec"></span><span class="tc" data-tc>' in hero   # ISO-картки нема; точка запису біля живого таймкоду (s.js)
    stats = hero[hero.index('<ul class="stats">'):hero.index("</ul>", hero.index('<ul class="stats">'))]
    assert stats.count("<li") == 2 and "Blackmagic Camera" in stats and "Almost 2 years" in stats
    assert 'class="st-ver"' in stats and "people</b>" in stats and "tested my LUTs" in stats   # «Свої LUT» злито з 6 000+ у верифіковану колонку
    assert "icons/blackmagic-camera-48.webp" in stats   # справжня іконка застосунку з App Store, не саморобна
    assert 'class="proof"' not in hero and "Own LUTs" not in hero and 'class="dim"' not in hero
    assert "Any video" not in stats and 'href="https://t.me/blackmagicamera"' in hero[hero.index('class="cta-row"'):]   # друга кнопка веде в канал (підписники)
    assert hero.index('class="stats"') < hero.index('id="hero-cta"') < hero.index('class="story"')   # соцдоказ перед кнопками, історія після
    assert re.search(r"\d[\d\u00a0]*000\+", hero)   # «6 000+», округлення вниз до тисячі
    assert 'style="' not in hero  # CSP: жодних inline-стилів
    for lang, word in (("uk", "LUT"), ("ru", "LUT"), ("es", "LUT"), ("ar", "LUT"), ("fa", "LUT")):  # слово LUT завжди латиницею
        page = client.get(f"/{lang}/luts").data.decode()
        assert word in page[page.index('class="stats"'):page.index("</ul>", page.index('class="stats"'))]
    uk = client.get("/uk/luts").data.decode()
    assert "Майже 2 роки" in uk and "перевірили мої LUT" in uk

def test_free_card_is_a_plain_single_card_that_goes_to_the_bot(client):
    html = client.get("/uk/luts").data.decode()
    grid = html[html.index('<div class="singles">'):html.index("</section>", html.index('<div class="singles">'))]
    free = grid[grid.index('class="single single-free"'):]
    assert "start=web_site__starter" in free and "6 безкоштовних LUT" in free and "FREE" in free   # просто: скільки безкоштовних LUT
    assert 'class="free-tile' not in html and 'class="card free"' not in html


TG_PAGE = (
    '<div class="tgme_channel_info_header_title"><span dir="auto">Blackmagic Camera | Settings</span></div>'
    '<i class="tgme_page_photo_image bgcolor1"><img src="https://cdn4.telesco.pe/file/ava.jpg"></i>'
    '<span class="counter_value">6.59K</span> <span class="counter_type">subscribers</span>'
    '<div class="tgme_widget_message_wrap"><div data-post="blackmagicamera/10"><div class="tgme_widget_message_text">https://vt.tiktok.com/x</div>'
    '<time datetime="2026-10-20T10:00:00+00:00"></time></div></div>'
    '<div class="tgme_widget_message_wrap"><div data-post="blackmagicamera/11"><a class="tgme_widget_message_photo_wrap" style="width:1px;background-image:url(\'https://cdn4.telesco.pe/file/a.jpg\')"></a>'
    '<div class="tgme_widget_message_text">Shot on iPhone &amp; LUT<br/>@blackmagicamera_bot <i class="emoji" style="x"><b>🔥</b></i></div>'
    '<div class="tgme_widget_message_reactions"><span class="tgme_reaction tgme_reaction_paid"><i class="icon icon-telegram-stars"></i>5</span>'
    '<span class="tgme_reaction"><i class="emoji" style="background-image:url(\'//telegram.org/img/emoji/40/F09F94A5.png\')"><b>🔥</b></i>4</span></div>'
    '<span class="tgme_widget_message_views">5.3K</span><time datetime="2026-10-23T17:46:43+00:00"></time></div></div>')


def test_channel_feed_parses_header_posts_reactions_and_views():
    feed = luts.parse_channel(TG_PAGE)
    assert feed["title"] == "Blackmagic Camera | Settings" and feed["subs"] == "6.59K" and feed["avatar"].endswith("ava.jpg")
    assert [p["id"] for p in feed["posts"]] == [10, 11]   # від старших до новіших, як у чаті
    post = feed["posts"][1]
    assert post["photo"].endswith("a.jpg") and post["views"] == "5.3K" and post["time"] == "17:46" and post["day"] == "2026-10-23"
    assert post["text"] == "Shot on iPhone & LUT\n@blackmagicamera_bot 🔥"
    assert post["reactions"] == [{"paid": True, "img": "", "char": "", "n": "5"},
                                 {"paid": False, "img": "https://telegram.org/img/emoji/40/F09F94A5.png", "char": "🔥", "n": "4"}]


def test_home_shows_the_channel_as_a_telegram_chat_and_hides_it_when_telegram_is_down(client, monkeypatch):
    down = client.get("/uk/luts").data.decode()
    assert 'id="channel"' not in down and "data-faq" not in down and "FAQPage" not in down   # Telegram недоступний: блоку немає; питань більше нема (буде AI-помічник)
    monkeypatch.setitem(luts._posts, "data", luts.parse_channel(TG_PAGE))
    monkeypatch.setitem(luts._posts, "at", time.time())
    html = client.get("/uk/luts").data.decode()
    assert 'class="tg-window"' in html and "https://t.me/blackmagicamera/11" in html and 'class="tg-join"' in html
    nav = html[html.index('class="top-nav"'):html.index("</nav>", html.index('class="top-nav"'))]
    assert 'href="/uk/luts#catalog"' in nav and 'href="/uk/luts#singles"' in nav and 'href="/uk/luts#channel"' in nav and "/free" not in nav
    assert 'href="https://t.me/blackmagicamera_bot"' in html and 'class="tg-react paid"' in html and "6.59K" in html
    data = client.get("/luts/channel.json").get_json()
    assert data["ids"] == [10, 11] and "tg-msg" in data["html"] and data["sig"]
