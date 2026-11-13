from django.urls import path
from . import views

urlpatterns = [
    path('configs/', views.runtime_configs, name='hosting-runtime-configs'),
    path('receipts/', views.runtime_receipt, name='hosting-runtime-receipts'),
]
