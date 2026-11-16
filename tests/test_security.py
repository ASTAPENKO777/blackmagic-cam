"""Security regression tests for token purposes, crypto fulfilment, pick binding,
the Payhip webhook and the deny list.

Run:  .venv-test/bin/python -m pytest tests -q
No network: KV is an in-memory dict behind app._kv_cmd, email is captured,
Groq is stubbed, and the real .env is never loaded.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Never read the developer's real .env: app.py calls load_dotenv() at import.
import dotenv  # noqa: E402
dotenv.load_dotenv = lambda *a, **k: False

SECRET = "test-secret-" + "x" * 40
PAYHIP_KEY = "payhip-test-api-key"
_ENV = {
    "KOFI_FULFILL_SECRET": SECRET,
    "PAYHIP_API_KEY": PAYHIP_KEY,
    "PAYHIP_PRODUCT_URL": "https://payhip.com/b/GUIDE1",
    "PAYHIP_GUIDE_PRODUCT_KEYS": "",
    "BINANCE_USDT_ADDRESS_TRC20": "TTestTrc20Address000000000000000000",
    "BINANCE_USDT_ADDRESS_TON": "UQTestTonAddress000000000000000000000000000000",
    "BINANCE_USDT_MEMO_TON": "123456789",
    "BASE_URL": "http://test.local",
    "ADMIN_EMAIL": "owner@example.com",
    "GMAIL_USER": "shop@example.com",
    "GMAIL_APP_PASSWORD": "unused",
    "GROQ_API_KEY": "test-groq",
    "UPSTASH_REDIS_REST_URL": "https://kv.test",
    "UPSTASH_REDIS_REST_TOKEN": "kv-token",
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "DB_PATH": os.path.join(tempfile.mkdtemp(prefix="bmc-test-"), "purchases.db"),
}
os.environ.update(_ENV)
for var in ("VERCEL", "VERCEL_ENV", "KV_REST_API_URL", "KV_REST_API_TOKEN", "TON_ADDRESS"):
    os.environ.pop(var, None)

import pytest  # noqa: E402

import app as appmod  # noqa: E402
from devices import DEVICES  # noqa: E402

DEV_A = DEVICES[0]["slug"]
DEV_B = DEVICES[1]["slug"]


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeKV:
    def __init__(self):
        self.store = {}
        self.commands = []

    def __call__(self, cmd):
        cmd = [str(c) for c in cmd]
        self.commands.append(cmd)
        op = cmd[0].upper()
        if op == "SET":
            key, value, opts = cmd[1], cmd[2], [c.upper() for c in cmd[3:]]
            if "NX" in opts and key in self.store:
                return None
            self.store[key] = value
            return "OK"
        if op == "GET":
            return self.store.get(cmd[1])
        if op == "DEL":
            return 1 if self.store.pop(cmd[1], None) is not None else 0
        raise AssertionError(f"unexpected KV command {cmd}")


class FakeGroqResponse:
    status_code = 200
    text = ""

    def iter_lines(self):
        yield b'data: {"choices":[{"delta":{"content":"ok"}}]}'
        yield b"data: [DONE]"


@pytest.fixture
def kv(monkeypatch):
    fake = FakeKV()
    monkeypatch.setattr(appmod, "_kv_cmd", fake)
    monkeypatch.setattr(appmod, "UPSTASH_URL", "https://kv.test")
    monkeypatch.setattr(appmod, "UPSTASH_TOKEN", "kv-token")
    return fake


class Outbox(list):
    """Captured emails. Set .fail = True to simulate an SMTP failure (nothing captured)."""
    fail = False

    def send(self, to, subject, html):
        if self.fail:
            return False
        self.append({"to": to, "subject": subject, "html": html})
        return True


@pytest.fixture
def mails(monkeypatch):
    sent = Outbox()
    monkeypatch.setattr(appmod, "_send_email", sent.send)
    return sent


@pytest.fixture
def client(kv, mails, monkeypatch):
    appmod.limiter.enabled = False
    monkeypatch.setattr(appmod.requests, "post", lambda *a, **k: FakeGroqResponse())
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as c:
        yield c


# ── Helpers ──────────────────────────────────────────────────────────────────

def legacy_token(data: dict) -> str:
    """A token exactly as the pre-hotfix code minted it (master-secret signature)."""
    payload = base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{sig}"


def links(html: str, kind: str) -> list:
    return re.findall(r"http://test\.local/%s/([A-Za-z0-9_\-]+\.[0-9a-f]+)" % kind, html)


def crypto_checkout(client, device=DEV_A, network="trc20"):
    resp = client.post("/crypto/checkout", data={
        "device": device, "email": "buyer@example.com", "network": network})
    assert resp.status_code == 302
    order_token = resp.headers["Location"].rsplit("/crypto/pay/", 1)[1]
    return order_token


def payhip(client, event="paid", sale_id="SALE1", product_key="GUIDE1",
           signature=None, email="card@example.com", **extra):
    sig = signature if signature is not None else hashlib.sha256(PAYHIP_KEY.encode()).hexdigest()
    payload = {
        **extra,
        "id": sale_id, "email": email, "currency": "USD", "price": 499,
        "items": [{
            "product_id": "2804256", "product_name": "Some product",
            "product_key": product_key,
            "product_permalink": f"https://payhip.com/b/{product_key}",
            "quantity": "1",
        }],
        "type": event, "signature": sig,
    }
    return client.post("/payhip/webhook", json=payload)


def chat(client, token):
    return client.post("/api/ai/chat", json={"token": token, "message": "best fps?"})


# ── Crypto flow ──────────────────────────────────────────────────────────────

def test_customer_redirect_uses_ord_token_that_opens_nothing_else(client, mails):
    order_token = crypto_checkout(client)
    assert appmod._claims(order_token, "ord")
    assert client.get(f"/crypto/pay/{order_token}").status_code == 200

    assert client.get(f"/access/{order_token}").status_code == 404
    assert client.get(f"/crypto/confirm/{order_token}").status_code == 404
    assert client.post(f"/crypto/confirm/{order_token}").status_code == 404
    assert chat(client, order_token).status_code == 401

    # The confirm link exists only in the owner's notification email.
    assert len(mails) == 1 and mails[0]["to"] == "owner@example.com"
    cfm = links(mails[0]["html"], "crypto/confirm")
    assert len(cfm) == 1 and cfm[0] != order_token
    assert order_token not in mails[0]["html"]


def test_get_confirm_has_no_side_effects(client, mails, kv):
    crypto_checkout(client)
    cfm = links(mails[0]["html"], "crypto/confirm")[0]
    before_store = dict(kv.store)

    for _ in range(3):
        resp = client.get(f"/crypto/confirm/{cfm}")
        assert resp.status_code == 200
        assert b'method="post"' in resp.data

    assert len(mails) == 1  # only the owner notification
    assert kv.store == before_store
    assert not any(c[0] == "SET" for c in kv.commands)


def test_post_confirm_fulfils_exactly_once(client, mails, kv):
    order_token = crypto_checkout(client)
    cfm = links(mails[0]["html"], "crypto/confirm")[0]
    nonce = appmod._claims(cfm, "cfm")["n"]

    assert client.post(f"/crypto/confirm/{cfm}").status_code == 200
    assert client.post(f"/crypto/confirm/{cfm}").status_code == 200
    assert client.get(f"/crypto/confirm/{cfm}").status_code == 200

    customer = [m for m in mails if m["to"] == "buyer@example.com"]
    assert len(customer) == 1
    assert kv.store.get(f"crypto:cfm:{nonce}") == DEV_A

    access = links(customer[0]["html"], "access")[0]
    claims = appmod._claims(access, "acc")
    assert claims["t"] == "acc" and claims["d"] == DEV_A and claims["n"] == nonce
    assert list(claims)[0] == "n"  # per-purchase field first
    assert client.get(f"/access/{access}").status_code == 200
    assert chat(client, access).status_code == 200

    # Neither the owner's nor the customer's crypto token is an access token.
    assert client.get(f"/access/{cfm}").status_code == 404
    assert client.get(f"/access/{order_token}").status_code == 404


def test_confirm_dedupes_on_kv_even_without_db_row(client, mails, kv, monkeypatch):
    crypto_checkout(client)
    cfm = links(mails[0]["html"], "crypto/confirm")[0]
    monkeypatch.setattr(appmod, "purchase_exists_for_session", lambda key: False)
    client.post(f"/crypto/confirm/{cfm}")
    client.post(f"/crypto/confirm/{cfm}")
    assert len([m for m in mails if m["to"] == "buyer@example.com"]) == 1


def test_ton_page_shows_memo_and_exchange_warning(client):
    order_token = crypto_checkout(client, network="ton")
    body = client.get(f"/crypto/pay/{order_token}").get_data(as_text=True)
    assert 'data-copy="123456789"' in body
    assert appmod.TRANSLATIONS["en"]["crypto_pay_memo_warning"] in body


# ── Legacy tokens ────────────────────────────────────────────────────────────

def test_legacy_access_token_still_opens_access(client):
    tok = legacy_token({"e": "old@example.com", "d": DEV_A, "s": "OLDSALE"})
    assert client.get(f"/access/{tok}").status_code == 200
    assert chat(client, tok).status_code == 200


def test_legacy_confirm_token_opens_nothing(client, mails):
    tok = legacy_token({"d": DEV_A, "e": "old@example.com", "n": "abcd1234", "net": "trc20"})
    assert client.get(f"/access/{tok}").status_code == 404
    assert client.get(f"/crypto/confirm/{tok}").status_code == 404
    assert client.post(f"/crypto/confirm/{tok}").status_code == 404
    assert client.get(f"/crypto/pay/{tok}").status_code == 404
    assert client.get(f"/pick/{tok}").status_code == 404
    assert chat(client, tok).status_code == 401
    assert mails == []


def test_legacy_keyset_must_match_exactly(client):
    # Extra or missing keys on a master-signed token are rejected.
    assert client.get("/access/" + legacy_token(
        {"e": "a@example.com", "d": DEV_A, "s": "S", "x": "1"})).status_code == 404
    assert client.get("/access/" + legacy_token({"e": "a@example.com", "d": DEV_A})).status_code == 404
    # A new-format access token signed with the master secret is not valid either.
    assert client.get("/access/" + legacy_token(
        {"n": "1", "t": "acc", "e": "a@example.com", "d": DEV_A, "s": "S"})).status_code == 404


def test_legacy_pick_token_works_but_binds_first_device(client, mails, kv):
    tok = legacy_token({"e": "old@example.com", "s": "PICKSALE"})
    assert client.get(f"/pick/{tok}").status_code == 200

    assert client.post(f"/pick/{tok}/confirm", data={"device": DEV_A}).status_code == 200
    assert kv.store["pick:PICKSALE"] == DEV_A
    first_link = links(mails[-1]["html"], "access")[0]
    assert client.get(f"/access/{first_link}").status_code == 200

    # Same device again: the access email is simply re-sent (same link).
    assert client.post(f"/pick/{tok}/confirm", data={"device": DEV_A}).status_code == 200
    assert len(mails) == 2 and links(mails[-1]["html"], "access")[0] == first_link

    # A different device is refused and nothing is sent.
    resp = client.post(f"/pick/{tok}/confirm", data={"device": DEV_B})
    assert resp.status_code == 409
    assert DEVICES[0]["name"].encode() in resp.data
    assert len(mails) == 2


def test_access_token_is_not_a_pick_token(client):
    acc = appmod._new_access_token("a@example.com", DEV_A, "S9")
    assert client.get(f"/pick/{acc}").status_code == 404
    legacy_acc = legacy_token({"e": "a@example.com", "d": DEV_A, "s": "S9"})
    assert client.post(f"/pick/{legacy_acc}/confirm", data={"device": DEV_B}).status_code == 404


# ── Payhip webhook ───────────────────────────────────────────────────────────

def test_payhip_paid_then_refunded_revokes_access(client, mails, kv):
    assert payhip(client, "paid", sale_id="S100").status_code == 200
    assert len(mails) == 1
    pick = links(mails[0]["html"], "pick")[0]
    assert appmod._claims(pick, "pick")["t"] == "pick"

    client.post(f"/pick/{pick}/confirm", data={"device": DEV_A})
    access = links(mails[-1]["html"], "access")[0]
    assert client.get(f"/access/{access}").status_code == 200

    assert payhip(client, "refunded", sale_id="S100").status_code == 200
    assert kv.store.get("deny:s:S100")
    assert len(mails) == 2  # refund sends nothing

    assert client.get(f"/access/{access}").status_code == 404
    assert chat(client, access).status_code == 401
    assert client.get(f"/pick/{pick}").status_code == 404
    # Legacy links for the refunded sale are revoked too.
    legacy = legacy_token({"e": "card@example.com", "d": DEV_A, "s": "S100"})
    assert client.get(f"/access/{legacy}").status_code == 404


def test_deny_by_nonce(client, kv):
    acc = appmod._new_access_token("a@example.com", DEV_A, "S5")
    assert client.get(f"/access/{acc}").status_code == 200
    kv.store["deny:n:" + appmod._claims(acc, "acc")["n"]] = "1"
    assert client.get(f"/access/{acc}").status_code == 404


def test_payhip_non_guide_product_sends_nothing(client, mails, kv):
    assert payhip(client, "paid", sale_id="S200", product_key="OTHER").status_code == 200
    assert mails == []
    assert "payhip:sale:S200" not in kv.store


def test_payhip_other_event_types_are_noops(client, mails):
    for event in ("subscription.created", "subscription.deleted", ""):
        assert payhip(client, event, sale_id="S300").status_code == 200
    assert mails == []


def test_payhip_retries_are_deduplicated(client, mails, kv):
    for _ in range(3):
        assert payhip(client, "paid", sale_id="S400").status_code == 200
    assert len(mails) == 1
    assert kv.store["payhip:sale:S400"]


def test_payhip_explicit_product_keys(client, mails, monkeypatch):
    monkeypatch.setattr(appmod, "PAYHIP_GUIDE_PRODUCT_KEYS", "OTHER, 999")
    assert payhip(client, "paid", sale_id="S500", product_key="GUIDE1").status_code == 200
    assert mails == []
    assert payhip(client, "paid", sale_id="S501", product_key="OTHER").status_code == 200
    assert len(mails) == 1


def test_payhip_bad_signature_rejected(client, mails):
    assert payhip(client, "paid", sale_id="S600", signature="0" * 64).status_code == 401
    assert payhip(client, "paid", sale_id="S601", signature="").status_code == 401
    assert payhip(client, "refunded", sale_id="S602", signature="é").status_code == 401
    assert mails == []


# ── Tampering ────────────────────────────────────────────────────────────────

def test_tampered_tokens_rejected(client):
    acc = appmod._new_access_token("a@example.com", DEV_A, "S7")
    payload, sig = acc.rsplit(".", 1)
    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert client.get(f"/access/{payload}.{flipped}").status_code == 404

    # Change the device inside the payload but keep the old signature.
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data["d"] = DEV_B
    forged = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    assert client.get(f"/access/{forged}.{sig}").status_code == 404

    # Relabel an order token as an access token: signature no longer matches.
    order = appmod._encode_token({"n": "1", "t": "ord", "d": DEV_A, "e": "a@example.com"}, "ord")
    p, s = order.rsplit(".", 1)
    d = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    d["t"] = "acc"
    relabeled = base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).decode().rstrip("=")
    assert client.get(f"/access/{relabeled}.{s}").status_code == 404


# ── KV / rate limit plumbing ─────────────────────────────────────────────────

def test_kv_uses_json_command_form(kv):
    assert appmod._kv_set("k1", "v1", ttl_seconds=60) is True
    assert kv.commands[-1] == ["SET", "k1", "v1", "EX", "60"]
    assert appmod._kv_set_nx("k2", "v2") is True
    assert kv.commands[-1] == ["SET", "k2", "v2", "NX"]
    assert appmod._kv_set_nx("k2", "other") is False
    assert kv.store["k2"] == "v2"


def test_kv_set_nx_fails_open_when_unconfigured(monkeypatch):
    monkeypatch.setattr(appmod, "UPSTASH_URL", "")
    assert appmod._kv_set_nx("anything", "1") is True


def test_ai_rate_limit_key_is_token_hash(client, kv):
    acc = appmod._new_access_token("a@example.com", DEV_A, "S8")
    assert chat(client, acc).status_code == 200
    rl = [k for k in kv.store if k.startswith("ai:rl:")]
    assert len(rl) == 1
    assert rl[0].split(":")[2] == hashlib.sha256(acc.encode()).hexdigest()[:32]


# ── Review fixes ─────────────────────────────────────────────────────────────

def test_payhip_buy_link_url_is_parsed(client, mails, monkeypatch):
    monkeypatch.setattr(appmod, "PAYHIP_PRODUCT_URL", "https://payhip.com/buy?link=GUIDE1")
    assert appmod._payhip_guide_keys() >= {"GUIDE1"}
    assert payhip(client, "paid", sale_id="S700").status_code == 200
    assert len(mails) == 1


def test_payhip_key_from_url_forms():
    k = appmod._payhip_key_from_url
    assert k("https://payhip.com/b/AbC12") == "AbC12"
    assert k("https://payhip.com/b/AbC12/?utm=x") == "AbC12"
    assert k("https://shop.example.com/b/AbC12") == "AbC12"
    assert k("https://payhip.com/buy?link=AbC12") == "AbC12"
    assert k("https://payhip.com/SomeStore") == ""
    assert k("") == ""


def test_payhip_unparsable_product_url_is_unconfigured(client, mails, kv, monkeypatch):
    monkeypatch.setattr(appmod, "PAYHIP_PRODUCT_URL", "https://payhip.com/SomeStore")
    assert payhip(client, "paid", sale_id="S701").status_code == 503
    assert mails == [] and "payhip:sale:S701" not in kv.store


def test_payhip_no_guide_item_is_logged_loudly(client, mails, caplog):
    with caplog.at_level("WARNING"):
        assert payhip(client, "paid", sale_id="S702", product_key="OTHER").status_code == 200
    rec = [r for r in caplog.records if "paid sale with no guide item" in r.getMessage()]
    assert rec and rec[0].levelname == "WARNING" and "OTHER" in rec[0].getMessage()
    assert PAYHIP_KEY not in caplog.text
    assert hashlib.sha256(PAYHIP_KEY.encode()).hexdigest() not in caplog.text


def test_payhip_refund_kv_failure_returns_503(client, kv, monkeypatch):
    def broken(cmd):
        if cmd[0] == "SET" and str(cmd[1]).startswith("deny:"):
            raise RuntimeError("upstash down")
        return kv(cmd)
    monkeypatch.setattr(appmod, "_kv_cmd", broken)
    assert payhip(client, "refunded", sale_id="S703").status_code == 503
    monkeypatch.setattr(appmod, "_kv_cmd", kv)  # Payhip retries later
    assert payhip(client, "refunded", sale_id="S703").status_code == 200
    assert kv.store["deny:s:S703"]


def test_payhip_partial_refund_keeps_access(client, kv):
    acc = appmod._new_access_token("card@example.com", DEV_A, "S704")
    assert payhip(client, "refunded", sale_id="S704", amount_refunded=100).status_code == 200
    assert "deny:s:S704" not in kv.store
    assert client.get(f"/access/{acc}").status_code == 200
    # A full refund (amount_refunded == price) revokes.
    assert payhip(client, "refunded", sale_id="S704", amount_refunded="499").status_code == 200
    assert kv.store["deny:s:S704"]
    assert client.get(f"/access/{acc}").status_code == 404


def test_payhip_email_failure_is_retried(client, mails, kv):
    mails.fail = True
    assert payhip(client, "paid", sale_id="S705").status_code == 503
    assert "payhip:sale:S705" not in kv.store
    mails.fail = False
    assert payhip(client, "paid", sale_id="S705").status_code == 200
    assert len(mails) == 1
    assert payhip(client, "paid", sale_id="S705").status_code == 200
    assert len(mails) == 1


def test_payhip_direct_device_email_failure_keeps_device_choice(client, mails, kv):
    kv.store["pay:card:card@example.com"] = DEV_B
    mails.fail = True
    assert payhip(client, "paid", sale_id="S706").status_code == 503
    assert kv.store["pay:card:card@example.com"] == DEV_B
    mails.fail = False
    assert payhip(client, "paid", sale_id="S706").status_code == 200
    assert len(mails) == 1 and links(mails[0]["html"], "access")
    assert "pay:card:card@example.com" not in kv.store


def test_crypto_confirm_email_failure_allows_retry(client, mails, kv):
    crypto_checkout(client)
    cfm = links(mails[0]["html"], "crypto/confirm")[0]
    nonce = appmod._claims(cfm, "cfm")["n"]

    mails.fail = True
    resp = client.post(f"/crypto/confirm/{cfm}")
    assert resp.status_code == 502
    assert b'role="alert"' in resp.data and b'method="post"' in resp.data
    assert f"crypto:cfm:{nonce}" not in kv.store
    # GET still offers the button (not "Already sent").
    assert b'method="post"' in client.get(f"/crypto/confirm/{cfm}").data

    mails.fail = False
    assert client.post(f"/crypto/confirm/{cfm}").status_code == 200
    assert client.post(f"/crypto/confirm/{cfm}").status_code == 200
    assert len([m for m in mails if m["to"] == "buyer@example.com"]) == 1


def test_pick_email_failure_reports_error_and_retry_works(client, mails, kv):
    tok = appmod._encode_token({"t": "pick", "e": "p@example.com", "s": "S707"}, "pick")
    mails.fail = True
    assert client.post(f"/pick/{tok}/confirm", data={"device": DEV_A}).status_code == 502
    mails.fail = False
    assert client.post(f"/pick/{tok}/confirm", data={"device": DEV_A}).status_code == 200
    assert len(mails) == 1


def test_ton_qr_encodes_memo_deeplink(client):
    order_token = crypto_checkout(client, network="ton")
    body = client.get(f"/crypto/pay/{order_token}").get_data(as_text=True)
    assert "ton://transfer/UQTestTonAddress000000000000000000000000000000?text=123456789" in body
    trc = crypto_checkout(client, network="trc20")
    assert 'var qrText = "TTestTrc20Address000000000000000000";' in client.get(f"/crypto/pay/{trc}").get_data(as_text=True)


def test_access_accepts_long_email_tokens(client):
    email = "a" * 150 + "@example.com"
    acc = appmod._new_access_token(email, DEV_A, "S708")
    assert 300 < len(acc) <= 600
    assert client.get(f"/access/{acc}").status_code == 200


def test_encode_token_rejects_mismatched_purpose():
    with pytest.raises(ValueError):
        appmod._encode_token({"t": "acc", "e": "a@example.com", "s": "S"}, "pick")
