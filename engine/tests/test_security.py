import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.models import User
from marsad.newsletter.mailer import FakeMailer
from marsad.security import decrypt, encrypt, totp_now, verify_totp
from marsad.seed import seed_all

SECRET = "JBSWY3DPEHPK3PXP"


def test_totp_rfc6238_vector():
    # RFC 6238 test secret "12345678901234567890" (base32 below), SHA-1, t=59 -> 94287082 (8 digits) -> last 6: 287082
    rfc = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_now(rfc, at=59) == "287082"
    assert totp_now(rfc, at=1111111109) == "081804"


def test_verify_totp_drift_and_replay():
    now = 1_800_000_000
    code = totp_now(SECRET, at=now)
    step = verify_totp(SECRET, code, None, at=now)
    assert step is not None
    assert verify_totp(SECRET, code, step, at=now) is None  # same step twice: replay refused
    assert verify_totp(SECRET, totp_now(SECRET, at=now - 30), None, at=now) is not None  # one step of drift
    assert verify_totp(SECRET, totp_now(SECRET, at=now - 90), None, at=now) is None
    assert verify_totp(SECRET, "12ab56", None, at=now) is None


def test_encryption_roundtrip(settings):
    token = encrypt(settings, SECRET)
    assert SECRET not in token and decrypt(settings, token) == SECRET
    assert decrypt(settings.model_copy(update={"secret_key": "other"}), token) is None


@pytest.fixture
def api(db, session_factory, settings):
    seed_all(db)
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass"), role="admin"))
    db.commit()
    app = create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler), embedder=None,
                     mailer=FakeMailer())
    return TestClient(app), settings


def login(api, password="secret-pass", code=None, ip="203.0.113.7", email="ed@example.org"):
    body = {"email": email, "password": password}
    if code:
        body["code"] = code
    return api.post("/api/editor/login", json=body, headers={"X-Client-IP": ip})


def test_lockout_after_five_failures(api):
    client, _ = api
    for _ in range(5):
        assert login(client, "wrong").status_code == 401
    r = login(client)  # correct password, still locked
    assert r.status_code == 429 and r.headers["Retry-After"] == "900"
    assert login(client, email="other@example.org", ip="198.51.100.1").status_code == 401  # others unaffected


def test_two_factor_setup_login_and_replay(api, db):
    client, settings = api
    h = {"Authorization": f"Bearer {login(client).json()['token']}"}
    setup = client.post("/api/editor/2fa/setup", headers=h).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/") and "<svg" in setup["qr_svg"]
    stored = db.scalar(select(User)).totp_secret_enc
    assert setup["secret"] not in (stored or "")  # stored encrypted
    assert client.post("/api/editor/2fa/enable", headers=h, json={"code": "000000"}).status_code == 400
    assert client.post("/api/editor/2fa/enable", headers=h, json={"code": totp_now(setup["secret"])}).status_code == 200

    r = login(client)
    assert r.status_code == 401 and r.json()["detail"]["otp_required"] is True
    # The code used to enable is already spent in this time step; use the next step's code (clock drift window).
    nxt = totp_now(setup["secret"], at=time.time() + 30)
    assert login(client, code=nxt).status_code == 200
    replay = login(client, code=nxt)
    assert replay.status_code == 401 and replay.json()["detail"]["otp_required"] is True


def test_two_factor_can_be_required(api):
    client, settings = api
    settings.require_editor_2fa = True
    h = {"Authorization": f"Bearer {login(client).json()['token']}"}
    assert client.get("/api/editor/queue", headers=h).status_code == 403
    assert client.get("/api/editor/me", headers=h).json()["two_factor_required"] is True
    assert client.post("/api/editor/2fa/setup", headers=h).status_code == 200  # setup stays reachable


def test_public_forms_are_limited_per_address(api):
    client, _ = api
    codes = [client.post("/api/subscribe", json={"email": f"x{i}@example.org"}, headers={"X-Client-IP": "192.0.2.9"}).status_code
             for i in range(11)]
    assert codes[:10] == [202] * 10 and codes[10] == 429
    assert client.post("/api/subscribe", json={"email": "y@example.org"}, headers={"X-Client-IP": "192.0.2.10"}).status_code == 202
