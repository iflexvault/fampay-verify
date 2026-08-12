"""Example usage of FamPayVerifier (Python)."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fampay_verify import FamPayVerifier, GenerateQrParams, VerifyPaymentParams


def main():
    # Database-free config (works with any database or no database)
    config = {
        "gmail": os.getenv("GMAIL", "your_email@gmail.com"),
        "gmail_app_password": os.getenv("GMAIL_APP_PASSWORD", "your_app_password"),
        # Optional: Add Supabase for auto-logging and replay protection
        # "supabase_url": os.getenv("SUPABASE_URL"),
        # "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    }

    print("Initializing FamPayVerifier...")
    verifier = FamPayVerifier(config)

    try:
        # Test 1: Generate QR
        print("\n--- Test 1: Generating QR Code ---")
        qr = verifier.generate_qr(GenerateQrParams(
            upi_id="your_upi_id@fam",
            amount="25.01",
            name="Your Name"
        ))
        print(f"UPI URI: {qr.upi_uri}")
        print(f"QR Code generated successfully (Base64 length): {len(qr.qr_image)}")

        # Test 2: Verify Payment (Dynamic check)
        print("\n--- Test 2: Verifying Payment (Dynamic Amount) ---")
        print("Searching for payment of ₹25.01 in the last 15 minutes...")
        result = verifier.verify_payment(VerifyPaymentParams(
            amount="25.01"
        ))
        print(f"Result: {result}")

        if result.verified:
            print(f"\nSuccess! Received ₹{result.amount} from {result.sender_name}")
            print(f"UTR Number: {result.utr}")
            print(f"Transaction ID: {result.transaction_id}")
            print(f"Payment Time (IST): {result.payment_time_ist}")
        else:
            print(f"\nFailed: {result.message}")
            print(f"Details: {result.details}")

    except Exception as error:
        print(f"Test failed with error: {error}")


if __name__ == "__main__":
    main()