from django.urls import path
from accounts import views_platform_help as views

urlpatterns = [
    path('', views.client_help, name='platform-help'),
    path('tours/<int:tour_id>/progress/', views.client_progress, name='platform-help-client-progress'),
    path('settings/', views.help_settings, name='platform-help-settings'),
    path('clients/', views.help_clients, name='platform-help-clients'),
    path('clients/<int:user_id>/', views.help_client, name='platform-help-client'),
    path('admin/tours/', views.tours, name='platform-help-tours'),
    path('admin/tours/<int:tour_id>/', views.tour_detail, name='platform-help-tour'),
    path('admin/tours/<int:tour_id>/publish/', views.tour_publish, name='platform-help-tour-publish'),
    path('admin/tours/<int:tour_id>/archive/', views.tour_archive, name='platform-help-tour-archive'),
    path('admin/tours/<int:tour_id>/preview/', views.tour_preview, name='platform-help-tour-preview'),
    path('admin/tours/<int:tour_id>/revisions/', views.tour_revisions, name='platform-help-tour-revisions'),
    path('admin/progress/', views.help_progress, name='platform-help-progress'),
]
