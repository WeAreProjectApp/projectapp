from django.urls import path

from accounts.views_issue_reports import bug_reopen_view, issue_attachment_view, issue_context_options


urlpatterns = [
    path('projects/<int:project_id>/issue-reports/context-options/', issue_context_options,
         name='platform-issue-context-options'),
    path('projects/<int:project_id>/bug-reports/<int:bug_id>/reopen/', bug_reopen_view,
         name='platform-bug-reopen'),
    path('issue-reports/attachments/<int:attachment_id>/', issue_attachment_view,
         name='platform-issue-attachment'),
]
