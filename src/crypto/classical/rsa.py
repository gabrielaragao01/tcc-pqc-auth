from __future__ import annotations

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.crypto.interfaces import IDigitalSignature
from src.crypto.models import SignatureKeyPair


class RSASignature(IDigitalSignature):
    """Classical RSA-PSS implementation of IDigitalSignature.

    Uses the `cryptography` library (not liboqs). Keys are DER-encoded bytes,
    matching the raw-bytes contract of SignatureKeyPair — consistent with the
    Dilithium implementation.
    """

    def __init__(self, key_size: int = 2048) -> None:
        self._key_size = key_size

    def generate_keypair(self) -> SignatureKeyPair:
        """Generate an RSA key pair. Returns DER-encoded bytes."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self._key_size,
        )
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return SignatureKeyPair(public_key=public_bytes, private_key=private_bytes)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """Sign message with RSA-PSS + SHA-256."""
        key = serialization.load_der_private_key(private_key, password=None)
        return key.sign(  # type: ignore[return-value]
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify RSA-PSS signature. Returns False on any failure, never raises."""
        try:
            key = serialization.load_der_public_key(public_key)
            key.verify(  # type: ignore[union-attr]
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def validate(self) -> bool:
        """Full RSA sign/verify round-trip smoke test."""
        message = b"Classical smoke test - RSA-PSS"
        keypair = self.generate_keypair()
        signature = self.sign(message, keypair.private_key)
        result = self.verify(message, signature, keypair.public_key)
        assert result, "RSA signature round-trip failed: verify returned False."
        return True
