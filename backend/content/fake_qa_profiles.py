"""Scenario recipes and read-only baseline checks for disposable DevQA copies."""

from calendar import monthrange
from datetime import date
from decimal import Decimal
from hashlib import file_digest

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from rest_framework.exceptions import APIException

from accounts.management.commands.create_fake_platform_cases import (
    B04_ACTORS, B04_GUIDE_KEY, B04_PROJECT, B04_REQUESTS, seed_b04,
)
from accounts.models import ChangeRequest, DeliveryStage, DeliveryWorkspace, Project
from accounts.services import delivery_access, issue_context, platform_features
from content.management.commands.create_fake_accounting import (
    FAKE_REF, QA_INCOME_CASES, seed_qa_income_cases,
)
from content.management.commands.create_fake_documents import (
    QA_DOCUMENT_FOLDER, QA_DOCUMENT_TITLES, seed_qa_document_history,
)
from content.models import (
    AccountingChangeLog, Document, DocumentFolder, EmailLog, EntityHistory,
    IncomeCompletionNotice, IncomeRecord, IncomeSettlement, PocketMovement,
)
from content.services.accounting_income_detail_service import income_detail_queryset
from content.services.uploaded_pdf_service import pdf_metadata


LIMITED_CLIENT = 'qa-limited@example.test'
STAFF_ACTOR = 'qa-staff@example.test'
SUPERUSER = 'qa-superuser@example.test'
PROFILE_ACTORS = {
    'b04': {
        B04_ACTORS[0]: ('admin', False, False),
        B04_ACTORS[1]: ('client', False, False),
    },
    'staff': {
        STAFF_ACTOR: ('admin', True, False),
        LIMITED_CLIENT: ('client', False, False),
    },
    'su': {
        SUPERUSER: ('admin', True, True),
        STAFF_ACTOR: ('admin', True, False),
    },
}


def _resolve(queryset, description, **fields):
    try:
        return queryset.get(**fields)
    except (queryset.model.DoesNotExist, queryset.model.MultipleObjectsReturned):
        raise CommandError(f'Falta un registro único para {description}.') from None


def profile_actors(profile):
    actors = {}
    for email, expected in PROFILE_ACTORS[profile].items():
        actor = _resolve(get_user_model().objects.select_related('profile'), f'actor {email}', username=email)
        identity = getattr(actor, 'profile', None)
        if (not identity or not actor.is_active or not identity.is_onboarded
                or not identity.email_verified or not identity.profile_completed
                or actor.email != email or (identity.role, actor.is_staff, actor.is_superuser) != expected):
            raise CommandError(f'El actor {email} no cumple el perfil de acceso esperado.')
        actors[email] = actor
    return actors


def _project(profile):
    owner = B04_ACTORS[1] if profile == 'b04' else LIMITED_CLIENT
    name = B04_PROJECT if profile == 'b04' else '[QA] Proyecto de otro cliente'
    return _resolve(
        Project.objects.select_related('client__profile'), f'proyecto {name}',
        client__username=owner, name=name,
    )


def seed_profile(profile, context):
    if profile == 'b04':
        seed_b04(context)
        return
    project = _project(profile)
    actors = profile_actors(profile)
    if profile == 'staff':
        seed_qa_document_history(context, project=project, actor=actors[STAFF_ACTOR])
    else:
        seed_qa_income_cases(context, project=project, actor=actors[SUPERUSER])


def _b04_baseline(project, actors):
    admin, client = (actors[email] for email in B04_ACTORS)
    for actor in (admin, client):
        try:
            delivery_access.project_for_actor(project.pk, actor)
            platform_features.require_feature(actor, 'platform.change_requests')
        except APIException:
            raise CommandError(f'El actor {actor.username} perdió acceso a Solicitudes.') from None
    if not delivery_access.is_admin(admin) or delivery_access.is_admin(client):
        raise CommandError('El permiso de evaluación de los actores B04 cambió.')

    stages = DeliveryStage.objects.filter(phase__scope__contract__project=project)
    published = _resolve(stages, 'etapa publicada B04', key='demo-review', editorial_status='published')
    draft = _resolve(stages, 'etapa borrador B04', key='demo-draft', editorial_status='draft')
    if draft.phase.scope_id != published.phase.scope_id or draft.requirements.exists():
        raise CommandError('La etapa de conversión B04 ya no conserva el alcance o el borrador inicial.')
    guide = _resolve(published.requirements.all(), 'requerimiento publicado B04', key=B04_GUIDE_KEY)
    try:
        publication, snapshot = issue_context.capture_context(project, client, {'source_requirement_id': guide.pk})
    except APIException:
        raise CommandError('El requerimiento B04 ya no está disponible en la publicación.') from None

    tickets = {}
    for status, title in B04_REQUESTS.items():
        ticket = _resolve(project.change_requests.all(), title, title=title)
        if (ticket.status != status or ticket.version != 0 or ticket.is_archived or ticket.linked_requirement_id
                or ticket.source_requirement_id != guide.pk or ticket.created_by_id != client.pk
                or issue_context.original_context(ticket) != snapshot):
            raise CommandError(f'{title} ya no conserva su estado inicial.')
        tickets[status] = {
            'id': ticket.pk, 'key': title, 'status': status, 'version': ticket.version, 'created_by': client.pk,
        }

    workspace = _resolve(DeliveryWorkspace.objects.all(), 'espacio de Entregas B04', project=project)
    return {
        'route': f'/platform/projects/{project.pk}/changes',
        'permission_checks': {
            'project_and_changes': {admin.username: True, client.username: True},
            'evaluate_as_team': {admin.username: True, client.username: False},
        },
        'tickets': tickets,
        'published_requirement': {
            'id': guide.pk, 'key': guide.key, 'version': guide.version,
            'publication_id': publication.pk, 'round': publication.round,
            'stage_id': published.pk, 'contract_id': snapshot['contract_id'],
        },
        'draft_stage': {
            'id': draft.pk, 'key': draft.key, 'status': draft.editorial_status, 'version': draft.version,
        },
        'workspace_version': workspace.version,
    }


def _document_baseline(project):
    folder = _resolve(
        DocumentFolder.objects.all(), QA_DOCUMENT_FOLDER,
        project=project, client_user=project.client, name=QA_DOCUMENT_FOLDER, is_archived=False,
    )
    documents = {}
    for key, title in QA_DOCUMENT_TITLES.items():
        doc = _resolve(
            Document.objects.all(), title, title=title, folder=folder, project=project,
            client_user=project.client, is_client_visible=False, is_archived=False,
        )
        documents[key] = doc
    history_doc = documents['history']
    history = _resolve(
        EntityHistory.objects.all(), QA_DOCUMENT_TITLES['history'],
        entity_type='document', object_id=history_doc.pk,
    )
    revisions = list(history.entries.exclude(action='prepared_version').order_by('number'))
    if [row.number for row in revisions] != list(range(1, 22)):
        raise CommandError('El historial documental ya no tiene las 21 revisiones iniciales.')
    pdf = documents['pdf']
    metadata = pdf_metadata(pdf)
    if not metadata or not pdf.uploaded_pdf or pdf.pdf_version != 1:
        raise CommandError('Falta la primera versión del PDF privado.')
    try:
        with pdf.uploaded_pdf.open('rb') as stream:
            if stream.size != pdf.pdf_size or file_digest(stream, 'sha256').hexdigest() != pdf.pdf_sha256:
                raise CommandError('El archivo del PDF privado difiere de la versión inicial.')
    except OSError:
        raise CommandError('Falta el archivo del PDF privado.') from None

    editable = documents['editable']
    editable_history = _resolve(
        EntityHistory.objects.all(), QA_DOCUMENT_TITLES['editable'],
        entity_type='document', object_id=editable.pk,
    )
    return {
        'route': '/panel/documents',
        'folder': {'id': folder.pk, 'key': folder.slug, 'name': folder.name},
        'documents': {
            key: {'id': doc.pk, 'key': str(doc.uuid), 'title': doc.title, 'status': doc.status}
            for key, doc in documents.items()
        },
        'history': {'count': len(revisions), 'comparison': [
            {'id': row.pk, 'number': row.number} for row in revisions[-2:]
        ]},
        'pdf': {
            **metadata, 'content_type': 'application/pdf',
            'download': f'/api/documents/{pdf.pk}/pdf/',
        },
        'editable_revision': editable_history.revision,
        'expected_status': {'staff_download': 200, 'client_download': 403, 'anonymous_download': 401, 'staff_admins': 403},
    }


def _accounting_baseline(project, context, mail_path):
    period = context.anchor_date.replace(day=1)
    month_end = date(period.year, period.month, monthrange(period.year, period.month)[1])
    records = {}
    for key, (concept, amount) in QA_INCOME_CASES.items():
        income = _resolve(income_detail_queryset(), concept, project=project, source_ref=FAKE_REF, concept=concept)
        if (income.kind != IncomeRecord.Kind.EXPECTED or income.client_id != project.client.profile.pk
                or income.period_date != period or income.total_amount != Decimal(amount)
                or income.paid_amount or income.settlement_id or income.pocket_movement_id):
            raise CommandError(f'{concept} ya no conserva el saldo o relaciones iniciales.')
        records[key] = {
            'id': income.pk, 'key': key, 'concept': concept, 'period': period.isoformat(),
            'total_amount': amount, 'pending_amount': amount,
            'detail': f'/api/accounting/incomes/{income.pk}/detail/',
            'child_ids': list(income.liquid_records.order_by('pk').values_list('pk', flat=True)),
            'settlement_ids': [str(pk) for pk in income.settlement_operations.order_by('pk').values_list('pk', flat=True)],
            'audit_ids': list(AccountingChangeLog.objects.filter(
                entity_type=AccountingChangeLog.EntityType.INCOME, object_id=income.pk,
            ).order_by('pk').values_list('pk', flat=True)),
            'completion_notice_ids': list(IncomeCompletionNotice.objects.filter(
                income=income,
            ).order_by('pk').values_list('pk', flat=True)),
        }
    return {
        'route': '/panel/accounting/incomes',
        'filters': {'date_from': period.isoformat(), 'date_to': month_end.isoformat(), 'kind': 'expected'},
        'incomes': records,
        'effects': {
            'settlements': IncomeSettlement.objects.count(),
            'liquid_incomes': IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count(),
            'pocket_movements': PocketMovement.objects.count(),
            'accounting_audit': AccountingChangeLog.objects.count(),
            'completion_notices': IncomeCompletionNotice.objects.count(),
            'email_log': EmailLog.objects.count(),
            'captured_mail': sum(path.is_file() for path in mail_path.iterdir()) if mail_path.is_dir() else 0,
        },
        'previews': {
            'automatic': {'received': '119.03', 'gustavo': '59.00', 'carlos': '59.00', 'projectapp': '1.03', 'pending': '0.00'},
            'manual': {'received': '119.00', 'gustavo': '50.25', 'carlos': '60.50', 'projectapp': '8.25', 'pending': '0.03'},
            'whole': {'received': '120.00', 'gustavo': '60.00', 'carlos': '60.00', 'projectapp': '0.00', 'pending': '0.00'},
        },
        'expected_status': {'su_income_list': 200, 'su_admins': 200, 'staff_income_list': 403},
    }


def profile_baseline(profile, actors, context, mail_path):
    project = _project(profile)
    if profile == 'b04':
        scenario = _b04_baseline(project, actors)
    elif profile == 'staff':
        scenario = _document_baseline(project)
    else:
        scenario = _accounting_baseline(project, context, mail_path)
    return {
        'actors': [
            {'id': actor.pk, 'key': email, 'role': actor.profile.role,
             'staff': actor.is_staff, 'superuser': actor.is_superuser, 'usable_password': True}
            for email, actor in actors.items()
        ],
        'project': {
            'id': project.pk, 'key': project.name, 'status': project.status,
            'client_user_id': project.client_id, 'client_profile_id': project.client.profile.pk,
        },
        **scenario,
    }
