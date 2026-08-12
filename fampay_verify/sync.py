"""Synchronous wrapper for FamPayVerifier for easier usage in non-async code."""

from .verifier import FamPayVerifier as AsyncFamPayVerifier
from .models import (
    FamPayVerifierConfig,
    GenerateQrParams,
    VerifyPaymentParams,
    QrResult,
    VerificationResult,
)


class FamPayVerifier:
    """Synchronous wrapper around AsyncFamPayVerifier."""

    def __init__(self, config: FamPayVerifierConfig):
        self._async_verifier = AsyncFamPayVerifier(config)

    def generate_qr(self, params: GenerateQrParams) -> QrResult:
        """Generate a UPI payment URI and QR code (sync)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context, need to run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._async_verifier.generate_qr(params))
                return future.result()
        else:
            return asyncio.run(self._async_verifier.generate_qr(params))

    def verify_payment(self, params: VerifyPaymentParams) -> VerificationResult:
        """Verify a payment by checking Gmail (sync)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._async_verifier.verify_payment(params))
                return future.result()
        else:
            return asyncio.run(self._async_verifier.verify_payment(params))


# Export the async version as well for advanced users
AsyncFamPayVerifier = AsyncFamPayVerifier