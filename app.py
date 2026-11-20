import os
import re
import secrets
import hmac
import hashlib
import base64
import json
import smtplib
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import escape as html_escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from flask import Flask, render_template, redirect, request, abort, url_for, make_response, Response, g, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from db import (init_db, save_purchase, purchase_exists_for_session)
from devices import DEVICES, get_device, group_template
from learn import (
    get_article as get_learn_article,
    indexable_articles as indexable_learn_articles,
    is_indexable as is_learn_indexable,
)
from translations import TRANSLATIONS
from testimonials import TESTIMONIALS
import luts as luts_shop
from luts import sitemap_entries as luts_sitemap_entries
from bmc_knowledge import build_full_knowledge

load_dotenv()

app = Flask(__name__)
# Vercel terminates HTTPS at the edge; without ProxyFix, request.is_secure is False
# inside the function and Flask drops Secure cookies. Trust X-Forwarded-Proto.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

HMAC_SECRET             = os.environ.get("KOFI_FULFILL_SECRET", "")
PAYHIP_PRODUCT_URL      = os.environ.get("PAYHIP_PRODUCT_URL", "")
PAYHIP_API_KEY          = os.environ.get("PAYHIP_API_KEY", "").strip()
# Payhip's webhook is account-wide: it fires for every product and every event type.
# Only items matching these keys unlock the guide. Optional comma list of
# product_key / product_id / product_permalink values; when unset, the key parsed
# from PAYHIP_PRODUCT_URL (https://payhip.com/b/<key>) is used.
PAYHIP_GUIDE_PRODUCT_KEYS = os.environ.get("PAYHIP_GUIDE_PRODUCT_KEYS", "")
GMAIL_USER              = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD      = os.environ.get("GMAIL_APP_PASSWORD", "")
# BASE_URL feeds every canonical, sitemap entry and emailed access link, and the
# Vercel value has been wrong in two different ways: once with a trailing newline
# ("https://host\n/ru/" in all 96 sitemap URLs) and once empty. Normalize it, and
# when it is unusable fall back to the real host on Vercel rather than to
# localhost, which would put dead links in customers' inboxes.
PRODUCTION_HOST         = "https://blackmagiccam.fly.dev"
_BASE_URL_ENV           = os.environ.get("BASE_URL", "").strip().rstrip("/")
BASE_URL                = _BASE_URL_ENV or (
    PRODUCTION_HOST if os.environ.get("VERCEL") == "1" else "http://localhost:5001"
)
ADMIN_EMAIL             = os.environ.get("ADMIN_EMAIL", GMAIL_USER)
# Search Console verification: *.vercel.app can only be verified as a URL-prefix
# property (the subdomain is on the Public Suffix List), and the meta tag is the
# one method that works without DNS control.
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "").strip()
PRICE_USD               = 4.99

GROQ_API_KEY            = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL              = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL            = "https://api.groq.com/openai/v1/chat/completions"
AI_DAILY_LIMIT          = int(os.environ.get("AI_DAILY_LIMIT_PER_USER", "30"))
TELEGRAM_BOT_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID", "")

_LEGACY_USDT_ADDR = os.environ.get("BINANCE_USDT_ADDRESS", "")

CRYPTO_NETWORKS = {
    "trc20": {
        "coin": "USDT",
        "network_label": "TRC20 (Tron)",
        "address": os.environ.get("BINANCE_USDT_ADDRESS_TRC20") or _LEGACY_USDT_ADDR,
    },
    "bep20": {
        "coin": "USDT",
        "network_label": "BEP20 (BNB Chain)",
        "address": os.environ.get("BINANCE_USDT_ADDRESS_BEP20", ""),
    },
    "erc20": {
        "coin": "USDT",
        "network_label": "ERC20 (Ethereum)",
        "address": os.environ.get("BINANCE_USDT_ADDRESS_ERC20", ""),
    },
    "ton": {
        "coin": "USDT",
        "network_label": "TON",
        "address": os.environ.get("BINANCE_USDT_ADDRESS_TON") or os.environ.get("TON_ADDRESS", ""),
        # Binance credits TON deposits to a shared exchange address by MEMO; a
        # transfer without it is not credited to the owner's account.
        "memo": os.environ.get("BINANCE_USDT_MEMO_TON", "").strip(),
        # Configured through the BINANCE_* variable = an exchange deposit address.
        "exchange": bool(os.environ.get("BINANCE_USDT_ADDRESS_TON", "").strip()),
    },
}

def _enabled_networks() -> dict:
    return {k: v for k, v in CRYPTO_NETWORKS.items() if v["address"]}

_VERCEL_ENV = os.environ.get("VERCEL_ENV", "")
# Treat localhost AND Vercel preview as "dev" — preview environments don't have
# the production secrets (KOFI_FULFILL_SECRET, Gmail, etc.) and otherwise the
# app raises at import time on every preview deploy.
IS_DEV = (
    (os.environ.get("VERCEL") != "1") or (_VERCEL_ENV != "production")
) and os.environ.get("FLASK_ENV") != "production"

if not HMAC_SECRET or len(HMAC_SECRET) < 32:
    if IS_DEV:
        app.logger.warning("KOFI_FULFILL_SECRET missing/short — generating ephemeral dev secret. Tokens will NOT persist across restarts.")
        HMAC_SECRET = secrets.token_hex(32)
    else:
        raise RuntimeError("KOFI_FULFILL_SECRET must be set (>=32 chars) in production")

_EXPECTED_PAYHIP_SIG = hashlib.sha256(PAYHIP_API_KEY.encode()).hexdigest() if PAYHIP_API_KEY else ""

UPSTASH_URL   = (os.environ.get("UPSTASH_REDIS_REST_URL")   or os.environ.get("KV_REST_API_URL")   or "").rstrip("/")
UPSTASH_TOKEN = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or "").strip()

def _kv_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)

def _kv_cmd(cmd: list):
    """Run one Redis command through Upstash REST (JSON command form: POST the
    base URL with a JSON array body). Returns the `result` field; raises on error."""
    req = urllib.request.Request(
        UPSTASH_URL,
        data=json.dumps([str(c) for c in cmd]).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {UPSTASH_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(f"upstash error: {body['error']}")
    return body.get("result") if isinstance(body, dict) else None

def _kv_set(key: str, value: str, ttl_seconds: int | None = 86400) -> bool:
    if not _kv_configured():
        return False
    try:
        cmd = ["SET", key, value]
        if ttl_seconds:
            cmd += ["EX", int(ttl_seconds)]
        return _kv_cmd(cmd) == "OK"
    except Exception as e:
        app.logger.warning(f"kv_set failed key={key!r}: {e}")
        return False

def _kv_set_nx(key: str, value: str, ttl: int | None = None) -> bool:
    """SET key value NX [EX ttl]. True if this call created the key.

    Fails OPEN: when KV is not configured or the call errors, returns True so a
    paying customer is never blocked by an outage. Callers that guard fulfilment
    therefore keep their own secondary check (the SQLite purchase row)."""
    if not _kv_configured():
        app.logger.error(f"KV NOT CONFIGURED — set-once guard for {key!r} is disabled (failing open)")
        return True
    try:
        cmd = ["SET", key, value, "NX"]
        if ttl:
            cmd += ["EX", int(ttl)]
        return _kv_cmd(cmd) == "OK"
    except Exception as e:
        app.logger.error(f"KV UNAVAILABLE — set-once guard for {key!r} failed open: {e}")
        return True

def _kv_get(key: str) -> str | None:
    if not _kv_configured():
        return None
    try:
        result = _kv_cmd(["GET", key])
        return result if isinstance(result, str) and result else None
    except Exception as e:
        app.logger.warning(f"kv_get failed key={key!r}: {e}")
        return None

def _kv_del(key: str) -> None:
    if not _kv_configured():
        return
    try:
        _kv_cmd(["DEL", key])
    except Exception:
        pass

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _is_valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(_EMAIL_RE.match(email))

def _sanitize_header(v: str) -> str:
    return (v or "").replace("\r", "").replace("\n", "").strip()[:200]

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)



# ── Tokens ────────────────────────────────────────────────────────────────────
# Every token is base64url(JSON) + "." + hexdigest[:20]. New tokens carry
# t=<purpose> and are signed with a purpose-derived key, so a token minted for one
# job (e.g. the customer's order page) can never be replayed at another (access,
# owner confirmation). Tokens emailed before purposes existed are signed with the
# master secret and accepted only by their exact key sets — see _claims().
TOKEN_PURPOSES = ("acc", "pick", "cfm", "ord")
_LEGACY_KEYSETS = {"acc": {"e", "d", "s"}, "pick": {"e", "s"}}

def _purpose_key(purpose: str) -> bytes:
    return hmac.new(HMAC_SECRET.encode(), ("purpose:" + purpose).encode(), hashlib.sha256).digest()

def _sign(payload: str, key: bytes | None = None) -> str:
    return hmac.new(key or HMAC_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]

def _encode_token(data: dict, purpose: str) -> str:
    if purpose not in TOKEN_PURPOSES:
        raise ValueError(f"unknown token purpose {purpose!r}")
    data = dict(data)
    if data.get("t", purpose) != purpose:
        raise ValueError(f"token t={data.get('t')!r} does not match purpose {purpose!r}")
    data.setdefault("t", purpose)  # keeps a caller-chosen key order (nonce first)
    payload = base64.urlsafe_b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode().rstrip('=')
    return f"{payload}.{_sign(payload, _purpose_key(purpose))}"

def _decode_token(token: str, key: bytes | None = None) -> dict | None:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig.encode(), _sign(payload, key).encode()):
            return None
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def _claims(token: str, purpose: str) -> dict | None:
    """The single gate for every token-bearing route.

    acc  (/access, /api/ai/chat): new t=="acc", or legacy master-signed exactly {e,d,s}
    pick (/pick/...):             new t=="pick", or legacy master-signed exactly {e,s}
    cfm  (owner /crypto/confirm): new t=="cfm" only
    ord  (customer /crypto/pay):  new t=="ord" only
    A legacy crypto confirm token {d,e,n,net} matches none of these.
    """
    if purpose not in TOKEN_PURPOSES or not isinstance(token, str) or not token or len(token) > 600:
        return None
    data = _decode_token(token, _purpose_key(purpose))
    if data is not None and data.get("t") == purpose:
        return data
    legacy = _LEGACY_KEYSETS.get(purpose)
    if legacy:
        data = _decode_token(token)
        if (data is not None and set(data) == legacy
                and all(isinstance(data[k], str) and data[k] for k in legacy)):
            return data
    return None

def _purchase_nonce(sale_id: str) -> str:
    """Stable per-sale nonce: re-sending the access email yields the same link."""
    return hmac.new(HMAC_SECRET.encode(), ("nonce:" + sale_id).encode(), hashlib.sha256).hexdigest()[:12]

def _new_access_token(email: str, device_slug: str, sale_id: str, nonce: str | None = None) -> str:
    # Per-purchase unique field first, so the token prefix differs per purchase.
    return _encode_token(
        {"n": nonce or _purchase_nonce(sale_id), "t": "acc", "e": email, "d": device_slug, "s": sale_id},
        "acc",
    )

def _is_denied(data: dict) -> bool:
    """Revocation list in KV: deny:s:<sale_id> (refunds) and deny:n:<nonce>."""
    for field, prefix in (("s", "deny:s:"), ("n", "deny:n:")):
        value = data.get(field)
        if isinstance(value, str) and value and _kv_get(prefix + value):
            return True
    return False



try:
    init_db()
except Exception as e:
    app.logger.error(f"init_db failed at startup: {e}")



SUPPORTED_LANGS = ('en', 'ru', 'ar')
URL_LANGS = ('ru', 'ar')  


def _strip_lang_prefix(path: str) -> str:
    """Remove leading /ru or /ar prefix, leaving the canonical English path."""
    for lang in URL_LANGS:
        if path == f"/{lang}" or path == f"/{lang}/":
            return "/"
        if path.startswith(f"/{lang}/"):
            return path[len(lang) + 1:]
    return path


def _localize_path(lang: str, base: str) -> str:
    """Build the URL path for a given language given a canonical (English) path."""
    if lang == "en":
        return base
    if base == "/":
        return f"/{lang}/"
    return f"/{lang}{base}"


def _is_publicly_localized(path: str) -> bool:
    """True if the path has registered lang URL variants (/, /select, /guide/<slug>).

    The slug is validated against DEVICES: accepting any /guide/* string made every
    404 under /guide/ advertise itself as canonical and indexable.
    """
    base = _strip_lang_prefix(path)
    if base in ("/", "/select"):
        return True
    if base.startswith("/guide/") and get_device(base[len("/guide/"):]):
        return True
    return False


def _is_guide_path(path: str) -> bool:
    return _strip_lang_prefix(path).startswith("/guide/")


def _is_indexable_learn_path(path: str) -> bool:
    """/learn is English-only: indexable with a canonical, but no hreflang.

    An article that fails learn.review() (too thin, or no link into a guide) is
    reachable but not indexed, so a draft can never quietly enter the index.
    """
    if path == "/learn":
        return True
    if path.startswith("/learn/"):
        article = get_learn_article(path[len("/learn/"):])
        return bool(article) and is_learn_indexable(article)
    return False


def _safe_next_path(value):
    """Allow only same-origin, well-formed relative paths to prevent open redirects."""
    if not isinstance(value, str) or not value or len(value) > 500:
        return None
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return None
    return value


def detect_language():
    url_lang = getattr(g, "url_lang", None)
    if url_lang in SUPPORTED_LANGS:
        return url_lang
    lang = request.cookies.get("lang")
    if lang in SUPPORTED_LANGS:
        return lang
    return request.accept_languages.best_match(SUPPORTED_LANGS, default="en")


_STATIC_VERSIONS = {}


def _static_version(filename: str) -> str:
    """Short content hash of a static file, computed once per process.

    Deliberately not mtime: Vercel normalizes file timestamps in the build output
    (every deploy came out as 1540000000), so an mtime stamp is identical on every
    deploy and never breaks the cache.
    """
    if filename in _STATIC_VERSIONS:
        return _STATIC_VERSIONS[filename]
    try:
        with open(os.path.join(app.static_folder, filename), "rb") as handle:
            version = hashlib.sha256(handle.read()).hexdigest()[:10]
    except OSError:
        version = ""
    _STATIC_VERSIONS[filename] = version
    return version


@app.context_processor
def inject_static_version():
    """Append a build version to static asset URLs.

    /static/* is served with `public, max-age=31536000, immutable`, and the links
    carried no version, so a returning visitor kept the cached CSS after a deploy:
    a redesign could ship and simply not appear until a hard refresh.
    """
    def static_v(filename: str) -> str:
        url = url_for("static", filename=filename)
        version = _static_version(filename)
        return f"{url}?v={version}" if version else url

    return {"static_v": static_v}


@app.context_processor
def inject_i18n():
    lang = detect_language()
    is_public = _is_publicly_localized(request.path)

    # Guide bodies are English-only. Their /ru/ and /ar/ URLs stay reachable for the
    # language switcher, but must not be indexed as Russian/Arabic pages — that is a
    # wrong-language signal on 60 URLs. They get noindex,follow and no hreflang.
    guide_in_other_lang = is_public and _is_guide_path(request.path) and lang != "en"
    seo_index = is_public and not guide_in_other_lang

    if is_public:
        base_path = _strip_lang_prefix(request.path)
        alternates = {code: _localize_path(code, base_path) for code in SUPPORTED_LANGS}
    else:
        if request.method == "GET":
            current = request.full_path.rstrip("?")
            next_q = urllib.parse.quote(current, safe="/")
        else:
            next_q = "/"  
        alternates = {code: f"/set-lang/{code}?next={next_q}" for code in SUPPORTED_LANGS}

    def lang_link(path: str, target_lang: str | None = None) -> str:
        """Prefix an internal path with the current (or target) language prefix."""
        if not path.startswith("/") or path.startswith("//"):
            return path
        return _localize_path(target_lang or lang, path)

    # Canonical is tracked separately from the language alternates: /learn pages
    # are indexable English-only pages, so they need a canonical but must not
    # advertise /ru/ and /ar/ variants that do not exist.
    if seo_index:
        canonical_path = alternates[lang]
    elif _is_indexable_learn_path(request.path):
        canonical_path = request.path
    else:
        canonical_path = None

    return {
        "lang": lang,
        "t": TRANSLATIONS[lang],
        "lang_alternates": alternates,
        "lang_link": lang_link,
        "is_seo_localized": seo_index,
        "seo_noindex_follow": guide_in_other_lang,
        "canonical_path": canonical_path,
        "emit_hreflang": seo_index,
        "google_site_verification": GOOGLE_SITE_VERIFICATION,
    }


@app.after_request
def persist_url_lang(resp):
    """When a localized URL is hit (/ru/..., /ar/...), persist that choice in a cookie
    so downstream private routes (crypto/pick/access) inherit the language too."""
    url_lang = getattr(g, "url_lang", None)
    if url_lang in URL_LANGS and request.cookies.get("lang") != url_lang:
        resp.set_cookie(
            "lang", url_lang,
            max_age=365 * 24 * 3600,
            samesite="Lax",
            secure=not IS_DEV,
            httponly=False,
        )
    return resp


@app.route("/set-lang/<lang>")
def set_lang(lang):
    if lang not in SUPPORTED_LANGS:
        lang = "en"

    next_path = _safe_next_path(request.args.get("next"))
    if next_path:
        target = next_path
    else:
        referrer = request.referrer or "/"
        try:
            parsed = urllib.parse.urlparse(referrer)
            ref_path = parsed.path or "/"
            if parsed.netloc and parsed.netloc != request.host:
                target = "/"  
            elif _is_publicly_localized(ref_path):
                base = _strip_lang_prefix(ref_path)
                target_path = _localize_path(lang, base)
                target = urllib.parse.urlunparse(parsed._replace(path=target_path))
            else:
                target = ref_path + (("?" + parsed.query) if parsed.query else "")
        except Exception:
            target = _localize_path(lang, "/")

    resp = make_response(redirect(target))
    resp.set_cookie(
        "lang", lang,
        max_age=365 * 24 * 3600,
        samesite="Lax",
        secure=not IS_DEV,
        httponly=False,
    )
    return resp



@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.ico"), code=301)

@app.route("/")
@app.route("/<any(ru, ar):lang>/")
def index(lang="en"):
    g.url_lang = lang
    if lang == "en" and not request.cookies.get("lang"):
        best = request.accept_languages.best_match(URL_LANGS)
        if best in URL_LANGS:
            return redirect(_localize_path(best, "/"), code=302)
    return render_template("index.html", testimonials=TESTIMONIALS, devices=DEVICES)


@app.route("/select")
@app.route("/<any(ru, ar):lang>/select")
def select(lang="en"):
    g.url_lang = lang
    return render_template(
        "select.html",
        devices=DEVICES,
        payhip_url=PAYHIP_PRODUCT_URL,
        networks=_enabled_networks(),
    )


@app.route("/guide/<slug>")
@app.route("/<any(ru, ar):lang>/guide/<slug>")
def guide(slug, lang="en"):
    g.url_lang = lang
    device = get_device(slug)
    if not device:
        abort(404)
    return render_template("guide.html", device=device)


_APP_DIR = os.path.dirname(os.path.abspath(__file__))


_SANE_MTIME = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()


def _lastmod(*relpaths) -> str:
    """Newest mtime of the files backing a page, as YYYY-MM-DD.

    Honest enough to be useful: on Vercel this is the deploy time of the files that
    actually render the page, not a moving datetime.now() that crawlers learn to ignore.
    """
    newest = 0.0
    for rel in relpaths:
        try:
            newest = max(newest, os.path.getmtime(os.path.join(_APP_DIR, rel)))
        except OSError:
            continue
    if newest < _SANE_MTIME:
        # Vercel ships files with a fixed fake mtime (2018-10-20): use the deploy
        # date that scripts/deploy.sh writes into build_info.json instead.
        try:
            with open(os.path.join(_APP_DIR, "build_info.json"), encoding="utf-8") as fh:
                return json.load(fh)["date"]
        except (OSError, ValueError, KeyError):
            return ""
    return datetime.fromtimestamp(newest, timezone.utc).strftime("%Y-%m-%d")


@app.route("/learn")
def learn_hub():
    return render_template("learn_hub.html", articles=indexable_learn_articles())


@app.route("/learn/<slug>")
def learn_article(slug):
    article = get_learn_article(slug)
    if not article:
        abort(404)
    related = [d for d in (get_device(s) for s in article.get("related", [])) if d]
    others = [a for a in indexable_learn_articles() if a["slug"] != slug][:3]
    return render_template(
        "learn_article.html",
        article=article,
        related_devices=related,
        other_articles=others,
    )


@app.route("/sitemap.xml")
def sitemap():
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]

    # Localized pages: real translations exist, so all three languages are indexable.
    localized = [
        ("/", "1.0", "weekly", _lastmod("templates/index.html", "translations.py")),
        ("/select", "0.9", "weekly", _lastmod("templates/select.html", "devices.py")),
    ]
    for base, priority, changefreq, lastmod in localized:
        for lang in SUPPORTED_LANGS:
            lines.append("  <url>")
            lines.append(f"    <loc>{BASE_URL + _localize_path(lang, base)}</loc>")
            for alt_lang in SUPPORTED_LANGS:
                href = BASE_URL + _localize_path(alt_lang, base)
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{href}" />'
                )
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="x-default" '
                f'href="{BASE_URL + base}" />'
            )
            if lastmod:
                lines.append(f"    <lastmod>{lastmod}</lastmod>")
            lines.append(f"    <changefreq>{changefreq}</changefreq>")
            lines.append(f"    <priority>{priority}</priority>")
            lines.append("  </url>")

    # Guides are English-only content; the /ru/ and /ar/ variants are noindex and
    # deliberately absent here (see inject_i18n).
    guide_lastmod = _lastmod("templates/guide.html", "devices.py")
    for device in DEVICES:
        lines.append("  <url>")
        lines.append(f"    <loc>{BASE_URL}/guide/{device['slug']}</loc>")
        if guide_lastmod:
            lines.append(f"    <lastmod>{guide_lastmod}</lastmod>")
        lines.append("    <changefreq>monthly</changefreq>")
        lines.append("    <priority>0.8</priority>")
        lines.append("  </url>")

    # Free articles: English-only, and only the ones that pass learn.review().
    learn_lastmod = _lastmod("learn.py", "templates/learn_article.html")
    lines.append("  <url>")
    lines.append(f"    <loc>{BASE_URL}/learn</loc>")
    if learn_lastmod:
        lines.append(f"    <lastmod>{learn_lastmod}</lastmod>")
    lines.append("    <changefreq>weekly</changefreq>")
    lines.append("    <priority>0.7</priority>")
    lines.append("  </url>")
    for article in indexable_learn_articles():
        lines.append("  <url>")
        lines.append(f"    <loc>{BASE_URL}/learn/{article['slug']}</loc>")
        if article.get('updated', learn_lastmod):
            lines.append(f"    <lastmod>{article.get('updated', learn_lastmod)}</lastmod>")
        lines.append("    <changefreq>monthly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")

    # /luts shop: every language that has a luts_i18n/<lang>.json (see luts_text.translated).
    luts_lastmod = _lastmod("luts.py", "luts_text.py", "luts_content.py", "templates/luts/home.html")
    lm = f"\n    <lastmod>{luts_lastmod}</lastmod>" if luts_lastmod else ""
    for loc, priority, alternates in luts_sitemap_entries(BASE_URL):
        alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{code}" href="{href}" />' for code, href in alternates)
        lines.append(f"  <url>\n    <loc>{loc}</loc>{alts}{lm}\n    <changefreq>weekly</changefreq>\n"
                     f"    <priority>{priority}</priority>\n  </url>")

    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")


@app.route("/robots.txt")
def robots_txt():
    """Served as a route, not a static file: vercel.json only maps /static/(.*), so
    static/robots.txt was reachable only at /static/robots.txt and /robots.txt 404'd.
    """
    disallow = [
        "/access/", "/pick/", "/crypto/", "/checkout", "/kofi/",
        "/payhip/", "/api/", "/set-lang/", "/debug/",
    ]
    lines = ["User-agent: *", "Allow: /"]
    lines += [f"Disallow: {path}" for path in disallow]
    lines.append("")

    # Assistants are a real discovery path for a niche product; let them read the
    # public pages. The Disallow list above still applies to every crawler.
    for bot in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
                "Claude-SearchBot", "PerplexityBot", "Google-Extended"):
        lines += [f"User-agent: {bot}", "Allow: /", ""]

    lines.append(f"Sitemap: {BASE_URL}/sitemap.xml")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")



@app.route("/checkout/card", methods=["POST"])
@limiter.limit("20 per hour")
def checkout_card():
    device_slug = (request.form.get("device") or "").strip()
    email       = (request.form.get("email") or "").strip().lower()

    device = get_device(device_slug)
    if not device or not _is_valid_email(email):
        abort(400, "Invalid device or email")

    if not PAYHIP_PRODUCT_URL:
        # The handoff template does <meta http-equiv="refresh" url="{{ payhip_url }}">.
        # An empty value there silently produces a dead checkout, so fail loudly
        # instead: the customer sees an error and the log says why.
        app.logger.error("PAYHIP_PRODUCT_URL is not set — card checkout unavailable")
        abort(503, "Card checkout is temporarily unavailable")

    _kv_set(f"pay:card:{email}", device["slug"], ttl_seconds=86400)
    # Interstitial: Telegram WebView users see a warning + manual continue button.
    # Other browsers auto-redirect to Payhip so the existing flow is unchanged.
    return render_template("checkout_card_handoff.html", payhip_url=PAYHIP_PRODUCT_URL)



@app.route("/payhip/webhook", methods=["POST"])
@limiter.limit("30 per minute")
def payhip_webhook():
    if not _EXPECTED_PAYHIP_SIG:
        app.logger.error("PAYHIP_API_KEY is not set — rejecting webhook")
        abort(503)

    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        raw = request.form.to_dict()
        raw["items"] = _form_items(raw)

    signature = str(raw.get("signature") or "").strip().lower()
    if not hmac.compare_digest(signature.encode(), _EXPECTED_PAYHIP_SIG.encode()):
        app.logger.warning("Invalid Payhip webhook signature from %s", get_remote_address())
        abort(401)

    event   = str(raw.get("type") or "").strip().lower()
    sale_id = str(raw.get("id") or raw.get("sale_id") or "").strip()

    if event == "refunded":
        if not sale_id:
            app.logger.error("payhip webhook: refunded event without sale id — nothing revoked")
            return "", 200
        refunded, price = _payhip_amount(raw.get("amount_refunded")), _payhip_amount(raw.get("price"))
        if refunded is not None and price is not None and 0 < refunded < price:
            # Partial refund (e.g. a goodwill discount): access stays. The owner
            # decides by hand and can set deny:s:<sale_id> in Upstash.
            app.logger.warning(
                "payhip webhook: PARTIAL refund sale_id=%s (%s of %s) — access kept, decide manually",
                sale_id, refunded, price)
            return "", 200
        if not _kv_set(f"deny:s:{sale_id}", "refunded", ttl_seconds=None):
            # Payhip retries only non-200 replies (hourly, 3 h): never lose a refund.
            app.logger.error("payhip webhook: could not write deny:s:%s to KV — returning 503 for a retry", sale_id)
            abort(503)
        app.logger.warning("payhip webhook: refunded sale_id=%s — access revoked", sale_id)
        return "", 200

    if event != "paid":
        app.logger.info("payhip webhook: ignoring event type=%r", event)
        return "", 200

    guide_keys = _payhip_guide_keys()
    if not guide_keys:
        # Fail loudly and let Payhip retry (hourly, 3 h) while the env is fixed.
        app.logger.error("payhip webhook: no guide product configured (PAYHIP_GUIDE_PRODUCT_KEYS / PAYHIP_PRODUCT_URL)")
        abort(503)
    items = [i for i in (raw.get("items") if isinstance(raw.get("items"), list) else []) if isinstance(i, dict)]
    if not any(_payhip_item_ids(item) & guide_keys for item in items):
        # Loud on purpose: if the guide product key is misconfigured, every real
        # sale lands here and Payhip does not retry a 200.
        app.logger.warning(
            "payhip webhook: paid sale with no guide item sale_id=%s item_keys=%s guide_keys=%s",
            sale_id, sorted({str(i.get("product_key") or i.get("product_id") or "?") for i in items}),
            sorted(guide_keys))
        return "", 200

    if not sale_id:
        app.logger.error("payhip webhook: paid guide sale without id — cannot fulfil")
        abort(400)

    buyer_email = str(raw.get("email") or raw.get("buyer_email") or "").strip().lower()
    if not _is_valid_email(buyer_email):
        app.logger.warning("payhip webhook: email missing — nothing sent")
        return "", 200

    if _kv_get(f"deny:s:{sale_id}"):
        app.logger.warning("payhip webhook: sale_id=%s is denied — nothing sent", sale_id)
        return "", 200

    # Payhip retries every hour for 3 h; process each sale once.
    if not _kv_set_nx(f"payhip:sale:{sale_id}", "1"):
        app.logger.info("payhip webhook: duplicate delivery sale_id=%s", sale_id)
        return "", 200

    kv_key = f"pay:card:{buyer_email}"
    kv_device = _kv_get(kv_key)
    device = get_device(kv_device) if kv_device else None

    app.logger.warning(
        "payhip webhook: email=%s sale_id=%s kv_device=%r matched=%s",
        buyer_email, sale_id, kv_device, bool(device),
    )

    if device:
        _kv_set_nx(f"pick:{sale_id}", device["slug"])
        session_key = f"{sale_id}:{device['slug']}"
        if not purchase_exists_for_session(session_key):
            access_token = _new_access_token(buyer_email, device["slug"], sale_id)
            if not _send_access_email(buyer_email, device["slug"], access_token):
                return _payhip_send_failed(sale_id)
            try:
                save_purchase(access_token[:43], device["slug"], session_key)
            except Exception as e:
                app.logger.warning(f"save_purchase failed (ok on vercel): {e}")
        _kv_del(kv_key)
        return "", 200

    select_token = _encode_token({"t": "pick", "e": buyer_email, "s": sale_id}, "pick")
    if not _send_pick_email(buyer_email, select_token):
        return _payhip_send_failed(sale_id)

    return "", 200


def _payhip_send_failed(sale_id: str):
    """The email did not go out: forget the sale so Payhip's retry fulfils it."""
    _kv_del(f"payhip:sale:{sale_id}")
    app.logger.error("payhip webhook: email failed for sale_id=%s — returning 503 so Payhip retries", sale_id)
    abort(503)


def _payhip_amount(value):
    """Payhip amounts (price, amount_refunded) as a float, or None if absent/unparsable."""
    try:
        return float(str(value).strip()) if value is not None and str(value).strip() else None
    except ValueError:
        return None


_FORM_ITEM_RE = re.compile(r"^items\[(\d+)\]\[(\w+)\]$")

def _form_items(form: dict) -> list:
    """items[] from a form-encoded body (items[0][product_key]=...)."""
    items: dict[int, dict] = {}
    for key, value in form.items():
        m = _FORM_ITEM_RE.match(key)
        if m:
            items.setdefault(int(m.group(1)), {})[m.group(2)] = value
    return [items[i] for i in sorted(items)]

def _payhip_key_from_url(url: str) -> str:
    """Product key from https://payhip.com/b/<KEY> or https://payhip.com/buy?link=<KEY>
    (also on a custom store domain). "" when the URL carries no product key."""
    parsed = urllib.parse.urlparse((url or "").strip())
    link = urllib.parse.parse_qs(parsed.query).get("link", [""])[0].strip()
    if link:
        return link
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[-2] == "b":
        return parts[-1]
    return ""

def _payhip_guide_keys() -> set:
    """Explicit PAYHIP_GUIDE_PRODUCT_KEYS, else the key parsed from PAYHIP_PRODUCT_URL.
    Empty set = unconfigured (the webhook answers 503 so Payhip retries)."""
    keys = {k.strip() for k in PAYHIP_GUIDE_PRODUCT_KEYS.split(",") if k.strip()}
    if not keys:
        key = _payhip_key_from_url(PAYHIP_PRODUCT_URL)
        if key:
            keys = {key, PAYHIP_PRODUCT_URL.strip().rstrip("/")}
    return {k for k in keys if k}

def _payhip_item_ids(item: dict) -> set:
    ids = {str(item.get(k)).strip() for k in ("product_key", "product_id") if item.get(k)}
    permalink = str(item.get("product_permalink") or "").strip().rstrip("/")
    if permalink:
        ids |= {permalink, _payhip_key_from_url(permalink)}
    return {i for i in ids if i}



@app.route("/crypto/checkout", methods=["POST"])
@limiter.limit("10 per hour")
def crypto_checkout():
    device_slug = (request.form.get("device") or "").strip()
    email       = (request.form.get("email") or "").strip().lower()
    network     = (request.form.get("network") or "trc20").strip().lower()

    device = get_device(device_slug)
    if not device or not _is_valid_email(email):
        abort(400, "Select a device and enter a valid email")

    enabled = _enabled_networks()
    if network not in enabled:
        abort(400, "Unsupported crypto network")

    order = {"n": secrets.token_hex(6), "d": device_slug, "e": email, "net": network}
    # Two tokens for one order: "cfm" goes only to the owner (it fulfils), "ord"
    # goes to the customer (it only shows payment instructions).
    confirm_token = _encode_token({"n": order["n"], "t": "cfm", **order}, "cfm")
    order_token   = _encode_token({"n": order["n"], "t": "ord", **order}, "ord")

    _send_admin_crypto_notification(email, device, confirm_token, network)

    return redirect(url_for("crypto_pay", token=order_token))


@app.route("/crypto/pay/<path:token>")
def crypto_pay(token):
    data = _claims(token, "ord")
    if not data or not data.get("d") or not data.get("e"):
        abort(404)
    device = get_device(data["d"])
    if not device:
        abort(404)

    network = (data.get("net") or "trc20").lower()
    net_cfg = _enabled_networks().get(network)
    if not net_cfg:
        abort(404)

    return render_template(
        "crypto_pay.html",
        email=data["e"],
        device=device,
        amount=PRICE_USD,
        address=net_cfg["address"],
        coin=net_cfg["coin"],
        network_label=net_cfg["network_label"],
        memo=net_cfg.get("memo", ""),
        exchange_address=net_cfg.get("exchange", False),
        qr_text=_qr_text(net_cfg),
    )


def _qr_text(net_cfg: dict) -> str:
    """What the payment QR encodes. With a TON MEMO, a ton://transfer deeplink that
    pre-fills the comment, so a scanned transfer is not sent without the MEMO."""
    memo = net_cfg.get("memo", "")
    if memo:
        return f"ton://transfer/{net_cfg['address']}?text={urllib.parse.quote(memo, safe='')}"
    return net_cfg["address"]


@app.route("/crypto/confirm/<path:token>", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def crypto_confirm(token):
    """Owner fulfilment. GET only renders a confirm button (mail scanners and
    link previews issue GETs); the POST sends the guide, once per order."""
    data = _claims(token, "cfm")
    if not data or not data.get("d") or not data.get("e") or not data.get("n"):
        abort(404)

    device_slug = data["d"]
    email       = data["e"]
    nonce       = data["n"]
    network     = (data.get("net") or "trc20").lower()
    device      = get_device(device_slug)
    if not device:
        abort(404)

    session_key = f"crypto:manual:{nonce}:{device_slug}:{network}"

    if request.method == "GET":
        already = bool(_kv_get(f"crypto:cfm:{nonce}")) or purchase_exists_for_session(session_key)
        return render_template(
            "crypto_confirmed.html",
            email=email, device=device, network=network,
            sent=already, already_sent=already, confirm_url=request.path,
        )

    cfm_key = f"crypto:cfm:{nonce}"
    first = _kv_set_nx(cfm_key, device_slug)
    # Secondary guard for when KV is unavailable (_kv_set_nx fails open).
    if first and not purchase_exists_for_session(session_key):
        access_token = _new_access_token(email, device_slug, nonce, nonce=nonce)
        if not _send_access_email(email, device_slug, access_token):
            # Nothing went out: release the once-only key so the owner can press again.
            _kv_del(cfm_key)
            app.logger.error("crypto confirm: access email failed for order n=%s — owner can retry", nonce)
            return render_template(
                "crypto_confirmed.html",
                email=email, device=device, network=network,
                sent=False, already_sent=False, send_failed=True, confirm_url=request.path,
            ), 502
        try:
            save_purchase(access_token[:43], device_slug, session_key)
        except Exception as e:
            app.logger.warning(f"save_purchase failed (ok on vercel): {e}")
        already = False
    else:
        already = True

    return render_template(
        "crypto_confirmed.html",
        email=email, device=device, network=network,
        sent=True, already_sent=already, confirm_url=request.path,
    )



@app.route("/pick/<token>")
@limiter.limit("60 per minute")
def pick_device(token):
    data = _claims(token, "pick")
    if not data or not data.get("e") or not data.get("s") or _is_denied(data):
        abort(404)
    return render_template("pick_device.html", token=token, devices=DEVICES)

@app.route("/pick/<token>/confirm", methods=["POST"])
@limiter.limit("30 per minute")
def confirm_device(token):
    data = _claims(token, "pick")
    if not data or not data.get("e") or not data.get("s") or _is_denied(data):
        abort(404)

    email       = data["e"]
    sale_id     = data["s"]
    device_slug = request.form.get("device", "").strip()
    device      = get_device(device_slug)

    if not device:
        abort(400, "Select a device")

    # One sale = one device: the first choice binds the sale for good.
    pick_key = f"pick:{sale_id}"
    if not _kv_set_nx(pick_key, device_slug):
        bound = _kv_get(pick_key)
        if bound != device_slug:
            bound_device = get_device(bound) if bound else None
            msg = TRANSLATIONS[detect_language()]["pick_already_bound"].replace(
                "{device}", bound_device["name"] if bound_device else "another iPhone"
            )
            return render_template("error.html", message=msg), 409

    session_key  = f"{sale_id}:{device_slug}"
    access_token = _new_access_token(email, device_slug, sale_id)
    if not purchase_exists_for_session(session_key):
        try:
            save_purchase(access_token[:43], device_slug, session_key)
        except Exception as e:
            app.logger.warning(f"save_purchase failed (ok on vercel): {e}")
    # Same device again: just re-send the (identical) access link.
    if not _send_access_email(email, device_slug, access_token):
        # The device stays bound, so pressing again with the same model re-sends.
        msg = TRANSLATIONS[detect_language()]["email_send_failed"]
        return render_template("error.html", message=msg), 502

    return render_template("guide_sent.html", email=email)



@app.route("/access/<path:token>")
@limiter.limit("60 per minute")
def access(token):
    if not token or len(token) > 600:  # same cap as _claims
        abort(404)

    def _render(device, token):
        # Drop a server-side breadcrumb so the restore-bar still works for users
        # whose localStorage is cleared between Telegram WebView sessions. The
        # token is already the access credential — exposing it via a JS-readable
        # cookie isn't a new disclosure.
        resp = make_response(render_template(group_template(device["slug"]), device=device, token=token))
        resp.set_cookie(
            "bmc_last", token,
            max_age=365 * 24 * 3600,
            samesite="Lax",
            secure=not IS_DEV,
            httponly=False,
        )
        return resp

    # Stateless HMAC only. The old SQLite fallback matched the stored token[:43],
    # which for legacy tokens is base64 of {"e":<email>,"d":... and so could be
    # rebuilt from a buyer's email without the secret. No emailed link relied on
    # it (emailed links are full signed tokens).
    data = _claims(token, "acc")
    if data and data.get("d") and not _is_denied(data):
        device_slug = data["d"]
        device      = get_device(device_slug)
        tmpl        = group_template(device_slug)
        if tmpl and device:
            return _render(device, token)

    abort(404)



_GROUP_CAPABILITIES = {
    "a": "iPhone XS / XR with A12 Bionic. BMC supports up to 4K30 (HEVC or H.264). No ProRes, no Apple Log, no Dolby Vision. Single-lens stabilization is basic OIS. Audio limited to built-in mics.",
    "b": "iPhone 11 series with A13 Bionic. BMC supports 4K60 (HEVC/H.264). No ProRes, no Apple Log, no Dolby Vision. Wide + Ultra Wide cameras (Pro adds Telephoto).",
    "c": "iPhone 12 series with A14 Bionic. BMC supports 4K60 and Dolby Vision HDR (10-bit HEVC). No ProRes and no Apple Log. Sensor-Shift OIS on 12 Pro Max only.",
    "d": "iPhone 13 series with A15 Bionic. BMC supports 4K60 + Dolby Vision HDR. No ProRes and no Apple Log on this generation in BMC. Sensor-Shift OIS on Pro / Pro Max.",
    "e": "iPhone 14 series. 14 / 14 Plus = A15. 14 Pro / Pro Max = A16. ProRes is available on 14 Pro / Pro Max only (4K30 ProRes requires external storage; internal capped at 1080p30 ProRes). No Apple Log yet. 48MP main on Pro models.",
    "f": "iPhone 15 series. 15 / 15 Plus = A16 (no ProRes, no Log). 15 Pro / Pro Max = A17 Pro and DO support ProRes Log (Apple Log) at 4K30, but ONLY when recording to external SSD via USB-C. Grade those ProRes Log files with a Log LUT in Resolve — iPhone cannot record BRAW, which is Blackmagic hardware only.",
    "g": "iPhone 16 series. 16 / 16 Plus = A18 (no ProRes/Log). 16 Pro / Pro Max = A18 Pro: ProRes Log up to 4K120 with external SSD, Camera Control button for hardware-style adjustments, 4-mic array for spatial audio.",
    "h": "iPhone 17 series with A19 / A19 Pro. 17 Pro / Pro Max support ProRes Log, Apple Log v2, and the latest BMC features including 4K120 internally on the Pro models. Camera Control hardware button present on Pro models.",
}


def _device_capabilities(device: dict) -> str:
    if not device:
        return ""
    return _GROUP_CAPABILITIES.get(device.get("group", ""), "")


_AI_LANG_INSTRUCTION = {
    "en": "Respond in English.",
    "ru": "Отвечай на русском языке.",
    "ar": "أجب باللغة العربية.",
}

_BMC_FULL_KNOWLEDGE = build_full_knowledge()


def _build_ai_system_prompt(lang: str, device: dict) -> str:
    caps = _device_capabilities(device)
    lang_instr = _AI_LANG_INSTRUCTION.get(lang, _AI_LANG_INSTRUCTION["en"])
    return (
        "You are an expert on the Blackmagic Camera (BMC) iOS app for iPhone. "
        "You ONLY answer questions about Blackmagic Camera and iPhone video shooting.\n\n"
        "## CRITICAL RULES (apply these BEFORE answering)\n"
        "1. SCOPE: If the question is not about Blackmagic Camera, iPhone video shooting, "
        "camera settings, lenses, lighting for video, audio for video, or video grading — "
        "REFUSE with ONE short sentence and offer to help with BMC instead. Do NOT write "
        "code, do NOT do math, do NOT answer general questions, do NOT translate, do NOT "
        "give life advice. Examples of what to refuse: programming, recipes, history, "
        "other apps, weather, jokes, general chat.\n"
        "2. LANGUAGE: Always reply in the SAME language the user wrote in (Ukrainian → "
        "Ukrainian, Russian → Russian, English → English, Arabic → Arabic, etc.). Stay in "
        "that ONE language for the entire reply — never switch mid-answer, never mix "
        "languages, never default to English unless the user wrote in English.\n"
        "3. DEVICE: Never recommend a feature this device does not support. Cross-check "
        "against the DEVICE CAPABILITIES section below. When the device matters for the "
        "answer (Apple Log, ProRes, Camera Control, 4K120, telephoto), name the device "
        f"explicitly — the user has {device['name']}.\n"
        "4. UI TERMINOLOGY: The Blackmagic Camera app interface is in ENGLISH on every "
        "device. ALWAYS keep menu names, button labels, and option values in English even "
        "when the rest of your answer is in another language. Examples of CORRECT bilingual "
        "answers:\n"
        "    Ukrainian: \"Відкрий **Settings** (шестерня внизу справа) → **Stabilization** → "
        "обери **Cinematic**.\"\n"
        "    Russian: \"Открой **Settings** (шестерёнка снизу справа) → **Codec** → "
        "**HEVC H.265**.\"\n"
        "  Do NOT translate: Settings, Codec, Resolution, Color Space, Stabilization, "
        "LUTs Manager, Import LUT, Save Clips to, In-App and Photo Library, Enable "
        "Vertical Video, HEVC H.265, ProRes, Rec.709, Apple Log, Apple Log 2, Off, "
        "Standard, Cinematic, Extreme, Auto, ON, Shutter, ISO, WB, Tint, FPS.\n"
        "5. ANTI-HALLUCINATION: If you don't know whether a feature or menu path exists in "
        "BMC, do NOT invent it. Cross-check the KNOWLEDGE BASE first. If the feature isn't "
        "documented there, either (a) suggest the closest known feature from the knowledge "
        "base, or (b) admit uncertainty: \"I'm not sure of the exact location — open "
        "**Settings** and scroll for [feature]; it might not exist in the current BMC "
        "version.\" Better to be honest than to mislead.\n"
        "6. STYLE: Be terse — aim for 80–150 words. Use bullets or numbered steps, not "
        "prose paragraphs. Cut filler phrases (\"certainly\", \"I'd be happy to help\", "
        "\"as mentioned earlier\", \"in conclusion\"). One concrete tip beats three vague ones.\n\n"
        f"USER'S DEVICE: {device['name']} ({device['chip']}).\n"
        f"DEVICE CAPABILITIES IN BMC: {caps}\n\n"
        "=== BMC KNOWLEDGE BASE ===\n"
        f"{_BMC_FULL_KNOWLEDGE}\n"
        "=== END KNOWLEDGE ===\n\n"
        "## OUTPUT FORMAT — pick the one that fits the question\n"
        "- SCENE-based (\"sunset on the beach\", \"interview indoors\", \"vlog walking\") →\n"
        "  give the GUIDE DEFAULTS first, then 1–2 scene-specific tweaks:\n"
        "    **Shutter / ISO / WB / Tint:** Auto (lock icon NOT pressed)\n"
        "    **FPS:** 50 (50 Hz countries) or 60 (60 Hz countries)\n"
        "    **Codec:** HEVC H.265\n"
        "    **Resolution:** 4K (3840×2160)\n"
        "    **Color Space:** Rec.709 (or Apple Log on iPhone 15 Pro+ if device supports)\n"
        "    **LUT:** apply a Rec.709 (or Log) LUT from the @blackmagicamera Telegram channel\n"
        "    **Tip:** 1–2 sentences specific to the scene\n"
        "  Do NOT recommend manual 180° shutter, manual ISO, or manual Kelvin WB unless\n"
        "  the user EXPLICITLY asks for cinematic / manual control.\n"
        "- TROUBLESHOOTING (\"image is shaky\", \"shutter is locked\", \"flicker indoors\") →\n"
        "  step-by-step with exact UI labels:\n"
        "    Tap the **lock icon** next to Shutter — it must be transparent, not blue.\n"
        "  Or: Open **Settings (gear, bottom-right) → Save Clips to → In-App and Photo Library**.\n"
        "- FEATURE EXPLANATION (\"what does the lock icon next to Shutter do?\") → 2–4 plain\n"
        "  sentences + when to use it.\n"
        "- HOW-TO (\"how do I import a LUT?\") → numbered steps following the guide:\n"
        "  Settings → LUTs Manager → scroll to bottom → Import LUT → Files picker → Select All → Open.\n"
        "- LIMITATION (\"why don't I see Apple Log?\") → diagnose by device chip and version.\n\n"
        "Keep answers under ~200 words. Use markdown **bold** for menu names, button labels,\n"
        "and key values. Use the EXACT UI names from the knowledge base — \"LUTs Manager\"\n"
        "(not \"LUTS tab\"), \"HEVC H.265\" (not \"HEVC\"), \"Settings\" (gear, bottom-right),\n"
        "\"Save Clips to → In-App and Photo Library\", \"Enable Vertical Video\"."
    )


def _send_chat_to_telegram(device: dict, question: str, answer: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    def _escape(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    text = (
        f"🎬 <b>BMC AI chat</b> — {_escape(device['name'])}\n\n"
        f"👤 {_escape(question[:400])}\n\n"
        f"🤖 {_escape(answer[:900])}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception as e:
        app.logger.warning(f"telegram chat notify failed: {e}")


@app.route("/api/ai/chat", methods=["POST"])
@limiter.limit("60 per hour")
def ai_chat():
    if not GROQ_API_KEY:
        return {"error": "ai_disabled"}, 503

    body = request.get_json(silent=True) or {}
    token   = (body.get("token") or "").strip()
    message = (body.get("message") or "").strip()
    history = body.get("history") or []

    if not message or len(message) > 500:
        return {"error": "bad_message"}, 400

    data = _claims(token, "acc")
    if not data or not data.get("d") or _is_denied(data):
        return {"error": "unauthorized"}, 401
    device = get_device(data["d"])
    if not device:
        return {"error": "unauthorized"}, 401

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Keyed on a hash of the whole token: legacy tokens share long prefixes
    # (base64 of {"e":...), so token[:43] could pool different buyers' quotas.
    rl_key = f"ai:rl:{hashlib.sha256(token.encode()).hexdigest()[:32]}:{day}"
    cur = int(_kv_get(rl_key) or "0")
    if cur >= AI_DAILY_LIMIT:
        return {"error": "quota_exceeded", "limit": AI_DAILY_LIMIT}, 429
    _kv_set(rl_key, str(cur + 1), ttl_seconds=36 * 3600)
    remaining = max(0, AI_DAILY_LIMIT - cur - 1)

    lang = detect_language()
    system_prompt = _build_ai_system_prompt(lang, device)

    safe_history = []
    if isinstance(history, list):
        for turn in history[-10:]:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                safe_history.append({"role": role, "content": content[:2000]})

    messages = (
        [{"role": "system", "content": system_prompt}]
        + safe_history
        + [{"role": "user", "content": message}]
    )

    def generate():
        full = []
        try:
            r = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "max_tokens": 700,
                    "temperature": 0.4,
                    "stream": True,
                },
                stream=True,
                timeout=30,
            )
            if r.status_code != 200:
                app.logger.error(f"Groq API error {r.status_code}: {r.text[:300]}")
                yield f"data: {json.dumps({'error': 'ai_unavailable'})}\n\n"
                return

            for line in r.iter_lines():
                if not line:
                    continue
                s = line.decode("utf-8")
                if not s.startswith("data: "):
                    continue
                payload = s[6:]
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                    if delta:
                        full.append(delta)
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
                except (json.JSONDecodeError, KeyError):
                    pass

            yield f"data: {json.dumps({'done': True, 'remaining': remaining, 'limit': AI_DAILY_LIMIT})}\n\n"

            answer = "".join(full)
            if answer:
                threading.Thread(
                    target=_send_chat_to_telegram,
                    args=(device, message, answer),
                    daemon=True,
                ).start()
        except Exception as e:
            app.logger.error(f"ai_chat stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'ai_unavailable'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



def _send_pick_email(to_email: str, select_token: str) -> bool:
    link = f"{BASE_URL}/pick/{select_token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;">
      <h2 style="color:#111;">Thank you for your purchase!</h2>
      <p style="color:#444;">One last step — click the button below to select your iPhone model and receive your Blackmagic Camera settings guide.</p>
      <a href="{link}" style="display:inline-block;background:#ff3c00;color:#fff;text-decoration:none;font-weight:700;padding:1rem 2rem;border-radius:8px;margin:1rem 0;font-size:1rem;">
        Select My iPhone Model →
      </a>
      <p style="color:#888;font-size:0.8rem;">Keep this email — the link lets you access your guide anytime.</p>
    </div>
    """
    return _send_email(to_email, "One more step — Select your iPhone model", html)

def _send_access_email(to_email: str, device_slug: str, token: str) -> bool:
    device = get_device(device_slug)
    link   = f"{BASE_URL}/access/{token}"
    html   = render_template("email_access.html", device=device, link=link)
    return _send_email(to_email, f"Your Blackmagic Camera guide — {device['name']}", html)

def _send_admin_crypto_notification(customer_email: str, device: dict, confirm_token: str, network: str = "trc20"):
    confirm_link = f"{BASE_URL}/crypto/confirm/{confirm_token}"
    net_cfg = CRYPTO_NETWORKS.get(network, CRYPTO_NETWORKS["trc20"])
    coin = net_cfg["coin"]
    net_label = net_cfg["network_label"]
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:2rem;">
      <h2 style="color:#111;">New crypto order (manual fulfillment)</h2>
      <p><b>Device:</b> {device['name']} ({device['chip']})</p>
      <p><b>Customer email:</b> {html_escape(customer_email)}</p>
      <p><b>Expected amount:</b> {PRICE_USD:.2f} {coin}</p>
      <p><b>Network:</b> {net_label}</p>
      <p style="color:#444;">Once you see the deposit, click below to send the guide to the customer:</p>
      <a href="{confirm_link}" style="display:inline-block;background:#ff3c00;color:#fff;text-decoration:none;font-weight:700;padding:1rem 2rem;border-radius:8px;margin:1rem 0;">
        Confirm &amp; send guide →
      </a>
      <p style="color:#888;font-size:0.8rem;">The link opens a confirmation page; the guide is sent only when you press its button, and only once per order.</p>
    </div>
    """
    _send_email(ADMIN_EMAIL, f"Crypto order ({coin} {net_label}): {device['name']} — {customer_email}", html)

def _send_email(to_email: str, subject: str, html: str) -> bool:
    """True once the message was handed to Gmail; False if every attempt failed.
    Fulfilment callers undo their set-once KV key on False so the send can be retried."""
    safe_to      = _sanitize_header(to_email)
    safe_subject = _sanitize_header(subject)
    if not safe_to or "@" not in safe_to:
        app.logger.warning("refusing to send email to invalid address")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = safe_subject
    msg["From"]    = f"Blackmagic Camera Settings <{GMAIL_USER}>"
    msg["To"]      = safe_to
    msg.attach(MIMEText(html, "html"))
    raw = msg.as_string()

    last_err = None
    for attempt in (1, 2, 3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                smtp.sendmail(GMAIL_USER, safe_to, raw)
            app.logger.info(f"email sent to={safe_to!r} subject={safe_subject!r} attempt={attempt}")
            return True
        except Exception as e:
            last_err = e
            app.logger.warning(f"smtp attempt {attempt} (587/STARTTLS) failed to={safe_to!r}: {e}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, safe_to, raw)
        app.logger.info(f"email sent to={safe_to!r} subject={safe_subject!r} via SSL fallback")
        return True
    except Exception as e:
        app.logger.error(f"email send failed to={safe_to!r} after retries: 587={last_err} 465={e}")
        return False



luts_shop.register(app, BASE_URL)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", message="Bad request"), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template("error.html", message="Unauthorized"), 401

@app.errorhandler(429)
def too_many_requests(e):
    return render_template("error.html", message="Too many requests. Please try again later."), 429

@app.errorhandler(500)
def server_error(e):
    app.logger.exception("Unhandled 500 error")
    return render_template("error.html", message="Something went wrong. Please try again."), 500


@app.after_request
def set_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    if request.is_secure or forwarded_proto == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    path = request.path or ""
    # "/" branches on Accept-Language (and the lang cookie) to 302 RU/AR visitors,
    # so any shared cache must key on those headers.
    if path == "/":
        existing = [v.strip() for v in resp.headers.get("Vary", "").split(",") if v.strip()]
        for header in ("Accept-Language", "Cookie"):
            if header.lower() not in [v.lower() for v in existing]:
                existing.append(header)
        resp.headers["Vary"] = ", ".join(existing)
    if path.startswith("/static/") and resp.status_code in (200, 206, 304):
        # Посилання на статику мають ?v=<хеш> (static_v), тож рік кешу безпечний. Flask сам ставить
        # «no-cache» на send_file, тому перезаписуємо: інакше відео тягнулися б щоразу й роздували трафік.
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    if "Cache-Control" not in resp.headers:
        if path == "/sitemap.xml" or path == "/favicon.ico":
            resp.headers["Cache-Control"] = "public, max-age=86400"
        elif path.startswith(("/access/", "/pick/", "/crypto/", "/api/", "/checkout/", "/payhip/", "/set-lang/")):
            resp.headers["Cache-Control"] = "private, no-store"
        elif request.method == "GET" and resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=3600"
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' https: data:; "
        "media-src 'self' https://pub-8fb494845cea47208e5a569a242eab94.r2.dev; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self' https://payhip.com"
    )
    return resp


if __name__ == "__main__":
    app.run(debug=IS_DEV, port=5001)