from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Installations (RBAC Protected)
    path('installations/', views.installation_list_view, name='installation_list'),
    path('installations/add/', views.installation_add_view, name='installation_add'),
    path('installations/create/', views.installation_add_view, name='installation_create'),
    path('installations/<int:pk>/', views.installation_detail_view, name='installation_detail'),
    path('installations/<int:pk>/assign-technician/', views.installation_assign_tech_view, name='installation_assign_tech'),

    # Phase 4: Layout Builder & Revision Management
    path('installations/<int:pk>/layout/', views.layout_builder_view, name='layout_builder'),
    path('installations/<int:pk>/layout/save/', views.layout_save_draft_view, name='layout_save_draft'),
    path('installations/<int:pk>/layout/submit/', views.layout_submit_view, name='layout_submit'),
    path('installations/<int:pk>/layout/cancel/', views.layout_cancel_view, name='layout_cancel'),
    path('installations/<int:pk>/layout/generate-rect/', views.layout_generate_rectangular_view, name='layout_generate_rectangular'),

    # Layout Revisions Verification
    path('layouts/<int:pk>/verify/', views.layout_verify_view, name='layout_verify'),

    # Panels Inventory & Digital Passport
    path('panels/', views.panel_list_view, name='panel_list'),
    path('panels/add/', views.panel_add_view, name='panel_add'),
    path('panels/<int:pk>/', views.panel_detail_view, name='panel_detail'),

    # Inspection History & Upload
    path('inspections/', views.inspection_list_view, name='inspection_list'),
    path('inspect/', views.inspect_view, name='inspect'),
    path('inspect/result/<int:pk>/', views.result_view, name='result_detail'),
    path('inspect/result/<int:pk>/image/', views.secure_inspection_image_view, name='secure_inspection_image'),

    # Maintenance Issues Lifecycle & Protected Photo
    path('issues/', views.issue_list_view, name='issue_list'),
    path('issues/create/', views.issue_create_view, name='issue_create'),
    path('inspect/<int:inspection_id>/create-issue/', views.issue_create_view, name='issue_create_from_inspection'),
    path('issues/<int:pk>/', views.issue_detail_view, name='issue_detail'),
    path('issues/<int:pk>/photo/', views.secure_maintenance_image_view, name='secure_maintenance_photo'),

    # Razorpay Test Mode Payment & PDF Receipt Routes
    path('maintenance/<int:issue_id>/pay/', views.payment_checkout_view, name='payment_checkout'),
    path('maintenance/<int:issue_id>/payment/verify/', views.payment_verify_view, name='payment_verify'),
    path('maintenance/payment/<int:payment_id>/receipt/', views.payment_receipt_download_view, name='payment_receipt_download'),

    # Phase 8: Reports Hub & Downloadable Reports
    path('reports/', views.reports_index_view, name='reports_index'),
    path('reports/panel/<int:pk>/', views.report_panel_view, name='report_panel'),
    path('reports/installation/<int:pk>/', views.report_installation_view, name='report_installation'),
    path('reports/maintenance/', views.report_maintenance_view, name='report_maintenance'),

    # Notifications Center
    path('notifications/', views.notification_list_view, name='notification_list'),
    path('notifications/<int:pk>/open/', views.notification_open_view, name='notification_open'),
    path('notifications/<int:pk>/mark-read/', views.notification_mark_read_view, name='notification_mark_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read_view, name='notification_mark_all_read'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]

