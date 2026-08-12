"""Type definitions for FamPayVerifier."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FamPayVerifierConfig:
    """Configuration for FamPayVerifier."""
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    gmail: str = ""
    gmail_app_password: str = ""


@dataclass
class GenerateQrParams:
    """Parameters for generating a UPI QR code."""
    upi_id: str
    amount: str | float | int
    name: str
    user_id: Optional[str] = None


@dataclass
class VerifyPaymentParams:
    """Parameters for verifying a payment."""
    amount: str | float | int
    utr: Optional[str] = None
    txnid: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class QrResult:
    """Result of QR code generation."""
    qr_image: str
    upi_uri: str
    upi_id: str
    amount: str
    name: str
    created_at_ist: str


@dataclass
class VerificationResult:
    """Result of payment verification."""
    verified: bool
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    utr: Optional[str] = None
    sender_name: Optional[str] = None
    payment_time_ist: Optional[str] = None
    message: Optional[str] = None
    details: Optional[str] = None