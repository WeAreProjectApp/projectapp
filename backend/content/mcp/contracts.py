"""Explicit model-field review contract for every MCP connector.

``read_write`` means the connector can both return and mutate the field (often
through a service-driven action). ``read_only`` means callers can observe it
but the server owns changes. Every omitted field must sit in ``excluded`` with
an explanation; the contract test therefore turns a new model field into a
required MCP review instead of silent drift.
"""
from dataclasses import dataclass


def _names(value):
    return frozenset(value.split())


def _excluded(reason, value):
    return {field: reason for field in value.split()}


@dataclass(frozen=True)
class McpModelContract:
    model_label: str
    read_only: frozenset
    read_write: frozenset
    excluded: dict

    @property
    def classified_fields(self):
        return self.read_only | self.read_write | frozenset(self.excluded)


def _contract(model_label, *, read_only='', read_write='', excluded=None):
    return McpModelContract(
        model_label=model_label,
        read_only=_names(read_only),
        read_write=_names(read_write),
        excluded=excluded or {},
    )


_AUDIT_INTERNAL = 'Identificador de auditoría o integración administrado por el servidor.'
_PANEL_ONLY = 'Configuración avanzada reservada al panel; no forma parte del contrato MCP.'
_COMMERCIAL_DOCUMENT = 'Campo exclusivo de cuentas de cobro; el MCP sólo opera documentos markdown.'
_PLATFORM_PROFILE = 'Dato del perfil de plataforma fuera del alcance del gestor comercial de clientes.'
_AUTOMATION_STATE = 'Estado interno de automatización; se observa por resultados, no se manipula por MCP.'
_DOCUMENT_THREAD_DERIVED_POSITION = (
    'La posición se deriva de la cronología del hilo; el conector envía fechas, '
    'nunca posiciones.'
)


MCP_MODEL_CONTRACTS = {
    'blog': (
        _contract(
            'content.BlogPost',
            read_only='id linkedin_post_id linkedin_published_at created_at updated_at',
            read_write=(
                'title_es title_en slug cover_image cover_image_url '
                'cover_image_credit cover_image_credit_url excerpt_es excerpt_en '
                'content_es content_en content_json_es content_json_en sources '
                'category read_time_minutes is_featured author meta_title_es '
                'meta_title_en meta_description_es meta_description_en '
                'meta_keywords_es meta_keywords_en linkedin_summary_es '
                'linkedin_summary_en is_published published_at'
            ),
        ),
    ),
    'documents': (
        _contract(
            'accounts.Project',
            read_only='id name client current_state',
            excluded=(
                _excluded(
                    'Configuración operativa del proyecto reservada al panel; '
                    'el MCP de Documentos sólo referencia proyectos existentes.',
                    'description status state_review_required progress start_date '
                    'estimated_end_date payment_milestones hosting_tiers '
                    'hosting_start_date production_url staging_url admin_url '
                    'repository_url admin_username',
                )
                | _excluded(
                    'Credencial cifrada del sitio del proyecto: nunca debe salir por MCP.',
                    'admin_password_encrypted',
                )
                | _excluded(_AUDIT_INTERNAL, 'created_at updated_at')
            ),
        ),
        _contract(
            'content.Document',
            read_only='id slug status created_at updated_at tags',
            read_write=(
                'folder project client_user title is_client_visible '
                'content_markdown client_name client_email_subject '
                'client_email_body client_whatsapp_message client_custom_notes '
                'language include_portada include_subportada include_contraportada'
            ),
            excluded=(
                _excluded(_AUDIT_INTERNAL, 'uuid created_by updated_by content_json')
                | _excluded(
                    _COMMERCIAL_DOCUMENT,
                    'document_type deliverable issuer hosting_record income_record '
                    'source_proposal source_version generated_file '
                    'public_number issue_date due_date city currency subtotal '
                    'discount_total tax_total total notes terms_and_conditions '
                    'template_version metadata commercial_status requires_signature '
                    'signed_at signed_by signature_name signature_ip signature_user_agent',
                )
                | _excluded(_PANEL_ONLY, 'cover_type template_style')
                | _excluded(
                    'Los documentos archivados quedan fuera de circulación para el MCP.',
                    'is_archived archived_at archived_via_folder',
                )
            ),
        ),
        _contract(
            'content.DocumentState',
            read_only=(
                'id name description color group system_key catalog '
                'operational_effect'
            ),
            excluded=_excluded(
                'El catálogo de estados se administra en el panel; MCP aplica estados activos.',
                'normalized_name slug order is_active merged_into created_by '
                'updated_by created_at updated_at incompatibilities '
                'show_in_document_manager',
            ),
        ),
        _contract(
            'content.DocumentFolder',
            read_only='id slug managed_project managed_client created_at updated_at created_by creation_source creation_operation',
            read_write='name parent project client_user order',
            excluded=(
                _excluded(_AUTOMATION_STATE, 'system_key')
                | _excluded(
                    'El archivado de carpetas es una cascada reservada al panel.',
                    'is_archived archived_at archived_via_folder',
                )
            ),
        ),
        _contract(
            'content.DocumentStateEpisode',
            read_only='id opened_by closed_by created_at updated_at',
            read_write='document state opened_at closed_at outcome close_note origin',
            excluded=_excluded(
                'El ciclo de proyectos se administra en el panel; el conector '
                'de documentos sólo opera episodios vinculados a documentos.',
                'project',
            ),
        ),
        _contract(
            'content.DocumentNote',
            read_only='id order created_at updated_at',
            read_write=(
                'document episode title content status resolution_note resolved_at '
                'deleted_at'
            ),
            excluded=_excluded(
                _AUDIT_INTERNAL,
                'created_by resolved_by deleted_by created_at_known',
            ),
        ),
        _contract(
            'content.DocumentNoteEvent',
            excluded=_excluded(
                'Bitácora append-only administrada por el servidor; el MCP '
                'observa el resultado de cada acción, no edita eventos.',
                'id document note event_type actor recorded_at details',
            ),
        ),
        _contract(
            'content.DocumentThread',
            read_only='id created_by updated_by created_at updated_at',
            read_write='title',
        ),
        _contract(
            'content.DocumentThreadItem',
            read_only='id linked_by updated_by linked_at updated_at',
            read_write='thread document occurred_on',
            excluded=_excluded(_DOCUMENT_THREAD_DERIVED_POSITION, 'position'),
        ),
    ),
    'clients': (
        _contract(
            'accounts.UserProfile',
            read_only=(
                'id user is_onboarded cedula nit billing_code archived_at '
                'created_at updated_at'
            ),
            read_write='company_name phone',
            excluded=(
                _excluded('El conector siempre opera perfiles con rol cliente.', 'role')
                | _excluded(
                    _PLATFORM_PROFILE,
                    'email_verified email_verified_at date_of_birth gender '
                    'education_level avatar avatar_url theme_color cover_image '
                    'custom_cover_image profile_completed document_navigation_mode',
                )
                | _excluded(_AUDIT_INTERNAL, 'created_by archived_by')
            ),
        ),
    ),
    'tasks': (
        _contract(
            'content.Task',
            read_only='id created_at updated_at',
            read_write=(
                'title description status priority board_type assignee due_date '
                'position is_archived archive_reason'
            ),
            excluded=_excluded(
                _AUTOMATION_STATE,
                'notified_40 notified_70 notified_100 last_overdue_notified_at',
            ),
        ),
        _contract(
            'content.TaskComment',
            read_only='id author created_at',
            read_write='task text',
        ),
        _contract(
            'content.TaskAlert',
            read_only='id sent created_at',
            read_write='task notify_at note',
        ),
    ),
    'accounting': (
        _contract(
            'content.IncomeRecord',
            read_only=(
                'id created_at updated_at pocket_movement reminder_target_date '
                'reminder_last_sent_at reminder_count'
            ),
            read_write=(
                'notes ledger total_amount gustavo_amount carlos_amount concept '
                'kind client project origin period_date period_start period_end '
                'period_cadence destination expected_income reminders_muted '
                'reminders_muted_until is_receivable_candidate '
                'collection_confidence'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.ExpenseRecord',
            read_only=(
                'id created_at updated_at deduction_type source_income pocket_movement'
            ),
            read_write=(
                'notes ledger total_amount gustavo_amount carlos_amount concept '
                'period_date category'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.HostingRecord',
            read_only=(
                'id created_at updated_at expiry_notice_target '
                'expiry_notice_last_sent_at expiry_notice_count billing_requested_at'
            ),
            read_write=(
                'notes client project client_name client_email client_contact_name '
                'client_identification domain_url monthly_value payment_modality '
                'benefit valid_from valid_to cycles_count payment_per_cycle '
                'total_paid is_active'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.PocketMovement',
            read_only='id created_at updated_at',
            read_write='notes concept movement_date direction amount',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.RecurringPayment',
            read_only=(
                'id created_at updated_at cop_equivalent reminder_target_date '
                'reminder_last_sent_at reminders_muted reminders_muted_until '
                'is_archived archived_at'
            ),
            read_write=(
                'notes name price currency payment_method frequency custom_months '
                'billing_day cycle_anchor_date cost_type is_active category order'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.AdsSpendRecord',
            read_only='id created_at updated_at',
            read_write='notes spend_date platform origin_card amount',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.CardBalanceSnapshot',
            read_only='id created_at updated_at',
            read_write='notes snapshot_date card_name available_amount debt_amount',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.NotificationRecipient',
            read_only='id created_at updated_at',
            read_write='notes email is_active',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.AccountingSettings',
            read_only=(
                'id card_reminder_cycle_start card_reminder_last_sent_at '
                'statement_reminder_last_sent_at created_at updated_at'
            ),
            read_write=(
                'notifications_enabled card_reminder_enabled '
                'statement_reminder_enabled hosting_expiry_reminder_enabled '
                'payment_calendar_enabled overdue_reminder_frequency '
                'usd_exchange_rate income_default_view_mode '
                'collection_accounts_view_mode collection_accounts_group_by'
            ),
        ),
        _contract(
            'content.CreditCard',
            read_only='id created_at updated_at',
            read_write='notes name credit_limit is_active statements_since',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.CreditCardStatement',
            read_only='id created_at updated_at',
            read_write=(
                'notes card_name period_date status purchases_total previous_balance '
                'payments_total interest_and_fees closing_balance minimum_payment '
                'due_date pdf_file'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.CreditCardTransaction',
            read_only=(
                'id statement transaction_date raw_description original_amount '
                'original_currency installment_number installments_total created_at '
                'updated_at'
            ),
            read_write=(
                'notes merchant_name category amount is_identified is_reversal'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
        _contract(
            'content.MerchantAlias',
            read_only='id created_at updated_at',
            read_write='notes match_text merchant_name default_category is_gateway',
            excluded=_excluded(_AUDIT_INTERNAL, 'source_ref created_by'),
        ),
    ),
    'diagnostics': (
        _contract(
            'content.WebAppDiagnostic',
            read_only=(
                'id uuid view_count last_viewed_at initial_sent_at final_sent_at '
                'responded_at created_at updated_at confidentiality_params'
            ),
            read_write=(
                'slug title client client_name client_email client_phone '
                'client_company language status investment_amount currency '
                'payment_terms duration_label size_category radiography expires_at'
            ),
            excluded=_excluded(_AUDIT_INTERNAL, 'created_by'),
        ),
        _contract(
            'content.DiagnosticSection',
            read_only='id diagnostic section_type',
            read_write='title order is_enabled content_json visibility',
        ),
    ),
    'proposals': (
        _contract(
            'content.ProposalDefaultConfig',
            read_only='id created_at updated_at',
            read_write=(
                'language sections_json default_currency default_total_investment '
                'hosting_percent hosting_discount_nine_month hosting_discount_semiannual '
                'hosting_discount_quarterly expiration_days reminder_days '
                'urgency_reminder_days default_discount_percent default_slug_pattern'
            ),
        ),
        _contract(
            'content.CompanySettings',
            read_only=(
                'contractor_full_name contractor_nit contractor_cedula contractor_email '
                'bank_name bank_account_type bank_account_number contract_city'
            ),
            read_write='service_contract_settings',
            excluded=_excluded(_PANEL_ONLY, 'id contractor_signature created_at updated_at'),
        ),
        _contract(
            'content.ContractTemplate',
            read_only='id name content_markdown',
            excluded=_excluded(
                'Plantilla canónica administrada fuera del módulo Propuestas; aquí sólo se consulta el texto predeterminado.',
                'service_content_markdown is_default mirror_document created_at updated_at',
            ),
        ),
        _contract(
            'content.EmailTemplateConfig',
            read_only='id template_key created_at updated_at',
            read_write='content_overrides is_active',
        ),
        _contract(
            'content.BusinessProposal',
            read_only=(
                'id uuid reminder_sent_at urgency_email_sent_at '
                'last_activity_at view_count first_viewed_at sent_at responded_at '
                'engagement_declining cached_heat_score deliverable '
                'platform_onboarding_completed_at platform_onboarding_status '
                'created_at updated_at'
            ),
            read_write=(
                'title slug client client_name client_email language total_investment currency '
                'nationality hosting_percent hosting_discount_nine_month '
                'hosting_discount_semiannual hosting_discount_quarterly status '
                'expires_at reminder_days urgency_reminder_days discount_percent '
                'is_active automations_paused show_contract_terms show_explainer_video project_type market_type '
                'project_type_custom market_type_custom client_phone email_intro '
                'email_features email_method_phases email_signed_by selected_modules '
                'contract_params contract_modality'
            ),
            excluded=(
                _excluded(
                    _AUTOMATION_STATE,
                    'revisit_alert_sent_at '
                    'abandonment_email_sent_at investment_interest_email_sent_at '
                    'followup_scheduled_at stakeholder_alert_sent_at '
                    'post_expiration_alert_sent_at calculator_followup_sent_at '
                    'last_automated_email_at first_view_notification_status '
                    'first_view_notification_attempts '
                    'first_view_notification_attempted_at '
                    'first_view_notification_sent_at '
                    'first_view_notification_last_error',
                )
                | _excluded(
                    'Respuesta privada del cliente; se gestiona en el flujo público.',
                    'rejection_reason rejection_comment',
                )
            ),
        ),
        _contract(
            'content.ProposalSection',
            read_only='id proposal section_type',
            read_write='title order is_enabled content_json is_wide_panel',
        ),
        _contract(
            'content.ProposalShareLink',
            read_only=(
                'id proposal uuid recipient_name recipient_email view_count '
                'first_viewed_at created_at'
            ),
            read_write='shared_by_name shared_by_email',
        ),
        _contract(
            'content.ProposalDocument',
            read_only='id proposal is_generated content_markdown created_at updated_at',
            read_write='document_type title file custom_type_label',
        ),
        _contract(
            'content.ProposalFormalization',
            read_only='id proposal html_body text_body status expires_at sent_at error',
            read_write='payload',
            excluded=_excluded(_AUDIT_INTERNAL, 'created_by mcp_credential source_hash created_at'),
        ),
        _contract(
            'content.ProposalFormalizationFile',
            read_only='id key filename description mime_type sha256 size',
            excluded=_excluded(
                'Archivo privado descargable sólo mediante artefacto temporal de la credencial propietaria.',
                'preparation file',
            ),
        ),
    ),
    'linkedin-personal': (
        _contract(
            'content.LinkedInPost',
            read_only=(
                'id status published_at linkedin_post_id error_message created_at updated_at'
            ),
            read_write='commentary scheduled_at',
            excluded=_excluded(
                'El conector personal v1 publica sólo texto; las imágenes quedan en el panel.',
                'image',
            ),
        ),
        _contract(
            'content.LinkedInToken',
            read_only=(
                'id expires_at refresh_token_expires_at member_sub profile_name '
                'profile_picture profile_email obtained_at updated_at'
            ),
            excluded=_excluded(
                'Credencial cifrada: nunca debe salir por MCP.',
                'access_token_encrypted refresh_token_encrypted',
            ),
        ),
    ),
    'communications': (
        _contract(
            'content.CommunicationFolder',
            read_only='id created_at updated_at',
            read_write='name parent client project',
        ),
        _contract(
            'accounts.CommunicationPanelPreference',
            excluded=_excluded(
                'Preferencia personal de interfaz; el MCP opera el registro '
                'conversacional y no la configuración visual de cada cuenta.',
                'id user navigation_mode thread_order page_size default_channel '
                'show_manual_help navigation_width updated_at',
            ),
        ),
        _contract(
            'content.CommunicationThread',
            read_only=(
                'id status last_activity_at closed_at created_at updated_at '
                'managed_project managed_client is_archived archived_at'
            ),
            read_write='client project title folder',
            excluded=_excluded(_AUDIT_INTERNAL, 'created_by updated_by'),
        ),
        _contract(
            'content.CommunicationMessage',
            read_only='id status recorded_at updated_at source voided_at void_reason',
            read_write=(
                'thread channel direction subject content occurred_at reply_to documents'
            ),
            excluded=(
                _excluded(_AUDIT_INTERNAL, 'created_by updated_by voided_by')
                | _excluded(
                    'Enlace interno al log de correo; la herramienta registra hechos manuales.',
                    'email_log',
                )
            ),
        ),
        _contract(
            'content.CommunicationAttachment',
            read_only='id created_at',
            read_write='message document',
        ),
        _contract(
            'content.CommunicationMessageRevision',
            read_only='id message changes edited_by edited_at',
        ),
        _contract(
            'content.CommunicationMessageDateCorrection',
            read_only=(
                'id message previous_occurred_at corrected_occurred_at reason '
                'corrected_by corrected_at'
            ),
        ),
        _contract(
            'secure_links.SecureLink',
            read_only='id origin expires_at consumed_at revoked_at sent_at sent_by activation_count created_at',
            read_write='secret_type title language client project validity_days',
            excluded=(
                _excluded(
                    'Cifrado interno; crear/actualizar reciben fields y la lectura explícita confirmada devuelve contenido, nunca ciphertext.',
                    'payload_encrypted',
                )
                | _excluded(
                    'Capacidad del enlace: la URL sólo se entrega una vez al crear.',
                    'token_hash token_encrypted',
                )
                | _excluded(
                    'Datos de red y de contacto del creador o destinatario; sólo en el panel.',
                    'creator_name creator_email creator_ip consumed_ip consumed_user_agent',
                )
                | _excluded(_AUDIT_INTERNAL, 'created_by updated_at')
            ),
        ),
        _contract(
            'secure_links.SecureLinkEvent',
            read_only='kind created_at',
            excluded=(
                _excluded(
                    'Auditoría del panel: IP, navegador y actor se revisan sólo allí.',
                    'actor ip_address user_agent details',
                )
                | _excluded('Relación implícita en get_secure_link.', 'id link')
            ),
        ),
    ),
}


def _contracts_from(profile, *model_labels):
    """Reuse a reviewed legacy contract in a canonical area connector."""
    by_label = {
        contract.model_label: contract
        for contract in MCP_MODEL_CONTRACTS[profile]
    }
    return tuple(by_label[label] for label in model_labels)


PROJECT_CONTRACTS = (
    _contract(
        'accounts.Project',
        read_only='id created_at updated_at',
        read_write=(
            'name description client status current_state state_review_required '
            'progress start_date estimated_end_date payment_milestones hosting_tiers '
            'hosting_start_date'
        ),
        excluded=(
            _excluded(
                'URLs y accesos operativos; sólo se administran desde el detalle '
                'seguro del proyecto.',
                'production_url staging_url repository_url admin_url admin_username',
            )
            | _excluded(
                'Credencial cifrada del sitio: nunca se expone ni se modifica por MCP.',
                'admin_password_encrypted',
            )
        ),
    ),
    _contract(
        'accounts.ProjectAdminAccess',
        excluded=_excluded(
            'URLs administrativas, usuarios, secretos y auditoría reservados al '
            'detalle seguro del proyecto; el MCP no los consulta ni modifica.',
            'id project environment admin_url admin_username '
            'admin_password_encrypted updated_by created_at updated_at',
        ),
    ),
    _contract(
        'accounts.ProjectAccessNote',
        excluded=_excluded(
            'Notas operativas cifradas reservadas al detalle seguro del proyecto; '
            'el MCP no las consulta ni modifica.',
            'id project title content_encrypted is_sensitive created_by updated_by '
            'created_at updated_at',
        ),
    ),
    _contract(
        'content.DocumentStateGroup',
        read_only='id created_at updated_at',
        read_write='catalog name selection_mode order is_active',
    ),
    _contract(
        'content.DocumentState',
        read_only='id created_by updated_by created_at updated_at',
        read_write=(
            'catalog name description normalized_name slug color group order is_active '
            'system_key operational_effect show_in_document_manager merged_into '
            'incompatibilities'
        ),
    ),
    _contract(
        'content.DocumentStateEpisode',
        read_only='id opened_by closed_by created_at updated_at',
        read_write='project state opened_at closed_at outcome close_note origin',
        excluded=_excluded(
            'El Gestor de Proyectos opera únicamente episodios cuyo propietario es un proyecto.',
            'document',
        ),
    ),
)


DELIVERY_CONTRACTS = (
    _contract(
        'accounts.DeliveryWorkspace',
        read_only='project version',
        excluded=_excluded(
            'Clave interna del espacio: el cliente MCP usa project_id y la '
            'versión compartida, nunca el identificador de esta fila.',
            'id',
        ),
    ),
    _contract(
        'accounts.ProjectContract',
        read_only='id project version created_at updated_at',
        read_write='key title document proposal_document client_visible',
    ),
    _contract(
        'accounts.ContractAmendment',
        read_only='id version created_at updated_at',
        read_write='key title contract document proposal_document client_visible',
    ),
    _contract(
        'accounts.DeliveryScope',
        read_only='id version created_at updated_at',
        read_write='key title contract amendment description is_current',
    ),
    _contract(
        'accounts.DeliveryPhase',
        read_only='id version created_at updated_at',
        read_write='key title scope commercial_phase description order',
    ),
    _contract(
        'accounts.DeliveryStage',
        read_only='id version editorial_status created_at updated_at',
        read_write='key title phase description order',
    ),
    _contract(
        'accounts.Requirement',
        read_only='id version review_status created_at updated_at',
        read_write='key title stage description guide order context source_references',
    ),
    _contract(
        'accounts.DeliveryPublication',
        read_only='id stage round payload published_by created_at',
    ),
    _contract(
        'accounts.DeliveryDocumentLink',
        read_only='id project created_by created_at',
        read_write='document level contract amendment scope phase stage requirement',
    ),
    _contract(
        'accounts.DeliveryDocumentSnapshot',
        read_only='id publication link title sha256 created_at',
        excluded=_excluded(
            'Ruta privada del PDF congelado; la descarga autorizada entrega un '
            'artefacto temporal ligado a la credencial, nunca la ruta.',
            'file',
        ),
    ),
    _contract(
        'accounts.ContractSignatureEvidence',
        read_only='id sha256 method source_sha256 attested_by created_at',
        read_write='contract amendment signer_name signed_at attestation',
        excluded=(_excluded(
            'PDF firmado en almacenamiento privado. La constancia consume un '
            'asset PDF validado y la descarga autorizada nunca expone la ruta.',
            'file',
        ) | _excluded(
            'Instantánea interna de la firma portal con datos de red y '
            'verificación. MCP solo expone método, actor, fecha y huellas; la '
            'copia contractual exacta se descarga por el servicio autorizado.',
            'source_snapshot',
        )),
    ),
    _contract(
        'accounts.RequirementReview',
        read_only=(
            'id publication requirement actor requirement_version '
            'content_snapshot decision message environment is_external '
            'client_statement original_reviewer reviewed_at source_message '
            'source_snapshot evidence_document_ids created_at'
        ),
    ),
    _contract(
        'accounts.DeliveryReviewDocumentEvidence',
        read_only='id review document title sha256 created_at',
        excluded=_excluded(
            'Copia privada e inmutable del documento que respalda la conformidad. '
            'La descarga autorizada entrega un artefacto temporal mediante '
            'review_id y evidence_id, nunca su ruta de almacenamiento.',
            'file',
        ),
    ),
    _contract(
        'accounts.DeliveryMessage',
        read_only='id project actor created_at',
        read_write=(
            'level target_id requirements documents message is_internal '
            'context source_references reply_classifications'
        ),
    ),
    _contract(
        'accounts.DeliveryPromptContext',
        read_only=(
            'id contract client destination scope stage mode captured_version amendment_ids '
            'missing_sources uncertainties warnings complete prompt template schema '
            'conversation manifest_sha256 created_at'
        ),
        excluded=(
            _excluded(
                'Proyecto implícito en project_id; la captura se lee exclusivamente '
                'dentro de ese proyecto y no admite cambio de propietario.',
                'project',
            ) | _excluded(
                'Actor de auditoría asignado por la credencial; no se acepta '
                'suplantación ni se modifica una captura inmutable.',
                'actor',
            ) | _excluded(
                'Control interno de reintentos: crear recibe request_id, pero '
                'la lectura no expone el recibo ni su huella y no permite editarlo.',
                'request_id fingerprint',
            )
        ),
    ),
    _contract(
        'accounts.DeliveryPromptSource',
        read_only=(
            'source_key title origin source_id role applicability_note document '
            'proposal_document signature_evidence version version_kind date '
            'filename content_type sha256 fragments status warnings limits'
        ),
        excluded=(
            _excluded(
                'Fila interna de la fuente; MCP usa context_id y source_key '
                'para consultar la captura inmutable y descargar su copia.',
                'id context',
            ) | _excluded(
                'Ruta privada de la copia exacta. La descarga autorizada '
                'devuelve un artefacto temporal de la misma credencial.',
                'file',
            ) | _excluded(
                'Instantánea interna del origen, que puede contener notas y '
                'metadata de firma. Solo se exponen fragmentos verificables '
                'y metadatos autorizados, nunca esta captura interna.',
                'snapshot',
            ) | _excluded(
                'Fecha interna de la fila de fuente; la lectura devuelve la '
                'fecha del origen y la creación del contexto que retuvo la copia.',
                'created_at',
            )
        ),
    ),
    _contract(
        'accounts.DeliveryEvidenceEmail',
        read_only=(
            'id project stage to_recipients from_email subject html_body text_body '
            'captured_version manifest_sha256 created_at'
        ),
        excluded=(
            _excluded(
                'Titular capturado para revalidar el destinatario del proyecto; '
                'el DTO expone To y el cuerpo revisado, nunca permite reasignar '
                'al cliente ni editar evidencia preparada.',
                'client',
            ) | _excluded(
                'Propiedad y canal asignados por actor y credencial actuales. '
                'La preparación es personal e inmutable; no admite identidad '
                'enviada por el llamador ni acceso desde otro canal.',
                'prepared_by mcp_credential',
            ) | _excluded(
                'Recibo interno de preparación; request_id se recibe al crear '
                'para repetir de forma idempotente, nunca para editar la captura.',
                'request_id',
            ) | _excluded(
                'Fundamento conservado de la composición y conformidades. '
                'La herramienta devuelve su proyección pública revisada y '
                'archivos autorizados, nunca permite editar estas capturas.',
                'snapshot_payload closure_history',
            ) | _excluded(
                'Vínculo de auditoría asignado al preparar un reenvío explícito. '
                'No se acepta ni se modifica como relación CRUD; se observa '
                'la nueva preparación mediante el resultado de la acción.',
                'resend_of',
            )
        ),
    ),
    _contract(
        'accounts.DeliveryEvidenceEmailFile',
        read_only='id filename mime_type size_bytes sha256',
        excluded=(
            _excluded(
                'La preparación autorizada determina el correo propietario y '
                'la posición del adjunto en el manifest; no existe CRUD de archivos.',
                'email position',
            ) | _excluded(
                'Origen interno de la copia pública exacta. La lectura expone '
                'versión y hash del adjunto, sin permitir cambiar su origen.',
                'delivery_snapshot',
            ) | _excluded(
                'Ruta de almacenamiento privado: la descarga propia entrega '
                'bytes autorizados como artefacto temporal, nunca la ruta.',
                'file',
            )
        ),
    ),
    _contract(
        'accounts.DeliveryEvidenceEmailAttempt',
        read_only=(
            'id request_id status error_message claimed_at sent_at finished_at created_at'
        ),
        excluded=(
            _excluded(
                'Correo propietario y actor/credencial son implícitos en la '
                'preparación propia confirmada; nunca se aceptan para suplantar '
                'la identidad del intento.',
                'email actor mcp_credential',
            ) | _excluded(
                'Enlaces internos al transporte y al intento original. '
                'El historial común conserva la evidencia; los estados sólo '
                'los escribe el servicio después de reclamar durablemente el envío.',
                'gateway_snapshot email_log resend_of',
            ) | _excluded(
                'Marca interna de actualización del recibo mutable; la lectura '
                'expone fechas de reclamación y finalización, sin edición directa.',
                'updated_at',
            )
        ),
    ),
    _contract(
        'accounts.DeliveryOperation',
        excluded=_excluded(
            'Recibo interno de idempotencia: la operación acepta request_id y '
            'devuelve su resultado, pero no expone ni permite editar el registro '
            'de control, su huella o respuestas históricas internas.',
            'id project request_id actor fingerprint response created_at',
        ),
    ),
)


COMMERCIAL_CATALOG_CONTRACTS = (
    _contract(
        'content.AdditionalModuleCategory',
        read_only='id slug created_at updated_at',
        read_write='name_es name_en order is_active',
    ),
    _contract(
        'content.AdditionalModule',
        read_only='id slug created_at updated_at',
        read_write=(
            'category icon order is_active name_es name_en summary_es summary_en '
            'what_is_es what_is_en purpose_es purpose_en problems_solved_es '
            'problems_solved_en integrations_es integrations_en '
            'implementation_requirements_es implementation_requirements_en'
        ),
    ),
    _contract(
        'content.AdditionalModuleShareLink',
        read_only=(
            'id uuid created_by revoked_at view_count first_viewed_at last_viewed_at '
            'created_at'
        ),
        read_write=(
            'recipient_label client language is_active selected_modules '
            'show_explainer_video'
        ),
    ),
    _contract(
        'content.ExplainerVideoSettings',
        read_only='id created_at updated_at',
        read_write='show_additional_modules_video show_financing_video show_proposal_video',
    ),
    _contract(
        'content.HourPackage',
        read_only='id created_at updated_at',
        read_write=(
            'nationality name_es name_en note_es note_en hours hourly_rate '
            'discount_percent is_active order'
        ),
    ),
    _contract(
        'content.HourPackageSettings',
        read_only='id created_at updated_at',
        read_write='default_view_mode base_rate_col base_rate_ext base_rate_usa',
    ),
)


CONTENT_CATALOG_CONTRACTS = (
    _contract(
        'content.PortfolioWork',
        read_only='id slug created_at updated_at',
        read_write=(
            'title_en title_es cover_image cover_image_url project_url '
            'category_title_en category_title_es excerpt_es excerpt_en '
            'content_json_es content_json_en meta_title_es meta_title_en '
            'meta_description_es meta_description_en meta_keywords_es '
            'meta_keywords_en is_published published_at order'
        ),
    ),
    _contract(
        'content.QRCard',
        read_only='id created_at updated_at',
        read_write='name destination_url destination_type linktree is_active',
    ),
    _contract(
        'content.Linktree',
        read_only='id created_at updated_at active_template_version',
        read_write=(
            'handle name kind project display_name role bio avatar logo background_color accent_color '
            'text_color muted_color button_text_color font_family claim_line_1 claim_line_2 '
            'badge_text footer_tagline show_brand_header pwa_enabled pwa_title '
            'pwa_description vcard_first_name vcard_last_name vcard_org vcard_email '
            'vcard_tel vcard_url is_active'
        ),
    ),
    # Nivel 3: paquetes inmutables creados por upload_linktree_template; el
    # único campo mutable es la compartición por cliente.
    _contract(
        'content.LinktreeTemplate',
        read_only='id owner client name manifest html css warnings created_at',
        read_write='is_shared',
        excluded=_excluded(
            'Rutas de almacenamiento privado; el MCP expone sólo metadatos por clave y descargas firmadas.',
            'assets',
        ),
    ),
    # Instantáneas validadas: se crean con upload/validate/override y se activan
    # sólo con publish_linktree_template tras la validación en navegador.
    _contract(
        'content.LinktreeTemplateVersion',
        read_only=(
            'id linktree template overrides profile document status report '
            'screenshots created_at published_at'
        ),
        excluded=(
            _excluded(
                'Rutas de almacenamiento privado; se sirven como vista previa firmada o artefacto temporal.',
                'assets',
            )
            | _excluded(
                'Huella interna del perfil; el MCP informa profile_current en lugar del hash.',
                'profile_digest',
            )
        ),
    ),
    _contract(
        'content.LinktreeTemplateClick',
        read_only='id version link_key day count',
    ),
    # Biblioteca de imágenes por tarjeta: upload_linktree_asset crea o
    # reemplaza por clave; las versiones publicadas conservan su instantánea.
    _contract(
        'content.LinktreeAsset',
        read_only='id linktree created_at updated_at',
        read_write='key alt image',
    ),
    _contract(
        'content.ProjectBrandAsset',
        excluded=_excluded(
            'Biblioteca privada del proyecto administrada y descargada exclusivamente en el panel.',
            'id project title category file filename size created_at',
        ),
    ),
    _contract(
        'content.LinktreeButton',
        read_only='id',
        read_write='linktree tier action label href icon order is_active',
    ),
)


LEDGER_CATALOG_CONTRACTS = (
    _contract(
        'content.RecurringCategory',
        read_only='id slug created_at updated_at',
        read_write='name order',
    ),
)


BILLING_CATALOG_CONTRACTS = (
    _contract(
        'content.HostingCycle',
        read_only='id created_by created_at updated_at',
        read_write=(
            'hosting_record modality amount paid_at period_from period_to '
            'cycles_represented notes'
        ),
        excluded=_excluded(_AUDIT_INTERNAL, 'source_ref'),
    ),
    _contract(
        'content.Document',
        read_only=(
            'id uuid generated_file public_number subtotal discount_total tax_total '
            'total created_by updated_by signed_at signed_by signature_name '
            'signature_ip signature_user_agent created_at updated_at'
        ),
        read_write=(
            'document_type folder project deliverable client_user issuer hosting_record '
            'income_record source_proposal source_version issue_date due_date city '
            'currency notes terms_and_conditions template_version metadata '
            'commercial_status title slug status is_client_visible requires_signature '
            'is_archived archived_at archived_via_folder'
        ),
        excluded=_excluded(
            'Campos editoriales del Gestor de Documentos, ajenos al flujo de cobro.',
            'content_markdown content_json client_name client_email_subject '
            'client_email_body client_whatsapp_message client_custom_notes language '
            'cover_type include_portada include_subportada include_contraportada '
            'template_style tags',
        ),
    ),
    _contract(
        'content.DocumentCollectionAccount',
        read_only='document created_at updated_at',
        read_write=(
            'billing_concept payment_term_type payment_term_days payer_name '
            'payer_identification payer_identification_type payer_address payer_phone '
            'payer_email customer_name customer_identification '
            'customer_identification_type customer_contact_name customer_email '
            'customer_address customer_project_name observations support_reference'
        ),
    ),
    _contract(
        'content.DocumentItem',
        read_only='id line_total created_at updated_at',
        read_write=(
            'document position item_type description quantity unit_price '
            'discount_amount tax_amount period_start period_end reference_type '
            'reference_id'
        ),
    ),
    _contract(
        'content.DocumentPaymentMethod',
        read_only='id created_at updated_at',
        read_write=(
            'document payment_method_type bank_name account_type account_number '
            'account_holder_name account_holder_identification payment_instructions '
            'is_primary'
        ),
    ),
    _contract(
        'content.IssuerProfile',
        read_only='id created_at updated_at',
        read_write=(
            'name legal_name identification_type identification_number email phone '
            'address city country logo public_number_prefix default_payment_methods'
        ),
    ),
)


MCP_MODEL_CONTRACTS.update({
    # Read-only aggregate; every source model remains governed by its domain
    # connector contract instead of receiving a second mutation contract here.
    'operations': (),
    'commercial': (
        MCP_MODEL_CONTRACTS['clients']
        + MCP_MODEL_CONTRACTS['proposals']
        + MCP_MODEL_CONTRACTS['diagnostics']
        + COMMERCIAL_CATALOG_CONTRACTS
    ),
    'projects': PROJECT_CONTRACTS + DELIVERY_CONTRACTS,
    'content': (
        MCP_MODEL_CONTRACTS['blog']
        + MCP_MODEL_CONTRACTS['linkedin-personal']
        + CONTENT_CATALOG_CONTRACTS
    ),
    'accounting-ledger': (
        _contracts_from(
            'accounting',
            'content.IncomeRecord',
            'content.ExpenseRecord',
            'content.PocketMovement',
            'content.RecurringPayment',
            'content.AdsSpendRecord',
        )
        + LEDGER_CATALOG_CONTRACTS
    ),
    'accounting-billing': (
        _contracts_from(
            'accounting',
            'content.HostingRecord',
            'content.NotificationRecipient',
            'content.AccountingSettings',
        )
        + BILLING_CATALOG_CONTRACTS
    ),
    'accounting-cards': _contracts_from(
        'accounting',
        'content.CardBalanceSnapshot',
        'content.CreditCard',
        'content.CreditCardStatement',
        'content.CreditCardTransaction',
        'content.MerchantAlias',
    ),
})

# Each connector owns the same service contract as its Panel surface.
VIDEO_RESOURCE_CONTRACT = _contract(
    'content.VideoResource',
    read_only='id key module language proposal poster filename size sha256 duration_seconds width height revision updated_by created_at updated_at',
    read_write='mode file',
)
PARTNERSHIP_CONTRACTS = (
    _contract(
        'content.FinancingAgreement',
        read_write=(
            'client source_proposal source_project client_full_name client_company client_id_type '
            'client_id_number client_email client_phone original_contract_reference original_contract_date '
            'project_name financed_scope modality partnership_start_date currency total_value initial_payment '
            'hosting_value hosting_period installment_schedule template contract_markdown signed_document '
            'status completion_note cancellation_reason is_archived policy_revision'
        ),
        read_only=(
            'id uuid number cycle_number previous_agreement partnership_end_date eligibility_exchange_rate '
            'financed_balance template_version resolved_contract_markdown resolved_contract_sha256 '
            'signed_document_sha256 signed_document_size ready_at ready_by activated_at activated_by '
            'completed_at completed_by cancelled_at cancelled_by second_cycle_approved_at second_cycle_approved_by '
            'archived_at archived_by created_by updated_by created_at updated_at'
        ),
    ),
    _contract('content.FinancingAgreementTemplate', read_only='id name version content_markdown is_default is_active created_at updated_at'),
    _contract(
        'content.FinancingPolicyRevision',
        read_only='id version created_by created_at',
        read_write='minimum_project_value_cop maximum_project_value_cop financing_months maximum_financed_percent late_hosting_increase_percent installment_due_day_start installment_due_day_end',
    ),
    _contract('content.FinancingAgreementEvent', read_only='id agreement event_type actor before_state after_state details created_at'),
)
MCP_MODEL_CONTRACTS['partnership-program'] = PARTNERSHIP_CONTRACTS + (VIDEO_RESOURCE_CONTRACT,)
MCP_MODEL_CONTRACTS['additional-modules'] = tuple(
    contract for contract in COMMERCIAL_CATALOG_CONTRACTS
    if contract.model_label.startswith('content.AdditionalModule')
) + (VIDEO_RESOURCE_CONTRACT,)
MCP_MODEL_CONTRACTS['proposals'] += (VIDEO_RESOURCE_CONTRACT,)
MCP_MODEL_CONTRACTS['commercial'] += PARTNERSHIP_CONTRACTS + (VIDEO_RESOURCE_CONTRACT,)

for connector, field in [('partnership-program', 'show_financing_video'), ('additional-modules', 'show_additional_modules_video')]:
    MCP_MODEL_CONTRACTS[connector] += (_contract(
        'content.ExplainerVideoSettings', read_only='id created_at updated_at', read_write=field,
        excluded={name: 'Interruptor de otro módulo; no es editable desde este conector.' for name in ('show_financing_video', 'show_additional_modules_video', 'show_proposal_video') if name != field},
    ),)
MCP_MODEL_CONTRACTS['proposals'] += (_contract(
    'content.ExplainerVideoSettings', read_only='id created_at updated_at', read_write='show_proposal_video',
    excluded=_excluded('Interruptor de otro módulo.', 'show_financing_video show_additional_modules_video'),
),)
