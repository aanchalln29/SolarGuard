"""
SolarGuard — Automated Unit & Integration Tests for Razorpay Test Mode Payments.

Verifies:
1. Razorpay configuration detection (configured vs unconfigured).
2. Sandbox order creation and INR-to-paise conversion (1 INR = 100 paise).
3. Server-side HMAC-SHA256 signature verification (success & rejection).
4. Idempotent callback handling (prevention of duplicate transactions).
5. Role-based access control (RBAC): unauthorized customers cannot pay for others' issues.
6. Admin-only service fee management.
7. Branded PDF receipt generation and access control.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import Installation, Panel, MaintenanceIssue, PaymentTransaction, UserProfile
from core.payment_service import (
    is_razorpay_configured, create_order_for_issue, verify_razorpay_payment_signature
)
from core.pdf_receipt import generate_payment_receipt_pdf


class RazorpayPaymentSystemTests(TestCase):
    def setUp(self):
        # 1. Setup Users with Profiles (UserProfile is created by post_save signal)
        self.admin_user = User.objects.create_superuser('admin_tester', 'admin@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.admin_user, defaults={'role': 'admin'})

        self.customer_a = User.objects.create_user('customer_alice', 'alice@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.customer_a, defaults={'role': 'customer'})

        self.customer_b = User.objects.create_user('customer_bob', 'bob@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.customer_b, defaults={'role': 'customer'})

        # 2. Setup Installation & Panel for Customer A
        self.installation_a = Installation.objects.create(
            name="Alice Solar Array",
            owner=self.customer_a,
            site_address="100 Solar Way, Nagpur",
            installation_type="residential_rooftop",
            status="active"
        )
        self.panel_a = Panel.objects.create(
            installation=self.installation_a,
            serial_number="SG-TEST-P001",
            permanent_id="PANEL-A-01",
            site_location="Roof Sector 1",
            status="active"
        )

        # 3. Setup Maintenance Issue for Panel A
        self.issue_a = MaintenanceIssue.objects.create(
            installation=self.installation_a,
            panel=self.panel_a,
            user=self.customer_a,
            title="Clean heavily soiled array",
            description="Thick dust coating detected across modules.",
            status="Open",
            priority="Medium",
            service_fee=Decimal('499.00'),
            payment_status="pending"
        )

        self.client = Client()

    def test_configuration_detection(self):
        """Tests that settings cleanly report configured state."""
        with self.settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET=''):
            self.assertFalse(is_razorpay_configured())

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            self.assertTrue(is_razorpay_configured())

    @patch('core.payment_service.get_razorpay_client')
    def test_order_creation_converts_paise_correctly(self, mock_get_client):
        """Verifies INR amount is multiplied by 100 to get paise and order is saved."""
        mock_client = MagicMock()
        mock_client.order.create.return_value = {
            'id': 'order_test_99999',
            'amount': 49900,
            'currency': 'INR',
            'status': 'created'
        }
        mock_get_client.return_value = mock_client

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            order_data, tx, err = create_order_for_issue(self.issue_a, self.customer_a)

            self.assertIsNone(err)
            self.assertIsNotNone(order_data)
            self.assertEqual(order_data['id'], 'order_test_99999')
            self.assertEqual(order_data['amount'], 49900)  # ₹499.00 * 100 = 49900 paise

            self.assertEqual(tx.razorpay_order_id, 'order_test_99999')
            self.assertEqual(tx.amount, Decimal('499.00'))
            self.assertEqual(tx.amount_paise, 49900)
            self.assertEqual(tx.status, 'created')

            # Verify issue status
            self.issue_a.refresh_from_db()
            self.assertEqual(self.issue_a.payment_status, 'pending')

    @patch('core.payment_service.get_razorpay_client')
    def test_signature_verification_success(self, mock_get_client):
        """Verifies signature verification + server-side payment entity fetch ('captured') marks issue paid and generates receipt."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client.payment.fetch.return_value = {
            'id': 'pay_test_abcde',
            'order_id': 'order_test_12345',
            'amount': 49900,
            'currency': 'INR',
            'status': 'captured'
        }
        mock_get_client.return_value = mock_client

        # Pre-create transaction
        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_test_12345',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, err = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_test_12345',
                razorpay_payment_id='pay_test_abcde',
                razorpay_signature='mock_valid_signature_hash'
            )

            self.assertTrue(is_valid)
            self.assertIsNone(err)
            self.assertEqual(updated_tx.status, 'success')
            self.assertEqual(updated_tx.razorpay_payment_id, 'pay_test_abcde')
            self.assertTrue(updated_tx.receipt_number.startswith('SG-RCP-'))
            self.assertIsNotNone(updated_tx.verified_at)

            self.issue_a.refresh_from_db()
            self.assertEqual(self.issue_a.payment_status, 'paid')

            # Check maintenance log was recorded
            latest_log = self.issue_a.action_logs.first()
            self.assertEqual(latest_log.action_type, 'payment')
            self.assertIn('₹499.00', latest_log.notes)

    @patch('core.payment_service.get_razorpay_client')
    def test_authorized_uncaptured_payment_retains_pending_state(self, mock_get_client):
        """Verifies authorized payments that are not yet captured retain pending status without receipt generation."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client.payment.fetch.return_value = {
            'id': 'pay_auth_only_123',
            'order_id': 'order_auth_test',
            'amount': 49900,
            'currency': 'INR',
            'status': 'authorized'  # Authorized, NOT captured
        }
        mock_get_client.return_value = mock_client

        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_auth_test',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, msg = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_auth_test',
                razorpay_payment_id='pay_auth_only_123',
                razorpay_signature='valid_sig'
            )

            self.assertFalse(is_valid)
            self.assertIn("authorized", msg.lower())
            self.assertEqual(updated_tx.status, 'pending')
            self.assertIsNone(updated_tx.receipt_number)

            self.issue_a.refresh_from_db()
            self.assertEqual(self.issue_a.payment_status, 'pending')
            self.assertNotEqual(self.issue_a.payment_status, 'paid')

    @patch('core.payment_service.get_razorpay_client')
    def test_amount_mismatch_rejects_settlement(self, mock_get_client):
        """Verifies amount mismatch against gateway triggers failure and prevents marking paid."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client.payment.fetch.return_value = {
            'id': 'pay_tamper_123',
            'order_id': 'order_tamper_test',
            'amount': 100,  # Only 100 paise instead of 49900 paise
            'currency': 'INR',
            'status': 'captured'
        }
        mock_get_client.return_value = mock_client

        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_tamper_test',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, err = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_tamper_test',
                razorpay_payment_id='pay_tamper_123',
                razorpay_signature='valid_sig'
            )

            self.assertFalse(is_valid)
            self.assertIn("Amount mismatch", err)
            self.assertEqual(updated_tx.status, 'failed')

            self.issue_a.refresh_from_db()
            self.assertEqual(self.issue_a.payment_status, 'failed')

    @patch('core.payment_service.get_razorpay_client')
    def test_order_id_mismatch_rejects_settlement(self, mock_get_client):
        """Verifies order ID mismatch against gateway triggers failure."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client.payment.fetch.return_value = {
            'id': 'pay_wrong_order_123',
            'order_id': 'order_different_555',
            'amount': 49900,
            'currency': 'INR',
            'status': 'captured'
        }
        mock_get_client.return_value = mock_client

        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_expected_888',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, err = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_expected_888',
                razorpay_payment_id='pay_wrong_order_123',
                razorpay_signature='valid_sig'
            )

            self.assertFalse(is_valid)
            self.assertIn("Order ID mismatch", err)
            self.assertEqual(updated_tx.status, 'failed')

    @patch('core.payment_service.get_razorpay_client')
    def test_currency_mismatch_rejects_settlement(self, mock_get_client):
        """Verifies non-INR currency against gateway triggers failure."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client.payment.fetch.return_value = {
            'id': 'pay_usd_123',
            'order_id': 'order_currency_test',
            'amount': 49900,
            'currency': 'USD',
            'status': 'captured'
        }
        mock_get_client.return_value = mock_client

        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_currency_test',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, err = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_currency_test',
                razorpay_payment_id='pay_usd_123',
                razorpay_signature='valid_sig'
            )

            self.assertFalse(is_valid)
            self.assertIn("Currency mismatch", err)
            self.assertEqual(updated_tx.status, 'failed')

    @patch('core.payment_service.get_razorpay_client')
    def test_signature_verification_failure_rejects_settlement(self, mock_get_client):
        """Verifies forged or mismatched signature fails and prevents marking paid."""
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception("Signature verification failed")
        mock_get_client.return_value = mock_client

        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_forged_999',
            status='created'
        )

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, err = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_forged_999',
                razorpay_payment_id='pay_forged_xxx',
                razorpay_signature='invalid_signature'
            )

            self.assertFalse(is_valid)
            self.assertIn("failed", err)
            self.assertEqual(updated_tx.status, 'failed')

            self.issue_a.refresh_from_db()
            self.assertEqual(self.issue_a.payment_status, 'failed')

    @patch('core.payment_service.get_razorpay_client')
    def test_idempotent_duplicate_callback_handling(self, mock_get_client):
        """Verifies duplicate verification callbacks do not duplicate settlement."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Pre-settled transaction
        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_already_paid',
            razorpay_payment_id='pay_already_paid',
            status='success',
            receipt_number='SG-RCP-20261028-0001',
            verified_at=timezone.now()
        )
        self.issue_a.payment_status = 'paid'
        self.issue_a.save()

        initial_tx_count = PaymentTransaction.objects.count()

        with self.settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='mock_secret'):
            updated_tx, is_valid, msg = verify_razorpay_payment_signature(
                issue=self.issue_a,
                razorpay_order_id='order_already_paid',
                razorpay_payment_id='pay_already_paid',
                razorpay_signature='some_sig'
            )
            self.assertTrue(is_valid)
            self.assertIn("already been verified", msg)
            self.assertEqual(updated_tx.receipt_number, 'SG-RCP-20261028-0001')
            self.assertEqual(PaymentTransaction.objects.count(), initial_tx_count)

            # Ensure client verify wasn't even called
            mock_client.utility.verify_payment_signature.assert_not_called()

    def test_customer_isolation_unauthorized_payment_denied(self):
        """Customer B cannot view checkout or pay for Customer A's work order."""
        self.client.login(username='customer_bob', password='password123')
        url = reverse('payment_checkout', kwargs={'issue_id': self.issue_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_set_service_charge(self):
        """Only administrators can set the maintenance charge."""
        self.client.login(username='admin_tester', password='password123')
        url = reverse('issue_detail', kwargs={'pk': self.issue_a.id})
        response = self.client.post(url, {
            'action': 'set_service_fee',
            'service_fee': '750.00'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.issue_a.refresh_from_db()
        self.assertEqual(self.issue_a.service_fee, Decimal('750.00'))

        # Customer attempts to change service fee -> Forbidden
        self.client.login(username='customer_alice', password='password123')
        response = self.client.post(url, {
            'action': 'set_service_fee',
            'service_fee': '10.00'
        })
        self.assertEqual(response.status_code, 403)

    def test_pdf_receipt_generation_and_access(self):
        """Verifies ReportLab generates valid PDF and enforces access permissions."""
        tx = PaymentTransaction.objects.create(
            issue=self.issue_a,
            user=self.customer_a,
            amount=Decimal('499.00'),
            amount_paise=49900,
            currency='INR',
            razorpay_order_id='order_receipt_test',
            razorpay_payment_id='pay_receipt_test',
            status='success',
            receipt_number='SG-RCP-20261028-9999',
            verified_at=timezone.now()
        )

        pdf_bytes = generate_payment_receipt_pdf(tx)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertGreater(len(pdf_bytes), 1000)

        # Authorized customer downloads receipt
        self.client.login(username='customer_alice', password='password123')
        receipt_url = reverse('payment_receipt_download', kwargs={'payment_id': tx.id})
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # Unauthorized customer cannot download
        self.client.login(username='customer_bob', password='password123')
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 403)
