"""Tests for verify_ingest_token — Entra-issued bearer-token validation."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _req(headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = headers or {}
    return req


def _settings(**overrides):
    base = {
        "INGEST_REQUIRE_JWT": True,
        "INGEST_AUDIENCE": "api://compliance-advisor-ingest",
        "INGEST_EXPECTED_APPID": "",
        "ALLOWED_TENANT_IDS": "",
        "allowed_tenants": set(),
    }
    base.update(overrides)
    s = MagicMock()
    for k, v in base.items():
        setattr(s, k, v)
    return s


def _make_token(signing_key, *, tid: str, aud: str, appid: str | None = None, exp_offset: int = 3600) -> str:
    now = int(time.time())
    claims = {
        "tid": tid,
        "aud": aud,
        "iss": f"https://sts.windows.net/{tid}/",
        "iat": now,
        "exp": now + exp_offset,
    }
    if appid:
        claims["appid"] = appid
    return jwt.encode(claims, signing_key, algorithm="RS256")


def _patch_jwks(signing_key):
    """Patch _get_jwks_client so signature verification uses our test key."""
    fake_signing_key = MagicMock()
    fake_signing_key.key = signing_key.public_key()

    fake_client = MagicMock()
    fake_client.get_signing_key_from_jwt.return_value = fake_signing_key
    return patch("shared.auth._get_jwks_client", return_value=fake_client)


def test_disabled_returns_empty():
    from shared import auth

    with patch.object(auth, "get_settings", return_value=_settings(INGEST_REQUIRE_JWT=False)):
        result = auth.verify_ingest_token(_req(), "any-tid")
    assert result == {}


def test_missing_audience_config_raises_500():
    from shared import auth

    with patch.object(auth, "get_settings", return_value=_settings(INGEST_AUDIENCE="")):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": "Bearer x"}), "t1")
    assert exc.value.status_code == 500


def test_missing_authorization_header_returns_401():
    from shared import auth

    with patch.object(auth, "get_settings", return_value=_settings()):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req(), "t1")
    assert exc.value.status_code == 401


def test_valid_token_passes(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://compliance-advisor-ingest")

    with patch.object(auth, "get_settings", return_value=_settings()), _patch_jwks(signing_key):
        claims = auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)

    assert claims["tid"] == tid


def test_token_tid_must_match_payload(signing_key):
    from shared import auth

    token_tid = "11111111-1111-1111-1111-111111111111"
    payload_tid = "22222222-2222-2222-2222-222222222222"
    token = _make_token(signing_key, tid=token_tid, aud="api://compliance-advisor-ingest")

    with patch.object(auth, "get_settings", return_value=_settings()):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), payload_tid)
    assert exc.value.status_code == 403
    assert "tenant" in exc.value.message.lower()


def test_tid_not_in_allowlist_rejected(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://compliance-advisor-ingest")
    settings = _settings(allowed_tenants={"99999999-9999-9999-9999-999999999999"})

    with patch.object(auth, "get_settings", return_value=settings):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)
    assert exc.value.status_code == 403


def test_audience_mismatch_rejected(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://wrong-audience")

    with patch.object(auth, "get_settings", return_value=_settings()), _patch_jwks(signing_key):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)
    assert exc.value.status_code == 401


def test_expired_token_rejected(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://compliance-advisor-ingest", exp_offset=-60)

    with patch.object(auth, "get_settings", return_value=_settings()), _patch_jwks(signing_key):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)
    assert exc.value.status_code == 401


def test_appid_check_enforced(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://compliance-advisor-ingest", appid="bad-app")
    settings = _settings(INGEST_EXPECTED_APPID="good-app")

    with patch.object(auth, "get_settings", return_value=settings), _patch_jwks(signing_key):
        with pytest.raises(auth.IngestAuthError) as exc:
            auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)
    assert exc.value.status_code == 403


def test_appid_check_passes_when_match(signing_key):
    from shared import auth

    tid = "11111111-1111-1111-1111-111111111111"
    token = _make_token(signing_key, tid=tid, aud="api://compliance-advisor-ingest", appid="good-app")
    settings = _settings(INGEST_EXPECTED_APPID="good-app")

    with patch.object(auth, "get_settings", return_value=settings), _patch_jwks(signing_key):
        claims = auth.verify_ingest_token(_req({"Authorization": f"Bearer {token}"}), tid)
    assert claims["appid"] == "good-app"
