"""Explicit domain projections. Authentication data and telemetry never enter history."""

from django.apps import apps
from django.db import models
from functools import lru_cache


ENTITIES = {
    'document': 'content.Document', 'proposal': 'content.BusinessProposal',
    'project': 'accounts.Project', 'client': 'accounts.UserProfile',
    'income': 'content.IncomeRecord', 'expense': 'content.ExpenseRecord',
    'hosting': 'content.HostingRecord', 'pocket': 'content.PocketMovement',
    'recurring': 'content.RecurringPayment', 'ads': 'content.AdsSpendRecord',
    'card_snapshot': 'content.CardBalanceSnapshot', 'credit_card': 'content.CreditCard',
    'statement': 'content.CreditCardStatement', 'statement_tx': 'content.CreditCardTransaction',
    'merchant_alias': 'content.MerchantAlias',
    'notification_recipient': 'content.NotificationRecipient',
    'settings': 'content.AccountingSettings',
}

FIELDS = {
    'document': '''title slug document_type folder project deliverable client_user issuer
        hosting_record income_record source_proposal source_version public_number issue_date
        due_date city currency subtotal discount_total tax_total total notes terms_and_conditions
        template_version commercial_status status is_client_visible content_markdown client_name
        client_email_subject client_email_body client_whatsapp_message client_custom_notes language
        cover_type include_portada include_subportada include_contraportada template_style
        requires_signature signed_at signed_by signature_name is_archived archived_at
        archived_via_folder generated_file metadata'''.split(),
    'proposal': '''title client client_name client_email client_phone total_investment currency
        discount_percent status language project_type market_type slug expires_at reminder_days
        urgency_reminder_days show_contract_terms email_intro nationality hosting_percent
        hosting_discount_nine_month hosting_discount_semiannual hosting_discount_quarterly
        is_active automations_paused project_type_custom market_type_custom email_features
        email_method_phases email_signed_by rejection_reason rejection_comment deliverable
        selected_modules contract_params contract_modality'''.split(),
    'project': '''name description status current_state client production_url staging_url repository_url
        admin_url admin_username'''.split(),
    'client': '''company_name phone address cedula nit billing_code archived_at'''.split(),
}

LABELS = {
    'title': 'Título', 'content_markdown': 'Contenido', 'content_json': 'Contenido estructurado',
    'folder': 'Carpeta', 'tags': 'Etiquetas', 'project': 'Proyecto', 'client': 'Cliente',
    'client_user': 'Cliente', 'client_name': 'Nombre del cliente', 'status': 'Estado',
    'states': 'Estados', 'notes': 'Notas', 'document_notes': 'Notas del documento', 'sections': 'Secciones', 'access': 'Accesos',
    'access_notes': 'Notas del proyecto', 'total_investment': 'Inversión', 'currency': 'Moneda',
    'discount_percent': 'Descuento', 'first_name': 'Nombre', 'last_name': 'Apellido',
    'email': 'Correo', 'phone': 'Teléfono', 'address': 'Dirección', 'cedula': 'Documento de identidad', 'nit': 'NIT',
    'company_name': 'Empresa', 'billing_code': 'Código de facturación',
    'production_url': 'URL de producción', 'staging_url': 'URL de staging',
    'repository_url': 'Repositorio', 'admin_url': 'URL de administración',
    'admin_username': 'Usuario de administración', 'archived_at': 'Archivado',
    'client_email_subject': 'Asunto preparado', 'client_email_body': 'Correo preparado',
    'client_whatsapp_message': 'WhatsApp preparado', 'client_custom_notes': 'Notas privadas',
    'is_client_visible': 'Visible para el cliente', 'language': 'Idioma',
    'generated_file': 'Archivo emitido', 'items': 'Ítems', 'collection_account': 'Datos de cobro',
    'payment_methods': 'Medios de pago', 'thread': 'Hilo', 'name': 'Nombre',
    'description': 'Descripción', 'document_type': 'Tipo de documento',
    'archived_pdf': 'PDF enviado', 'current_state': 'Estado actual',
    'contract_modality': 'Modalidad de cierre',
}


@lru_cache(maxsize=1)
def field_labels():
    from content.services.accounting_service import TRACKED_FIELDS
    labels = dict(pair for fields in TRACKED_FIELDS.values() for pair in fields)
    labels.update(LABELS)
    return labels


def canonical_type(entity_type):
    return 'document' if entity_type == 'collection_account' else entity_type


def entity_model(entity_type):
    return apps.get_model(ENTITIES[canonical_type(entity_type)])


def tracked_fields(kind):
    if kind in FIELDS:
        return FIELDS[kind]
    # Financial snapshots include domain fields omitted by the old notification
    # diff (for example income service periods). Delivery telemetry is excluded.
    excluded = {'id', 'created_at', 'updated_at', 'created_by', 'source_ref',
                'reminder_target_date', 'reminder_last_sent_at', 'reminder_count'}
    return [field.name for field in entity_model(kind)._meta.concrete_fields
            if field.name not in excluded and not field.name.endswith('_sent_at')]


def tracks_fields(model, fields):
    if fields is None:
        return True
    names = {name.removesuffix('_id') for name in fields}
    for kind, model_label in ENTITIES.items():
        if model._meta.label != model_label:
            continue
        tracked = tracked_fields(kind)
        return bool(names & (set(tracked) | {'admin_password_encrypted', 'content_json', 'pdf_file'}))
    return bool(names - {'updated_at', 'updated_by', 'created_by'})


def roots_for(instance):
    """Resolve affected aggregate identities without relying on cached relations."""
    label = instance._meta.label
    for kind, model_label in ENTITIES.items():
        if label == model_label:
            roots = [(kind, instance.pk)] if instance.pk else []
            if kind == 'income':
                if instance.expected_income_id:
                    roots.append(('income', instance.expected_income_id))
                if instance.pocket_movement_id:
                    roots.append(('pocket', instance.pocket_movement_id))
            return roots
    if label == 'auth.User' and instance.pk:
        return [('client', pk) for pk in entity_model('client').objects.filter(
            user_id=instance.pk,
        ).values_list('pk', flat=True)]
    relations = {
        'content.ProposalSection': ('proposal', 'proposal_id'),
        'content.DocumentNote': ('document', 'document_id'),
        'content.DocumentCollectionAccount': ('document', 'document_id'),
        'accounts.CollectionAccountContext': ('document', 'document_id'),
        'content.DocumentItem': ('document', 'document_id'),
        'content.DocumentPaymentMethod': ('document', 'document_id'),
        'content.DocumentThreadItem': ('document', 'document_id'),
        'accounts.ProjectAdminAccess': ('project', 'project_id'),
        'accounts.ProjectAccessNote': ('project', 'project_id'),
        'content.HostingCycle': ('hosting', 'hosting_record_id'),
    }
    if label in relations:
        kind, field = relations[label]
        pk = getattr(instance, field, None)
        return [(kind, pk)] if pk else []
    if label == 'content.DocumentStateEpisode':
        return [(kind, getattr(instance, f'{kind}_id')) for kind in ('document', 'project')
                if getattr(instance, f'{kind}_id', None)]
    return []


def scalar(value):
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    return str(value)


def record_values(instance, fields):
    values = {}
    available = {field.name: field for field in instance._meta.concrete_fields}
    for name in fields:
        field = available.get(name)
        if not field:
            continue
        value = getattr(instance, name)
        if isinstance(field, models.ForeignKey):
            values[name] = None if value is None else {
                'id': value.pk,
                'label': str(getattr(value, 'name', None) or getattr(value, 'title', None) or value),
            }
        else:
            values[name] = scalar(value)
    return values


def child_values(queryset, fields):
    relations = [f.name for f in queryset.model._meta.concrete_fields
                 if f.name in fields and isinstance(f, models.ForeignKey)]
    if relations:
        queryset = queryset.select_related(*relations)
    return {str(row.pk): record_values(row, fields) for row in queryset.order_by('pk')}


def snapshot_entity(kind, pk):
    """Return public data plus existing encrypted tokens in a separate payload."""
    model = entity_model(kind)
    fields = tracked_fields(kind)
    relations = [f.name for f in model._meta.concrete_fields
                 if f.name in fields and isinstance(f, models.ForeignKey)]
    if kind == 'client':
        relations.append('user')
    if kind == 'document':
        relations.extend(['collection_account', 'thread_item__thread'])
    queryset = model.objects.select_related(*relations) if relations else model.objects.all()
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        return None, {}, ''
    data = record_values(obj, fields)
    secrets = {}
    label = str(getattr(obj, 'title', None) or getattr(obj, 'name', None)
                or getattr(obj, 'concept', None) or obj)[:255]
    if kind == 'client':
        data.update(record_values(obj.user, ['first_name', 'last_name', 'email']))
        label = obj.user.get_full_name() or obj.user.email
    if kind == 'hosting':
        data['cycles'] = child_values(obj.cycles.all(), ['modality', 'amount', 'paid_at', 'period_from', 'period_to', 'notes'])
    if kind == 'income':
        data['payments'] = child_values(obj.liquid_records.all(), [
            'total_amount', 'period_date', 'destination', 'notes',
        ])
    if kind == 'pocket':
        data['allocations'] = child_values(obj.income_records.all(), [
            'expected_income', 'total_amount', 'notes',
        ])
    if kind == 'proposal':
        data['sections'] = child_values(obj.sections.all(), [
            'section_type', 'title', 'order', 'is_enabled', 'content_json', 'is_wide_panel',
        ])
    if kind in ('document', 'project'):
        data['states'] = child_values(obj.state_episodes.all(), [
            'state', 'opened_at', 'closed_at', 'outcome', 'close_note',
        ])
    if kind == 'document':
        data['tags'] = list(obj.tags.order_by('pk').values('id', 'name'))
        # Markdown is canonical; only keep structured content when there is no Markdown.
        if not obj.content_markdown:
            data['content_json'] = obj.content_json
        data['document_notes'] = child_values(obj.document_notes.all(), [
            'title', 'content', 'order', 'status', 'resolution_note', 'resolved_at', 'deleted_at',
        ])
        for relation in ('collection_account', 'billing_context'):
            child = getattr(obj, relation, None)
            if child:
                data[relation] = record_values(child, [f.name for f in child._meta.fields
                    if f.name not in ('document', 'created_at', 'updated_at')])
        for relation in ('items', 'payment_methods'):
            manager = getattr(obj, relation, None)
            if manager is not None:
                data[relation] = child_values(manager.all(), [f.name for f in manager.model._meta.fields
                    if f.name not in ('id', 'document', 'created_at', 'updated_at')])
        item = getattr(obj, 'thread_item', None)
        if item:
            data['thread'] = record_values(item, ['thread', 'occurred_on', 'position'])
    if kind == 'project':
        data['access'] = {}
        for access in obj.admin_accesses.order_by('environment'):
            prefix = f'access.{access.environment}.password'
            data['access'][access.environment] = record_values(access, ['admin_url', 'admin_username'])
            data['access'][access.environment]['password'] = {'protected': True, 'present': bool(access.admin_password_encrypted)}
            secrets[prefix] = access.admin_password_encrypted
        if obj.admin_password_encrypted:
            data['legacy_password'] = {'protected': True, 'present': True}
            secrets['legacy_password'] = obj.admin_password_encrypted
        data['access_notes'] = {}
        for note in obj.access_notes.order_by('pk'):
            # All note content is encrypted, including notes later marked non-sensitive.
            data['access_notes'][str(note.pk)] = {
                'title': note.title, 'is_sensitive': note.is_sensitive,
                'content': {'protected': True, 'present': bool(note.content_encrypted)},
            }
            secrets[f'access_notes.{note.pk}.content'] = note.content_encrypted
    return data, secrets, label[:255]
