from django.contrib import admin
from .models import UserProfile, Installation, LayoutRevision, Panel, Inspection, MaintenanceIssue, MaintenanceLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'organization', 'phone_number', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email', 'organization')


class LayoutRevisionInline(admin.TabularInline):
    model = LayoutRevision
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


class PanelInline(admin.TabularInline):
    model = Panel
    extra = 0
    fields = ('permanent_id', 'serial_number', 'grid_row', 'grid_col', 'status')
    readonly_fields = ('permanent_id', 'serial_number')


@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'installation_type', 'assigned_technician', 'status', 'install_date', 'created_at')
    list_filter = ('installation_type', 'status', 'created_at')
    search_fields = ('name', 'site_address', 'owner__username', 'assigned_technician__username')
    inlines = [LayoutRevisionInline, PanelInline]


@admin.register(LayoutRevision)
class LayoutRevisionAdmin(admin.ModelAdmin):
    list_display = ('installation', 'version_number', 'status', 'grid_rows', 'grid_cols', 'submitted_by', 'reviewed_by', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'submitted_at', 'reviewed_at')
    search_fields = ('installation__name', 'review_notes')


@admin.register(Panel)
class PanelAdmin(admin.ModelAdmin):
    list_display = ('permanent_id', 'serial_number', 'installation', 'grid_row', 'grid_col', 'status', 'install_date', 'last_cleaned_date')
    search_fields = ('permanent_id', 'serial_number', 'site_location', 'installation__name')
    list_filter = ('status', 'installation', 'install_date')
    date_hierarchy = 'install_date'


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ('panel', 'predicted_class', 'confidence_score', 'risk_category', 'maintenance_priority_level', 'review_status', 'inspected_at')
    list_filter = ('predicted_class', 'risk_category', 'maintenance_priority_level', 'review_status', 'inspected_at')
    search_fields = ('panel__permanent_id', 'panel__serial_number', 'predicted_class', 'notes')
    readonly_fields = ('inspected_at',)
    date_hierarchy = 'inspected_at'


@admin.register(MaintenanceIssue)
class MaintenanceIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'panel', 'installation', 'status', 'priority', 'assigned_technician', 'created_at', 'resolved_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('title', 'panel__permanent_id', 'panel__serial_number', 'description', 'installation__name')
    date_hierarchy = 'created_at'


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ('panel', 'action_type', 'performed_at', 'user', 'notes')
    list_filter = ('action_type', 'performed_at')
    search_fields = ('panel__permanent_id', 'panel__serial_number', 'notes')
    date_hierarchy = 'performed_at'
