from django.urls import path
from content.views import billing_context as views

urlpatterns = [
    path('projects/<int:project_id>/options/', views.options),
    path('projects/<int:project_id>/hosting/', views.reconciliation),
    path('projects/<int:project_id>/evidence/', views.evidence),
    path('accounts/<int:account_id>/', views.account_context),
]
