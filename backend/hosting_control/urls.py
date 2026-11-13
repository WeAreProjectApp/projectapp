from django.urls import path
from . import views

urlpatterns = [
    path('', views.controls, name='hosting-controls'),
    path('<int:control_id>/', views.detail, name='hosting-control-detail'),
    path('<int:control_id>/mode/', views.mode, name='hosting-control-mode'),
    path('<int:control_id>/message/', views.message, name='hosting-control-message'),
    path('<int:control_id>/events/', views.events, name='hosting-control-events'),
]
