from django.urls import path
from accounts import views_feature_flags as views

urlpatterns = [
    path('', views.effective, name='platform-features'),
    path('admin/', views.settings, name='platform-feature-settings'),
    path('admin/clients/', views.clients, name='platform-feature-clients'),
    path('admin/clients/<int:user_id>/', views.client, name='platform-feature-client'),
    path('admin/events/', views.events, name='platform-feature-events'),
]
