"""Main FamPayVerifier class for payment verification and QR generation."""

import re
import asyncio
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO
import base64

import qrcode
from imap_tools import MailBox, AND

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

from .models import (
    FamPayVerifierConfig,
    GenerateQrParams,
    VerifyPaymentParams,
    QrResult,
    VerificationResult,
)


def _generate_qr_base64(upi_uri: str) -> str:
    """Generate QR code as base64 PNG, with fallback to SVG if Pillow not available."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)

    try:
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{qr_base64}"
    except ImportError:
        import qrcode.image.svg
        svg_img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        svg_buffer = BytesIO()
        svg_img.save(svg_buffer)
        svg_base64 = base64.b64encode(svg_buffer.getvalue()).decode("utf-8")
        return f"data:image/svg+xml;base64,{svg_base64}"


class FamPayVerifier:
    """FamPay payment verification and QR code generator."""

    def __init__(self, config: FamPayVerifierConfig):
        """Initialize the verifier with configuration."""
        if not config.gmail or not config.gmail_app_password:
            raise ValueError("Gmail credentials (gmail and app password) are required.")

        self.supabase: Optional[Client] = None
        if config.supabase_url and config.supabase_service_role_key:
            self.supabase = create_client(config.supabase_url, config.supabase_service_role_key)

        self.gmail = config.gmail
        self.gmail_app_password = config.gmail_app_password.replace(" ", "")

    async def generate_qr(self, params: GenerateQrParams) -> QrResult:
        """Generate a UPI payment URI and QR code image in Base64 format."""
        upi_id = params.upi_id
        amount = params.amount
        name = params.name
        user_id = params.user_id

        if not upi_id or not amount or not name:
            if self.supabase:
                await self._log_to_supabase(
                    user_id=user_id,
                    endpoint="py:generateQr",
                    status=400,
                    amount=float(amount) if amount else None,
                )
            raise ValueError("Missing parameters (upiId, amount, and name are required)")

        try:
            upi_uri = f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR"
            qr_data_url = _generate_qr_base64(upi_uri)

            now_ist = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

            if self.supabase:
                await self._log_to_supabase(
                    user_id=user_id,
                    endpoint="py:generateQr",
                    status=200,
                    amount=float(amount),
                )

            return QrResult(
                qr_image=qr_data_url,
                upi_uri=upi_uri,
                upi_id=upi_id,
                amount=str(amount),
                name=name,
                created_at_ist=now_ist,
            )

        except Exception as err:
            if self.supabase:
                await self._log_to_supabase(
                    user_id=user_id,
                    endpoint="py:generateQr",
                    status=500,
                    amount=float(amount) if amount else None,
                )
            raise RuntimeError(f"Failed to generate QR code: {err}")

    async def verify_payment(self, params: VerifyPaymentParams) -> VerificationResult:
        """Connect to Gmail and verify if a payment matches the specified criteria."""
        amount = params.amount
        utr = params.utr
        txnid = params.txnid
        user_id = params.user_id

        if not amount:
            raise ValueError("Amount is required for verification.")

        target_tx = utr or txnid
        filter_col = "utr" if utr else "txn_id"

        # Prevent double verification if UTR/TxnID provided
        if target_tx and self.supabase:
            existing = await self._check_existing_transaction(filter_col, target_tx)
            if existing:
                return VerificationResult(
                    verified=False,
                    message="Transaction already verified",
                    details="This UTR / Txn ID has already been used.",
                )

        expected_amount = float(amount)
        email_clean = self.gmail if "@" in self.gmail else f"{self.gmail}@gmail.com"
        app_password_clean = self.gmail_app_password

        try:
            async with MailBox("imap.gmail.com", 993).login(
                email_clean, app_password_clean, "INBOX"
            ) as mailbox:
                search_val = utr or txnid or str(amount)
                criteria = AND(text=search_val)

                messages = []
                async for msg in mailbox.fetch(criteria, reverse=True, limit=50):
                    messages.append(msg)

                if not messages:
                    await self._log_failure(user_id, 404, utr, txnid, expected_amount)
                    return VerificationResult(
                        verified=False,
                        message="Transaction not found",
                        details="No matching payment found in email inbox",
                    )

                for msg in messages:
                    full_text = f"{msg.subject or ''}\n{msg.text or ''}".lower()

                    # Check if it contains credit keywords
                    is_received = any(
                        kw in full_text
                        for kw in ["received", "credited", "added"]
                    )
                    if not is_received:
                        continue

                    # Date restriction: ignore emails older than 15 mins for dynamic checks
                    if not utr and not txnid and msg.date:
                        email_time = msg.date.timestamp() * 1000
                        fifteen_min_ago = datetime.now().timestamp() * 1000 - (15 * 60 * 1000)
                        if email_time < fifteen_min_ago:
                            continue

                    # Validate amount matching
                    amount_pattern = rf"(?:rs\.?|inr|₹|\s|^){expected_amount}(?:\.00)?(?:\s|$|\.)"
                    has_amount = bool(
                        re.search(amount_pattern, full_text, re.IGNORECASE)
                        or str(expected_amount) in full_text
                    )

                    if not has_amount:
                        continue

                    # Extract sender name
                    sender_name = "UPI User"
                    name_match = re.search(
                        r"(?:from|received from|sender)\s+([a-zA-Z ]{3,30})", full_text
                    )
                    if name_match and name_match.group(1):
                        sender_name = name_match.group(1).strip()
                        if sender_name.lower().endswith(" at"):
                            sender_name = sender_name[:-3].strip()

                    # Extract UTR/TxnID if not supplied
                    extracted_utr = utr
                    extracted_txn_id = txnid

                    if not extracted_utr:
                        utr_match = re.search(
                            r"(?:utr|upi ref no|ref no|reference no)\s*:\s*([0-9]{12})",
                            full_text,
                            re.IGNORECASE,
                        )
                        if utr_match and utr_match.group(1):
                            extracted_utr = utr_match.group(1).strip()

                    if not extracted_txn_id:
                        txn_match = re.search(
                            r"(?:transaction id|txn id)\s*:\s*([a-zA-Z0-9]+)",
                            full_text,
                            re.IGNORECASE,
                        )
                        if txn_match and txn_match.group(1):
                            extracted_txn_id = txn_match.group(1).strip()

                    # Check if extracted UTR/TxnID was already verified
                    check_val = extracted_utr or extracted_txn_id
                    check_col = "utr" if extracted_utr else "txn_id"
                    if check_val and self.supabase:
                        existing = await self._check_existing_transaction(check_col, check_val)
                        if existing:
                            continue  # Skip already verified email

                    payment_time_ist = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if self.supabase:
                        await self._log_to_supabase(
                            user_id=user_id,
                            endpoint="py:verifyPayment",
                            status=200,
                            utr=extracted_utr,
                            txn_id=extracted_txn_id,
                            amount=expected_amount,
                        )

                    return VerificationResult(
                        verified=True,
                        transaction_id=extracted_txn_id or extracted_utr,
                        amount=expected_amount,
                        utr=extracted_utr,
                        sender_name=sender_name,
                        payment_time_ist=payment_time_ist,
                    )

                # If loop ends without matching receipt
                await self._log_failure(user_id, 404, utr, txnid, expected_amount)
                return VerificationResult(
                    verified=False,
                    message="Transaction not found",
                    details="No matching payment found in email inbox",
                )

        except Exception as err:
            is_auth_error = any(
                kw in str(err).lower()
                for kw in ["authentication", "invalid credentials", "auth"]
            )
            err_status = 401 if is_auth_error else 500
            await self._log_failure(user_id, err_status, utr, txnid, expected_amount)

            return VerificationResult(
                verified=False,
                message="Invalid Gmail credentials" if is_auth_error else "Error during check",
                details=str(err),
            )

    async def _check_existing_transaction(self, column: str, value: str) -> bool:
        """Check if transaction already exists in Supabase logs."""
        if not self.supabase:
            return False
        try:
            response = (
                self.supabase.table("api_logs")
                .select("id")
                .eq("status", 200)
                .eq(column, value)
                .limit(1)
                .execute()
            )
            return bool(response.data and len(response.data) > 0)
        except Exception:
            return False

    async def _log_to_supabase(
        self,
        user_id: Optional[str],
        endpoint: str,
        status: int,
        utr: Optional[str] = None,
        txn_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> None:
        """Log API call to Supabase."""
        if not self.supabase:
            return
        try:
            self.supabase.table("api_logs").insert({
                "user_id": user_id,
                "endpoint": endpoint,
                "status": status,
                "utr": utr,
                "txn_id": txn_id,
                "amount": amount,
            }).execute()
        except Exception:
            pass  # Fail silently for logging

    async def _log_failure(
        self,
        user_id: Optional[str],
        status: int,
        utr: Optional[str],
        txnid: Optional[str],
        amount: float,
    ) -> None:
        """Log verification failure to Supabase."""
        await self._log_to_supabase(
            user_id=user_id,
            endpoint="py:verifyPayment",
            status=status,
            utr=utr,
            txn_id=txnid,
            amount=amount,
        )