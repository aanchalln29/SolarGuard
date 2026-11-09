"""
SolarGuard — Role-Based Notification Service.

Provides clean, database-backed in-app notification dispatching with:
- Strict recipient isolation per role (Admin, Customer, Technician).
- Automatic de-duplication to prevent repeated notifications on browser refresh or double-submit.
- Zero external webhooks, polling loops, SMS, or background workers.
"""

import datetime
import logging
from typing import Optional, List
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Notification

logger = logging.getLogger(__name__)


def notify_user(
    recipient: User,
    event_type: str,
    title: str,
    message: str,
    target_url: str = '',
    dedup_seconds: int = 60
) -> Optional[Notification]:
    """
    Delivers an in-app notification to a specific user.
    Prevents duplicate notifications for the same event and target within dedup_seconds.
    """
    if not recipient or not recipient.is_active:
        return None

    # De-duplication check: avoid duplicate notifications on browser refresh
    if dedup_seconds > 0:
        cutoff = timezone.now() - datetime.timedelta(seconds=dedup_seconds)
        recent_duplicate = Notification.objects.filter(
            recipient=recipient,
            event_type=event_type,
            target_url=target_url,
            created_at__gte=cutoff
        ).exists()
        if recent_duplicate:
            logger.debug(f"[SolarGuard Notification] Suppressed duplicate for {recipient.username}: {title}")
            return None

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            event_type=event_type,
            title=title[:200],
            message=message,
            target_url=target_url[:255] if target_url else '',
            is_read=False,
        )
        return notification
    except Exception as e:
        logger.error(f"[SolarGuard Notification] Failed to create notification for {recipient.username}: {e}")
        return None


def notify_admins(
    event_type: str,
    title: str,
    message: str,
    target_url: str = '',
    exclude_user: Optional[User] = None
) -> List[Notification]:
    """
    Broadcasts a notification to all active administrators.
    Optionally excludes the user who triggered the event.
    """
    admin_filter = Q(is_superuser=True) | Q(profile__role__iexact='admin')
    admins = User.objects.filter(admin_filter, is_active=True).distinct()

    created_notifications = []
    for admin in admins:
        if exclude_user and admin.id == exclude_user.id:
            continue
        n = notify_user(
            recipient=admin,
            event_type=event_type,
            title=title,
            message=message,
            target_url=target_url
        )
        if n:
            created_notifications.append(n)

    return created_notifications


def get_unread_count(user: User) -> int:
    """Returns total unread notifications count for a user."""
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()


def get_recent_notifications(user: User, limit: int = 7) -> List[Notification]:
    """Returns the most recent notifications for user dropdown and center."""
    if not user.is_authenticated:
        return []
    return list(Notification.objects.filter(recipient=user).select_related('recipient')[:limit])
