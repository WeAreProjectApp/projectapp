from django.urls import path

from accounts import views_delivery as views
from accounts import views_delivery_notifications as notices

urlpatterns = [
    path('notices/', notices.delivery_notice_list, name='delivery-notice-list'),
    path('notices/<uuid:event_id>/', notices.delivery_notice_detail, name='delivery-notice-detail'),
    path('notices/<uuid:event_id>/retry-preview/', notices.delivery_notice_retry_preview, name='delivery-notice-retry-preview'),
    path('notices/<uuid:event_id>/retry/', notices.delivery_notice_retry, name='delivery-notice-retry'),
    path('', views.delivery_overview, name='delivery-overview'),
    path('prompt/', views.delivery_prompt, name='delivery-prompt'),
    path('prompt/options/', views.delivery_prompt_options, name='delivery-prompt-options'),
    path('prompt/contexts/', views.delivery_prompt_contexts, name='delivery-prompt-contexts'),
    path('prompt/<uuid:context_id>/', views.delivery_prompt_context, name='delivery-prompt-context'),
    path('prompt/<uuid:context_id>/sources/<str:source_key>/download/', views.delivery_prompt_source_download, name='delivery-prompt-source-download'),
    path('reply/preview/', views.delivery_reply_preview, name='delivery-reply-preview'),
    path('import/preview/', views.delivery_import, name='delivery-import-preview'),
    path('import/apply/', views.delivery_import, {'apply': True}, name='delivery-import-apply'),
    path('stages/<int:stage_id>/publish/', views.delivery_publish, name='delivery-publish'),
    path('stages/<int:stage_id>/review/', views.delivery_review, name='delivery-review'),
    path('stages/<int:stage_id>/historical-approvals/', views.delivery_review, {'historical': True}, name='delivery-historical-approvals'),
    path('stages/<int:stage_id>/closure-email/prepare/', views.delivery_closure_email_prepare, name='delivery-closure-email-prepare'),
    path('stages/<int:stage_id>/closure-email/history/', views.delivery_closure_email_history, name='delivery-closure-email-history'),
    path('closure-emails/<uuid:preparation_id>/', views.delivery_closure_email_detail, name='delivery-closure-email-detail'),
    path('closure-emails/<uuid:preparation_id>/send/', views.delivery_closure_email_send, name='delivery-closure-email-send'),
    path('closure-emails/<uuid:preparation_id>/resend/prepare/', views.delivery_closure_email_resend_prepare, name='delivery-closure-email-resend-prepare'),
    path('closure-emails/<uuid:preparation_id>/attachments/<int:file_id>/download/', views.delivery_closure_email_attachment, name='delivery-closure-email-attachment'),
    path('messages/', views.delivery_messages, name='delivery-messages'),
    path('documents/options/', views.delivery_document_options, name='delivery-document-options'),
    path('evidence-options/', views.delivery_evidence_options, name='delivery-evidence-options'),
    path('documents/', views.delivery_documents, name='delivery-documents'),
    path('documents/<int:link_id>/', views.delivery_document_delete, name='delivery-document-delete'),
    path('documents/<int:link_id>/pdf/', views.delivery_document_pdf, name='delivery-document-pdf'),
    path('reviews/<int:review_id>/evidence/', views.delivery_review_evidence_list, name='delivery-review-evidence'),
    path('reviews/<int:review_id>/evidence/<int:evidence_id>/pdf/', views.delivery_review_evidence_pdf, name='delivery-review-evidence-pdf'),
]

for kind in ('contracts', 'amendments', 'scopes', 'phases', 'stages', 'requirements'):
    urlpatterns += [
        path(f'{kind}/', views.delivery_node, {'kind': kind}, name=f'delivery-{kind}'),
        path(f'{kind}/<int:node_id>/', views.delivery_node, {'kind': kind}, name=f'delivery-{kind}-detail'),
    ]

for kind in ('contracts', 'amendments'):
    urlpatterns += [
        path(f'{kind}/<int:node_id>/signature-external/', views.delivery_signature, {'kind': kind}, name=f'delivery-{kind}-signature'),
        path(f'{kind}/<int:node_id>/pdf/', views.delivery_contract_pdf, {'kind': kind}, name=f'delivery-{kind}-pdf'),
    ]
