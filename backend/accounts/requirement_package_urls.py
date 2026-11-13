from django.urls import path
from accounts import views_requirement_packages as views
from accounts.feature_permissions import bind_feature_permissions

urlpatterns = [
    path('admin/requests/', views.package_admin_queue, name='package-admin-queue'),
    path('admin/projects/', views.package_admin_projects, name='package-admin-projects'),
    path('examples/', views.package_examples, name='package-examples-general'),
    path('examples/history/', views.package_example_history, name='package-examples-general-history'),
    path('projects/<int:project_id>/', views.package_overview, name='package-overview'),
    path('projects/<int:project_id>/examples/', views.package_examples, name='package-examples'),
    path('projects/<int:project_id>/examples/history/', views.package_example_history, name='package-examples-history'),
    path('projects/<int:project_id>/settings/', views.package_settings, name='package-settings'),
    path('projects/<int:project_id>/evaluation-context/', views.package_evaluation_context, name='package-evaluation-context'),
    path('projects/<int:project_id>/orders/', views.package_order_create, name='package-order-create'),
    path('projects/<int:project_id>/orders/<uuid:order_key>/<str:action>/', views.package_order_action, name='package-order-action'),
    path('projects/<int:project_id>/requests/', views.package_request_create, name='package-request-create'),
    path('projects/<int:project_id>/requests/<int:package_request_id>/', views.package_request_detail, name='package-request-detail'),
    path('projects/<int:project_id>/requests/<int:package_request_id>/<str:action>/', views.package_request_action, name='package-request-action'),
    path('projects/<int:project_id>/movements/<int:movement_id>/reverse/', views.package_reverse, name='package-reverse'),
]

bind_feature_permissions(urlpatterns)
