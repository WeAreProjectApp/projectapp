from django.urls import path

from accounts import views_appi as views

urlpatterns = [
    path('quota/', views.quota_view, name='appi-quota'),
    path('conversations/', views.conversations_view, name='appi-conversations'),
    path('conversations/<uuid:conversation_id>/', views.conversation_view, name='appi-conversation'),
    path('conversations/<uuid:conversation_id>/messages/', views.messages_view, name='appi-messages'),
    path('conversations/<uuid:conversation_id>/messages/<uuid:turn_id>/', views.message_view, name='appi-message'),
]
