from django.urls import path

from . import views

urlpatterns = [
    path('', views.link_list),
    path('create/', views.link_create),
    path('<int:pk>/', views.link_detail),
    path('<int:pk>/content/', views.link_content),
    path('<int:pk>/link/', views.link_url),
    path('<int:pk>/reactivate/', views.link_reactivate),
    path('<int:pk>/revoke/', views.link_revoke),
    # The token always travels in the POST body, never in a URL path.
    path('public/types/', views.public_types),
    path('public/create/', views.public_create),
    path('public/status/', views.public_status),
    path('public/reveal/', views.public_reveal),
]
