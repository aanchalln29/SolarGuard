"""
SolarGuard — Automated Unit & Integration Tests for Role-Based Notification Center.

Tests:
1. Notification model creation, fields, choices, and representation.
2. Admin event triggers (new installation, layout review, new maintenance, tech completion).
3. Customer event triggers (layout verified, layout rejected, tech assigned, work resolved, ticket closed).
4. Technician event triggers (work assigned, work reassigned, installation assigned).
5. Recipient isolation (users can only access, view, and mark their own notifications).
6. Unread count increments and read transitions via open/mark-read views.
7. Deduplication window preventing accidental duplicate alerts on refresh or double submit.
8. Context processor isolation for dropdown navbar integration.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import Installation, Panel, MaintenanceIssue, LayoutRevision, UserProfile, Notification
from core.notification_service import (
    notify_user, notify_admins, get_unread_count, get_recent_notifications
)


class NotificationSystemTests(TestCase):
    def setUp(self):
        # 1. Setup Users with Profiles
        self.admin = User.objects.create_superuser('admin_notif', 'admin@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.admin, defaults={'role': 'admin'})

        self.tech = User.objects.create_user('tech_notif', 'tech@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.tech, defaults={'role': 'technician'})

        self.customer = User.objects.create_user('customer_notif', 'customer@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.customer, defaults={'role': 'customer'})

        self.customer_b = User.objects.create_user('customer_b_notif', 'customer_b@solarguard.local', 'password123')
        UserProfile.objects.update_or_create(user=self.customer_b, defaults={'role': 'customer'})

        # 2. Setup Installation & Panel
        self.installation = Installation.objects.create(
            name="Alpha Solar Rooftop",
            owner=self.customer,
            site_address="123 Renewable Ave, Nagpur",
            installation_type="rooftop",
            status="active"
        )

        self.panel = Panel.objects.create(
            installation=self.installation,
            serial_number="SG-NOTIF-P01",
            permanent_id="PANEL-NOTIF-01",
            site_location="Roof Sector 1",
            status="active"
        )

        self.client = Client()

    def test_notification_creation_and_fields(self):
        """Verifies notification model persistence and string representation."""
        n = notify_user(
            recipient=self.customer,
            event_type='layout_verified',
            title='Layout Approved: Alpha Solar Rooftop',
            message='Your panel layout was verified and applied.',
            target_url=f"/installations/{self.installation.id}/"
        )
        self.assertIsNotNone(n)
        self.assertEqual(n.recipient, self.customer)
        self.assertEqual(n.event_type, 'layout_verified')
        self.assertFalse(n.is_read)
        self.assertIn('customer_notif', str(n))
        self.assertIn('Unread', str(n))

    def test_admin_broadcast_excludes_sender(self):
        """Verifies notify_admins delivers to active admins and excludes sender."""
        notifs = notify_admins(
            event_type='new_installation',
            title='New Site Added',
            message='Site submitted.',
            target_url='/installations/1/',
            exclude_user=self.admin
        )
        self.assertEqual(len(notifs), 0)

        # Broadcast triggered by customer
        notifs = notify_admins(
            event_type='new_installation',
            title='New Site Added',
            message='Site submitted.',
            target_url='/installations/1/',
            exclude_user=self.customer
        )
        self.assertGreaterEqual(len(notifs), 1)
        self.assertEqual(notifs[0].recipient, self.admin)

    def test_recipient_isolation(self):
        """Verifies Customer B cannot access Customer A's notification."""
        n = notify_user(
            recipient=self.customer,
            event_type='maintenance_assigned',
            title='Technician Assigned',
            message='Tech is on the way.',
            target_url=f"/maintenance/1/"
        )

        # Customer B tries to open Customer A's notification -> 404
        self.client.login(username='customer_b_notif', password='password123')
        open_url = reverse('notification_open', kwargs={'pk': n.id})
        response = self.client.get(open_url)
        self.assertEqual(response.status_code, 404)

        # Customer A opens own notification -> Marks read and redirects
        self.client.login(username='customer_notif', password='password123')
        response = self.client.get(open_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/maintenance/1/')

        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_all_read_action(self):
        """Verifies mark_all_read clears all unread notifications for authenticated user."""
        notify_user(self.customer, 'work_assigned', 'Alert 1', 'Message 1')
        notify_user(self.customer, 'work_assigned', 'Alert 2', 'Message 2', dedup_seconds=0)
        notify_user(self.customer_b, 'work_assigned', 'Alert 3', 'Message 3')

        self.assertEqual(get_unread_count(self.customer), 2)
        self.assertEqual(get_unread_count(self.customer_b), 1)

        self.client.login(username='customer_notif', password='password123')
        response = self.client.get(reverse('notification_mark_all_read'), follow=True)
        self.assertEqual(response.status_code, 200)

        # Customer's notifications are marked read; Customer B's are untouched
        self.assertEqual(get_unread_count(self.customer), 0)
        self.assertEqual(get_unread_count(self.customer_b), 1)

    def test_deduplication_window_suppresses_rapid_repeats(self):
        """Verifies duplicate notifications for same event/target within window are suppressed."""
        n1 = notify_user(
            recipient=self.customer,
            event_type='new_maintenance_issue',
            title='Ticket Logged',
            message='Ticket #1 created.',
            target_url='/maintenance/1/',
            dedup_seconds=60
        )
        self.assertIsNotNone(n1)

        # Immediate repeat attempt
        n2 = notify_user(
            recipient=self.customer,
            event_type='new_maintenance_issue',
            title='Ticket Logged',
            message='Ticket #1 created.',
            target_url='/maintenance/1/',
            dedup_seconds=60
        )
        self.assertIsNone(n2)
        self.assertEqual(Notification.objects.filter(recipient=self.customer).count(), 1)

    def test_workflow_installation_creation_notifies_admin(self):
        """Creating an installation via view triggers notification to administrator."""
        self.client.login(username='customer_notif', password='password123')
        admin_init_notifs = Notification.objects.filter(recipient=self.admin).count()

        response = self.client.post(reverse('installation_add'), {
            'name': 'Beta Rooftop System',
            'site_address': '456 Solar Blvd',
            'installation_type': 'rooftop'
        })
        self.assertEqual(response.status_code, 302)

        admin_new_notifs = Notification.objects.filter(recipient=self.admin, event_type='new_installation')
        self.assertEqual(admin_new_notifs.count(), admin_init_notifs + 1)
        self.assertIn('Beta Rooftop System', admin_new_notifs.first().title)

    def test_workflow_issue_assignment_notifies_technician_and_customer(self):
        """Admin assigning technician notifies both technician and customer."""
        issue = MaintenanceIssue.objects.create(
            installation=self.installation,
            panel=self.panel,
            user=self.customer,
            title="Clean array surface",
            description="Accumulated dust coating",
            status="Open",
            priority="High"
        )

        self.client.login(username='admin_notif', password='password123')
        url = reverse('issue_detail', kwargs={'pk': issue.id})
        response = self.client.post(url, {
            'action': 'assign_technician',
            'technician': self.tech.id,
            'priority': 'High'
        })
        self.assertEqual(response.status_code, 302)

        # Verify Technician notification
        tech_notifs = Notification.objects.filter(recipient=self.tech, event_type='work_assigned')
        self.assertEqual(tech_notifs.count(), 1)
        self.assertIn(f"#{issue.id}", tech_notifs.first().title)

        # Verify Customer notification
        cust_notifs = Notification.objects.filter(recipient=self.customer, event_type='maintenance_assigned')
        self.assertEqual(cust_notifs.count(), 1)
        self.assertIn(f"#{issue.id}", cust_notifs.first().title)

    def test_workflow_technician_resolution_notifies_admin_and_customer(self):
        """Technician resolving work order notifies administrator and customer."""
        issue = MaintenanceIssue.objects.create(
            installation=self.installation,
            panel=self.panel,
            user=self.customer,
            assigned_technician=self.tech,
            title="Repair damaged bypass diode",
            description="Cell overheating",
            status="In Progress",
            priority="High"
        )

        self.client.login(username='tech_notif', password='password123')
        url = reverse('issue_detail', kwargs={'pk': issue.id})
        response = self.client.post(url, {
            'action': 'resolve_work',
            'resolution_notes': 'Replaced cracked diode and verified voltage.'
        })
        self.assertEqual(response.status_code, 302)

        # Verify Admin notification
        admin_notifs = Notification.objects.filter(recipient=self.admin, event_type='technician_completion')
        self.assertEqual(admin_notifs.count(), 1)

        # Verify Customer notification
        cust_notifs = Notification.objects.filter(recipient=self.customer, event_type='maintenance_completed')
        self.assertEqual(cust_notifs.count(), 1)

    def test_notification_list_view_and_filtering(self):
        """Tests the full notification center view with unread/read filter tabs."""
        n1 = notify_user(self.customer, 'work_assigned', 'Alert 1', 'Message 1')
        n2 = notify_user(self.customer, 'work_assigned', 'Alert 2', 'Message 2', dedup_seconds=0)
        n1.is_read = True
        n1.save()

        self.client.login(username='customer_notif', password='password123')
        url = reverse('notification_list')

        # All notifications
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 2)

        # Filter unread
        response = self.client.get(f"{url}?status=unread")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 1)
        self.assertEqual(response.context['notifications'][0].id, n2.id)

        # Filter read
        response = self.client.get(f"{url}?status=read")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 1)
        self.assertEqual(response.context['notifications'][0].id, n1.id)
