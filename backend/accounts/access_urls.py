from django.urls import path
from accounts import views_access as views

urlpatterns = [
    path('config/', views.auth_config),
    path('<str:surface>/<str:operation>/', views.authenticate_access),
]
