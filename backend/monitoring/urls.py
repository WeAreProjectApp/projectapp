from django.urls import path

from . import views

urlpatterns = [
    path('v1/ingest/', views.receive),
    path('catalog/', views.catalog, name='monitoring-catalog'),
    path('status/', views.dashboard_status, name='monitoring-status'),
    path('resources/<int:resource_id>/', views.resource_link, name='monitoring-resource-link'),
    path('resources/<int:resource_id>/capacity/', views.resource_capacity, name='monitoring-capacity'),
    path('resources/<int:resource_id>/capacity/history/', views.capacity_history, name='monitoring-capacity-history'),
    path('servers/<int:server_id>/series/', views.server_series, name='monitoring-series'),
    path('cases/', views.cases, name='monitoring-cases'),
    path('cases/<int:case_id>/', views.case_detail, name='monitoring-case-detail'),
    path('cases/<int:case_id>/state/', views.case_state, name='monitoring-case-state'),
    path('cases/<int:case_id>/notes/', views.case_note, name='monitoring-case-note'),
    path('reports/', views.reports, name='monitoring-reports'),
    path('reports/<int:report_id>/', views.report_detail, name='monitoring-report-detail'),
    path('resources/<int:pk>/', views.resource_link, name='monitoring-resource-link'),
    path('cases/<int:pk>/', views.case_detail, name='monitoring-case'),
    path('cases/<int:pk>/state/', views.case_state, name='monitoring-case-state'),
    path('cases/<int:pk>/notes/', views.case_note, name='monitoring-case-note'),
    path('reports/<int:pk>/', views.report_detail, name='monitoring-report'),
]
