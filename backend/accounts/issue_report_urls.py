from django.urls import path

from accounts import views_issue_reports as views


urlpatterns = [
    path('projects/<int:project_id>/issue-reports/context-options/', views.issue_context_options,
         name='platform-issue-context-options'),
    path('projects/<int:project_id>/bug-reports/<int:bug_id>/reopen/', views.bug_reopen_view,
         name='platform-bug-reopen'),
    path('issue-reports/attachments/<int:attachment_id>/', views.issue_attachment_view,
         name='platform-issue-attachment'),
    path('projects/<int:project_id>/issue-reports/<str:kind>/<int:ticket_id>/reply/options/',
         views.issue_reply_options, name='platform-issue-reply-options'),
    path('projects/<int:project_id>/issue-reports/<str:kind>/<int:ticket_id>/reply/contexts/',
         views.issue_reply_prepare, name='platform-issue-reply-prepare'),
    path('projects/<int:project_id>/issue-reports/<str:kind>/<int:ticket_id>/reply/contexts/<uuid:context_id>/',
         views.issue_reply_context, name='platform-issue-reply-context'),
    path('projects/<int:project_id>/issue-reports/<str:kind>/<int:ticket_id>/reply/preview/',
         views.issue_reply_preview, name='platform-issue-reply-preview'),
    path('projects/<int:project_id>/issue-reports/<str:kind>/<int:ticket_id>/reply/contexts/<uuid:context_id>/sources/<str:source_key>/',
         views.issue_reply_source, name='platform-issue-reply-source'),
]
