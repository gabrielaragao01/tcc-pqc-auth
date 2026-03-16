from __future__ import annotations

import oqs  # pyright: ignore[reportMissingImports]

from src.crypto.interfaces import IKeyEncapsulation
from src.crypto.models import KEMKeyPair, KEMResult


class KyberKEM(IKeyEncapsulation):
    """liboqs Kyber implementation of IKeyEncapsulation. Only file that imports oqs KEM."""

    def __init__(self, algorithm: str = "Kyber512") -> None:
        self._algorithm = algorithm

    def generate_keypair(self) -> KEMKeyPair:
        """Generate a Kyber key pair."""
        with oqs.KeyEncapsulation(self._algorithm) as kem:
            public_key: bytes = kem.generate_keypair()
            private_key: bytes = kem.export_secret_key()
        return KEMKeyPair(public_key=public_key, private_key=private_key)

    def encapsulate(self, public_key: bytes) -> KEMResult:
        """Encapsulate a shared secret under the recipient's public key (sender side)."""
        with oqs.KeyEncapsulation(self._algorithm) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key)
        return KEMResult(ciphertext=ciphertext, shared_secret=shared_secret)

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Recover the shared secret from ciphertext using the private key (receiver side)."""
        with oqs.KeyEncapsulation(self._algorithm, private_key) as kem:
            shared_secret: bytes = kem.decap_secret(ciphertext)
        return shared_secret

    def validate(self) -> bool:
        """Full KEM round-trip smoke test (generate → encapsulate → decapsulate)."""
        if self._algorithm not in oqs.get_enabled_kem_mechanisms():
            raise RuntimeError(
                f"KEM algorithm {self._algorithm!r} is not enabled in this liboqs build."
            )

        keypair = self.generate_keypair()
        result = self.encapsulate(keypair.public_key)
        recovered = self.decapsulate(result.ciphertext, keypair.private_key)

        assert recovered == result.shared_secret, (
            f"{self._algorithm} KEM round-trip failed: shared secrets do not match."
        )
        return True
