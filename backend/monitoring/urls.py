from django.urls import path

from . import views

urlpatterns = [
    path('v1/ingest/', views.receive),
    path('catalog/', views.catalog, name='monitoring-catalog'),
    path('resources/<int:pk>/', views.resource_link, name='monitoring-resource-link'),
    path('cases/', views.cases, name='monitoring-cases'),
    path('cases/<int:pk>/', views.case_detail, name='monitoring-case'),
    path('cases/<int:pk>/state/', views.case_state, name='monitoring-case-state'),
    path('cases/<int:pk>/notes/', views.case_note, name='monitoring-case-note'),
    path('reports/', views.reports, name='monitoring-reports'),
    path('reports/<int:pk>/', views.report_detail, name='monitoring-report'),
]
