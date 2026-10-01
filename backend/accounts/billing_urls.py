from django.urls import path
from accounts import views_billing_context as views

urlpatterns = [
    path('hosting/', views.hosting_list_view, name='billing-hosting-list'),
    path('projects/<int:project_id>/billing-options/', views.billing_options_view, name='billing-options'),
    path('projects/<int:project_id>/hosting-context/', views.hosting_read_view, name='billing-hosting-read'),
    path('projects/<int:project_id>/hosting-reconciliation/', views.hosting_reconciliation_view, name='billing-hosting-reconcile'),
    path('projects/<int:project_id>/hosting-evidence/', views.hosting_evidence_view, name='billing-hosting-evidence'),
    path('collection-accounts/<int:account_id>/context/', views.account_context_view, name='billing-account-context'),
]
