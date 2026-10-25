from django.urls import path
from accounts import views_ai as views

urlpatterns = [
    path('capabilities/', views.capabilities_view, name='platform-ai-capabilities'),
    path('transcriptions/', views.transcriptions_view, name='platform-ai-transcriptions'),
    path('transcriptions/<uuid:job_id>/', views.job_view, name='platform-ai-job'),
    path('projects/<int:project_id>/report-drafts/', views.report_drafts_view, name='platform-ai-report-drafts'),
    path('admin/settings/', views.settings_view, name='platform-ai-settings'),
    path('admin/clients/', views.clients_view, name='platform-ai-clients'),
    path('admin/clients/<int:user_id>/', views.client_view, name='platform-ai-client'),
    path('admin/credentials/<str:provider>/', views.credential_view, name='platform-ai-credential'),
    path('admin/credentials/<str:provider>/test/', views.credential_test_view, name='platform-ai-credential-test'),
    path('admin/templates/', views.templates_view, name='platform-ai-templates'),
    path('admin/templates/<int:template_id>/', views.template_view, name='platform-ai-template'),
    path('admin/templates/<int:template_id>/versions/', views.template_versions_view, name='platform-ai-template-versions'),
    path('admin/templates/<int:template_id>/preview/', views.template_preview_view, name='platform-ai-template-preview'),
    path('admin/templates/<int:template_id>/restore/', views.template_restore_view, name='platform-ai-template-restore'),
    path('admin/usage/', views.usage_view, name='platform-ai-usage'),
    path('admin/events/', views.events_view, name='platform-ai-events'),
    path('admin/cache/invalidate/', views.invalidate_view, name='platform-ai-cache-invalidate'),
]
