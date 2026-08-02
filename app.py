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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from flask import Flask, render_template, redirect, request, abort, url_for, make_response, Response, g, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from db import (init_db, save_purchase, get_purchase_by_token, purchase_exists_for_session)
from devices import DEVICES, get_device, group_template
from translations import TRANSLATIONS
from testimonials import TESTIMONIALS
from bmc_knowledge import build_full_knowledge

load_dotenv()

app = Flask(__name__)
# Vercel terminates HTTPS at the edge; without ProxyFix, request.is_secure is False
# inside the function and Flask drops Secure cookies. Trust X-Forwarded-Proto.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

HMAC_SECRET             = os.environ.get("KOFI_FULFILL_SECRET", "")
PAYHIP_PRODUCT_URL      = os.environ.get("PAYHIP_PRODUCT_URL", "")
PAYHIP_API_KEY          = os.environ.get("PAYHIP_API_KEY", "").strip()
GMAIL_USER              = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD      = os.environ.get("GMAIL_APP_PASSWORD", "")
BASE_URL                = os.environ.get("BASE_URL", "http://localhost:5001")
ADMIN_EMAIL             = os.environ.get("ADMIN_EMAIL", GMAIL_USER)
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

def _kv_set(key: str, value: str, ttl_seconds: int = 86400) -> bool:
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        path = f"/set/{urllib.parse.quote(key, safe='')}/{urllib.parse.quote(value, safe='')}?EX={int(ttl_seconds)}"
        req = urllib.request.Request(
            UPSTASH_URL + path,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        app.logger.warning(f"kv_set failed: {e}")
        return False

def _kv_get(key: str) -> str | None:
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        path = f"/get/{urllib.parse.quote(key, safe='')}"
        req = urllib.request.Request(
            UPSTASH_URL + path,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result")
            return result if isinstance(result, str) and result else None
    except Exception as e:
        app.logger.warning(f"kv_get failed: {e}")
        return None

def _kv_del(key: str) -> None:
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return
    try:
        path = f"/del/{urllib.parse.quote(key, safe='')}"
        req = urllib.request.Request(
            UPSTASH_URL + path,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).close()
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



def _sign(payload: str) -> str:
    return hmac.new(HMAC_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]

def _encode_token(data: dict) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode().rstrip('=')
    return f"{payload}.{_sign(payload)}"

def _decode_token(token: str) -> dict | None:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return None



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
    """True if the path has registered lang URL variants (/, /select, /guide/<slug>)."""
    base = _strip_lang_prefix(path)
    if base in ("/", "/select"):
        return True
    if base.startswith("/guide/") and len(base) > len("/guide/"):
        return True
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


@app.context_processor
def inject_i18n():
    lang = detect_language()
    is_public = _is_publicly_localized(request.path)

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

    return {
        "lang": lang,
        "t": TRANSLATIONS[lang],
        "lang_alternates": alternates,
        "lang_link": lang_link,
        "is_seo_localized": is_public,
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
    return render_template("index.html", testimonials=TESTIMONIALS)


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


@app.route("/sitemap.xml")
def sitemap():
    base_paths = ["/", "/select"] + [f"/guide/{d['slug']}" for d in DEVICES]
    priorities = {"/": "1.0", "/select": "0.9"}

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for base in base_paths:
        priority = priorities.get(base, "0.8")
        changefreq = "weekly" if base in priorities else "monthly"
        for lang in SUPPORTED_LANGS:
            loc = BASE_URL + _localize_path(lang, base)
            lines.append("  <url>")
            lines.append(f"    <loc>{loc}</loc>")
            for alt_lang in SUPPORTED_LANGS:
                href = BASE_URL + _localize_path(alt_lang, base)
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{href}" />'
                )
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="x-default" '
                f'href="{BASE_URL + base}" />'
            )
            lines.append(f"    <changefreq>{changefreq}</changefreq>")
            lines.append(f"    <priority>{priority}</priority>")
            lines.append("  </url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")



@app.route("/checkout/card", methods=["POST"])
@limiter.limit("20 per hour")
def checkout_card():
    device_slug = (request.form.get("device") or "").strip()
    email       = (request.form.get("email") or "").strip().lower()

    device = get_device(device_slug)
    if not device or not _is_valid_email(email):
        abort(400, "Invalid device or email")

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

    raw = request.form.to_dict()
    if not raw:
        raw = request.get_json(silent=True) or {}

    signature = (raw.get("signature") or "").strip().lower()
    if not hmac.compare_digest(signature, _EXPECTED_PAYHIP_SIG):
        app.logger.warning("Invalid Payhip webhook signature from %s", get_remote_address())
        abort(401)

    buyer_email = (raw.get("email") or raw.get("buyer_email") or "").strip().lower()
    sale_id     = (raw.get("id") or raw.get("sale_id") or "").strip() or secrets.token_hex(8)

    if not _is_valid_email(buyer_email):
        app.logger.warning("payhip webhook: email missing — nothing sent")
        return "", 200

    kv_key = f"pay:card:{buyer_email}"
    kv_device = _kv_get(kv_key)
    device = get_device(kv_device) if kv_device else None

    app.logger.warning(
        "payhip webhook: email=%s sale_id=%s kv_device=%r matched=%s",
        buyer_email, sale_id, kv_device, bool(device),
    )

    if device:
        _kv_del(kv_key)
        session_key = f"{sale_id}:{device['slug']}"
        if not purchase_exists_for_session(session_key):
            access_token = _encode_token({"e": buyer_email, "d": device["slug"], "s": sale_id})
            try:
                save_purchase(access_token[:43], device["slug"], session_key)
            except Exception as e:
                app.logger.warning(f"save_purchase failed (ok on vercel): {e}")
            _send_access_email(buyer_email, device["slug"], access_token)
        return "", 200

    select_token = _encode_token({"e": buyer_email, "s": sale_id})
    _send_pick_email(buyer_email, select_token)

    return "", 200



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

    confirm_token = _encode_token({
        "d": device_slug,
        "e": email,
        "n": secrets.token_hex(4),
        "net": network,
    })

    _send_admin_crypto_notification(email, device, confirm_token, network)

    return redirect(url_for("crypto_pay", token=confirm_token))


@app.route("/crypto/pay/<path:token>")
def crypto_pay(token):
    data = _decode_token(token)
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
    )


@app.route("/crypto/confirm/<path:token>")
def crypto_confirm(token):
    data = _decode_token(token)
    if not data or not data.get("d") or not data.get("e") or not data.get("n"):
        abort(404)

    device_slug = data["d"]
    email       = data["e"]
    network     = (data.get("net") or "trc20").lower()
    if not get_device(device_slug):
        abort(404)

    session_key = f"crypto:manual:{data['n']}:{device_slug}:{network}"
    access_token = _encode_token({"e": email, "d": device_slug, "s": data["n"]})

    if not purchase_exists_for_session(session_key):
        save_purchase(access_token[:43], device_slug, session_key)
        _send_access_email(email, device_slug, access_token)

    return render_template(
        "crypto_confirmed.html",
        email=email,
        device=get_device(device_slug),
    )



@app.route("/pick/<token>")
@limiter.limit("60 per minute")
def pick_device(token):
    data = _decode_token(token)
    if not data or not data.get("e"):
        abort(404)
    return render_template("pick_device.html", token=token, devices=DEVICES)

@app.route("/pick/<token>/confirm", methods=["POST"])
@limiter.limit("30 per minute")
def confirm_device(token):
    data = _decode_token(token)
    if not data or not data.get("e"):
        abort(404)

    email      = data["e"]
    sale_id    = data.get("s", "")
    device_slug = request.form.get("device", "").strip()
    device     = get_device(device_slug)

    if not device:
        abort(400, "Select a device")

    session_key = f"{sale_id}:{device_slug}"
    if not purchase_exists_for_session(session_key):
        access_token = _encode_token({"e": email, "d": device_slug, "s": sale_id})
        save_purchase(access_token[:43], device_slug, session_key)
        _send_access_email(email, device_slug, access_token)

    return render_template("guide_sent.html", email=email)



@app.route("/access/<path:token>")
@limiter.limit("60 per minute")
def access(token):
    if not token or len(token) > 300:
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

    data = _decode_token(token)
    if data and data.get("d"):
        device_slug = data["d"]
        device      = get_device(device_slug)
        tmpl        = group_template(device_slug)
        if tmpl and device:
            return _render(device, token)

    purchase = get_purchase_by_token(token)
    if purchase:
        device_slug = purchase["device_slug"]
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
    "f": "iPhone 15 series. 15 / 15 Plus = A16 (no ProRes, no Log). 15 Pro / Pro Max = A17 Pro and DO support ProRes Log (Apple Log) at 4K30, but ONLY when recording to external SSD via USB-C. Use BRAW + LUT in Resolve for grading.",
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

    data = _decode_token(token)
    if not data or not data.get("d"):
        return {"error": "unauthorized"}, 401
    device = get_device(data["d"])
    if not device:
        return {"error": "unauthorized"}, 401

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    rl_key = f"ai:rl:{token[:43]}:{day}"
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



def _send_pick_email(to_email: str, select_token: str):
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
    _send_email(to_email, "One more step — Select your iPhone model", html)

def _send_access_email(to_email: str, device_slug: str, token: str):
    device = get_device(device_slug)
    link   = f"{BASE_URL}/access/{token}"
    html   = render_template("email_access.html", device=device, link=link)
    _send_email(to_email, f"Your Blackmagic Camera guide — {device['name']}", html)

def _send_admin_crypto_notification(customer_email: str, device: dict, confirm_token: str, network: str = "trc20"):
    confirm_link = f"{BASE_URL}/crypto/confirm/{confirm_token}"
    net_cfg = CRYPTO_NETWORKS.get(network, CRYPTO_NETWORKS["trc20"])
    coin = net_cfg["coin"]
    net_label = net_cfg["network_label"]
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:2rem;">
      <h2 style="color:#111;">New crypto order (manual fulfillment)</h2>
      <p><b>Device:</b> {device['name']} ({device['chip']})</p>
      <p><b>Customer email:</b> {customer_email}</p>
      <p><b>Expected amount:</b> {PRICE_USD:.2f} {coin}</p>
      <p><b>Network:</b> {net_label}</p>
      <p style="color:#444;">Once you see the deposit, click below to send the guide to the customer:</p>
      <a href="{confirm_link}" style="display:inline-block;background:#ff3c00;color:#fff;text-decoration:none;font-weight:700;padding:1rem 2rem;border-radius:8px;margin:1rem 0;">
        Confirm &amp; send guide →
      </a>
      <p style="color:#888;font-size:0.8rem;">The link is idempotent — clicking twice won't send the email twice.</p>
    </div>
    """
    _send_email(ADMIN_EMAIL, f"Crypto order ({coin} {net_label}): {device['name']} — {customer_email}", html)

def _send_email(to_email: str, subject: str, html: str):
    safe_to      = _sanitize_header(to_email)
    safe_subject = _sanitize_header(subject)
    if not safe_to or "@" not in safe_to:
        app.logger.warning("refusing to send email to invalid address")
        return

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
            return
        except Exception as e:
            last_err = e
            app.logger.warning(f"smtp attempt {attempt} (587/STARTTLS) failed to={safe_to!r}: {e}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, safe_to, raw)
        app.logger.info(f"email sent to={safe_to!r} subject={safe_subject!r} via SSL fallback")
        return
    except Exception as e:
        app.logger.error(f"email send failed to={safe_to!r} after retries: 587={last_err} 465={e}")



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
    if "Cache-Control" not in resp.headers:
        if path.startswith("/static/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path == "/sitemap.xml" or path == "/favicon.ico":
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