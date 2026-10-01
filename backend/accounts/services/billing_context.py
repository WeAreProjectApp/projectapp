"""Exclusive project-account associations; snapshots and finances are untouched."""
from django.db import transaction

from accounts.models import (
    BillingContextEvent, CollectionAccountContext, ContractAmendment, ProjectContract,
    ProjectHosting,
)
from accounts.services.billing_access import (
    BillingConflict, invalid, require_billing_admin,
)
from content.models import Document
from accounts.services.billing_locks import lock_billing_document


def context_data(context):
    if not context:
        return {'nature': None, 'status': 'pending', 'version': 0,
                'contract': None, 'amendment': None, 'hosting_id': None}
    return {
        'nature': context.nature, 'status': 'associated', 'version': context.version,
        'contract': {'id': context.contract_id, 'title': context.contract.title} if context.contract_id else None,
        'amendment': {'id': context.amendment_id, 'title': context.amendment.title} if context.amendment_id else None,
        'hosting_id': context.hosting_id,
    }


def validate_document_ownership(document):
    project = document.project
    if not project:
        return
    if document.client_user_id and document.client_user_id != project.client_id:
        invalid('La cuenta y el proyecto deben pertenecer al mismo cliente.')
    if document.deliverable_id and document.deliverable.project_id != project.pk:
        invalid('La entrega pertenece a otro proyecto.')
    for origin in (document.hosting_record, document.income_record):
        if not origin:
            continue
        if origin.project_id and origin.project_id != project.pk:
            invalid('El origen financiero pertenece a otro proyecto.')
        if origin.client_id and origin.client.user_id != project.client_id:
            invalid('El origen financiero pertenece a otro cliente.')


def resolve_context(document, data, *, lock_relations=False):
    if not document.project_id:
        if any(data.get(key) is not None for key in (
            'billing_nature', 'contract_id', 'amendment_id', 'project_hosting_id', 'hosting_payment_id',
        )):
            invalid('Los cobros sin proyecto conservan su flujo contable sin contexto de proyecto.')
        return None
    validate_document_ownership(document)
    nature = data.get('billing_nature')
    if nature == 'contract':
        if data.get('project_hosting_id') or data.get('hosting_payment_id') or document.hosting_record_id:
            invalid('Una cuenta de contrato no puede tener naturaleza hosting.')
        contract = ProjectContract.objects.filter(pk=data.get('contract_id'), project_id=document.project_id).first()
        if not contract:
            invalid('Selecciona un contrato del proyecto de la cuenta.')
        amendment = None
        if data.get('amendment_id'):
            amendments = ContractAmendment.objects.select_for_update() if lock_relations else ContractAmendment.objects
            amendment = amendments.filter(pk=data['amendment_id'], contract=contract).first()
            if not amendment:
                invalid('El otrosí debe pertenecer al contrato seleccionado.')
        return {'nature': nature, 'contract': contract, 'amendment': amendment, 'hosting': None}
    if nature == 'hosting':
        if data.get('contract_id') or data.get('amendment_id'):
            invalid('El hosting del proyecto es independiente de sus contratos.')
        hosting = ProjectHosting.objects.filter(pk=data.get('project_hosting_id'), project_id=document.project_id).first()
        if not hosting:
            invalid('Selecciona el hosting único del proyecto de la cuenta.')
        if hosting.subscription_id and hosting.subscription.project_id != document.project_id:
            invalid('La suscripción de hosting pertenece a otro proyecto.')
        if document.hosting_record_id:
            source = hosting.accounting_sources.filter(hosting_record_id=document.hosting_record_id).first()
            if not source:
                invalid('El origen contable debe asociarse explícitamente al hosting del proyecto.')
        return {'nature': nature, 'contract': None, 'amendment': None, 'hosting': hosting}
    invalid('Toda cuenta nueva de proyecto requiere naturaleza contrato u hosting y su vínculo explícito.')


def validate_account_context(document):
    if not document.project_id:
        if CollectionAccountContext.objects.filter(document=document).exists():
            invalid('No se puede desvincular el proyecto de una cuenta ya asociada.')
        return
    context = _lock_context(document)
    if not context:
        invalid('Cuenta pendiente de asociar: fija su contrato/otrosí o hosting antes de emitir.')
    resolve_context(document, {
        'billing_nature': context.nature, 'contract_id': context.contract_id,
        'amendment_id': context.amendment_id, 'project_hosting_id': context.hosting_id,
    }, lock_relations=True)
    if context.hosting_id:
        from accounts.services.hosting_context import validate_hosting_account_evidence
        validate_hosting_account_evidence(document, context.hosting)


def _lock_context(document, *, selected_amendment_id=None):
    # Amendment writers lock their own row before checking associated contexts.
    # Discover IDs, then lock amendments before contexts to keep that order too.
    previous = CollectionAccountContext.objects.filter(document=document).values('amendment_id').first()
    ids = {selected_amendment_id, previous['amendment_id'] if previous else None} - {None}
    list(ContractAmendment.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    context = CollectionAccountContext.objects.select_for_update().filter(document=document).first()
    if context and context.amendment_id and context.amendment_id not in ids:
        raise BillingConflict()
    return context


@transaction.atomic
def associate_account(document_id, actor, data, *, creating=False):
    require_billing_admin(actor)
    document = lock_billing_document(document_id)
    if not document or not document.document_type_id or document.document_type.code != 'collection_account':
        invalid('Cuenta de cobro no encontrada.')
    context = _lock_context(document, selected_amendment_id=data.get('amendment_id'))
    if not creating and data['expected_version'] != (context.version if context else 0):
        raise BillingConflict()
    fields = resolve_context(document, data, lock_relations=True)
    if fields is None:
        return None
    if not creating and not data.get('reason', '').strip():
        invalid('Indica la razón de la asociación administrativa.')
    from accounts.models import HostingEvidence
    evidence = HostingEvidence.objects.select_related('group').filter(document=document).first()
    if evidence:
        if fields['hosting'] is None or fields['hosting'].pk != evidence.group.hosting_id:
            invalid('Primero corrige explícitamente la conciliación del hosting de esta cuenta.')
    before = context_data(context)
    if context:
        for field, value in fields.items():
            setattr(context, field, value)
        context.version += 1
        context.save()
    else:
        context = CollectionAccountContext.objects.create(document=document, **fields)
    if fields['hosting'] and data.get('hosting_payment_id'):
        from accounts.services.hosting_context import link_account_payment
        link_account_payment(document, fields['hosting'], data['hosting_payment_id'], actor,
                             data.get('reason', 'Creación de cuenta con obligación explícita.'))
    BillingContextEvent.objects.create(
        project=document.project, document=document, actor=actor, operation='associate_account',
        reason=data.get('reason', 'Contexto explícito al crear la cuenta.'),
        before={**before, 'document_id': document.pk}, after={**context_data(context), 'document_id': document.pk},
    )
    return context
