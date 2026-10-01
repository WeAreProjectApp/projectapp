from django.urls import path

from accounts import views_delivery as views

urlpatterns = [
    path('', views.delivery_overview, name='delivery-overview'),
    path('prompt/', views.delivery_prompt, name='delivery-prompt'),
    path('import/preview/', views.delivery_import, name='delivery-import-preview'),
    path('import/apply/', views.delivery_import, {'apply': True}, name='delivery-import-apply'),
    path('stages/<int:stage_id>/publish/', views.delivery_publish, name='delivery-publish'),
    path('stages/<int:stage_id>/review/', views.delivery_review, name='delivery-review'),
    path('stages/<int:stage_id>/historical-approvals/', views.delivery_review, {'historical': True}, name='delivery-historical-approvals'),
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
