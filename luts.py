"""Магазин LUT на /luts. Каталог і ціни — з бота (public/catalog.json); сторінка не робить жодних записів.

Поки оплата карткою не підключена (CARD_ENABLED = False), єдина дія на сторінці — перейти в Telegram-бота.
"""
import json
import os
import re
import time

import requests
from markupsafe import Markup, escape
from flask import Blueprint, Response, abort, current_app, g, render_template, request

import luts_content as content
from luts_media import MEDIA, PAIRS
from luts_text import LUT_LANGS, NAMES, RTL, text, translated

bp = Blueprint("luts", __name__)

CATALOG_URL = os.environ.get("LUTS_CATALOG_URL", "https://bmc-lut-bot.fly.dev/public/catalog.json")
EVENT_URL = CATALOG_URL.rsplit("/", 1)[0] + "/event"
CARD_ENABLED = os.environ.get("LUTS_CARD_ENABLED", "").lower() in ("1", "true", "yes")
CACHE_SECONDS = 60
PAGE_CACHE = "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"
OTHER_LANGS = "uk,ru,ar,fa,es,fr,id"
_cache: dict = {"data": None, "etag": None, "at": 0.0}


def _seed() -> dict:
    with open(os.path.join(current_app.static_folder, "luts", "catalog_seed.json"), encoding="utf-8") as handle:
        return json.load(handle)


def get_catalog() -> dict:
    """Каталог з бота: кеш на 60 с, при збої бота — останній вдалий, а на холодному старті — знімок із репозиторію."""
    now = time.time()
    if _cache["data"] and now - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    try:
        headers = {"If-None-Match": _cache["etag"]} if _cache["etag"] and _cache["data"] else {}
        resp = requests.get(CATALOG_URL, headers=headers, timeout=2.5)
        if resp.status_code == 304 and _cache["data"]:
            _cache["at"] = now
        elif resp.status_code == 200 and resp.json().get("items"):
            _cache.update(data=resp.json(), etag=resp.headers.get("ETag"), at=now)
    except (requests.RequestException, ValueError):
        pass
    if not _cache["data"]:
        _cache.update(data=_seed(), etag=None, at=now - CACHE_SECONDS + 10)  # знімок: пробуємо бота знову за 10 с
    return _cache["data"]


def site_media(items: list[dict]) -> list[dict]:
    """Медіа бота → легкі копії сайту (scripts/sync_site_media.py): те саме кадрування, менший розмір.
    Якщо копії ще немає (щойно додане в боті), лишається оригінал із бота."""
    result, seen = [], set()
    for media in items:
        match = re.search(r"/media/(\d+)\.", media["url"])
        entry = MEDIA.get(int(match.group(1))) if match else None
        if entry:
            if entry["key"] in seen:
                continue
            seen.add(entry["key"])
            base = f"/static/luts/media/{entry['key']}"
            result.append({"video": entry["video"], "url": base + (".mp4" if entry["video"] else ".webp"),
                           "poster": base + ".webp", "w": entry["w"], "h": entry["h"], "local": True})
        else:
            result.append({"video": media["video"], "url": media["url"], "poster": None, "w": 720, "h": 900, "local": False})
    return result


def _field(item: dict, lang: str, key: str, default: str = "") -> str:
    value = (item["i18n"].get(lang) or {}).get(key) or (item["i18n"].get("en") or {}).get(key) or default
    return value.replace(" — ", ", ").replace("—", ",")


def view_items(catalog: dict, lang: str = "en") -> dict:
    """Паки й окремі LUT для шаблонів: з каталогу + наш текст про пак."""
    copy = content.for_lang(lang)["packs"]
    packs, singles = [], []
    for item in catalog["items"]:
        row = {**item, "title": _field(item, lang, "title", item["slug"].replace("_", " ").title()),
               "desc": _field(item, lang, "desc"), "media": site_media(item["media"])}
        if item["kind"] == "pack":
            row.update(copy.get(item["slug"], {}))
            row["lead_tall"] = bool(row["media"]) and row["media"][0]["h"] > row["media"][0]["w"]
            row["pair_meta"] = row.get("pair")
            packs.append(row)
        else:
            row["pair_meta"] = PAIRS.get(item["slug"])
            singles.append(row)
    packs.sort(key=lambda r: r["sort"])
    seen_clips, work = set(), []
    for pack in packs:  # портфоліо: відео паків з бота, без повторів
        for m in pack["media"]:
            if m["video"] and m["url"] not in seen_clips:
                seen_clips.add(m["url"])
                work.append(m)
    sold_alone = {slug for pack in packs for slug in pack["looks"]}
    by_slug = {s["slug"]: s for s in singles}
    for pack in packs:
        names = pack.get("look_names") or {}

        def look_title(slug: str) -> str:
            data = names.get(slug) or {}
            return (data.get(lang) or data.get("en") or {}).get("title") or slug.replace("_", " ").title()

        pack["inside"] = [by_slug.get(slug) or {"slug": slug, "title": look_title(slug), "alone": False} for slug in pack["looks"]]
        for look in pack["inside"]:
            look.setdefault("alone", True)
        pack["has_alone"] = any(look["alone"] for look in pack["inside"])
    return {"work": work, "packs": packs, "singles": singles, "by_slug": {i["slug"]: i for i in packs + singles}, "alone": sold_alone}


def _lang(lang: str) -> str:
    return lang if lang in LUT_LANGS else "en"


def _base_ctx(lang: str, **extra) -> dict:
    lang = _lang(lang)
    catalog = get_catalog()

    def u(path: str = "", target: str | None = None) -> str:
        code = target or lang
        return ("/luts" if code == "en" else f"/{code}/luts") + path

    base = current_app.config.get("LUTS_BASE_URL", "")
    path = request.path
    sub = path.split("/luts", 1)[1] if "/luts" in path else ""  # шлях без префікса мови: однаковий у всіх мов
    done = translated()
    return {
        "lang": lang, "dir": "rtl" if lang in RTL else "ltr", "T": text(lang), "u": u, "bot": catalog["bot"],
        "starter": catalog.get("starter"), "card_enabled": CARD_ENABLED, "event_url": EVENT_URL,
        "translated": lang in done, "alternates": done, "sub": sub,
        "switch": [(c, NAMES[c], u(sub, c)) for c in done],
        "base_url": base, "path": path, "pair_url": lambda name, kind, w, ext: f"/static/luts/img/pairs/{name}-{kind}-{w}.{ext}",
        **extra,
    }


def faq_ld(T: dict) -> dict:
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in T["faq"]]}


def _crumbs(ctx: dict, *trail: tuple[str, str]) -> dict:
    items = [(ctx["T"]["brand"], ctx["u"]())] + list(trail)
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": ctx["base_url"] + url}
        for i, (name, url) in enumerate(items, 1)]}


def _page(template: str, lang: str, **extra) -> Response:
    ctx = _base_ctx(lang, **extra)
    ctx["ld"] = {"@context": "https://schema.org", "@graph": ctx.pop("graph", lambda c: [])(ctx)}
    resp = Response(render_template(f"luts/{template}", **ctx))
    resp.headers["Cache-Control"] = PAGE_CACHE
    resp.headers["Content-Language"] = ctx["lang"]
    bot_origin = "/".join(CATALOG_URL.split("/")[:3])  # події і медіа йдуть на бота
    resp.headers["Content-Security-Policy"] = (
        f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; "
        f"media-src 'self' {bot_origin}; connect-src 'self' {bot_origin}; frame-ancestors 'none'; base-uri 'self'; form-action 'none'")
    return resp


def _route(rule: str):
    """Одне правило на англійську (/luts…) і одне з префіксом мови (/<lang>/luts…)."""
    def deco(fn):
        bp.add_url_rule(f"/luts{rule}", endpoint=fn.__name__, view_func=fn, defaults={"lang": "en"})
        bp.add_url_rule(f"/<any({OTHER_LANGS}):lang>/luts{rule}", endpoint=fn.__name__, view_func=fn)
        return fn
    return deco


@_route("")
def home(lang):
    shop = view_items(get_catalog(), lang)
    return _page("home.html", lang, shop=shop, graph=lambda c: [
        {"@type": "WebSite", "name": c["T"]["brand"], "url": c["base_url"] + c["u"]()}, faq_ld(c["T"])])


@_route("/free")
def free(lang):
    return _page("free.html", lang, graph=lambda c: [_crumbs(c, (c["T"]["free_title"], c["u"]("/free")))])


@_route("/rec709-vs-log")
def compare(lang):
    page = content.for_lang(lang)["compare"]
    return _page("compare.html", lang, page=page, graph=lambda c: [_crumbs(c, (page["title"], c["u"]("/rec709-vs-log")))])


@_route("/guide/<name>")
def guide(lang, name):
    guides = content.for_lang(lang)["guides"]
    page = guides.get(name)
    if page is None:
        abort(404)
    def graph(c):
        how = {"@type": "HowTo", "name": page["title"], "step": [
            {"@type": "HowToStep", "name": n, "text": d} for n, d, _ in page["steps"]]}
        return [how, _crumbs(c, (page["title"], c["u"](f"/guide/{name}")))]
    return _page("guide.html", lang, page=page, name=name, guides=guides, sizes=content.SHOT_SIZE, graph=graph)


@_route("/legal/<name>")
def legal(lang, name):
    page = content.for_lang(lang)["legal"].get(name)
    if page is None:
        abort(404)
    return _page("legal.html", lang, page=page, name=name, graph=lambda c: [
        _crumbs(c, (page["title"], c["u"](f"/legal/{name}")))])


@_route("/<slug>")
def product(lang, slug):
    shop = view_items(get_catalog(), lang)
    item = shop["by_slug"].get(slug)
    if item is None:
        abort(404)
    parents = [p for p in shop["packs"] if slug in p["looks"]] if item["kind"] == "look" else []
    def graph(c):
        photo = next((m["url"] for m in item["media"] if not m["video"]), None)
        photo = (c["base_url"] + photo) if photo and photo.startswith("/") else photo
        product_ld = {"@type": "Product", "name": item["title"], "brand": {"@type": "Brand", "name": "@blackmagicamera"},
                      "description": item.get("tagline") or item["desc"] or item["title"],
                      "category": "LUT", **({"image": photo} if photo else {})}
        return [product_ld, _crumbs(c, (item["title"], c["u"](f"/{slug}")))]
    return _page("product.html", lang, item=item, shop=shop, parents=parents, graph=graph)


def sitemap_entries(base_url: str) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """(url, пріоритет, [(hreflang, url)]) для /sitemap.xml: усі мови з готовим перекладом."""
    shop = view_items(get_catalog())
    done = translated()
    paths = ["", "/free", "/rec709-vs-log"] + [f"/guide/{n}" for n in content.GUIDES]
    paths += [f"/{slug}" for slug in shop["by_slug"]] + [f"/legal/{n}" for n in content.LEGAL]
    def url(code: str, p: str) -> str:
        return f"{base_url}{'/luts' if code == 'en' else f'/{code}/luts'}{p}"

    return [(url(code, p), "0.9" if p in ("", "/free") else "0.7", [(c, url(c, p)) for c in done] + [("x-default", url("en", p))])
            for p in paths for code in done]


STAR_SVG = ('<svg class="star" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2.6l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.4l-5.9 3.3 1.3-6.6L2.5 9.5l6.6-.8z"/></svg>')


def star(value) -> Markup:
    """⭐ у тексті кнопки замінюємо на SVG-зірку: емодзі виглядають по-різному на різних пристроях."""
    return Markup(str(escape(value)).replace("⭐", STAR_SVG))


_SHORT = re.compile(r"(?<!\w)(\w{1,3}) +", re.UNICODE)


def nb(value) -> Markup:
    """Нерозривні пробіли: короткі слова («я», «в», «I'm») не лишаються на кінці рядка, а останнє слово не стоїть самотнім."""
    text = str(escape(value))
    text = _SHORT.sub(lambda m: m.group(1) + "\u00a0", text)
    return Markup(re.sub(r" +(\S+)$", "\u00a0\\1", text))


def bio(value) -> Markup:
    """*слово* у біографії стає посиланням на канал."""
    channel = "https://t.me/blackmagicamera"
    text = str(nb(value))
    return Markup(re.sub(r"\*(.+?)\*", f'<a href="{channel}" rel="noopener">\\1</a>', text))


def register(app, base_url: str = "") -> None:
    app.jinja_env.filters["star"] = star
    app.jinja_env.filters["nb"] = nb
    app.jinja_env.filters["bio"] = bio
    app.config["LUTS_BASE_URL"] = base_url  # абсолютні canonical, hreflang і og:image
    app.register_blueprint(bp)
