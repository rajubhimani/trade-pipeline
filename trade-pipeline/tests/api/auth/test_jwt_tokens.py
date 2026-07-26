import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

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
    """
    _, public_key = keypair
    forged = jwt.encode(
        {"sub": "attacker", "jti": "x", "exp": int(time.time()) + 3600},
        key=public_key,
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_access_token(forged, public_key)
