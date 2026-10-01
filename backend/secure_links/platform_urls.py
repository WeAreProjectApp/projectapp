from django.urls import path

from . import platform_views as views

urlpatterns = [
    path('', views.collection, name='platform-secure-link-list-create'),
    path('types/', views.types, name='platform-secure-link-types'),
    path('<int:link_id>/', views.detail, name='platform-secure-link-detail'),
    path('<int:link_id>/events/', views.events, name='platform-secure-link-events'),
    path('<int:link_id>/link/', views.copy_url, name='platform-secure-link-url'),
    path('<int:link_id>/revoke/', views.revoke, name='platform-secure-link-revoke'),
    path('<int:link_id>/reactivate/', views.reactivate, name='platform-secure-link-reactivate'),
]
