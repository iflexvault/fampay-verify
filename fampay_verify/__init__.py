"""FamPay payment verification utility and QR generator for Python."""

from .verifier import FamPayVerifier as AsyncFamPayVerifier
from .sync import FamPayVerifier
from .models import (
    FamPayVerifierConfig,
    GenerateQrParams,
    VerifyPaymentParams,
    QrResult,
    VerificationResult,
)

__all__ = [
    "FamPayVerifier",           # Sync wrapper (recommended for most users)
    "AsyncFamPayVerifier",      # Async version for async contexts
    "FamPayVerifierConfig",
    "GenerateQrParams",
    "VerifyPaymentParams",
    "QrResult",
    "VerificationResult",
]
__version__ = "1.0.3"