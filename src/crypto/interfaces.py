from __future__ import annotations

from abc import ABC, abstractmethod

from src.crypto.models import KEMKeyPair, KEMResult, SignatureKeyPair


class IKeyEncapsulation(ABC):
    """Abstract interface for Key Encapsulation Mechanisms (KEM)."""

    @abstractmethod
    def generate_keypair(self) -> KEMKeyPair:
        """Generate a fresh public/private key pair."""
        ...

    @abstractmethod
    def encapsulate(self, public_key: bytes) -> KEMResult:
        """Encapsulate a shared secret under the recipient's public key."""
        ...

    @abstractmethod
    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Recover the shared secret from a ciphertext using the private key."""
        ...

    @abstractmethod
    def validate(self) -> bool:
        """Run a full KEM round-trip smoke test. Raises on failure."""
        ...


class IDigitalSignature(ABC):
    """Abstract interface for Digital Signature schemes."""

    @abstractmethod
    def generate_keypair(self) -> SignatureKeyPair:
        """Generate a fresh signing/verification key pair."""
        ...

    @abstractmethod
    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """Sign a message with the private key. Returns signature bytes."""
        ...

    @abstractmethod
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature. Returns False for invalid signatures, never raises."""
        ...

    @abstractmethod
    def validate(self) -> bool:
        """Run a full sign/verify round-trip smoke test. Raises on failure."""
        ...
