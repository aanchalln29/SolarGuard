"""
SolarGuard — Portable Razorpay Test Mode Payment Service.

Provides secure, portable Razorpay Sandbox / Test Mode operations:
- Order creation with proper INR paise conversion (1 INR = 100 paise)
- Client-side checkout configuration (public Key ID only; Secret Key strictly backend)
- Server-side HMAC-SHA256 signature verification
- Duplicate transaction prevention & idempotent callbacks
- Error, cancellation, and failure handling
- Audit trail logging via MaintenanceLog & PaymentTransaction
- Zero external webhook dependency for local demonstration portability
"""

import time
import datetime
import logging
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import MaintenanceIssue, MaintenanceLog, PaymentTransaction

logger = logging.getLogger(__name__)


def is_razorpay_configured() -> bool:
    """Returns True if both Razorpay Key ID and Key Secret are present in settings/env."""
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '').strip()
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '').strip()
    return bool(key_id and key_secret)


def get_razorpay_public_key() -> str:
    """Returns public key ID safe for template rendering. Never returns secret key."""
    return getattr(settings, 'RAZORPAY_KEY_ID', '').strip()


def get_razorpay_client():
    """
    Initializes and returns Razorpay Client instance using configured credentials.
    Returns None if not configured.
    """
    if not is_razorpay_configured():
        return None
    try:
        import razorpay
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    except Exception as e:
        logger.error(f"Failed to initialize Razorpay Client: {e}")
        return None


def create_order_for_issue(issue: MaintenanceIssue, user) -> Tuple[Optional[Dict[str, Any]], Optional[PaymentTransaction], Optional[str]]:
    """
    Creates a real Razorpay Sandbox Order for the given maintenance issue service fee.
    Converts amount to integer paise (1 INR = 100 paise).
    Records an initial PaymentTransaction record with status='created'.
    
    Returns: (order_data_dict, payment_transaction_instance, error_message)
    """
    if not is_razorpay_configured():
        return None, None, "Razorpay Test Mode is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env."

    if not issue.service_fee or issue.service_fee <= Decimal('0.00'):
        return None, None, "This maintenance work order has no billable service fee."

    client = get_razorpay_client()
    if not client:
        return None, None, "Razorpay client initialization failed."

    # Convert INR to paise (e.g. ₹499.00 -> 49900 paise)
    amount_paise = int(round(issue.service_fee * 100))
    receipt_tag = f"sg_wo_{issue.id}_{int(time.time())}"[:40]

    order_payload = {
        'amount': amount_paise,
        'currency': getattr(settings, 'RAZORPAY_CURRENCY', 'INR'),
        'receipt': receipt_tag,
        'notes': {
            'issue_id': str(issue.id),
            'panel_serial': str(issue.panel.serial_number),
            'user': user.username if user else 'guest',
            'environment': 'Test Mode (Sandbox)',
        }
    }

    try:
        order = client.order.create(data=order_payload)
        
        with transaction.atomic():
            tx = PaymentTransaction.objects.create(
                issue=issue,
                user=user,
                amount=issue.service_fee,
                amount_paise=amount_paise,
                currency=order_payload['currency'],
                razorpay_order_id=order['id'],
                status='created',
                is_sandbox=True,
                receipt_number=None,
            )
            issue.payment_status = 'pending'
            issue.save(update_fields=['payment_status', 'updated_at'])

        return order, tx, None

    except Exception as e:
        error_msg = f"Razorpay order creation failed: {e}"
        logger.error(error_msg)
        return None, None, error_msg


def verify_razorpay_payment_signature(
    issue: MaintenanceIssue,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> Tuple[Optional[PaymentTransaction], bool, Optional[str]]:
    """
    Cryptographically verifies the Razorpay payment signature server-side AND
    independently fetches the payment entity from the Razorpay API to validate:
    1. Captured status ('captured')
    2. Expected amount in paise (matching tx.amount_paise)
    3. Currency (matching INR)
    4. Matching Order ID (matching razorpay_order_id & tx.razorpay_order_id)
    
    If the payment is 'authorized' but not captured, it retains a 'pending' state
    and does NOT mark the issue paid or issue a receipt.
    
    Enforces idempotency: duplicate callbacks cannot generate duplicate transactions or receipts.
    
    Returns: (payment_transaction, is_verified_bool, error_or_status_message)
    """
    if not is_razorpay_configured():
        return None, False, "Payment verification unavailable: Razorpay Test Mode is not configured."

    tx = PaymentTransaction.objects.filter(
        razorpay_order_id=razorpay_order_id,
        issue=issue
    ).first()

    if not tx:
        return None, False, f"Payment transaction with Order ID '{razorpay_order_id}' not found for work order #{issue.id}."

    # Idempotency check: if this transaction was already successfully verified, return cleanly without duplicating receipt or log
    if tx.status == 'success':
        return tx, True, "Payment has already been verified and settled."

    client = get_razorpay_client()
    if not client:
        return tx, False, "Razorpay client unavailable for signature verification."

    # Step 1: Cryptographic HMAC-SHA256 signature verification
    verification_data = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature,
    }

    try:
        # Raises SignatureVerificationError if signature does not match HMAC-SHA256
        client.utility.verify_payment_signature(verification_data)
    except Exception as e:
        error_str = str(e)
        logger.warning(f"Razorpay signature verification rejected for order {razorpay_order_id}: {error_str}")
        with transaction.atomic():
            tx.status = 'failed'
            tx.error_code = 'SIGNATURE_VERIFICATION_FAILED'
            tx.error_description = error_str
            tx.save(update_fields=['status', 'error_code', 'error_description'])

            issue.payment_status = 'failed'
            issue.save(update_fields=['payment_status', 'updated_at'])

        return tx, False, f"Payment signature verification failed: {error_str}"

    # Step 2: Independently fetch payment details server-side from Razorpay API
    try:
        payment_entity = client.payment.fetch(razorpay_payment_id)
    except Exception as e:
        error_str = f"Failed to fetch payment details from Razorpay: {e}"
        logger.warning(error_str)
        with transaction.atomic():
            tx.status = 'pending'
            tx.error_code = 'GATEWAY_FETCH_FAILED'
            tx.error_description = error_str
            tx.save(update_fields=['status', 'error_code', 'error_description'])
        return tx, False, error_str

    if not isinstance(payment_entity, dict):
        payment_dict = getattr(payment_entity, '__dict__', {}) if not hasattr(payment_entity, 'get') else payment_entity
    else:
        payment_dict = payment_entity

    entity_order_id = payment_dict.get('order_id')
    entity_amount = payment_dict.get('amount')
    entity_currency = (payment_dict.get('currency') or '').upper()
    entity_status = (payment_dict.get('status') or '').lower()

    # Step 3: Validate matching Order ID
    if entity_order_id != razorpay_order_id:
        mismatch_err = f"Order ID mismatch: Gateway order '{entity_order_id}' does not match expected '{razorpay_order_id}'."
        logger.warning(mismatch_err)
        with transaction.atomic():
            tx.status = 'failed'
            tx.error_code = 'ORDER_ID_MISMATCH'
            tx.error_description = mismatch_err
            tx.save(update_fields=['status', 'error_code', 'error_description'])

            issue.payment_status = 'failed'
            issue.save(update_fields=['payment_status', 'updated_at'])
        return tx, False, mismatch_err

    # Step 4: Validate expected amount in paise
    try:
        entity_amount_int = int(entity_amount)
    except (TypeError, ValueError):
        entity_amount_int = -1

    if entity_amount_int != int(tx.amount_paise):
        amount_err = f"Amount mismatch: Gateway amount ({entity_amount_int} paise) does not match expected ({tx.amount_paise} paise)."
        logger.warning(amount_err)
        with transaction.atomic():
            tx.status = 'failed'
            tx.error_code = 'AMOUNT_MISMATCH'
            tx.error_description = amount_err
            tx.save(update_fields=['status', 'error_code', 'error_description'])

            issue.payment_status = 'failed'
            issue.save(update_fields=['payment_status', 'updated_at'])
        return tx, False, amount_err

    # Step 5: Validate INR currency
    expected_currency = (getattr(settings, 'RAZORPAY_CURRENCY', 'INR') or 'INR').upper()
    if entity_currency != expected_currency:
        curr_err = f"Currency mismatch: Gateway currency '{entity_currency}' does not match expected '{expected_currency}'."
        logger.warning(curr_err)
        with transaction.atomic():
            tx.status = 'failed'
            tx.error_code = 'CURRENCY_MISMATCH'
            tx.error_description = curr_err
            tx.save(update_fields=['status', 'error_code', 'error_description'])

            issue.payment_status = 'failed'
            issue.save(update_fields=['payment_status', 'updated_at'])
        return tx, False, curr_err

    # Step 6: Validate captured status
    if entity_status == 'captured':
        with transaction.atomic():
            # Generate branded human-readable receipt number
            receipt_code = f"SG-RCP-{datetime.date.today().strftime('%Y%m%d')}-{tx.id:04d}"

            tx.razorpay_payment_id = razorpay_payment_id
            tx.razorpay_signature = razorpay_signature
            tx.status = 'success'
            tx.receipt_number = receipt_code
            tx.verified_at = timezone.now()
            tx.error_code = ''
            tx.error_description = ''
            tx.save()

            issue.payment_status = 'paid'
            issue.save(update_fields=['payment_status', 'updated_at'])

            MaintenanceLog.objects.create(
                panel=issue.panel,
                issue=issue,
                user=tx.user,
                action_type='payment',
                notes=(
                    f"[Razorpay Sandbox Test Mode] Service charge of ₹{tx.amount:.2f} verified & captured. "
                    f"Payment ID: {razorpay_payment_id} | Order ID: {razorpay_order_id} | "
                    f"Receipt #{receipt_code}."
                ),
                previous_status=issue.status,
                new_status=issue.status,
                performed_at=datetime.date.today(),
            )

        return tx, True, None

    elif entity_status == 'authorized':
        # Retain pending state if authorized but not captured
        pending_msg = "Payment is authorized by the gateway but not yet captured. Retaining pending status."
        logger.info(f"Payment {razorpay_payment_id} for order {razorpay_order_id} is authorized but uncaptured.")
        with transaction.atomic():
            tx.razorpay_payment_id = razorpay_payment_id
            tx.razorpay_signature = razorpay_signature
            tx.status = 'pending'
            tx.error_code = 'PAYMENT_AUTHORIZED_NOT_CAPTURED'
            tx.error_description = 'Payment authorized by gateway; awaiting capture settlement.'
            tx.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'status', 'error_code', 'error_description'])

            issue.payment_status = 'pending'
            issue.save(update_fields=['payment_status', 'updated_at'])

        return tx, False, pending_msg

    else:
        fail_msg = f"Payment status at gateway is '{entity_status}' instead of 'captured'."
        logger.warning(f"Payment {razorpay_payment_id} failed: {fail_msg}")
        with transaction.atomic():
            tx.razorpay_payment_id = razorpay_payment_id
            tx.razorpay_signature = razorpay_signature
            tx.status = 'failed'
            tx.error_code = f"GATEWAY_STATUS_{entity_status.upper()}"
            tx.error_description = fail_msg
            tx.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'status', 'error_code', 'error_description'])

            issue.payment_status = 'failed'
            issue.save(update_fields=['payment_status', 'updated_at'])

        return tx, False, fail_msg


def record_payment_cancellation(issue: MaintenanceIssue, razorpay_order_id: str, error_code: str = '', description: str = '') -> Optional[PaymentTransaction]:
    """Records payment cancellation or client-side dismissal without corrupting work order state."""
    tx = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id, issue=issue).first()
    if tx and tx.status != 'success':
        tx.status = 'cancelled'
        tx.error_code = error_code or 'PAYMENT_CANCELLED'
        tx.error_description = description or 'Payment modal was dismissed or cancelled by the user.'
        tx.save(update_fields=['status', 'error_code', 'error_description'])
        if issue.payment_status != 'paid':
            issue.payment_status = 'unbilled' if issue.service_fee == Decimal('0.00') else 'pending'
            issue.save(update_fields=['payment_status', 'updated_at'])
    return tx
