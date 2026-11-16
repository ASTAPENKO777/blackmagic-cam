# BlackmagicCam — CLAUDE.md

## Project Overview

Flask web app selling device-specific Blackmagic Camera settings guides for iPhone.
Users pay $4.99 via Ko-fi/Payhip (card, automated) or USDT direct to the owner's Binance wallet on one of four networks (TRC20 / BEP20 / ERC20 / TON — all manually fulfilled by the owner) → get a permanent access link → see a guide for their exact iPhone model.

## Stack

- **Backend:** Python 3.13 + Flask 3.1
- **Payments:** Ko-fi/Payhip (primary, card, automated) + USDT direct to owner's Binance wallet on TRC20 / BEP20 / ERC20 / TON networks — all owner-confirmed
- **DB:** SQLite (`purchases.db`) via `db.py`
- **Deploy:** Vercel (`vercel.json` → `@vercel/python`)
- **i18n:** Custom (`translations.py`) — EN / RU / AR with RTL support

## Dev Server

```bash
python3 app.py          # runs on http://localhost:5001
```

No build step. No package manager. Pure Flask.

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Routes: pages, Payhip webhook, crypto checkout/confirm, HMAC tokens, email |
| `translations.py` | All UI strings for EN / RU / AR |
| `devices.py` | Device list + group mapping (A–H) |
| `db.py` | SQLite helpers (init, save, lookup purchases) |
| `learn.py` | Free `/learn` articles + the quality gate that decides which are indexable |
| `scripts/seo_check.py` | Post-deploy SEO smoke test — run it against the live URL after every deploy |
| `vercel.json` | Vercel deployment config |
| `templates/base.html` | Nav, footer, RTL styles, lang switcher, `window.BMC_I18N` |
| `templates/index.html` | Landing page |
| `templates/learn_hub.html` | `/learn` index of free articles |
| `templates/learn_article.html` | `/learn/<slug>` article + Article/FAQ/Breadcrumb JSON-LD |
| `templates/select.html` | Device picker → Payhip (card) + crypto form |
| `templates/crypto_pay.html` | Instructions page after crypto form submit (address + QR + amount) |
| `templates/crypto_confirmed.html` | Owner-side confirmation view (after clicking magic link) |
| `templates/content/base_content.html` | Paid guide shell (sidebar, restore bar) |
| `templates/content/group-{a-h}.html` | Per-chip-group guide content |

## Architecture

### Device groups (A–H by chip)
- `devices.py` maps each iPhone slug → group letter
- `group_template(slug)` returns `content/group-X.html`
- Adding a new iPhone = add entry to `DEVICES` list only

### Purchase flow

**Card (Ko-fi / Payhip)** — device picked AFTER payment:
1. User clicks Payhip link on `/select` → pays externally.
2. Payhip webhook `POST /payhip/webhook` (account-wide: fires for every product and every event type, retried hourly for 3 h until it gets a 200):
   - signature must equal `sha256(PAYHIP_API_KEY)` (never logged);
   - `type == "refunded"` with `amount_refunded >= price` (or either amount missing) → `deny:s:<sale_id>` in KV (revokes every link of that sale), no email. If that KV write fails the webhook answers 503 so Payhip retries. **Partial refunds** (`0 < amount_refunded < price`, e.g. a goodwill discount) do NOT revoke access: they are logged at WARNING ("PARTIAL refund") and the owner decides by hand (set `deny:s:<sale_id>` in Upstash to revoke);
   - `type == "paid"` is processed only if an `items[]` entry matches the guide product (`PAYHIP_GUIDE_PRODUCT_KEYS`, else the key parsed from `PAYHIP_PRODUCT_URL` — `payhip.com/b/<KEY>` or `payhip.com/buy?link=<KEY>` — compared with `product_key` / `product_id` / `product_permalink`). If neither yields a key the webhook answers **503** (unconfigured). A paid sale with no matching item → 200 no-op, logged at WARNING as "paid sale with no guide item" with the item keys — **if real sales show up there, the product key is misconfigured** (Payhip does not retry a 200). Every other event type → 200 no-op;
   - each sale is processed once (`payhip:sale:<id>`), then a `pick` token `{t:"pick", e, s}` is emailed with the `/pick/<token>` link (or, when `/checkout/card` recorded a device, the access email directly). If the email fails, `payhip:sale:<id>` is deleted again and the webhook answers 503, so Payhip's retry re-sends it.
3. User opens email → `/pick/<token>` → picks device → `POST /pick/<token>/confirm` binds the sale to that first device (`pick:<sale_id>`); the same device again just re-sends the access email, a different device gets a 409 "already linked" page. Access email carries `/access/<acc token>`.

**Crypto (multi-network, manual fulfillment)** — device picked BEFORE payment:
1. User picks device + email + network on `/select` → `POST /crypto/checkout` validates inputs and network and mints **two** tokens for the order `{n, d, e, net}`: a `cfm` token that goes **only** into the owner's (`ADMIN_EMAIL`) notification email as the "Confirm & send guide" link, and an `ord` token for the customer redirect `/crypto/pay/<ord token>` (`crypto_pay.html`: address, exact amount, QR, and for TON the MEMO from `BINANCE_USDT_MEMO_TON`; with a MEMO the QR encodes `ton://transfer/<address>?text=<memo>` so a scanning wallet pre-fills it). The `ord` token opens nothing but that page.
2. Customer sends the chosen coin on the chosen network directly to the owner's wallet.
3. **Owner** checks Binance/wallet for the deposit → clicks the magic link → `GET /crypto/confirm/<cfm token>` only renders a page with a POST button (no side effects — mail scanners and link previews issue GETs) → pressing it sends `POST /crypto/confirm/<cfm token>`, which fulfils once per order (`crypto:cfm:<n>` via `_kv_set_nx`, plus the SQLite row `crypto:manual:{nonce}:{device_slug}:{network}` as a fallback guard) and emails an `acc` token `{n, t:"acc", e, d, s:n}`. If the email fails, `crypto:cfm:<n>` is deleted again, no SQLite row is written and the page shows "could not be sent — press again" (502).
4. Customer receives the access email with `/access/<token>` and opens their guide.

Supported networks live in `CRYPTO_NETWORKS` at the top of `app.py`. Each entry needs an env var with the deposit address — only networks with an address appear in the UI. Adding a new network = add a dict entry + env var. Legacy `BINANCE_USDT_ADDRESS` is honored as a fallback for TRC20.

This flow trades automation for simplicity: at $4.99 per sale, no crypto gateway (NOWPayments, CoinGate, CoinPayments) has a low enough per-coin minimum to accept the payment — they all require $8–15 minimums because of network fees and per-coin thresholds. Direct wallet deposits have no such minimum, but there's no webhook, so fulfillment is manual. The magic link turns "manual" into one click for the owner.

**Access** — `GET /access/<token>` accepts only an `acc` token (stateless HMAC, `d` from the token) that is not on the deny list. There is no DB fallback any more: the stored `token[:43]` of a legacy token is base64 of `{"e":<email>,"d":...` and could be rebuilt from an email address.

### Token purposes

All tokens are `base64url(JSON) + "." + hexdigest[:20]`. `_claims(token, purpose)` is the only way a route reads a token. New tokens carry `t=<purpose>` and are signed with `HMAC_SHA256(KOFI_FULFILL_SECRET, "purpose:" + purpose)` (raw digest as the key). Legacy tokens (signed with `KOFI_FULFILL_SECRET` itself, no `t`) are accepted only by exact key set, so links already in customers' inboxes keep working. **Never rotate or rename `KOFI_FULFILL_SECRET`** — every emailed link dies with it.

| Purpose | Used by | New token | Legacy accepted |
|---------|---------|-----------|-----------------|
| `acc` | `/access/<t>`, `/api/ai/chat` | `{n, t:"acc", e, d, s}` (`n` first: per-purchase) | exactly `{e, d, s}` |
| `pick` | `/pick/<t>`, `/pick/<t>/confirm` | `{t:"pick", e, s}` | exactly `{e, s}` |
| `cfm` | `GET/POST /crypto/confirm/<t>` (owner only) | `{n, t:"cfm", d, e, net}` | none |
| `ord` | `/crypto/pay/<t>` (customer order page) | `{n, t:"ord", d, e, net}` | none |

A legacy crypto confirm token `{d, e, n, net}` matches none of these and opens nothing. Revoke any access link by setting `deny:s:<sale_id>` or `deny:n:<n>` in Upstash (no TTL); `/access`, `/api/ai/chat` and `/pick` check both.

### KV keys (Upstash REST)

The SQLite DB lives in `/tmp` on Vercel and disappears, so every durable fact is in Upstash. Commands use the JSON form (`POST <UPSTASH_URL>` with body `["SET", key, value, "NX"]`) via `_kv_cmd`. `_kv_set_nx` **fails open** (returns True and logs an ERROR) when KV is missing or down, so an outage never blocks a paying customer — but it also disables the one-device and once-only guards until KV is back.

| Key | Value | TTL | Written by |
|-----|-------|-----|------------|
| `pay:card:<email>` | device slug chosen before Payhip | 24 h | `/checkout/card` (read + deleted by the webhook) |
| `payhip:sale:<sale_id>` | `1` | none | webhook, once per paid guide sale (dedupes Payhip retries); deleted again if the email fails |
| `pick:<sale_id>` | bound device slug | none | `/pick/<t>/confirm` (first device wins), webhook direct path |
| `crypto:cfm:<n>` | device slug | none | `POST /crypto/confirm` (once per crypto order); deleted again if the email fails |
| `deny:s:<sale_id>` | `refunded` / anything | none | webhook on a full `refunded`; owner by hand (partial refunds) |
| `deny:n:<n>` | anything | none | owner by hand (revoke one crypto order / token) |
| `ai:rl:<sha256(token)[:32]>:<YYYYMMDD>` | message count | 36 h | `/api/ai/chat` |

### AI assistant (paid-only chat)

`POST /api/ai/chat` — chat widget rendered on every `/access/<token>` page (added to `templates/content/base_content.html`).
- Auth goes through `_claims(token, "acc")` and the deny list, same as `/access`.
- Rate-limit: per-token, default 30 messages/day, stored in Upstash KV (`ai:rl:{sha256(token)[:32]}:{YYYYMMDD}`, TTL 36h). Plus IP-level via Flask-Limiter (60/h). Not keyed on a token prefix: legacy tokens share long prefixes (`{"e":...`).
- Provider: Groq API (free tier) → `llama-3.3-70b-versatile`, streamed back to the browser via SSE (`text/event-stream`).
- System prompt is built per request from `_device_capabilities(device)` (chip-specific BMC features) + `detect_language()`, so the model never recommends features the device can't do (e.g. no Apple Log on A14).
- Optional: if `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are set, every Q/A is forwarded to the owner via Telegram (fire-and-forget thread, doesn't block the stream).
- Disabled gracefully: if `GROQ_API_KEY` is missing, the endpoint returns 503 and the widget shows the network error.

### SEO

The site runs on `blackmagiccam.vercel.app` — no custom domain by choice. Every URL is
built from `BASE_URL`, so moving to a real domain later is a one-variable change.

- **`/robots.txt` and `/sitemap.xml` are Flask routes, not static files.** `vercel.json`
  only maps `/static/(.*)`, so a static `static/robots.txt` is served at
  `/static/robots.txt` and `/robots.txt` 404s. Do not reintroduce the static file.
- **Three indexing states**, decided in `inject_i18n` and rendered by `base.html`:
  1. `canonical_path` + `emit_hreflang` — the localized pages (`/`, `/select`,
     `/guide/<slug>` in English): canonical plus `hreflang` alternates.
  2. `canonical_path` without `emit_hreflang` — `/learn` pages: English-only, so they
     get a canonical but must never advertise `/ru/` or `/ar/` variants.
  3. `seo_noindex_follow` — `/ru/guide/*` and `/ar/guide/*`. Guide bodies are English;
     declaring them as Russian/Arabic across 60 URLs is a wrong-language signal. They
     stay reachable for the language switcher but are `noindex, follow` and are absent
     from the sitemap. **If guides are ever translated, flip this off in one place.**
- **`_is_publicly_localized` validates the slug** against `DEVICES`. Accepting any
  `/guide/*` string made every 404 under `/guide/` self-canonical and indexable.
- **`/learn` quality gate** (`learn.review()`): an article needs `MIN_WORDS` and at
  least one link into a device guide before it is listed or put in the sitemap. It
  returns the *reason* it failed, so a thin draft is visible rather than silently
  dropped. Facts in `learn.py` must match `bmc_knowledge.py` — that module is the
  source of truth for the paid guide and the AI assistant.
- **No `aggregateRating` anywhere.** It previously claimed 4.9 from 1200 reviews with
  14 testimonials on the page, which risks a manual action across the whole domain.
  Do not re-add it without real `Review` markup behind it.
- Homepage device chips link to all 30 guides — those pages had no other inbound link.
- After deploying: `python3 scripts/seo_check.py https://blackmagiccam.vercel.app`.

### i18n / Language
- **URL-based routing for SEO.** Indexable pages have 3 variants:
  - `/`, `/select`, `/guide/<slug>` → English (x-default)
  - `/ru/`, `/ru/select`, `/ru/guide/<slug>` → Russian
  - `/ar/`, `/ar/select`, `/ar/guide/<slug>` → Arabic
  - Implemented via dual `@app.route` with `<any(ru, ar):lang>` converter; handler stashes lang in `g.url_lang`.
- `detect_language()` priority: `g.url_lang` (URL) → `lang` cookie → `Accept-Language` header → EN.
- **Soft auto-redirect**: direct visitors hitting `/` with no cookie and RU/AR `Accept-Language` are 302-redirected to `/ru/` or `/ar/`. Googlebot (sends `en`) stays on `/` so canonical indexing stays correct.
- **Non-indexable routes** (`/access/<token>`, `/pick/<token>`, `/crypto/*`, `/checkout/card`) have no URL prefix — language comes from the cookie set by `/set-lang/<lang>`.
- `_strip_lang_prefix()` and `_localize_path()` in `app.py` build URL variants for sitemap + hreflang + `lang_link` helper.
- `@app.context_processor` injects `lang`, `t`, `lang_alternates` (canonical URLs per language for current page), and `lang_link(path)` for template internal links.
- `sitemap.xml` emits every public page × 3 languages with `<xhtml:link rel="alternate" hreflang>` alternates including `x-default`.
- `<link rel="canonical">` + `<link rel="alternate" hreflang>` in `base.html` are generated from `lang_alternates`.
- Language switcher in nav links directly to the localized URL variant of the current page (keeps SEO-friendly URLs; `/set-lang/<lang>` stays as a cookie-setting redirect fallback).
- Arabic: `dir="rtl"` on `<html>`, RTL CSS injected inline in `base.html`.
- JS strings passed via `window.BMC_I18N` rendered in `<head>` of `base.html`.

## Environment Variables

```
# HMAC for stateless access tokens + crypto order_id signing
KOFI_FULFILL_SECRET=...

# Payhip (card checkout)
PAYHIP_PRODUCT_URL=https://payhip.com/b/<product-id>
PAYHIP_API_KEY=...                 # webhook signature = sha256(this)
PAYHIP_GUIDE_PRODUCT_KEYS=...      # optional comma list of product_key/product_id/permalink that unlock the guide; default = key from PAYHIP_PRODUCT_URL

# Crypto (manual fulfillment) — set one or more; only configured networks appear in the UI
BINANCE_USDT_ADDRESS_TRC20=T...    # owner's USDT-TRC20 deposit address on Binance (Tron)
BINANCE_USDT_ADDRESS_BEP20=0x...   # owner's USDT-BEP20 deposit address on Binance (BNB Chain)
BINANCE_USDT_ADDRESS_ERC20=0x...   # owner's USDT-ERC20 deposit address on Binance (Ethereum)
BINANCE_USDT_ADDRESS_TON=UQ...     # owner's USDT-TON deposit address on Binance (The Open Network)
BINANCE_USDT_MEMO_TON=...          # MEMO Binance requires for TON deposits — shown with a copy button; without it deposits are not credited
BINANCE_USDT_ADDRESS=T...          # legacy fallback — used as TRC20 if BINANCE_USDT_ADDRESS_TRC20 not set
ADMIN_EMAIL=you@example.com        # receives "Confirm & send guide" magic link; defaults to GMAIL_USER

# Email (Gmail SMTP)
GMAIL_USER=...
GMAIL_APP_PASSWORD=...

# URLs
BASE_URL=https://yourdomain.com   # used in confirm-link URLs, access-link emails, canonical URLs and the sitemap
GOOGLE_SITE_VERIFICATION=...      # optional — meta-tag verification for Search Console
UPSTASH_REDIS_REST_URL=...        # KV (or KV_REST_API_URL) — required in production, see "KV keys"
UPSTASH_REDIS_REST_TOKEN=...
DB_PATH=purchases.db              # optional, defaults to /tmp/purchases.db

# AI assistant (paid-guide chat widget on /access/<token>)
GROQ_API_KEY=gsk_...                     # free tier from console.groq.com — required to enable chat
GROQ_MODEL=llama-3.3-70b-versatile       # optional, default
AI_DAILY_LIMIT_PER_USER=30               # optional, per-token daily cap, default 30
TELEGRAM_BOT_TOKEN=...                   # optional — enables owner notifications of every chat
TELEGRAM_CHAT_ID=...                     # optional — owner's Telegram chat id
```

Local: create `.env` file (loaded via `python-dotenv`).

## Adding a New Language

1. Add new locale key to `TRANSLATIONS` dict in `translations.py`
2. Add to `SUPPORTED_LANGS` tuple in `app.py`
3. Add lang button in `base.html` nav switcher
4. Add RTL block in `base.html` if needed
5. Add `{% if lang == 'xx' %}` blocks in all group templates

## Adding a New iPhone Model

1. Add entry to `DEVICES` list in `devices.py` (slug, name, chip, group, image)
2. If new chip group needed: create `templates/content/group-X.html`
3. Add group label key to `translations.py` (`group_X`) for all 3 languages
4. Add group to `groups` dict in `select.html`

## Gotchas

- `purchases.db` is a local file — **not persisted on Vercel** (ephemeral filesystem). Access is stateless HMAC; anything that must survive (dedupe, device binding, refunds) lives in Upstash KV.
- `BASE_URL` must match the actual deployed domain or confirm-link URLs in owner-notification emails break.
- DB column `stripe_session_id` is a misnomer (historical) — it stores Payhip `sale_id:device_slug` or `crypto:manual:{nonce}:{device_slug}:{network}`.
- Crypto confirm magic link is a `cfm`-purpose token that exists only in the owner's email; the customer gets a separate `ord` token. Opening the link (GET) never fulfils — only the POST button does.
- TON on Binance needs a MEMO. If `BINANCE_USDT_ADDRESS_TON` is set, `crypto_pay.html` shows a warning; set `BINANCE_USDT_MEMO_TON` so the MEMO is shown with a copy button.
- Tests: `python3.13 -m venv .venv-test && .venv-test/bin/pip install -r requirements.txt pytest && .venv-test/bin/python -m pytest tests -q`. They never load `.env`, KV and email are faked.
- `_send_admin_crypto_notification` uses the same Gmail SMTP path as customer emails — failures are logged but don't block the checkout page render (customer still sees the pay instructions).
- `make_response` is imported from Flask for `/set-lang` cookie response — don't remove it.
- Group templates use `{% if lang == 'ru' %} ... {% elif lang == 'ar' %} ... {% else %} ... {% endif %}` pattern inline — no separate template files per language.
- `BASE_URL` is `.strip().rstrip("/")`-ed at import. A trailing newline in the Vercel env value once put a literal `\n` inside all 96 sitemap `<loc>` values, which made the whole sitemap unparseable. Set env vars with `printf`, never `echo`.
- `static/img/` holds `og-image.jpg` and both video posters. It was untracked for months, so every share unfurled without an image and the hero showed black until the video painted. Keep it committed.
- Hero video is ~45 MB on Cloudflare R2 with `moov` at the end of the file. `preload` must stay `metadata` — `auto` makes every first visit pull the whole file.
- Mobile homepage rules live in `@media (max-width: 640px)` / `(max-width: 400px)` blocks at the end of `style.css`. Note that a 375 px phone matches **both**, so the 400 px block wins — check it first when a mobile value seems ignored.
- In the 2×2 benefit cards the icon is absolutely positioned and only the title's first line is indented past it. A grid column or a float both shortened *every* line and split the Russian word "кинематографические"; it needs the full 138 px tile width.

## Deployment (Vercel)

```bash
vercel                  # preview deploy
vercel --prod           # production deploy
vercel env pull .env    # sync env vars locally
```

Set env vars in Vercel dashboard or via `vercel env add`.

Deploy checklist:
- Upstash KV env vars are set in production (otherwise the once-only / one-device guards fail open).
- Guide product key: confirm the production `PAYHIP_PRODUCT_URL` has the form `https://payhip.com/b/<KEY>` or `https://payhip.com/buy?link=<KEY>`, or (safer) set `PAYHIP_GUIDE_PRODUCT_KEYS=<KEY>` explicitly. No parsable key → paid webhooks return 503 (Payhip retries for 3 h). A key that parses but is **wrong** → every sale is a silent 200 "paid sale with no guide item" WARNING and no customer gets an email — after the first real sale, check the logs for that line.
- `BINANCE_USDT_MEMO_TON` is set if TON is enabled with a Binance address.
- crypto orders pending at deploy time must be confirmed manually (old confirm links stop working). Procedure, run locally with the **production** `KOFI_FULFILL_SECRET` and `BASE_URL` in the environment (e.g. after `vercel env pull .env`), once per pending order whose deposit you have verified:
  ```bash
  python3 -c 'import os,secrets,app; assert app.HMAC_SECRET==os.environ["KOFI_FULFILL_SECRET"]; n=secrets.token_hex(6); print(app.BASE_URL+"/crypto/confirm/"+app._encode_token({"n":n,"t":"cfm","d":"<device-slug>","e":"<customer-email>","net":"<trc20|bep20|erc20|ton>"},"cfm"))'
  ```
  Open the printed link and press "Confirm & send guide" — the normal, once-only fulfilment sends the access email. (`<device-slug>` and the email are in the old owner notification; the old link's payload is plain base64 if you need them.) Alternatively ask the customer to submit `/crypto/checkout` again and confirm the new order.
