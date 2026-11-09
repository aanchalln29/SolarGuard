from .permissions import (
    get_accessible_maintenance_issues, get_user_role,
    is_admin, is_technician, is_customer
)
from .notification_service import get_unread_count, get_recent_notifications

def global_stats(request):
    """
    Context processor to provide global role context and notification badges.
    Strictly isolated per user role:
    - Customer: Open issues on owned installations & own notifications
    - Technician: Open issues assigned to them & technician notifications
    - Admin: All open system issues & administrator notifications
    """
    if not request.user.is_authenticated:
        return {
            'global_open_issues_count': 0,
            'unread_notifications_count': 0,
            'recent_notifications': [],
            'current_user_role': 'anonymous',
            'is_admin_user': False,
            'is_technician_user': False,
            'is_customer_user': False,
        }

    open_count = get_accessible_maintenance_issues(request.user).filter(
        status__in=['Open', 'Assigned', 'In Progress']
    ).count()

    role = get_user_role(request.user)
    unread_notifs = get_unread_count(request.user)
    recent_notifs = get_recent_notifications(request.user, limit=6)

    return {
        'global_open_issues_count': open_count,
        'unread_notifications_count': unread_notifs,
        'recent_notifications': recent_notifs,
        'current_user_role': role,
        'is_admin_user': is_admin(request.user),
        'is_technician_user': is_technician(request.user),
        'is_customer_user': is_customer(request.user),
    }
