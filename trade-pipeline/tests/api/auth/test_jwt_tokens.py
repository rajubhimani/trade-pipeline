import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from trade_pipeline.api.auth.jwt_tokens import (
    ALGORITHM,
    TokenError,
    decode_access_token,
    issue_access_token,
)


def _generate_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture(scope="module")
def keypair() -> tuple[str, str]:
    return _generate_keypair()


def test_issue_and_decode_round_trip(keypair):
    private_key, public_key = keypair
    token = issue_access_token("user-1", private_key)
    claims = decode_access_token(token, public_key)

    assert claims.sub == "user-1"
    assert claims.jti  # non-empty unique id present


def test_two_tokens_have_different_jti(keypair):
    private_key, _ = keypair
    a = issue_access_token("user-1", private_key)
    b = issue_access_token("user-1", private_key)
    assert a != b


def test_expired_token_is_rejected(keypair):
    private_key, public_key = keypair
    # Hand-craft an already-expired token rather than sleeping in the test.
    import time as _time

    now = int(_time.time())
    payload = {"sub": "user-1", "jti": "x", "iat": now - 100, "exp": now - 1}
    token = jwt.encode(payload, private_key, algorithm=ALGORITHM)

    with pytest.raises(TokenError):
        decode_access_token(token, public_key)


def test_token_missing_exp_is_rejected(keypair):
    private_key, public_key = keypair
    token = jwt.encode({"sub": "user-1", "jti": "x"}, private_key, algorithm=ALGORITHM)

    with pytest.raises(TokenError):
        decode_access_token(token, public_key)


def test_alg_none_attack_is_rejected(keypair):
    """The classic alg:none attack: attacker strips the signature and sets
    alg=none in the header. Decoding must fail because we pin algorithms=[RS256]
    explicitly rather than trusting the token's own header.
    """
    _, public_key = keypair
    forged = jwt.encode(
        {"sub": "attacker", "jti": "x", "exp": int(time.time()) + 3600},
        key="",
        algorithm="none",
    )

    with pytest.raises(TokenError):
        decode_access_token(forged, public_key)


def test_hs256_confusion_attack_is_rejected(keypair):
    """Algorithm-confusion attack: attacker signs with HS256 using the RS256
    public key as if it were a shared secret. Must fail because we pin
    algorithms=[RS256] on decode, so an HS256-signed token is rejected outright.

    PyJWT's own ``encode()`` now refuses to build this token (it detects the
    key looks like a PEM/asymmetric key and won't use it as an HMAC secret) —
    which is itself a nice defense-in-depth data point, but means we have to
    hand-forge the token with raw ``hmac``/base64 to simulate an actual
    attacker, who wouldn't be using our copy of PyJWT to attack us.
    """
    import base64
    import hashlib
    import hmac
    import json

    _, public_key = keypair

    def b64url(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(
        json.dumps({"sub": "attacker", "jti": "x", "exp": int(time.time()) + 3600}).encode()
    )
    signing_input = header + b"." + payload
    signature = b64url(
        hmac.new(public_key.encode(), signing_input, hashlib.sha256).digest()
    )
    forged = (signing_input + b"." + signature).decode()

    with pytest.raises(TokenError):
        decode_access_token(forged, public_key)
