"""Explicit reconciliation of the one project hosting and existing evidence."""
from django.db import transaction
from django.db.models import Q

from accounts.models import (
    BillingContextEvent, CollectionAccountContext, HostingEvidence, HostingEvidenceGroup,
    HostingSubscription, Payment, Project, ProjectHosting, ProjectHostingAccountingSource,
)
from accounts.services.billing_access import (
    BillingConflict, billing_project, invalid, require_billing_admin,
)
from content.models import Document, HostingCycle, HostingRecord


def _reason(data):
    if not data.get('reason', '').strip():
        invalid('Indica la razón de la conciliación administrativa.')


def _event(hosting, actor, operation, data, before, after):
    BillingContextEvent.objects.create(project=hosting.project, actor=actor,
                                      operation=operation, reason=data['reason'], before=before, after=after)


def _identity(hosting):
    return {'id': hosting.pk, 'subscription_id': hosting.subscription_id,
            'hosting_record_ids': list(hosting.accounting_sources.order_by('pk').values_list('hosting_record_id', flat=True)),
            'operational_record_id': (hosting.operational_accounting_source.hosting_record_id
                                      if hosting.operational_accounting_source_id else None),
            'version': hosting.version}


def _source_errors(record, project):
    errors = []
    if record.project_id != project.pk:
        errors.append('Proyecto distinto o pendiente.')
    if not record.client_id or record.client.user_id != project.client_id:
        errors.append('Cliente distinto o pendiente.')
    return errors


def hosting_inventory(project_id, actor):
    require_billing_admin(actor)
    project = billing_project(project_id, actor)
    hosting = ProjectHosting.objects.select_related('operational_accounting_source').filter(project=project).first()
    records = HostingRecord.objects.filter(
        Q(project=project) | Q(billing_source__hosting=hosting) if hosting else Q(project=project),
    ).select_related('client', 'billing_source')
    return {
        'project_id': project.pk, 'project_name': project.name,
        'hosting': _identity(hosting) if hosting else None,
        'version': hosting.version if hosting else 0,
        'subscriptions': list(HostingSubscription.objects.filter(project=project).values(
            'id', 'plan', 'status', 'billing_amount', 'next_billing_date',
        )),
        'accounting_sources': [
            {'id': row.pk, 'domain_url': row.domain_url, 'client_id': row.client_id,
             'project_id': row.project_id, 'is_active': row.is_active,
             'payment_modality': row.payment_modality, 'monthly_value': str(row.monthly_value),
             'payment_per_cycle': str(row.payment_per_cycle), 'total_paid': str(row.total_paid),
             'mapped_hosting_id': row.billing_source.hosting_id if hasattr(row, 'billing_source') else None,
             'conflicts': _source_errors(row, project)} for row in records.order_by('pk')
        ],
        'hosting_accounts': list(Document.objects.filter(billing_context__hosting=hosting, project=project).values('id', 'public_number', 'total', 'commercial_status')) if hosting else [],
        'pending_account_ids': list(Document.objects.filter(
            project=project, document_type__code='collection_account', billing_context__isnull=True,
        ).order_by('pk').values_list('pk', flat=True)),
        'events': list(project.billing_context_events.values('id', 'document_id', 'actor_id', 'operation', 'reason', 'before', 'after', 'created_at')),
    }


def _resolve_identity(project, hosting, data):
    _reason(data)
    current = hosting.version if hosting else 0
    if data['expected_version'] != current:
        raise BillingConflict()
    subscription = hosting.subscription if hosting else None
    if 'subscription_id' in data:
        if subscription and data['subscription_id'] != subscription.pk:
            invalid('No se puede reemplazar una suscripción con historia; concilia sus evidencias.')
        subscription = HostingSubscription.objects.select_for_update().filter(pk=data['subscription_id'], project=project).first() if data['subscription_id'] else None
        if data['subscription_id'] and not subscription:
            invalid('La suscripción debe pertenecer al proyecto.')
    record_ids = data.get('hosting_record_ids', [])
    if len(set(record_ids)) != len(record_ids):
        invalid('No repitas registros contables.')
    records = list(HostingRecord.objects.select_for_update().filter(pk__in=record_ids).order_by('pk'))
    if len(records) != len(record_ids):
        invalid('Registro contable inexistente.')
    for record in records:
        if _source_errors(record, project):
            invalid('Completa o corrige el cliente/proyecto del registro antes de asociarlo.')
        source = ProjectHostingAccountingSource.objects.filter(hosting_record=record).first()
        if source and (not hosting or source.hosting_id != hosting.pk):
            invalid('El registro contable ya pertenece a otro hosting.')
    selected = data.get('operational_record_id')
    if selected and selected not in record_ids and (not hosting or not hosting.accounting_sources.filter(hosting_record_id=selected).exists()):
        invalid('El origen operativo debe ser un registro asociado explícitamente.')
    if selected:
        selected_record = HostingRecord.objects.select_for_update().get(pk=selected)
        if _source_errors(selected_record, project):
            invalid('El origen operativo tiene relaciones contradictorias.')
    return subscription, records


@transaction.atomic
def reconcile_hosting(project_id, actor, data, *, preview=False):
    require_billing_admin(actor)
    project = billing_project(project_id, actor, lock=True)
    hosting = ProjectHosting.objects.select_for_update().filter(project=project).first()
    subscription, records = _resolve_identity(project, hosting, data)
    before = _identity(hosting) if hosting else None
    proposal = {'subscription_id': subscription.pk if subscription else None,
                'add_record_ids': [r.pk for r in records],
                'operational_record_id': data.get('operational_record_id'),
                'financial_effect': 'none'}
    if preview:
        return {'before': before, 'proposal': proposal, 'version': hosting.version if hosting else 0}
    if not hosting:
        hosting = ProjectHosting.objects.create(project=project)
    hosting.subscription = subscription
    for record in records:
        ProjectHostingAccountingSource.objects.get_or_create(hosting=hosting, hosting_record=record)
    if 'operational_record_id' in data:
        hosting.operational_accounting_source = hosting.accounting_sources.filter(hosting_record_id=data['operational_record_id']).first()
    hosting.version += 1
    hosting.save()
    _event(hosting, actor, 'reconcile_hosting_identity', data, before or {}, _identity(hosting))
    return _identity(hosting)


def _validate_evidence(hosting, data, *, group=None):
    _reason(data)
    if data['expected_version'] != hosting.version:
        raise BillingConflict()
    resolved = {}
    for kind, model, key in (
        ('payment', Payment, 'payment_ids'), ('cycle', HostingCycle, 'cycle_ids'),
        ('document', Document, 'document_ids'),
    ):
        ids = data.get(key, [])
        if len(set(ids)) != len(ids):
            invalid('Una evidencia no puede repetirse.')
        rows = list(model.objects.select_for_update().filter(pk__in=ids))
        if len(rows) != len(ids):
            invalid('Evidencia financiera inexistente.')
        for row in rows:
            if kind == 'payment':
                valid = hosting.subscription_id and row.subscription_id == hosting.subscription_id and row.subscription.project_id == hosting.project_id
            elif kind == 'cycle':
                valid = hosting.accounting_sources.filter(hosting_record_id=row.hosting_record_id).exists() and not _source_errors(row.hosting_record, hosting.project)
            else:
                valid = CollectionAccountContext.objects.filter(document=row, nature='hosting', hosting=hosting).exists()
            if valid and kind == 'document':
                from accounts.services.billing_context import validate_document_ownership
                validate_document_ownership(row)
            if not valid:
                invalid('Toda evidencia debe pertenecer al mismo hosting mediante relaciones explícitas.')
            existing = HostingEvidence.objects.filter(**{kind: row})
            if group:
                existing = existing.exclude(group=group)
            if existing.exists():
                invalid('La evidencia ya está conciliada; corrige su grupo anterior primero.')
        resolved[kind] = rows
    if not group and not any(resolved.values()):
        invalid('Selecciona evidencias existentes para conciliar.')
    return resolved


def _group_data(group):
    return {'id': group.pk, 'label': group.label,
            'evidence': list(group.evidence.order_by('pk').values('payment_id', 'cycle_id', 'document_id'))}


@transaction.atomic
def reconcile_evidence(project_id, actor, data, *, preview=False):
    require_billing_admin(actor)
    project = billing_project(project_id, actor, lock=True)
    hosting = ProjectHosting.objects.select_for_update().filter(project=project).first()
    if not hosting:
        invalid('Asocia primero la identidad del hosting.')
    group = None
    if data.get('group_id'):
        group = HostingEvidenceGroup.objects.filter(pk=data['group_id'], hosting=hosting).first()
        if not group:
            invalid('Grupo de conciliación inexistente en el proyecto.')
    resolved = _validate_evidence(hosting, data, group=group)
    before = _group_data(group) if group else {}
    if preview:
        return {'before': before, 'proposal': data, 'financial_effect': 'none'}
    if group:
        # Only relationship rows change. Durable events retain their prior membership.
        group.evidence.all().delete()
        group.label = data['label']
        group.save(update_fields=['label'])
    else:
        group = HostingEvidenceGroup.objects.create(hosting=hosting, label=data['label'])
    for kind, rows in resolved.items():
        for row in rows:
            HostingEvidence.objects.create(group=group, **{kind: row})
    hosting.version += 1
    hosting.save(update_fields=['version', 'updated_at'])
    after = _group_data(group)
    _event(hosting, actor, 'reconcile_hosting_evidence', data, before, after)
    return {**after, 'version': hosting.version}


@transaction.atomic
def link_account_payment(document, hosting, payment_id, actor, reason):
    # Explicit selection, never matching by concept, amount or billing dates.
    hosting = ProjectHosting.objects.select_for_update().get(pk=hosting.pk)
    payment = Payment.objects.select_for_update().filter(pk=payment_id, subscription_id=hosting.subscription_id).first()
    if not hosting.subscription_id or not payment:
        invalid('Selecciona un pago de la suscripción asociada al hosting.')
    previous = HostingEvidence.objects.filter(document=document).first()
    payment_evidence = HostingEvidence.objects.filter(payment=payment).first()
    if previous and (not payment_evidence or previous.group_id != payment_evidence.group_id):
        invalid('La cuenta ya pertenece a otro grupo; corrige la conciliación administrativa.')
    group = payment_evidence.group if payment_evidence else HostingEvidenceGroup.objects.create(
        hosting=hosting, label=f'Obligación de hosting — pago {payment.pk}',
    )
    if not payment_evidence:
        HostingEvidence.objects.create(group=group, payment=payment)
    HostingEvidence.objects.get_or_create(group=group, document=document)
    hosting.version += 1
    hosting.save(update_fields=['version', 'updated_at'])
    _event(hosting, actor, 'link_account_payment', {'reason': reason}, {}, _group_data(group))


def validate_hosting_account_evidence(document, hosting):
    hosting = ProjectHosting.objects.select_for_update().get(pk=hosting.pk)
    subscription = HostingSubscription.objects.filter(project_id=hosting.project_id).first()
    if subscription and hosting.subscription_id != subscription.pk:
        invalid('La suscripción del proyecto está pendiente de asociar al hosting; concilia antes de emitir.')
    if HostingRecord.objects.filter(project_id=hosting.project_id).exclude(billing_source__hosting=hosting).exists():
        invalid('Hay orígenes contables del proyecto pendientes de asociar al hosting; concilia antes de emitir.')
    if hosting.subscription_id:
        evidence = HostingEvidence.objects.select_related('group').filter(document=document).first()
        if not evidence or evidence.group.hosting_id != hosting.pk or not evidence.group.evidence.filter(payment__subscription_id=hosting.subscription_id).exists():
            invalid('Asocia explícitamente esta cuenta a la obligación de la suscripción antes de emitir; no se deduce un ciclo por importe o fecha.')
        if evidence.group.evidence.filter(document__commercial_status__in=('issued', 'paid')).exclude(document=document).exists():
            invalid('La obligación seleccionada ya tiene una cuenta emitida; concilia o anula explícitamente antes de emitir otra.')
    if document.hosting_record_id:
        source = hosting.operational_accounting_source
        if not source or source.hosting_record_id != document.hosting_record_id:
            invalid('El registro de origen no es el operativo del hosting; concilia antes de emitir.')


@transaction.atomic
def register_new_hosting_origin(instance, actor, *, subscription=False):
    """Only for a just-created origin; historical origins require reconciliation."""
    if not instance.project_id:
        return
    project = Project.objects.select_for_update().get(pk=instance.project_id)
    hosting, _ = ProjectHosting.objects.get_or_create(project=project)
    before = _identity(hosting)
    if subscription:
        if hosting.subscription_id and hosting.subscription_id != instance.pk:
            invalid('Ya existe una suscripción asociada al hosting.')
        hosting.subscription = instance
    else:
        if _source_errors(instance, project):
            invalid('El hosting nuevo debe pertenecer al cliente del proyecto.')
        source = ProjectHostingAccountingSource.objects.create(hosting=hosting, hosting_record=instance)
        if hosting.operational_accounting_source_id:
            invalid('El proyecto ya tiene hosting contable; utiliza la conciliación administrativa.')
        if HostingRecord.objects.filter(project=project).exclude(pk=instance.pk).exists():
            invalid('Hay orígenes históricos de hosting; concílialos antes de crear otro.')
        hosting.operational_accounting_source = source
    hosting.version += 1
    hosting.save()
    _event(hosting, actor, 'register_new_hosting_origin', {'reason': 'Alta explícita de origen de hosting.'}, before, _identity(hosting))
