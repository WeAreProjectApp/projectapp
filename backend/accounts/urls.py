from django.urls import include, path

from accounts.collection_account_views import (
    collection_account_detail_view,
    collection_account_issue_view,
    collection_account_list_create_view,
    collection_account_mark_cancelled_view,
    collection_account_mark_paid_view,
    collection_account_pdf_view,
    project_collection_account_list_view,
)
from accounts.document_views import (
    client_document_detail_view,
    client_document_list_view,
    client_document_pdf_view,
    client_document_sign_view,
    email_verify_confirm_view,
    email_verify_request_view,
)
from accounts.views_bridge import session_token_bridge
from accounts.views_saved_filter_tabs import (
    saved_filter_tab_detail,
    saved_filter_tabs_collection,
    saved_filter_tabs_reorder,
    saved_filter_tabs_reset,
)
from accounts.views_panel_preferences import (
    communication_panel_preferences,
    document_panel_preferences,
    reset_communication_panel_preferences,
)
from accounts.views_project_access import (
    platform_project_access_detail,
    platform_project_access_legacy_classify,
    platform_project_access_note_detail,
    platform_project_access_note_reveal,
    platform_project_access_notes,
    platform_project_access_password_delete,
    platform_project_access_password_reveal,
)
from accounts.views import (
    admin_detail_view,
    admin_list_view,
    admin_login_as_view,
    admin_resend_invite_view,
    impersonation_exchange_view,
    bug_report_all_view,
    bug_report_bulk_evaluate_view,
    bug_report_comment_view,
    bug_report_detail_view,
    bug_report_evaluate_view,
    bug_report_list_view,
    change_request_all_view,
    change_request_bulk_evaluate_view,
    deliverable_all_view,
    deliverable_attachment_files_view,
    deliverable_client_folder_detail_view,
    deliverable_client_folders_view,
    deliverable_client_uploads_view,
    deliverable_commercial_proposal_pdf_view,
    deliverable_data_model_entities_view,
    deliverable_detail_view,
    project_data_model_entities_view,
    project_data_model_template_view,
    deliverable_list_view,
    deliverable_sync_technical_resources_view,
    deliverable_technical_document_pdf_view,
    deliverable_upload_version_view,
    notification_list_view,
    notification_mark_all_read_view,
    notification_mark_read_view,
    notification_unread_count_view,
    payment_card_pay_view,
    payment_charge_stored_view,
    payment_generate_link_view,
    payment_verify_transaction_view,
    payment_widget_data_view,
    card_setup_start_view,
    card_setup_status_view,
    card_setup_confirm_view,
    card_delete_view,
    project_payments_view,
    register_manual_payment_view,
    project_subscription_view,
    proposal_list_for_selector_view,
    subscription_list_view,
    cover_gallery_view,
    wompi_webhook_view,
    change_request_comment_view,
    change_request_convert_view,
    change_request_detail_view,
    change_request_evaluate_view,
    change_request_list_view,
    client_detail_view,
    client_eligible_proposals_view,
    client_list_view,
    client_resend_invite_view,
    complete_profile_view,
    login_view,
    me_view,
    password_reset_confirm_view,
    password_reset_request_view,
    password_reset_verify_view,
    project_access_list_view,
    project_detail_view,
    project_list_view,
    project_phase_detail_view,
    project_phases_reorder_view,
    project_phases_view,
    requirement_list_view,
    resend_code_view,
    token_refresh_view,
    verify_view,
)

urlpatterns = [
    path('projects/<int:project_id>/', include('accounts.project_collaboration_urls')),
    path('', include('accounts.billing_urls')),
    path('', include('accounts.issue_report_urls')),
    path('projects/<int:project_id>/delivery/', include('accounts.delivery_urls')),
    # Auth
    path('session-token-bridge/', session_token_bridge, name='platform-session-bridge'),
    path('login/', login_view, name='platform-login'),
    path('verify/', verify_view, name='platform-verify'),
    path('resend-code/', resend_code_view, name='platform-resend-code'),
    path('token/refresh/', token_refresh_view, name='platform-token-refresh'),
    path('password-reset/request/', password_reset_request_view, name='platform-password-reset-request'),
    path('password-reset/verify-code/', password_reset_verify_view, name='platform-password-reset-verify'),
    path('password-reset/confirm/', password_reset_confirm_view, name='platform-password-reset-confirm'),

    # Profile
    path('me/', me_view, name='platform-me'),
    path('me/complete-profile/', complete_profile_view, name='platform-complete-profile'),

    # Panel — saved filter tabs (per-user, per-view)
    path('saved-filter-tabs/', saved_filter_tabs_collection, name='panel-saved-filter-tabs'),
    path('saved-filter-tabs/reset/', saved_filter_tabs_reset, name='panel-saved-filter-tabs-reset'),
    path('saved-filter-tabs/reorder/', saved_filter_tabs_reorder, name='panel-saved-filter-tabs-reorder'),
    path('saved-filter-tabs/<int:tab_id>/', saved_filter_tab_detail, name='panel-saved-filter-tab-detail'),
    path(
        'panel-preferences/documents/',
        document_panel_preferences,
        name='document-panel-preferences',
    ),
    path(
        'panel-preferences/communications/',
        communication_panel_preferences,
        name='communication-panel-preferences',
    ),
    path(
        'panel-preferences/communications/reset/',
        reset_communication_panel_preferences,
        name='reset-communication-panel-preferences',
    ),

    # Super admin — platform admin management
    path('admins/', admin_list_view, name='panel-admin-list'),
    path('admins/<int:user_id>/', admin_detail_view, name='panel-admin-detail'),
    path('admins/<int:user_id>/resend-invite/', admin_resend_invite_view, name='panel-admin-resend-invite'),
    path('admins/<int:user_id>/login-as/', admin_login_as_view, name='panel-admin-login-as'),
    path('impersonation/exchange/', impersonation_exchange_view, name='platform-impersonation-exchange'),

    # Admin — client management
    path('clients/', client_list_view, name='platform-client-list'),
    path('clients/<int:user_id>/', client_detail_view, name='platform-client-detail'),
    path('clients/<int:user_id>/eligible-proposals/', client_eligible_proposals_view, name='platform-client-eligible-proposals'),
    path('clients/<int:user_id>/resend-invite/', client_resend_invite_view, name='platform-client-resend-invite'),

    # Projects
    path('projects/', project_list_view, name='platform-project-list'),
    path('projects/access/', project_access_list_view, name='platform-project-access-list'),
    path('projects/<int:project_id>/', project_detail_view, name='platform-project-detail'),
    path(
        'projects/<int:project_id>/access/',
        platform_project_access_detail,
        name='platform-project-access-detail',
    ),
    path(
        'projects/<int:project_id>/access/environments/<str:environment>/password/reveal/',
        platform_project_access_password_reveal,
        name='platform-project-access-password-reveal',
    ),
    path(
        'projects/<int:project_id>/access/environments/<str:environment>/password/',
        platform_project_access_password_delete,
        name='platform-project-access-password-delete',
    ),
    path(
        'projects/<int:project_id>/access/notes/',
        platform_project_access_notes,
        name='platform-project-access-notes',
    ),
    path(
        'projects/<int:project_id>/access/notes/<int:note_id>/',
        platform_project_access_note_detail,
        name='platform-project-access-note-detail',
    ),
    path(
        'projects/<int:project_id>/access/notes/<int:note_id>/reveal/',
        platform_project_access_note_reveal,
        name='platform-project-access-note-reveal',
    ),
    path(
        'projects/<int:project_id>/access/legacy/classify/',
        platform_project_access_legacy_classify,
        name='platform-project-access-legacy-classify',
    ),
    path('projects/<int:project_id>/phases/', project_phases_view, name='platform-project-phases'),
    path('projects/<int:project_id>/phases/reorder/', project_phases_reorder_view, name='platform-project-phases-reorder'),
    path('projects/<int:project_id>/phases/<int:phase_id>/', project_phase_detail_view, name='platform-project-phase-detail'),

    # Change Requests
    path('change-requests/', change_request_all_view, name='platform-change-request-all'),
    path('projects/<int:project_id>/change-requests/', change_request_list_view, name='platform-change-request-list'),
    path('projects/<int:project_id>/change-requests/bulk-evaluate/', change_request_bulk_evaluate_view, name='platform-change-request-bulk-evaluate'),
    path('projects/<int:project_id>/change-requests/<int:cr_id>/', change_request_detail_view, name='platform-change-request-detail'),
    path('projects/<int:project_id>/change-requests/<int:cr_id>/evaluate/', change_request_evaluate_view, name='platform-change-request-evaluate'),
    path('projects/<int:project_id>/change-requests/<int:cr_id>/comments/', change_request_comment_view, name='platform-change-request-comments'),
    path('projects/<int:project_id>/change-requests/<int:cr_id>/convert/', change_request_convert_view, name='platform-change-request-convert'),

    # Bug Reports
    path('bug-reports/', bug_report_all_view, name='platform-bug-report-all'),
    path('projects/<int:project_id>/bug-reports/', bug_report_list_view, name='platform-bug-report-list'),
    path('projects/<int:project_id>/bug-reports/bulk-evaluate/', bug_report_bulk_evaluate_view, name='platform-bug-report-bulk-evaluate'),
    path('projects/<int:project_id>/bug-reports/<int:bug_id>/', bug_report_detail_view, name='platform-bug-report-detail'),
    path('projects/<int:project_id>/bug-reports/<int:bug_id>/evaluate/', bug_report_evaluate_view, name='platform-bug-report-evaluate'),
    path('projects/<int:project_id>/bug-reports/<int:bug_id>/comments/', bug_report_comment_view, name='platform-bug-report-comments'),

    # Deliverables
    path('deliverables/', deliverable_all_view, name='platform-deliverable-all'),
    path('projects/<int:project_id>/deliverables/', deliverable_list_view, name='platform-deliverable-list'),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/sync-technical-resources/',
        deliverable_sync_technical_resources_view,
        name='platform-deliverable-sync-technical',
    ),
    path(
        'projects/<int:project_id>/requirements/',
        requirement_list_view,
        name='platform-requirement-list',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/client-folders/',
        deliverable_client_folders_view,
        name='platform-deliverable-client-folders',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/client-folders/<int:folder_id>/',
        deliverable_client_folder_detail_view,
        name='platform-deliverable-client-folder-detail',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/client-uploads/',
        deliverable_client_uploads_view,
        name='platform-deliverable-client-uploads',
    ),
    path('projects/<int:project_id>/deliverables/<int:deliverable_id>/', deliverable_detail_view, name='platform-deliverable-detail'),
    path('projects/<int:project_id>/deliverables/<int:deliverable_id>/upload-version/', deliverable_upload_version_view, name='platform-deliverable-upload-version'),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/attachments/',
        deliverable_attachment_files_view,
        name='platform-deliverable-attachments',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/download/commercial-proposal-pdf/',
        deliverable_commercial_proposal_pdf_view,
        name='platform-deliverable-commercial-pdf',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/download/technical-document-pdf/',
        deliverable_technical_document_pdf_view,
        name='platform-deliverable-technical-pdf',
    ),
    path(
        'projects/<int:project_id>/deliverables/<int:deliverable_id>/data-model-entities/',
        deliverable_data_model_entities_view,
        name='platform-deliverable-data-model-entities',
    ),
    path(
        'projects/<int:project_id>/data-model-entities/',
        project_data_model_entities_view,
        name='platform-project-data-model-entities',
    ),
    path(
        'projects/<int:project_id>/data-model-entities/template/',
        project_data_model_template_view,
        name='platform-project-data-model-template',
    ),

    # Notifications
    path('notifications/', notification_list_view, name='platform-notification-list'),
    path('notifications/unread-count/', notification_unread_count_view, name='platform-notification-unread-count'),
    path('notifications/<int:notification_id>/read/', notification_mark_read_view, name='platform-notification-mark-read'),
    path('notifications/mark-all-read/', notification_mark_all_read_view, name='platform-notification-mark-all-read'),

    # Collection accounts (commercial documents)
    path('collection-accounts/', collection_account_list_create_view, name='platform-collection-account-list'),
    path(
        'collection-accounts/<int:account_id>/',
        collection_account_detail_view,
        name='platform-collection-account-detail',
    ),
    path(
        'collection-accounts/<int:account_id>/issue/',
        collection_account_issue_view,
        name='platform-collection-account-issue',
    ),
    path(
        'collection-accounts/<int:account_id>/mark-paid/',
        collection_account_mark_paid_view,
        name='platform-collection-account-mark-paid',
    ),
    path(
        'collection-accounts/<int:account_id>/mark-cancelled/',
        collection_account_mark_cancelled_view,
        name='platform-collection-account-mark-cancelled',
    ),
    path(
        'collection-accounts/<int:account_id>/pdf/',
        collection_account_pdf_view,
        name='platform-collection-account-pdf',
    ),
    path(
        'projects/<int:project_id>/collection-accounts/',
        project_collection_account_list_view,
        name='platform-project-collection-accounts',
    ),

    # Payments & Subscriptions
    path('proposals/', proposal_list_for_selector_view, name='platform-proposal-list'),
    path('subscriptions/', subscription_list_view, name='platform-subscription-list'),
    path('projects/<int:project_id>/subscription/', project_subscription_view, name='platform-project-subscription'),
    path('projects/<int:project_id>/subscription/card/', card_setup_start_view, name='platform-card-setup-start'),
    path('projects/<int:project_id>/subscription/card/<int:payment_source_id>/status/', card_setup_status_view, name='platform-card-setup-status'),
    path('projects/<int:project_id>/subscription/card/<int:payment_source_id>/confirm/', card_setup_confirm_view, name='platform-card-setup-confirm'),
    path('projects/<int:project_id>/subscription/card/remove/', card_delete_view, name='platform-card-delete'),
    path('projects/<int:project_id>/payments/', project_payments_view, name='platform-project-payments'),
    path('projects/<int:project_id>/payments/manual/', register_manual_payment_view, name='platform-payment-register-manual'),
    path('projects/<int:project_id>/payments/<int:payment_id>/generate-link/', payment_generate_link_view, name='platform-payment-generate-link'),
    path('projects/<int:project_id>/payments/<int:payment_id>/widget-data/', payment_widget_data_view, name='platform-payment-widget-data'),
    path('projects/<int:project_id>/payments/<int:payment_id>/card-pay/', payment_card_pay_view, name='platform-payment-card-pay'),
    path('projects/<int:project_id>/payments/<int:payment_id>/charge/', payment_charge_stored_view, name='platform-payment-charge-stored'),
    path('projects/<int:project_id>/payments/<int:payment_id>/verify/', payment_verify_transaction_view, name='platform-payment-verify'),
    path('webhooks/wompi/', wompi_webhook_view, name='platform-wompi-webhook'),

    # Client document portal
    path('documents/', client_document_list_view, name='platform-client-document-list'),
    path('documents/<uuid:doc_uuid>/', client_document_detail_view, name='platform-client-document-detail'),
    path('documents/<uuid:doc_uuid>/pdf/', client_document_pdf_view, name='platform-client-document-pdf'),
    path('documents/<uuid:doc_uuid>/sign/', client_document_sign_view, name='platform-client-document-sign'),

    # Email validation (client portal)
    path('email/verify/request/', email_verify_request_view, name='platform-email-verify-request'),
    path('email/verify/confirm/', email_verify_confirm_view, name='platform-email-verify-confirm'),

    # Cover gallery
    path('cover-gallery/', cover_gallery_view, name='platform-cover-gallery'),
]
