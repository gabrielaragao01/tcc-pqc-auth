from __future__ import annotations

from src.crypto.interfaces import IDigitalSignature, IKeyEncapsulation
from src.crypto.models import PQCSmokeTestReport, SmokeTestResult


class PQCAuthService:
    """Application-layer service that orchestrates PQC operations via injected interfaces."""

    def __init__(
        self,
        kem: IKeyEncapsulation,
        signature: IDigitalSignature,
    ) -> None:
        self._kem = kem
        self._signature = signature

    def run_smoke_tests(self) -> PQCSmokeTestReport:
        """Run validate() on each provider and return a structured report."""
        results: list[SmokeTestResult] = []

        providers: list[tuple[str, IKeyEncapsulation | IDigitalSignature]] = [
            ("kem", self._kem),
            ("signature", self._signature),
        ]

        for label, provider in providers:
            try:
                provider.validate()
                results.append(SmokeTestResult(algorithm=label, passed=True))
            except Exception as exc:  # noqa: BLE001
                results.append(
                    SmokeTestResult(algorithm=label, passed=False, error=str(exc))
                )

        return PQCSmokeTestReport(
            all_passed=all(r.passed for r in results),
            results=results,
        )
