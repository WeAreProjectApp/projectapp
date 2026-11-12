from django.urls import path
from . import views

urlpatterns = [
    path('opportunities/', views.opportunities, name='procurement-opportunities'),
    path('opportunities/<int:pk>/', views.opportunity_detail, name='procurement-opportunity'),
    path('opportunities/<int:pk>/classification/', views.classify, name='procurement-classify'),
    path('opportunities/<int:pk>/restore/', views.restore, name='procurement-restore'),
    path('searches/', views.searches, name='procurement-searches'),
    path('searches/<int:pk>/', views.search_detail, name='procurement-search'),
    path('alerts/', views.alerts, name='procurement-alerts'),
    path('alerts/<int:pk>/', views.alert_detail, name='procurement-alert'),
    path('settings/', views.settings, name='procurement-settings'),
    path('filters/', views.catalog, name='procurement-filters'),
    path('sync/', views.sync, name='procurement-sync'),
    path('deliveries/', views.deliveries, name='procurement-deliveries'),
    path('deliveries/<int:pk>/', views.delivery_detail, name='procurement-delivery'),
    path('deliveries/<int:pk>/retry/', views.retry, name='procurement-retry'),
    path('export/', views.export, name='procurement-export'),
]
