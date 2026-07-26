"""Generate the RSA keypair used for JWT RS256 signing (see api/settings.py).

Replaces the manual `openssl genrsa` / `openssl rsa -pubout` steps in
README.md for the Docker/compose path, where there's no host shell to run
them against a container-only volume. Uses `cryptography` (already a
dependency via pyjwt's RS256 backend), not a subprocess call to openssl.

Idempotent: skips generation if both files already exist, so it's safe to
run on every `docker compose up` (the `keys-init` service) without
clobbering a keypair that JWTs have already been issued against.
"""

import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from trade_pipeline.api.settings import ApiEnvSettings

logger = logging.getLogger(__name__)


def generate_keypair(private_key_path, public_key_path) -> None:
    if private_key_path.exists() and public_key_path.exists():
        logger.info("keys already exist at %s / %s, skipping", private_key_path, public_key_path)
        return

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    logger.info("generated RSA keypair at %s / %s", private_key_path, public_key_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    env = ApiEnvSettings()
    generate_keypair(env.jwt_private_key_path, env.jwt_public_key_path)
