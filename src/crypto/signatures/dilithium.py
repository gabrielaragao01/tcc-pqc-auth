from __future__ import annotations

import oqs  # pyright: ignore[reportMissingImports]

from src.crypto.interfaces import IDigitalSignature
from src.crypto.models import SignatureKeyPair


class DilithiumSignature(IDigitalSignature):
    """liboqs Dilithium implementation of IDigitalSignature. Only file that imports oqs Signature."""

    def __init__(self, algorithm: str = "ML-DSA-44") -> None:
        self._algorithm = algorithm

    def generate_keypair(self) -> SignatureKeyPair:
        """Generate a Dilithium key pair."""
        with oqs.Signature(self._algorithm) as signer:
            public_key: bytes = signer.generate_keypair()
            private_key: bytes = signer.export_secret_key()
        return SignatureKeyPair(public_key=public_key, private_key=private_key)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """Sign a message with Dilithium using the private key."""
        with oqs.Signature(self._algorithm, private_key) as signer:
            signature: bytes = signer.sign(message)
        return signature

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature. Returns False for invalid signatures, never raises."""
        with oqs.Signature(self._algorithm) as verifier:
            return verifier.verify(message, signature, public_key)

    def validate(self) -> bool:
        """Full signature round-trip smoke test (generate → sign → verify)."""
        if self._algorithm not in oqs.get_enabled_sig_mechanisms():
            raise RuntimeError(
                f"Signature algorithm {self._algorithm!r} is not enabled in this liboqs build."
            )

        message = b"PQC smoke test - Dilithium"
        keypair = self.generate_keypair()
        signature = self.sign(message, keypair.private_key)
        is_valid = self.verify(message, signature, keypair.public_key)

        assert is_valid, (
            f"{self._algorithm} signature round-trip failed: verification returned False."
        )
        return True
