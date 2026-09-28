from content.views.document_move import move_document_batch
from content.views.proposal_document_exports import contract_markdown, formalization_markdown, attachment_markdown, attachment_download
from content.views import linktree_template as lt_templates
from django.urls import path
from content.views.accounting import (
    accounting_dashboard, accounting_stats, accounting_receivables,
    list_income_records, create_income_record, retrieve_income_record,
    retrieve_income_detail, list_client_projects,
    settle_income_record, bulk_assign_income_client, mute_income_reminders,
    bulk_assign_income_project, bulk_settle_income_records,
    duplicate_income_draft, suggest_income_period,
    update_income_record, delete_income_record,
    list_expense_records, create_expense_record, retrieve_expense_record,
    update_expense_record, delete_expense_record,
    list_hosting_records, create_hosting_record, retrieve_hosting_record,
    bulk_assign_hosting_client, bulk_assign_hosting_project,
    update_hosting_record, delete_hosting_record,
    list_hosting_cycles, create_hosting_cycle, delete_hosting_cycle,
    list_pocket_movements, create_pocket_movement, retrieve_pocket_movement,
    update_pocket_movement, delete_pocket_movement,
    list_recurring_payments, create_recurring_payment,
    retrieve_recurring_payment, update_recurring_payment,
    duplicate_recurring_payment_draft, set_recurring_payment_state,
    archive_recurring_payment, restore_recurring_payment,
    mute_recurring_payment_reminders, bulk_recurring_payment_action,
    delete_recurring_payment, reorder_recurring_payments,
    list_ads_spend_records, create_ads_spend_record,
    retrieve_ads_spend_record, update_ads_spend_record,
    delete_ads_spend_record,
    list_card_snapshots, create_card_snapshot, retrieve_card_snapshot,
    update_card_snapshot, delete_card_snapshot,
    list_credit_cards, create_credit_card, retrieve_credit_card,
    update_credit_card, delete_credit_card,
    list_notification_recipients, create_notification_recipient,
    retrieve_notification_recipient, update_notification_recipient,
    delete_notification_recipient,
    list_accounting_change_logs, list_accounting_email_logs,
    accounting_history_tab_counts, accounting_email_log_body,
    retry_accounting_email_log,
    get_accounting_settings, update_accounting_settings,
)
from content.views.accounting_export import (
    export_accounting_records, export_accounting_workbook,
)
from content.views.collection_accounts_panel import (
    cancel_collection_account_view,
    collection_account_next_number_view,
    collection_account_pdf,
    collection_account_preview_pdf_view,
    create_collection_account_view,
    delete_collection_account_view,
    list_collection_accounts,
    mark_collection_account_paid_view,
    preview_collection_account_view,
    resend_collection_account,
    retrieve_collection_account,
    send_hosting_collection_account,
)
from content.views.contact import contact_list, new_contact
from content.views.panel_dashboard import panel_dashboard
from content.views.project_brand import project_brand, project_brand_asset
from content.views.panel_projects import (
    archive_panel_project,
    assign_project_unlinked_records,
    change_project_client,
    create_panel_project,
    list_panel_projects,
    list_project_unlinked_records,
    preview_project_client_change,
    unarchive_panel_project,
    update_panel_project,
)
from content.views.panel_project_access import (
    panel_project_access_detail,
    panel_project_access_legacy_classify,
    panel_project_access_note_detail,
    panel_project_access_note_reveal,
    panel_project_access_notes,
    panel_project_access_password_delete,
    panel_project_access_password_reveal,
)
from content.views.portfolio_works import (
    list_portfolio_works, retrieve_portfolio_work,
    portfolio_sitemap_data,
    list_admin_portfolio_works, create_portfolio_work,
    create_portfolio_work_from_json, get_portfolio_json_template,
    retrieve_admin_portfolio_work, update_portfolio_work,
    delete_portfolio_work, duplicate_portfolio_work,
    upload_portfolio_cover_image,
)
from content.views.linktree import (
    list_admin_linktrees, retrieve_admin_linktree, create_linktree,
    update_linktree, delete_linktree, public_linktree, upload_linktree_avatar, upload_linktree_logo,
)
from content.views.qr_cards import (
    list_admin_qr_cards, create_qr_card, update_qr_card, delete_qr_card,
)
from content.views.accounting_statement import (
    batch_create_transactions, create_merchant_alias, create_statement,
    delete_merchant_alias, delete_statement, delete_statement_transaction,
    finalize_statement, learn_merchant_alias, list_merchant_aliases,
    list_statements,
    reopen_statement, resolve_merchant_aliases, retrieve_statement,
    statements_status, update_merchant_alias, update_statement,
    update_statement_transaction, upload_statement_pdf, delete_statement_pdf,
)
from content.views.hour_packages import (
    list_admin_hour_packages, create_hour_package,
    retrieve_admin_hour_package, update_hour_package,
    delete_hour_package, get_hour_package_settings,
    update_hour_package_settings, restore_default_hour_packages,
)
from content.views.view_map import (
    get_view_map_settings, update_view_map_settings,
)
from content.views.proposal import (
    retrieve_public_proposal, retrieve_public_proposal_by_slug,
    download_proposal_pdf, retrieve_public_contract_terms,
    download_public_draft_contract_pdf,
    list_proposals, retrieve_proposal, create_proposal,
    create_proposal_from_json, get_proposal_json_template,
    export_proposal_json, update_proposal_from_json,
    update_proposal, delete_proposal, duplicate_proposal, send_proposal,
    send_multi_proposal, preview_proposal_email,
    resend_proposal, toggle_proposal_active, bulk_action,
    update_proposal_section, bulk_reorder_sections,
    create_proposal_section, delete_proposal_section,
    respond_to_proposal, comment_on_proposal, check_admin_auth,
    track_proposal_engagement, track_calculator_interaction, track_requirement_click,
    retrieve_proposal_analytics, retry_first_view_notification,
    proposal_dashboard, export_proposal_analytics_csv,
    create_share_link, retrieve_shared_proposal, schedule_followup,
    list_clients, log_activity, proposal_alerts,
    create_proposal_alert, dismiss_proposal_alert,
    update_proposal_status, launch_to_platform, proposal_scorecard,
    proposal_defaults, reset_proposal_defaults,
    email_deliverability_dashboard,
    request_magic_link,
    preview_sync_section, apply_sync_section,
    save_contract_and_negotiate, update_contract_params, update_contract_modality,
    download_contract_pdf, download_draft_contract_pdf,
    send_documents_to_client,
    send_discount_offer,
    get_company_settings,
    get_default_contract_template,
    list_proposal_documents, upload_proposal_document,
    delete_proposal_document,
    send_branded_email, get_branded_email_defaults, list_branded_emails,
    send_proposal_email, get_proposal_email_defaults, list_proposal_emails,
    generate_email_markdown_attachment,
    update_project_stage, complete_project_stage,
)
from content.views.email_templates import (
    email_template_list, email_template_detail,
    email_template_preview, email_template_reset,
)
from content.views.blog import (
    list_blog_posts, retrieve_blog_post, blog_sitemap_data,
    list_admin_blog_posts, create_blog_post, create_blog_post_from_json,
    get_blog_json_template,
    retrieve_admin_blog_post, update_blog_post, delete_blog_post,
    duplicate_blog_post, upload_blog_cover_image, blog_calendar,
)
from content.views.mcp_blog import (
    create_mcp_credential,
    generate_mcp_connector_token,
    list_mcp_connectors,
    mcp_credential_detail,
    mcp_endpoint,
    rotate_mcp_credential,
    update_mcp_connector,
)
from content.views.mcp_upload import mcp_signed_asset, mcp_signed_upload
from content.views.linkedin import (
    linkedin_auth_url, linkedin_callback, linkedin_status,
    publish_to_linkedin,
    list_linkedin_posts, create_linkedin_post,
    update_linkedin_post, delete_linkedin_post,
    publish_linkedin_post,
)
from content.views.standalone_email import (
    send_standalone_email, standalone_email_defaults, list_standalone_emails,
    preview_composed_email, resend_standalone_email,
    standalone_email_attachment, standalone_email_body,
)
from content.views.document import (
    browse_documents, list_documents, create_document, create_document_from_markdown,
    upload_document_markdown, retrieve_document, update_document,
    delete_document, duplicate_document, download_document_pdf,
    archive_document, unarchive_document, document_counts,
    document_email_usage, document_navigation, suggest_folder_client,
)
from content.views.document_thread import (
    create_thread,
    document_thread_candidates,
    document_thread_detail,
    update_or_delete_thread,
)
from content.views.recurring_category import (
    list_recurring_categories, create_recurring_category,
    update_recurring_category, delete_recurring_category,
    reorder_recurring_categories,
)
from content.views.document_folder import (
    list_document_folders, create_document_folder,
    update_document_folder, delete_document_folder,
    reorder_document_folders,
    archive_document_folder, unarchive_document_folder,
    preview_document_folder_client_change, change_document_folder_client,
    project_folder_readiness,
)
from content.views.document_tag import (
    list_document_tags, create_document_tag,
    update_document_tag, delete_document_tag,
)
from content.views.document_state import (
    bulk_delete_document_notes,
    close_document_state,
    correct_document_state_opening,
    document_notes,
    document_note_events,
    document_state_group_detail,
    document_state_groups,
    document_state_history,
    document_state_suggestions,
    document_states,
    finish_document_note,
    merge_document_state,
    open_document_state,
    retire_document_state,
    restore_document_note,
    update_document_note,
    update_document_state,
)
from content.views.project_state import (
    apply_project_state_transition,
    merge_project_state,
    preview_project_state_transition,
    project_state_groups,
    project_state_history,
    project_state_suggestions,
    project_states,
    retire_project_state,
    update_project_state,
)
from content.views.client_emails import (
    client_email_body,
    list_client_emails,
    retry_client_email,
)
from content.views.client_email_copy import (
    client_email_copy_recipient_detail,
    client_email_copy_recipients,
)
from content.views.communication_folder import communication_folders, communication_folder_detail
from content.views.communication import (
    archive_communication_thread,
    close_communication_thread,
    communication_message_detail,
    communication_thread_detail,
    communication_thread_messages,
    communication_thread_tab_counts,
    communication_threads,
    correct_communication_message_date,
    document_communication_usage,
    mark_communication_message_sent,
    reopen_communication_thread,
    unarchive_communication_thread,
    void_communication_message,
)
from content.views.proposal_clients import (
    list_proposal_clients, search_proposal_clients, retrieve_proposal_client,
    create_proposal_client, update_proposal_client, delete_proposal_client,
    proposal_client_status_counts,
    preview_client_archive, archive_proposal_client, unarchive_proposal_client,
)
from content.views.task import (
    list_tasks, create_task, update_task, reorder_task, delete_task,
    duplicate_task,
    list_task_assignees,
    archive_task, unarchive_task, list_archived_tasks,
    list_task_comments, create_task_comment, delete_task_comment,
    list_task_alerts, create_task_alert, delete_task_alert,
)
from content.views.diagnostic_template import (
    list_diagnostic_templates, get_diagnostic_template,
)
from content.views.diagnostic import (
    list_diagnostics, create_diagnostic, retrieve_diagnostic,
    update_diagnostic, delete_diagnostic, bulk_diagnostic_action,
    diagnostic_scorecard,
    list_diagnostic_sections, update_diagnostic_section,
    bulk_update_diagnostic_sections, reset_diagnostic_section,
    list_diagnostic_activity, create_diagnostic_activity,
    diagnostic_analytics, export_diagnostic_analytics_csv,
    send_initial, mark_in_analysis, send_final,
    list_diagnostic_attachments, upload_diagnostic_attachment,
    delete_diagnostic_attachment, send_diagnostic_attachments,
    update_confidentiality_params, generate_confidentiality_pdf_view,
    download_confidentiality_pdf, download_draft_confidentiality_pdf,
    send_diagnostic_email, get_diagnostic_email_defaults,
    list_diagnostic_emails, generate_diagnostic_email_markdown_attachment,
    retrieve_public_diagnostic, retrieve_public_diagnostic_by_slug,
    track_public_diagnostic,
    track_diagnostic_section_view, respond_public_diagnostic,
    download_public_diagnostic_pdf,
    diagnostic_defaults, reset_diagnostic_defaults,
)
from content.views.additional_modules import (
    admin_catalog,
    admin_catalog_pdf,
    admin_share_links,
    create_category as create_additional_module_category,
    create_module as create_additional_module,
    public_catalog as public_additional_module_catalog,
    public_catalog_pdf as public_additional_module_catalog_pdf,
    public_share_catalog as public_additional_module_share,
    public_share_catalog_pdf as public_additional_module_share_pdf,
    reorder_admin_catalog as reorder_additional_module_catalog,
    set_category_status as set_additional_module_category_status,
    set_module_status as set_additional_module_status,
    set_share_link_status as set_additional_module_share_status,
    track_public_share_catalog as track_public_additional_module_share,
    update_category as update_additional_module_category,
    update_module as update_additional_module,
    update_share_link as update_additional_module_share,
)
from content.views.explainer_videos import (
    get_explainer_video_settings,
    update_explainer_video_settings,
)
from content.views.financing import (
    public_financing_program,
    public_financing_program_pdf,
)
from content.views.financing_agreements import (
    financing_agreement_action,
    financing_agreement_detail,
    financing_agreement_draft_pdf,
    financing_agreement_list,
    financing_agreement_signed_pdf,
    financing_agreement_templates,
    financing_client_context,
    financing_settings,
)

from content.views.formalization import (
    formalization_options, formalization_pdf, prepare_formalization,
    retrieve_formalization, formalization_attachment, send_formalization,
)

from content.views.entity_history import (
    entity_history_list, entity_history_version, entity_history_compare, entity_history_reveal, entity_history_file,
)

urlpatterns = [
    path('entity-history/<str:entity_type>/<int:object_id>/', entity_history_list),
    path('entity-history/<str:entity_type>/<int:object_id>/versions/<int:revision_id>/file/', entity_history_file),
    path('entity-history/<str:entity_type>/<int:object_id>/compare/', entity_history_compare),
    path('entity-history/<str:entity_type>/<int:object_id>/versions/<int:revision_id>/', entity_history_version),
    path('entity-history/<str:entity_type>/<int:object_id>/versions/<int:revision_id>/reveal/', entity_history_reveal),
    path('proposals/<int:proposal_id>/formalization/', formalization_options, name='formalization-options'),
    path('proposals/<int:proposal_id>/formalization/pdf/<str:kind>/', formalization_pdf, name='formalization-pdf'),
    path('proposals/<int:proposal_id>/formalization/prepare/', prepare_formalization, name='formalization-prepare'),
    path('proposals/<int:proposal_id>/formalization/preparations/<uuid:preparation_id>/', retrieve_formalization, name='formalization-detail'),
    path('proposals/<int:proposal_id>/formalization/preparations/<uuid:preparation_id>/files/<int:file_id>/', formalization_attachment, name='formalization-file'),
    path('proposals/<int:proposal_id>/formalization/preparations/<uuid:preparation_id>/send/', send_formalization, name='formalization-send'),
    path('contacts/', contact_list, name='contact-list'),
    path('new-contact/', new_contact, name='new-contact'),

    # Financing program — public informational resource
    path(
        'financing/public/',
        public_financing_program,
        name='public-financing-program',
    ),
    path(
        'financing/public/pdf/',
        public_financing_program_pdf,
        name='public-financing-program-pdf',
    ),
    path(
        'financing/settings/',
        financing_settings,
        name='financing-settings',
    ),
    path(
        'financing/agreements/',
        financing_agreement_list,
        name='financing-agreement-list',
    ),
    path(
        'financing/agreements/templates/',
        financing_agreement_templates,
        name='financing-agreement-templates',
    ),
    path(
        'financing/agreements/client-context/',
        financing_client_context,
        name='financing-client-context',
    ),
    path(
        'financing/agreements/<int:agreement_id>/',
        financing_agreement_detail,
        name='financing-agreement-detail',
    ),
    path(
        'financing/agreements/<int:agreement_id>/draft-pdf/',
        financing_agreement_draft_pdf,
        name='financing-agreement-draft-pdf',
    ),
    path(
        'financing/agreements/<int:agreement_id>/signed-pdf/',
        financing_agreement_signed_pdf,
        name='financing-agreement-signed-pdf',
    ),
    path(
        'financing/agreements/<int:agreement_id>/<slug:action>/',
        financing_agreement_action,
        name='financing-agreement-action',
    ),

    # Additional modules catalog — public
    path(
        'additional-modules/public/',
        public_additional_module_catalog,
        name='public-additional-module-catalog',
    ),
    path(
        'additional-modules/public/pdf/',
        public_additional_module_catalog_pdf,
        name='public-additional-module-catalog-pdf',
    ),
    path(
        'additional-modules/public/shares/<uuid:share_uuid>/',
        public_additional_module_share,
        name='public-additional-module-share',
    ),
    path(
        'additional-modules/public/shares/<uuid:share_uuid>/track/',
        track_public_additional_module_share,
        name='track-public-additional-module-share',
    ),
    path(
        'additional-modules/public/shares/<uuid:share_uuid>/pdf/',
        public_additional_module_share_pdf,
        name='public-additional-module-share-pdf',
    ),

    # Additional modules catalog — admin
    path(
        'additional-modules/admin/',
        admin_catalog,
        name='admin-additional-module-catalog',
    ),
    path(
        'additional-modules/admin/categories/',
        create_additional_module_category,
        name='create-additional-module-category',
    ),
    path(
        'additional-modules/admin/categories/<int:category_id>/',
        update_additional_module_category,
        name='update-additional-module-category',
    ),
    path(
        'additional-modules/admin/categories/<int:category_id>/<str:action>/',
        set_additional_module_category_status,
        name='set-additional-module-category-status',
    ),
    path(
        'additional-modules/admin/modules/',
        create_additional_module,
        name='create-additional-module',
    ),
    path(
        'additional-modules/admin/modules/<int:module_id>/',
        update_additional_module,
        name='update-additional-module',
    ),
    path(
        'additional-modules/admin/modules/<int:module_id>/<str:action>/',
        set_additional_module_status,
        name='set-additional-module-status',
    ),
    path(
        'additional-modules/admin/reorder/',
        reorder_additional_module_catalog,
        name='reorder-additional-module-catalog',
    ),
    path(
        'additional-modules/admin/shares/',
        admin_share_links,
        name='admin-additional-module-shares',
    ),
    path(
        'additional-modules/admin/shares/<uuid:share_uuid>/',
        update_additional_module_share,
        name='update-additional-module-share',
    ),
    path(
        'additional-modules/admin/shares/<uuid:share_uuid>/<str:action>/',
        set_additional_module_share_status,
        name='set-additional-module-share-status',
    ),

    # Explainer videos — panel switches for the client-facing views (singleton)
    path(
        'explainer-videos/admin/settings/',
        get_explainer_video_settings,
        name='explainer-video-settings',
    ),
    path(
        'explainer-videos/admin/settings/update/',
        update_explainer_video_settings,
        name='update-explainer-video-settings',
    ),
    path(
        'additional-modules/admin/pdf/',
        admin_catalog_pdf,
        name='admin-additional-module-catalog-pdf',
    ),

    # Proposals — public
    path('proposals/<uuid:proposal_uuid>/', retrieve_public_proposal, name='retrieve-public-proposal'),
    path('proposals/by-slug/<slug:proposal_slug>/', retrieve_public_proposal_by_slug, name='retrieve-public-proposal-by-slug'),
    path('proposals/<uuid:proposal_uuid>/pdf/', download_proposal_pdf, name='download-proposal-pdf'),
    path('proposals/<uuid:proposal_uuid>/contract-terms/', retrieve_public_contract_terms, name='retrieve-public-contract-terms'),
    path('proposals/<uuid:proposal_uuid>/contract/draft-pdf/', download_public_draft_contract_pdf, name='download-public-draft-contract-pdf'),
    path('proposals/<uuid:proposal_uuid>/respond/', respond_to_proposal, name='respond-to-proposal'),
    path('proposals/<uuid:proposal_uuid>/comment/', comment_on_proposal, name='comment-on-proposal'),
    path('proposals/<uuid:proposal_uuid>/track/', track_proposal_engagement, name='track-proposal-engagement'),
    path('proposals/<uuid:proposal_uuid>/track-calculator/', track_calculator_interaction, name='track-calculator-interaction'),
    path('proposals/<uuid:proposal_uuid>/track-requirement-click/', track_requirement_click, name='track-requirement-click'),
    path('proposals/<uuid:proposal_uuid>/share/', create_share_link, name='create-share-link'),
    path('proposals/<uuid:proposal_uuid>/schedule-followup/', schedule_followup, name='schedule-followup'),
    path('proposals/shared/<uuid:share_uuid>/', retrieve_shared_proposal, name='retrieve-shared-proposal'),
    path('proposals/request-link/', request_magic_link, name='request-magic-link'),

    # Proposals — admin auth check
    path('auth/check/', check_admin_auth, name='check-admin-auth'),

    # Panel — global dashboard
    path('panel/dashboard/', panel_dashboard, name='panel-dashboard'),

    # Panel — Projects module (Plataforma space)
    path('projects/<int:project_id>/brand/', project_brand, name='project-brand'),
    path('projects/<int:project_id>/brand/<int:asset_id>/', project_brand_asset, name='project-brand-asset'),
    path('projects/', list_panel_projects, name='panel-projects-list'),
    path('projects/create/', create_panel_project, name='panel-projects-create'),
    path('projects/<int:project_id>/update/', update_panel_project, name='panel-projects-update'),
    path(
        'projects/<int:project_id>/access/',
        panel_project_access_detail,
        name='panel-project-access-detail',
    ),
    path(
        'projects/<int:project_id>/access/environments/<str:environment>/password/reveal/',
        panel_project_access_password_reveal,
        name='panel-project-access-password-reveal',
    ),
    path(
        'projects/<int:project_id>/access/environments/<str:environment>/password/',
        panel_project_access_password_delete,
        name='panel-project-access-password-delete',
    ),
    path(
        'projects/<int:project_id>/access/notes/',
        panel_project_access_notes,
        name='panel-project-access-notes',
    ),
    path(
        'projects/<int:project_id>/access/notes/<int:note_id>/',
        panel_project_access_note_detail,
        name='panel-project-access-note-detail',
    ),
    path(
        'projects/<int:project_id>/access/notes/<int:note_id>/reveal/',
        panel_project_access_note_reveal,
        name='panel-project-access-note-reveal',
    ),
    path(
        'projects/<int:project_id>/access/legacy/classify/',
        panel_project_access_legacy_classify,
        name='panel-project-access-legacy-classify',
    ),
    path('projects/<int:project_id>/archive/', archive_panel_project, name='panel-projects-archive'),
    path('projects/<int:project_id>/unarchive/', unarchive_panel_project, name='panel-projects-unarchive'),
    path('projects/<int:project_id>/unlinked-records/', list_project_unlinked_records, name='panel-projects-unlinked-records'),
    path('projects/<int:project_id>/assign-unlinked/', assign_project_unlinked_records, name='panel-projects-assign-unlinked'),
    path('projects/<int:project_id>/change-client/preview/', preview_project_client_change, name='panel-projects-change-client-preview'),
    path('projects/<int:project_id>/change-client/', change_project_client, name='panel-projects-change-client'),
    path(
        'projects/<int:project_id>/state-transitions/preview/',
        preview_project_state_transition,
        name='panel-project-state-transition-preview',
    ),
    path(
        'projects/<int:project_id>/state-transitions/',
        apply_project_state_transition,
        name='panel-project-state-transition',
    ),
    path(
        'projects/<int:project_id>/state-history/',
        project_state_history,
        name='panel-project-state-history',
    ),
    path(
        'project-state-groups/',
        project_state_groups,
        name='project-state-groups',
    ),
    path('project-states/', project_states, name='project-states'),
    path(
        'project-states/suggestions/',
        project_state_suggestions,
        name='project-state-suggestions',
    ),
    path(
        'project-states/<int:state_id>/',
        update_project_state,
        name='update-project-state',
    ),
    path(
        'project-states/<int:state_id>/retire/',
        retire_project_state,
        name='retire-project-state',
    ),
    path(
        'project-states/<int:state_id>/merge/',
        merge_project_state,
        name='merge-project-state',
    ),

    # Proposals — admin CRUD
    path('proposals/', list_proposals, name='list-proposals'),
    path('proposals/create/', create_proposal, name='create-proposal'),
    path('proposals/create-from-json/', create_proposal_from_json, name='create-proposal-from-json'),
    path('proposals/json-template/', get_proposal_json_template, name='proposal-json-template'),
    path('proposals/<int:proposal_id>/detail/', retrieve_proposal, name='retrieve-proposal'),
    path('proposals/<int:proposal_id>/export-json/', export_proposal_json, name='export-proposal-json'),
    path('proposals/<int:proposal_id>/update-from-json/', update_proposal_from_json, name='update-proposal-from-json'),
    path('proposals/<int:proposal_id>/update/', update_proposal, name='update-proposal'),
    path('proposals/<int:proposal_id>/delete/', delete_proposal, name='delete-proposal'),
    path('proposals/<int:proposal_id>/duplicate/', duplicate_proposal, name='duplicate-proposal'),
    path('proposals/<int:proposal_id>/send/', send_proposal, name='send-proposal'),
    path('proposals/<int:proposal_id>/send-multi/', send_multi_proposal, name='send-multi-proposal'),
    path('proposals/<int:proposal_id>/email-preview/', preview_proposal_email, name='preview-proposal-email'),
    path('proposals/<int:proposal_id>/resend/', resend_proposal, name='resend-proposal'),
    path('proposals/<int:proposal_id>/toggle-active/', toggle_proposal_active, name='toggle-proposal-active'),
    path('proposals/<int:proposal_id>/update-status/', update_proposal_status, name='update-proposal-status'),
    path('proposals/<int:proposal_id>/launch-to-platform/', launch_to_platform, name='launch-to-platform'),
    path('proposals/<int:proposal_id>/scorecard/', proposal_scorecard, name='proposal-scorecard'),
    path('proposals/<int:proposal_id>/reorder-sections/', bulk_reorder_sections, name='reorder-sections'),
    path('proposals/<int:proposal_id>/analytics/', retrieve_proposal_analytics, name='proposal-analytics'),
    path('proposals/<int:proposal_id>/analytics/csv/', export_proposal_analytics_csv, name='proposal-analytics-csv'),
    path(
        'proposals/<int:proposal_id>/notifications/first-view/retry/',
        retry_first_view_notification,
        name='retry-first-view-notification',
    ),
    path('proposals/dashboard/', proposal_dashboard, name='proposal-dashboard'),
    path('proposals/clients/', list_clients, name='list-clients'),

    # Proposals — client profiles (real UserProfile entities, replaces grouped list_clients)
    path('proposals/client-profiles/', list_proposal_clients, name='list-proposal-clients'),
    path('proposals/client-profiles/search/', search_proposal_clients, name='search-proposal-clients'),
    path('proposals/client-profiles/status-counts/', proposal_client_status_counts, name='proposal-client-status-counts'),
    path('proposals/client-profiles/create/', create_proposal_client, name='create-proposal-client'),
    path('proposals/client-profiles/<int:client_id>/', retrieve_proposal_client, name='retrieve-proposal-client'),
    path('proposals/client-profiles/<int:client_id>/update/', update_proposal_client, name='update-proposal-client'),
    path('proposals/client-profiles/<int:client_id>/delete/', delete_proposal_client, name='delete-proposal-client'),
    path('proposals/client-profiles/<int:client_id>/archive-preview/', preview_client_archive, name='preview-client-archive'),
    path('proposals/client-profiles/<int:client_id>/archive/', archive_proposal_client, name='archive-proposal-client'),
    path('proposals/client-profiles/<int:client_id>/unarchive/', unarchive_proposal_client, name='unarchive-proposal-client'),
    # The client's email history. Nested under the client on purpose: the
    # scope is what authorizes the row.
    path('proposals/client-profiles/<int:client_id>/emails/', list_client_emails, name='list-client-emails'),
    path('proposals/client-profiles/<int:client_id>/emails/<int:log_id>/body/', client_email_body, name='client-email-body'),
    path('proposals/client-profiles/<int:client_id>/emails/<int:log_id>/retry/', retry_client_email, name='retry-client-email'),
    path('proposals/alerts/', proposal_alerts, name='proposal-alerts'),
    path('proposals/alerts/create/', create_proposal_alert, name='create-proposal-alert'),
    path('proposals/alerts/<int:alert_id>/dismiss/', dismiss_proposal_alert, name='dismiss-proposal-alert'),
    path('proposals/<int:proposal_id>/log-activity/', log_activity, name='log-activity'),
    path('proposals/bulk-action/', bulk_action, name='bulk-action'),

    # Proposals — section editing
    path('proposals/<int:proposal_id>/sections/create/', create_proposal_section, name='create-proposal-section'),
    path('proposals/sections/<int:section_id>/update/', update_proposal_section, name='update-proposal-section'),
    path('proposals/sections/<int:section_id>/delete/', delete_proposal_section, name='delete-proposal-section'),
    path('proposals/sections/<int:section_id>/sync-preview/', preview_sync_section, name='section-sync-preview'),
    path('proposals/sections/<int:section_id>/apply-sync/', apply_sync_section, name='section-apply-sync'),

    # Contract & documents — admin
    path('proposals/<int:proposal_id>/contract/save-and-negotiate/', save_contract_and_negotiate, name='save-contract-and-negotiate'),
    path('proposals/<int:proposal_id>/contract/update/', update_contract_params, name='update-contract-params'),
    path('proposals/<int:proposal_id>/contract/modality/', update_contract_modality, name='update-contract-modality'),
    path('proposals/<int:proposal_id>/contract/markdown/', contract_markdown, name='contract-markdown'),
    path('proposals/<int:proposal_id>/formalization/markdown/<str:kind>/', formalization_markdown, name='formalization-markdown'),
    path('proposals/<int:proposal_id>/documents/<int:doc_id>/markdown/', attachment_markdown, name='proposal-attachment-markdown'),
    path('proposals/<int:proposal_id>/documents/<int:doc_id>/download/', attachment_download, name='proposal-attachment-download'),
    path('proposals/<int:proposal_id>/contract/pdf/', download_contract_pdf, name='download-contract-pdf'),
    path('proposals/<int:proposal_id>/contract/draft-pdf/', download_draft_contract_pdf, name='download-draft-contract-pdf'),
    path('proposals/<int:proposal_id>/documents/', list_proposal_documents, name='list-proposal-documents'),
    path('proposals/<int:proposal_id>/documents/upload/', upload_proposal_document, name='upload-proposal-document'),
    path('proposals/<int:proposal_id>/documents/send/', send_documents_to_client, name='send-documents-to-client'),
    path('proposals/<int:proposal_id>/discount-offer/send/', send_discount_offer, name='send-discount-offer'),
    path('proposals/<int:proposal_id>/documents/<int:doc_id>/delete/', delete_proposal_document, name='delete-proposal-document'),

    # Branded email — admin
    path('proposals/<int:proposal_id>/branded-email/send/', send_branded_email, name='send-branded-email'),
    path('proposals/<int:proposal_id>/branded-email/defaults/', get_branded_email_defaults, name='branded-email-defaults'),
    path('proposals/<int:proposal_id>/branded-email/history/', list_branded_emails, name='list-branded-emails'),

    # Proposal email — admin (logged as activity)
    path('proposals/<int:proposal_id>/proposal-email/send/', send_proposal_email, name='send-proposal-email'),
    path('proposals/<int:proposal_id>/proposal-email/defaults/', get_proposal_email_defaults, name='proposal-email-defaults'),
    path('proposals/<int:proposal_id>/proposal-email/history/', list_proposal_emails, name='list-proposal-emails'),
    path('proposals/<int:proposal_id>/proposal-email/markdown-attachment/', generate_email_markdown_attachment, name='generate-email-markdown-attachment'),

    # Project schedule (Cronograma admin tab)
    path('proposals/<int:proposal_id>/stages/<str:stage_key>/', update_project_stage, name='update-project-stage'),
    path('proposals/<int:proposal_id>/stages/<str:stage_key>/complete/', complete_project_stage, name='complete-project-stage'),

    path('proposals/company-settings/', get_company_settings, name='get-company-settings'),
    path('proposals/contract-template/default/', get_default_contract_template, name='get-default-contract-template'),

    # Proposals — default config
    path('proposals/defaults/', proposal_defaults, name='proposal-defaults'),
    path('proposals/defaults/reset/', reset_proposal_defaults, name='reset-proposal-defaults'),

    # Email deliverability
    path('email-deliverability/', email_deliverability_dashboard, name='email-deliverability-dashboard'),

    # Email templates
    path('email-templates/', email_template_list, name='email-template-list'),
    path('email-templates/<str:template_key>/', email_template_detail, name='email-template-detail'),
    path('email-templates/<str:template_key>/preview/', email_template_preview, name='email-template-preview'),
    path('email-templates/<str:template_key>/reset/', email_template_reset, name='email-template-reset'),

    # Blog — admin CRUD (must come before slug catch-all)
    path('blog/admin/', list_admin_blog_posts, name='list-admin-blog-posts'),
    path('blog/admin/create/', create_blog_post, name='create-blog-post'),
    path('blog/admin/create-from-json/', create_blog_post_from_json, name='create-blog-post-from-json'),
    path('blog/admin/json-template/', get_blog_json_template, name='blog-json-template'),
    path('blog/admin/<int:post_id>/detail/', retrieve_admin_blog_post, name='retrieve-admin-blog-post'),
    path('blog/admin/<int:post_id>/update/', update_blog_post, name='update-blog-post'),
    path('blog/admin/<int:post_id>/delete/', delete_blog_post, name='delete-blog-post'),
    path('blog/admin/<int:post_id>/duplicate/', duplicate_blog_post, name='duplicate-blog-post'),
    path('blog/admin/<int:post_id>/upload-cover/', upload_blog_cover_image, name='upload-blog-cover-image'),
    path('blog/admin/calendar/', blog_calendar, name='blog-calendar'),

    # MCP (Model Context Protocol) — token-authenticated remote connectors.
    # Both slash variants: a POST to the unslashed URL must not fall through
    # to the SPA catch-all (403 CSRF) — connector URLs get hand-copied and
    # the trailing slash is the first thing that gets lost.
    path('mcp/<slug:slug>/<str:token>/', mcp_endpoint, name='mcp-endpoint'),
    path('mcp/<slug:slug>/<str:token>', mcp_endpoint, name='mcp-endpoint-noslash'),
    path('mcp/<slug:slug>/', mcp_endpoint, name='mcp-bearer-endpoint'),
    path('mcp/<slug:slug>', mcp_endpoint, name='mcp-bearer-endpoint-noslash'),
    path(
        'mcp-uploads/<uuid:upload_id>/<str:signature>/',
        mcp_signed_upload,
        name='mcp-signed-upload',
    ),
    path(
        'mcp-assets/<uuid:asset_id>/<str:signature>/',
        mcp_signed_asset,
        name='mcp-signed-asset',
    ),
    path('mcp-connectors/', list_mcp_connectors, name='list-mcp-connectors'),
    path('mcp-connectors/<slug:slug>/', update_mcp_connector, name='update-mcp-connector'),
    path('mcp-connectors/<slug:slug>/generate-token/', generate_mcp_connector_token, name='generate-mcp-connector-token'),
    path('mcp-connectors/<slug:slug>/credentials/', create_mcp_credential, name='create-mcp-credential'),
    path('mcp-connectors/<slug:slug>/credentials/<int:credential_id>/', mcp_credential_detail, name='mcp-credential-detail'),
    path('mcp-connectors/<slug:slug>/credentials/<int:credential_id>/rotate/', rotate_mcp_credential, name='rotate-mcp-credential'),
    path('blog/admin/<int:post_id>/publish-linkedin/', publish_to_linkedin, name='publish-to-linkedin'),

    # LinkedIn OAuth
    path('linkedin/auth-url/', linkedin_auth_url, name='linkedin-auth-url'),
    path('linkedin/callback/', linkedin_callback, name='linkedin-callback'),
    path('linkedin/status/', linkedin_status, name='linkedin-status'),

    # Freeform LinkedIn posts (panel module)
    path('linkedin/posts/', list_linkedin_posts, name='list-linkedin-posts'),
    path('linkedin/posts/create/', create_linkedin_post, name='create-linkedin-post'),
    path('linkedin/posts/<int:post_id>/update/', update_linkedin_post, name='update-linkedin-post'),
    path('linkedin/posts/<int:post_id>/delete/', delete_linkedin_post, name='delete-linkedin-post'),
    path('linkedin/posts/<int:post_id>/publish/', publish_linkedin_post, name='publish-linkedin-post'),

    # Blog — public
    path('blog/', list_blog_posts, name='list-blog-posts'),
    path('blog/sitemap-data/', blog_sitemap_data, name='blog-sitemap-data'),
    path('blog/<slug:slug>/', retrieve_blog_post, name='retrieve-blog-post'),

    # ── Standalone emails (generic branded, not proposal-tied) ────
    path('emails/send/', send_standalone_email, name='send-standalone-email'),
    path('emails/preview/', preview_composed_email, name='preview-composed-email'),
    path('emails/defaults/', standalone_email_defaults, name='standalone-email-defaults'),
    path('emails/history/', list_standalone_emails, name='list-standalone-emails'),
    path(
        'emails/history/<int:log_id>/body/', standalone_email_body,
        name='standalone-email-body',
    ),
    path(
        'emails/history/<int:log_id>/attachments/<int:attachment_id>/',
        standalone_email_attachment,
        name='standalone-email-attachment',
    ),
    path(
        'emails/history/<int:log_id>/resend/',
        resend_standalone_email,
        name='resend-standalone-email',
    ),
    path(
        'emails/copy-recipients/', client_email_copy_recipients,
        name='client-email-copy-recipients',
    ),
    path(
        'emails/copy-recipients/<int:recipient_id>/',
        client_email_copy_recipient_detail,
        name='client-email-copy-recipient-detail',
    ),

    # ── Client communications registry ────────────────────────────
    path('communications/folders/', communication_folders, name='communication-folders'),
    path('communications/folders/<int:folder_id>/', communication_folder_detail, name='communication-folder-detail'),
    path('communications/threads/', communication_threads, name='communication-threads'),
    path(
        'communications/threads/tab-counts/',
        communication_thread_tab_counts,
        name='communication-thread-tab-counts',
    ),
    path(
        'communications/threads/<int:thread_id>/',
        communication_thread_detail,
        name='communication-thread-detail',
    ),
    path(
        'communications/threads/<int:thread_id>/close/',
        close_communication_thread,
        name='close-communication-thread',
    ),
    path(
        'communications/threads/<int:thread_id>/reopen/',
        reopen_communication_thread,
        name='reopen-communication-thread',
    ),
    path(
        'communications/threads/<int:thread_id>/archive/',
        archive_communication_thread,
        name='archive-communication-thread',
    ),
    path(
        'communications/threads/<int:thread_id>/unarchive/',
        unarchive_communication_thread,
        name='unarchive-communication-thread',
    ),
    path(
        'communications/threads/<int:thread_id>/messages/',
        communication_thread_messages,
        name='communication-thread-messages',
    ),
    path(
        'communications/messages/<int:message_id>/',
        communication_message_detail,
        name='communication-message-detail',
    ),
    path(
        'communications/messages/<int:message_id>/mark-sent/',
        mark_communication_message_sent,
        name='mark-communication-message-sent',
    ),
    path(
        'communications/messages/<int:message_id>/void/',
        void_communication_message,
        name='void-communication-message',
    ),
    path(
        'communications/messages/<int:message_id>/correct-date/',
        correct_communication_message_date,
        name='correct-communication-message-date',
    ),

    # ── Documents ──────────────────────────────────────────────────
    path('documents/', list_documents, name='list-documents'),
    path('documents/browse/', browse_documents, name='browse-documents'),
    path('documents/counts/', document_counts, name='document-counts'),
    path('documents/navigation/', document_navigation, name='document-navigation'),
    path('documents/folder-client-suggestion/', suggest_folder_client, name='document-folder-client-suggestion'),
    path('documents/create/', create_document, name='create-document'),
    path('documents/create-from-markdown/', create_document_from_markdown, name='create-document-from-markdown'),
    path('documents/upload-markdown/', upload_document_markdown, name='upload-document-markdown'),
    path('documents/<int:document_id>/detail/', retrieve_document, name='retrieve-document'),
    path(
        'documents/<int:document_id>/thread/',
        document_thread_detail,
        name='document-thread-detail',
    ),
    path('documents/move/', move_document_batch, name='move-documents'),
    path('documents/<int:document_id>/update/', update_document, name='update-document'),
    path('documents/<int:document_id>/delete/', delete_document, name='delete-document'),
    path('documents/<int:document_id>/archive/', archive_document, name='archive-document'),
    path('documents/<int:document_id>/unarchive/', unarchive_document, name='unarchive-document'),
    path('documents/<int:document_id>/duplicate/', duplicate_document, name='duplicate-document'),
    path('documents/<int:document_id>/pdf/', download_document_pdf, name='download-document-pdf'),
    path(
        'documents/<int:document_id>/email-usage/',
        document_email_usage,
        name='document-email-usage',
    ),
    path(
        'documents/<int:document_id>/state-episodes/',
        open_document_state,
        name='open-document-state',
    ),
    path(
        'documents/<int:document_id>/state-episodes/<int:episode_id>/close/',
        close_document_state,
        name='close-document-state',
    ),
    path(
        'documents/<int:document_id>/state-episodes/<int:episode_id>/opened-at/',
        correct_document_state_opening,
        name='correct-document-state-opening',
    ),
    path(
        'documents/<int:document_id>/state-history/',
        document_state_history,
        name='document-state-history',
    ),
    path(
        'documents/<int:document_id>/notes/',
        document_notes,
        name='document-notes',
    ),
    path(
        'documents/<int:document_id>/notes/events/',
        document_note_events,
        name='document-note-events',
    ),
    path(
        'documents/<int:document_id>/notes/bulk-delete/',
        bulk_delete_document_notes,
        name='bulk-delete-document-notes',
    ),
    path(
        'documents/<int:document_id>/notes/<int:note_id>/',
        update_document_note,
        name='update-document-note',
    ),
    path(
        'documents/<int:document_id>/notes/<int:note_id>/finish/',
        finish_document_note,
        name='finish-document-note',
    ),
    path(
        'documents/<int:document_id>/notes/<int:note_id>/restore/',
        restore_document_note,
        name='restore-document-note',
    ),
    path(
        'documents/<int:document_id>/communications/',
        document_communication_usage,
        name='document-communication-usage',
    ),
    path(
        'document-threads/candidates/',
        document_thread_candidates,
        name='document-thread-candidates',
    ),
    path('document-threads/', create_thread, name='create-document-thread'),
    path(
        'document-threads/<int:thread_id>/',
        update_or_delete_thread,
        name='update-or-delete-document-thread',
    ),

    # Document folders (flat, inline-managed)
    path('document-folders/', list_document_folders, name='list-document-folders'),
    path(
        'document-folders/project-readiness/',
        project_folder_readiness,
        name='project-folder-readiness',
    ),
    path('document-folders/create/', create_document_folder, name='create-document-folder'),
    path('document-folders/reorder/', reorder_document_folders, name='reorder-document-folders'),
    path('document-folders/<int:folder_id>/update/', update_document_folder, name='update-document-folder'),
    path('document-folders/<int:folder_id>/delete/', delete_document_folder, name='delete-document-folder'),
    path('document-folders/<int:folder_id>/archive/', archive_document_folder, name='archive-document-folder'),
    path('document-folders/<int:folder_id>/unarchive/', unarchive_document_folder, name='unarchive-document-folder'),
    path('document-folders/<int:folder_id>/change-client/preview/', preview_document_folder_client_change, name='preview-document-folder-client-change'),
    path('document-folders/<int:folder_id>/change-client/', change_document_folder_client, name='change-document-folder-client'),

    # Kanban tasks (admin panel)
    path('tasks/', list_tasks, name='list-tasks'),
    path('tasks/create/', create_task, name='create-task'),
    path('tasks/assignees/', list_task_assignees, name='list-task-assignees'),
    path('tasks/archived/', list_archived_tasks, name='list-archived-tasks'),
    path('tasks/<int:task_id>/update/', update_task, name='update-task'),
    path('tasks/<int:task_id>/reorder/', reorder_task, name='reorder-task'),
    path('tasks/<int:task_id>/delete/', delete_task, name='delete-task'),
    path('tasks/<int:task_id>/duplicate/', duplicate_task, name='duplicate-task'),
    path('tasks/<int:task_id>/archive/', archive_task, name='archive-task'),
    path('tasks/<int:task_id>/unarchive/', unarchive_task, name='unarchive-task'),
    path('tasks/<int:task_id>/comments/', list_task_comments, name='list-task-comments'),
    path('tasks/<int:task_id>/comments/create/', create_task_comment, name='create-task-comment'),
    path('tasks/<int:task_id>/comments/<int:comment_id>/delete/', delete_task_comment, name='delete-task-comment'),
    path('tasks/<int:task_id>/alerts/', list_task_alerts, name='list-task-alerts'),
    path('tasks/<int:task_id>/alerts/create/', create_task_alert, name='create-task-alert'),
    path('tasks/<int:task_id>/alerts/<int:alert_id>/delete/', delete_task_alert, name='delete-task-alert'),

    # Document tags (M2M, inline-managed)
    path('document-tags/', list_document_tags, name='list-document-tags'),
    path('document-tags/create/', create_document_tag, name='create-document-tag'),
    path('document-tags/<int:tag_id>/update/', update_document_tag, name='update-document-tag'),
    path('document-tags/<int:tag_id>/delete/', delete_document_tag, name='delete-document-tag'),
    path('document-state-groups/', document_state_groups, name='document-state-groups'),
    path(
        'document-state-groups/<int:group_id>/',
        document_state_group_detail,
        name='document-state-group-detail',
    ),
    path('document-states/', document_states, name='document-states'),
    path(
        'document-states/suggestions/',
        document_state_suggestions,
        name='document-state-suggestions',
    ),
    path(
        'document-states/<int:state_id>/',
        update_document_state,
        name='update-document-state',
    ),
    path(
        'document-states/<int:state_id>/retire/',
        retire_document_state,
        name='retire-document-state',
    ),
    path(
        'document-states/<int:state_id>/merge/',
        merge_document_state,
        name='merge-document-state',
    ),

    # ── Web App Diagnostics ───────────────────────────────────────
    # Public (UUID-based)
    path('diagnostics/public/<uuid:diagnostic_uuid>/', retrieve_public_diagnostic, name='retrieve-public-diagnostic'),
    path('diagnostics/public/by-slug/<slug:diagnostic_slug>/', retrieve_public_diagnostic_by_slug, name='retrieve-public-diagnostic-by-slug'),
    path('diagnostics/public/<uuid:diagnostic_uuid>/track/', track_public_diagnostic, name='track-public-diagnostic'),
    path('diagnostics/public/<uuid:diagnostic_uuid>/track-section/', track_diagnostic_section_view, name='track-diagnostic-section-view'),
    path('diagnostics/public/<uuid:diagnostic_uuid>/respond/', respond_public_diagnostic, name='respond-public-diagnostic'),
    path('diagnostics/public/<uuid:diagnostic_uuid>/pdf/', download_public_diagnostic_pdf, name='download-public-diagnostic-pdf'),

    # Admin CRUD
    path('diagnostics/', list_diagnostics, name='list-diagnostics'),
    path('diagnostics/create/', create_diagnostic, name='create-diagnostic'),
    path('diagnostics/bulk-action/', bulk_diagnostic_action, name='bulk-diagnostic-action'),
    path('diagnostics/<int:diagnostic_id>/detail/', retrieve_diagnostic, name='retrieve-diagnostic'),
    path('diagnostics/<int:diagnostic_id>/update/', update_diagnostic, name='update-diagnostic'),
    path('diagnostics/<int:diagnostic_id>/delete/', delete_diagnostic, name='delete-diagnostic'),
    path('diagnostics/<int:diagnostic_id>/scorecard/', diagnostic_scorecard, name='diagnostic-scorecard'),
    path('diagnostics/<int:diagnostic_id>/send-initial/', send_initial, name='send-initial-diagnostic'),
    path('diagnostics/<int:diagnostic_id>/mark-in-analysis/', mark_in_analysis, name='mark-in-analysis-diagnostic'),
    path('diagnostics/<int:diagnostic_id>/send-final/', send_final, name='send-final-diagnostic'),

    # Sections (JSON-driven content)
    path('diagnostics/<int:diagnostic_id>/sections/', list_diagnostic_sections, name='list-diagnostic-sections'),
    path('diagnostics/<int:diagnostic_id>/sections/bulk-update/', bulk_update_diagnostic_sections, name='bulk-update-diagnostic-sections'),
    path('diagnostics/<int:diagnostic_id>/sections/<int:section_id>/update/', update_diagnostic_section, name='update-diagnostic-section'),
    path('diagnostics/<int:diagnostic_id>/sections/<int:section_id>/reset/', reset_diagnostic_section, name='reset-diagnostic-section'),

    # Activity (change log)
    path('diagnostics/<int:diagnostic_id>/activity/', list_diagnostic_activity, name='list-diagnostic-activity'),
    path('diagnostics/<int:diagnostic_id>/activity/create/', create_diagnostic_activity, name='create-diagnostic-activity'),

    # Analytics
    path('diagnostics/<int:diagnostic_id>/analytics/', diagnostic_analytics, name='diagnostic-analytics'),
    path('diagnostics/<int:diagnostic_id>/analytics/csv/', export_diagnostic_analytics_csv, name='diagnostic-analytics-csv'),

    # Attachments (files uploaded to a diagnostic)
    path('diagnostics/<int:diagnostic_id>/attachments/', list_diagnostic_attachments, name='list-diagnostic-attachments'),
    path('diagnostics/<int:diagnostic_id>/attachments/upload/', upload_diagnostic_attachment, name='upload-diagnostic-attachment'),
    path('diagnostics/<int:diagnostic_id>/attachments/send/', send_diagnostic_attachments, name='send-diagnostic-attachments'),
    path('diagnostics/<int:diagnostic_id>/attachments/<int:attachment_id>/delete/', delete_diagnostic_attachment, name='delete-diagnostic-attachment'),

    # Acuerdo de Confidencialidad (NDA)
    path('diagnostics/<int:diagnostic_id>/confidentiality/params/', update_confidentiality_params, name='diagnostic-update-confidentiality-params'),
    path('diagnostics/<int:diagnostic_id>/confidentiality/generate/', generate_confidentiality_pdf_view, name='diagnostic-generate-confidentiality'),
    path('diagnostics/<int:diagnostic_id>/confidentiality/pdf/', download_confidentiality_pdf, name='diagnostic-download-confidentiality'),
    path('diagnostics/<int:diagnostic_id>/confidentiality/draft-pdf/', download_draft_confidentiality_pdf, name='diagnostic-download-draft-confidentiality'),

    # Email composer (history + send)
    path('diagnostics/<int:diagnostic_id>/email/send/', send_diagnostic_email, name='send-diagnostic-email'),
    path('diagnostics/<int:diagnostic_id>/email/defaults/', get_diagnostic_email_defaults, name='diagnostic-email-defaults'),
    path('diagnostics/<int:diagnostic_id>/email/history/', list_diagnostic_emails, name='list-diagnostic-emails'),
    path('diagnostics/<int:diagnostic_id>/email/markdown-attachment/', generate_diagnostic_email_markdown_attachment, name='generate-diagnostic-email-markdown-attachment'),

    # Diagnostics — default config (admin)
    path('diagnostics/defaults/', diagnostic_defaults, name='diagnostic-defaults'),
    path('diagnostics/defaults/reset/', reset_diagnostic_defaults, name='reset-diagnostic-defaults'),

    # Diagnostic markdown templates (static .md files exposed for sellers)
    path('diagnostic-templates/', list_diagnostic_templates, name='list-diagnostic-templates'),
    path('diagnostic-templates/<slug:slug>/', get_diagnostic_template, name='get-diagnostic-template'),

    # Portfolio — admin CRUD (must come before slug catch-all)
    path('portfolio/admin/', list_admin_portfolio_works, name='list-admin-portfolio-works'),
    path('portfolio/admin/create/', create_portfolio_work, name='create-portfolio-work'),
    path('portfolio/admin/create-from-json/', create_portfolio_work_from_json, name='create-portfolio-work-from-json'),
    path('portfolio/admin/json-template/', get_portfolio_json_template, name='portfolio-json-template'),
    path('portfolio/admin/<int:work_id>/detail/', retrieve_admin_portfolio_work, name='retrieve-admin-portfolio-work'),
    path('portfolio/admin/<int:work_id>/update/', update_portfolio_work, name='update-portfolio-work'),
    path('portfolio/admin/<int:work_id>/delete/', delete_portfolio_work, name='delete-portfolio-work'),
    path('portfolio/admin/<int:work_id>/duplicate/', duplicate_portfolio_work, name='duplicate-portfolio-work'),

    # QR Cards — admin CRUD
    path('qr-cards/admin/', list_admin_qr_cards, name='list-admin-qr-cards'),
    path('qr-cards/admin/create/', create_qr_card, name='create-qr-card'),
    path('qr-cards/admin/<uuid:card_id>/update/', update_qr_card, name='update-qr-card'),
    path('qr-cards/admin/<uuid:card_id>/delete/', delete_qr_card, name='delete-qr-card'),

    # Linktrees (admin CRUD + public by handle)
    path('linktrees/admin/', list_admin_linktrees, name='list-admin-linktrees'),
    path('linktrees/admin/create/', create_linktree, name='create-linktree'),
    path('linktrees/admin/<uuid:linktree_id>/', retrieve_admin_linktree, name='retrieve-admin-linktree'),
    path('linktrees/admin/<uuid:linktree_id>/update/', update_linktree, name='update-linktree'),
    path('linktrees/admin/<uuid:linktree_id>/delete/', delete_linktree, name='delete-linktree'),
    path('linktrees/admin/<uuid:linktree_id>/avatar/', upload_linktree_avatar, name='upload-linktree-avatar'),
    path('linktrees/admin/<uuid:linktree_id>/logo/', upload_linktree_logo, name='upload-linktree-logo'),
    path('linktrees/admin/<uuid:linktree_id>/templates/', lt_templates.template_library, name='linktree-template-library'),
    path('linktrees/admin/<uuid:linktree_id>/templates/reset/', lt_templates.reset_template, name='linktree-template-reset'),
    path('linktrees/admin/<uuid:linktree_id>/templates/library/<uuid:template_id>/share/', lt_templates.share_template, name='linktree-template-share'),
    path('linktrees/admin/<uuid:linktree_id>/templates/<uuid:version_id>/publish/', lt_templates.publish_template, name='linktree-template-publish'),
    path('linktrees/admin/<uuid:linktree_id>/templates/<uuid:version_id>/assets/<slug:key>/', lt_templates.template_asset_override, name='linktree-template-override'),
    path('linktrees/admin/<uuid:linktree_id>/assets/', lt_templates.linktree_assets, name='linktree-assets'),
    path('linktrees/admin/<uuid:linktree_id>/assets/<slug:key>/', lt_templates.linktree_asset, name='linktree-asset'),
    path('linktrees/admin/<uuid:linktree_id>/templates/<uuid:version_id>/preview/', lt_templates.template_preview, name='linktree-template-preview'),
    path('linktrees/admin/<uuid:linktree_id>/templates/<uuid:version_id>/screenshots/<int:width>/', lt_templates.template_screenshot, name='linktree-template-screenshot'),
    path('linktrees/admin/<uuid:linktree_id>/templates/<uuid:version_id>/asset-preview/<slug:key>/', lt_templates.template_asset_preview, name='linktree-template-asset-preview'),
    path('linktrees/templates/<uuid:version_id>/assets/<slug:key>/<int:density>/', lt_templates.public_template_asset, name='linktree-template-public-asset'),
    path('linktrees/templates/<uuid:version_id>/click/', lt_templates.template_click, name='linktree-template-click'),
    path('linktrees/public/<str:handle>/manifest.webmanifest', lt_templates.template_manifest, name='linktree-template-manifest'),
    path('linktrees/public/<str:handle>/template/', lt_templates.public_template, name='linktree-template-public'),
    path('linktrees/public/<str:handle>/', public_linktree, name='public-linktree'),

    # Hour packages — admin catalog CRUD (per-nationality pricing)
    path('hour-packages/admin/', list_admin_hour_packages, name='list-admin-hour-packages'),
    path('hour-packages/admin/create/', create_hour_package, name='create-hour-package'),
    path('hour-packages/admin/<int:package_id>/detail/', retrieve_admin_hour_package, name='retrieve-admin-hour-package'),
    path('hour-packages/admin/<int:package_id>/update/', update_hour_package, name='update-hour-package'),
    path('hour-packages/admin/<int:package_id>/delete/', delete_hour_package, name='delete-hour-package'),
    path('hour-packages/admin/settings/', get_hour_package_settings, name='hour-package-settings'),
    path('hour-packages/admin/settings/update/', update_hour_package_settings, name='update-hour-package-settings'),
    path('hour-packages/admin/restore-defaults/', restore_default_hour_packages, name='restore-default-hour-packages'),

    # View map — admin panel settings (singleton)
    path('view-map/admin/settings/', get_view_map_settings, name='view-map-settings'),
    path('view-map/admin/settings/update/', update_view_map_settings, name='update-view-map-settings'),
    path('portfolio/admin/<int:work_id>/upload-cover/', upload_portfolio_cover_image, name='upload-portfolio-cover-image'),

    # Portfolio — public
    path('portfolio/', list_portfolio_works, name='list-portfolio-works-public'),
    path('portfolio/sitemap-data/', portfolio_sitemap_data, name='portfolio-sitemap-data'),
    path('portfolio/<slug:slug>/', retrieve_portfolio_work, name='retrieve-portfolio-work'),

    # ── Accounting module (panel, superuser-only) ──────────────────
    path('accounting/dashboard/', accounting_dashboard, name='accounting-dashboard'),
    path('accounting/stats/', accounting_stats, name='accounting-stats'),
    path('accounting/receivables/', accounting_receivables, name='accounting-receivables'),

    path('accounting/incomes/', list_income_records, name='list-income-records'),
    path('accounting/incomes/create/', create_income_record, name='create-income-record'),
    path('accounting/incomes/<int:record_id>/detail/', retrieve_income_detail, name='retrieve-income-detail'),
    path('accounting/incomes/<int:record_id>/settle/', settle_income_record, name='settle-income-record'),
    path('accounting/incomes/<int:record_id>/mute/', mute_income_reminders, name='mute-income-reminders'),
    path('accounting/incomes/<int:record_id>/duplicate-draft/', duplicate_income_draft, name='duplicate-income-draft'),
    path('accounting/incomes/period-suggestion/', suggest_income_period, name='suggest-income-period'),
    path('accounting/incomes/bulk-assign-client/', bulk_assign_income_client, name='bulk-assign-income-client'),
    path('accounting/incomes/bulk-assign-project/', bulk_assign_income_project, name='bulk-assign-income-project'),
    path('accounting/incomes/bulk-settle/', bulk_settle_income_records, name='bulk-settle-income-records'),
    path('accounting/incomes/<int:record_id>/', retrieve_income_record, name='retrieve-income-record'),
    path('accounting/incomes/<int:record_id>/update/', update_income_record, name='update-income-record'),
    path('accounting/incomes/<int:record_id>/delete/', delete_income_record, name='delete-income-record'),

    path('accounting/expenses/', list_expense_records, name='list-expense-records'),
    path('accounting/expenses/create/', create_expense_record, name='create-expense-record'),
    path('accounting/expenses/<int:record_id>/', retrieve_expense_record, name='retrieve-expense-record'),
    path('accounting/expenses/<int:record_id>/update/', update_expense_record, name='update-expense-record'),
    path('accounting/expenses/<int:record_id>/delete/', delete_expense_record, name='delete-expense-record'),

    path('accounting/hostings/', list_hosting_records, name='list-hosting-records'),
    path('accounting/hostings/create/', create_hosting_record, name='create-hosting-record'),
    path('accounting/hostings/<int:record_id>/', retrieve_hosting_record, name='retrieve-hosting-record'),
    path('accounting/hostings/<int:record_id>/update/', update_hosting_record, name='update-hosting-record'),
    path('accounting/hostings/<int:record_id>/delete/', delete_hosting_record, name='delete-hosting-record'),
    path(
        'accounting/hostings/<int:record_id>/send-collection-account/',
        send_hosting_collection_account,
        name='send-hosting-collection-account',
    ),
    path('accounting/hostings/bulk-assign-client/', bulk_assign_hosting_client, name='bulk-assign-hosting-client'),
    path('accounting/hostings/bulk-assign-project/', bulk_assign_hosting_project, name='bulk-assign-hosting-project'),
    path('accounting/hostings/<int:record_id>/cycles/', list_hosting_cycles, name='list-hosting-cycles'),
    path('accounting/hostings/<int:record_id>/cycles/create/', create_hosting_cycle, name='create-hosting-cycle'),
    path('accounting/hostings/<int:record_id>/cycles/<int:cycle_id>/delete/', delete_hosting_cycle, name='delete-hosting-cycle'),

    path('accounting/collection-accounts/', list_collection_accounts, name='list-collection-accounts'),
    path('accounting/collection-accounts/create/', create_collection_account_view, name='create-collection-account'),
    path('accounting/collection-accounts/preview/', preview_collection_account_view, name='preview-collection-account'),
    # No trailing slash: the last segment has to BE the consecutivo, because a
    # viewer that ignores Content-Disposition names the download after the URL.
    path('accounting/collection-accounts/preview/<str:token>/<str:filename>', collection_account_preview_pdf_view, name='collection-account-preview-pdf'),
    path('accounting/collection-accounts/next-number/', collection_account_next_number_view, name='collection-account-next-number'),
    path('accounting/collection-accounts/<int:doc_id>/', retrieve_collection_account, name='retrieve-collection-account'),
    path('accounting/projects/', list_client_projects, name='list-client-projects'),
    path('accounting/collection-accounts/<int:doc_id>/pdf/', collection_account_pdf, name='collection-account-pdf'),
    path('accounting/collection-accounts/<int:doc_id>/resend/', resend_collection_account, name='resend-collection-account'),
    path('accounting/collection-accounts/<int:doc_id>/mark-paid/', mark_collection_account_paid_view, name='mark-collection-account-paid'),
    path('accounting/collection-accounts/<int:doc_id>/cancel/', cancel_collection_account_view, name='cancel-collection-account'),
    path('accounting/collection-accounts/<int:doc_id>/delete/', delete_collection_account_view, name='delete-collection-account'),

    path('accounting/pocket/', list_pocket_movements, name='list-pocket-movements'),
    path('accounting/pocket/create/', create_pocket_movement, name='create-pocket-movement'),
    path('accounting/pocket/<int:record_id>/', retrieve_pocket_movement, name='retrieve-pocket-movement'),
    path('accounting/pocket/<int:record_id>/update/', update_pocket_movement, name='update-pocket-movement'),
    path('accounting/pocket/<int:record_id>/delete/', delete_pocket_movement, name='delete-pocket-movement'),

    path('accounting/recurring/', list_recurring_payments, name='list-recurring-payments'),
    path('accounting/recurring/create/', create_recurring_payment, name='create-recurring-payment'),
    path('accounting/recurring/bulk-action/', bulk_recurring_payment_action, name='bulk-recurring-payment-action'),
    path('accounting/recurring/reorder/', reorder_recurring_payments, name='reorder-recurring-payments'),
    path('accounting/recurring/<int:record_id>/', retrieve_recurring_payment, name='retrieve-recurring-payment'),
    path('accounting/recurring/<int:record_id>/duplicate-draft/', duplicate_recurring_payment_draft, name='duplicate-recurring-payment-draft'),
    path('accounting/recurring/<int:record_id>/update/', update_recurring_payment, name='update-recurring-payment'),
    path('accounting/recurring/<int:record_id>/state/', set_recurring_payment_state, name='set-recurring-payment-state'),
    path('accounting/recurring/<int:record_id>/archive/', archive_recurring_payment, name='archive-recurring-payment'),
    path('accounting/recurring/<int:record_id>/restore/', restore_recurring_payment, name='restore-recurring-payment'),
    path('accounting/recurring/<int:record_id>/reminders/mute/', mute_recurring_payment_reminders, name='mute-recurring-payment-reminders'),
    path('accounting/recurring/<int:record_id>/delete/', delete_recurring_payment, name='delete-recurring-payment'),

    path('accounting/recurring-categories/', list_recurring_categories, name='list-recurring-categories'),
    path('accounting/recurring-categories/create/', create_recurring_category, name='create-recurring-category'),
    path('accounting/recurring-categories/reorder/', reorder_recurring_categories, name='reorder-recurring-categories'),
    path('accounting/recurring-categories/<int:category_id>/update/', update_recurring_category, name='update-recurring-category'),
    path('accounting/recurring-categories/<int:category_id>/delete/', delete_recurring_category, name='delete-recurring-category'),

    path('accounting/ads/', list_ads_spend_records, name='list-ads-spend-records'),
    path('accounting/ads/create/', create_ads_spend_record, name='create-ads-spend-record'),
    path('accounting/ads/<int:record_id>/', retrieve_ads_spend_record, name='retrieve-ads-spend-record'),
    path('accounting/ads/<int:record_id>/update/', update_ads_spend_record, name='update-ads-spend-record'),
    path('accounting/ads/<int:record_id>/delete/', delete_ads_spend_record, name='delete-ads-spend-record'),

    path('accounting/card-snapshots/', list_card_snapshots, name='list-card-snapshots'),
    path('accounting/card-snapshots/create/', create_card_snapshot, name='create-card-snapshot'),
    path('accounting/card-snapshots/<int:record_id>/', retrieve_card_snapshot, name='retrieve-card-snapshot'),
    path('accounting/card-snapshots/<int:record_id>/update/', update_card_snapshot, name='update-card-snapshot'),
    path('accounting/card-snapshots/<int:record_id>/delete/', delete_card_snapshot, name='delete-card-snapshot'),

    path('accounting/credit-cards/', list_credit_cards, name='list-credit-cards'),
    path('accounting/credit-cards/create/', create_credit_card, name='create-credit-card'),
    path('accounting/credit-cards/<int:record_id>/', retrieve_credit_card, name='retrieve-credit-card'),
    path('accounting/credit-cards/<int:record_id>/update/', update_credit_card, name='update-credit-card'),
    path('accounting/credit-cards/<int:record_id>/delete/', delete_credit_card, name='delete-credit-card'),

    path('accounting/statements/', list_statements, name='list-statements'),
    path('accounting/statements/create/', create_statement, name='create-statement'),
    # 'status/' must resolve before '<int:record_id>/'.
    path('accounting/statements/status/', statements_status, name='statements-status'),
    path('accounting/statements/<int:record_id>/', retrieve_statement, name='retrieve-statement'),
    path('accounting/statements/<int:record_id>/update/', update_statement, name='update-statement'),
    path('accounting/statements/<int:record_id>/delete/', delete_statement, name='delete-statement'),
    path('accounting/statements/<int:record_id>/finalize/', finalize_statement, name='finalize-statement'),
    path('accounting/statements/<int:record_id>/reopen/', reopen_statement, name='reopen-statement'),
    path('accounting/statements/<int:record_id>/pdf/upload/', upload_statement_pdf, name='upload-statement-pdf'),
    path('accounting/statements/<int:record_id>/pdf/delete/', delete_statement_pdf, name='delete-statement-pdf'),
    path('accounting/statements/<int:record_id>/transactions/batch/', batch_create_transactions, name='batch-create-statement-transactions'),
    path('accounting/statements/<int:record_id>/transactions/<int:tx_id>/update/', update_statement_transaction, name='update-statement-transaction'),
    path('accounting/statements/<int:record_id>/transactions/<int:tx_id>/delete/', delete_statement_transaction, name='delete-statement-transaction'),

    path('accounting/merchant-aliases/', list_merchant_aliases, name='list-merchant-aliases'),
    path('accounting/merchant-aliases/create/', create_merchant_alias, name='create-merchant-alias'),
    path('accounting/merchant-aliases/learn/', learn_merchant_alias, name='learn-merchant-alias'),
    path('accounting/merchant-aliases/resolve/', resolve_merchant_aliases, name='resolve-merchant-aliases'),
    path('accounting/merchant-aliases/<int:record_id>/update/', update_merchant_alias, name='update-merchant-alias'),
    path('accounting/merchant-aliases/<int:record_id>/delete/', delete_merchant_alias, name='delete-merchant-alias'),

    path('accounting/notification-recipients/', list_notification_recipients, name='list-notification-recipients'),
    path('accounting/notification-recipients/create/', create_notification_recipient, name='create-notification-recipient'),
    path('accounting/notification-recipients/<int:record_id>/', retrieve_notification_recipient, name='retrieve-notification-recipient'),
    path('accounting/notification-recipients/<int:record_id>/update/', update_notification_recipient, name='update-notification-recipient'),
    path('accounting/notification-recipients/<int:record_id>/delete/', delete_notification_recipient, name='delete-notification-recipient'),

    path('accounting/change-logs/', list_accounting_change_logs, name='list-accounting-change-logs'),
    path('accounting/email-log/', list_accounting_email_logs, name='list-accounting-email-log'),
    path('accounting/history/tab-counts/', accounting_history_tab_counts, name='accounting-history-tab-counts'),
    path('accounting/email-log/<int:log_id>/body/', accounting_email_log_body, name='accounting-email-log-body'),
    path('accounting/email-log/<int:log_id>/retry/', retry_accounting_email_log, name='retry-accounting-email-log'),

    path('accounting/settings/', get_accounting_settings, name='get-accounting-settings'),
    path('accounting/settings/update/', update_accounting_settings, name='update-accounting-settings'),

    path('accounting/export/', export_accounting_records, name='export-accounting-records'),
    path('accounting/export/workbook/', export_accounting_workbook, name='export-accounting-workbook'),
]
