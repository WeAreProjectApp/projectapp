"""Panel endpoints for the Projects module (Plataforma space).

``/panel/projects`` is the commercial face of ``accounts.Project``: the
platform (JWT) side keeps its own CRUD under ``/api/accounts/projects/``,
while these views speak the panel's language — Django session +
``IsAdminUser`` (the same tier as ``/panel/clients``, which already nests
hostings and incomes per client) and UserProfile ids for the client.

The accounting picker ``GET /api/accounting/projects/`` stays untouched:
it is superuser-scoped and shaped for a dropdown, not for administration.

Endpoints
---------
- ``GET   /api/projects/``                        listing with scope, counts, meta
- ``POST  /api/projects/create/``                 PA-38 minimum create
- ``PATCH /api/projects/<id>/update/``            name/description/document inclusion
- ``POST  /api/projects/<id>/state-transitions/preview/`` consequences
- ``POST  /api/projects/<id>/state-transitions/`` apply confirmed transition
- ``GET   /api/projects/<id>/state-history/``     dated lifecycle history
- ``PATCH /api/projects/<id>/(un)archive/``       legacy endpoint (HTTP 410)
- ``GET   /api/projects/<id>/unlinked-records/``  assign preview (PA-51)
- ``POST  /api/projects/<id>/assign-unlinked/``   assign confirmed ids (PA-51)
- ``GET   /api/projects/<id>/change-client/preview/``  cascade preview
- ``POST  /api/projects/<id>/change-client/``     move/detach cascade
"""

import logging

from django.db.models import (
    Count, Exists, IntegerField, OuterRef, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import Project, UserProfile
from content.api_errors import error_response
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentState,
    HostingRecord,
    IncomeRecord,
)
from content.serializers.accounting import (
    HostingRecordSerializer,
    IncomeRecordSerializer,
    month_label,
)
from content.serializers.document import DocumentListSerializer
from content.serializers.panel_projects import (
    CreatePanelProjectSerializer,
    DeletePanelProjectSerializer,
    PanelProjectSerializer,
    ProjectAssignUnlinkedSerializer,
    ProjectChangeClientSerializer,
    UpdatePanelProjectSerializer,
)
from content.services import accounting_service, project_service
from content.services.project_deletion_service import (
    ProjectDeleteBlocked, delete_empty_project, deletion_preview,
)
from content.services.project_force_deletion import (
    ProjectForceDeleteError, force_delete_project, forced_deletion_preview,
    require_superuser,
)

EntityType = AccountingChangeLog.EntityType

logger = logging.getLogger(__name__)

_SCOPES = ('active', 'archived', 'all')


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def preview_panel_project_delete(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.method == 'POST' or request.query_params.get('force') == 'true':
        require_superuser(request.user)
        from content.serializers.panel_projects import ProjectDeletionSelectionSerializer
        keys = []
        if request.method == 'POST':
            serializer = ProjectDeletionSelectionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            keys = serializer.validated_data['delete_keys']
        return Response(forced_deletion_preview(project, actor=request.user, delete_keys=keys))
    return Response(deletion_preview(project))


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def delete_panel_project(request, project_id):
    serializer = DeletePanelProjectSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if data['force']:
        require_superuser(request.user)
    try:
        if data['force']:
            force_delete_project(
                project_id, actor=request.user,
                confirmation=data['confirmation'], impact_token=data['impact_token'],
                delete_keys=data['delete_keys'],
            )
        else:
            delete_empty_project(project_id, actor=request.user)
    except Project.DoesNotExist:
        return error_response('El proyecto no existe.', status=status.HTTP_404_NOT_FOUND)
    except ProjectDeleteBlocked as exc:
        return error_response(
            str(exc), code='project_delete_blocked',
            hint='Revisa las dependencias o usa Cambiar estado para conservar el historial.',
            errors=exc.preview, status=status.HTTP_409_CONFLICT,
        )
    except ProjectForceDeleteError as exc:
        return error_response(
            str(exc), code=exc.code, errors=exc.preview,
            status=status.HTTP_409_CONFLICT,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


def _count_for(model):
    """Per-project row count as a Subquery annotation.

    Subquery instead of stacked ``Count(distinct=True)`` — same lesson as
    the clients list: parallel reverse joins multiply the rows every other
    aggregate then has to de-duplicate.
    """
    return Coalesce(
        Subquery(
            model.objects
            .filter(project=OuterRef('pk'))
            .order_by()
            .values('project')
            .annotate(total=Count('id'))
            .values('total')[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def _unlinked_count_for(model):
    """Per-project count of the CLIENT's records still without a project.

    "Unlinked" reads from the record's own FK (``project IS NULL``) scoped to
    the project's client — the completion backlog the assign flow works on.
    A client with several projects repeats the number on each of their rows
    on purpose: the backlog belongs to the client, not to one project.
    """
    return Coalesce(
        Subquery(
            model.objects
            .filter(client__user_id=OuterRef('client_id'), project__isnull=True)
            .order_by()
            .values('client__user_id')
            .annotate(total=Count('id'))
            .values('total')[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def _unlinked_documents_count():
    """Documents flavour of :func:`_unlinked_count_for`.

    Separate because the join differs: ``Document.client_user`` points at the
    User directly (same key space as ``Project.client``), with no profile in
    between. The filters mirror ``documents_no_project_count`` in the clients
    list, so both surfaces always show the same backlog.
    """
    return Coalesce(
        Subquery(
            Document.objects
            .filter(
                client_user_id=OuterRef('client_id'),
                project__isnull=True,
                is_archived=False,
            )
            .order_by()
            .values('client_user_id')
            .annotate(total=Count('id'))
            .values('total')[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def _annotated_queryset():
    """Projects with the counts the listing shows, ordered for the table."""
    return (
        Project.objects
        .select_related(
            'client__profile',
            'current_state__group',
            'hosting_subscription',
        )
        .annotate(
            hostings_count=_count_for(HostingRecord),
            incomes_count=_count_for(IncomeRecord),
            unlinked_hostings_count=_unlinked_count_for(HostingRecord),
            unlinked_incomes_count=_unlinked_count_for(IncomeRecord),
            unlinked_documents_count=_unlinked_documents_count(),
        )
        .order_by('name')
    )


def _records_without_project_count():
    """Global backlog: accounting records with a client but no project.

    Client-less rows are excluded — without a client there is no project to
    propose (ownership is per client), and the module's own docs treat an
    empty project as a legitimate state, not pending work.
    """
    return (
        HostingRecord.objects
        .filter(client__isnull=False, project__isnull=True).count()
        + IncomeRecord.objects
        .filter(client__isnull=False, project__isnull=True).count()
    )


def _unlinked_qs(model, project):
    """The project's assignable set: its client's rows with no project yet."""
    return model.objects.filter(
        client__user=project.client, project__isnull=True,
    )


def _unlinked_documents_qs(project):
    """Documents flavour of :func:`_unlinked_qs` (direct User join, active
    only — the mirror of ``documents_no_project_count``). Cuentas de cobro
    of any commercial status qualify: filling a missing project is
    organisational metadata, not a rewrite of the issued fact."""
    return Document.objects.filter(
        client_user=project.client, project__isnull=True, is_archived=False,
    )


def _clients_without_projects_count():
    """How many visible clients still have no project registered.

    ``.clients()`` plus the deactivated filter mirror the ``/panel/clients``
    default, so this number matches the list the module's indicator opens.
    """
    return (
        UserProfile.objects.clients()
        .filter(archived_at__isnull=True)
        .filter(~Exists(Project.objects.filter(client_id=OuterRef('user_id'))))
        .count()
    )


def _scope_or_none(request):
    """Scope pedido: 'active' (default), 'archived' o 'all'. None si es inválido.

    El parámetro selecciona datos, así que un valor inválido responde 400 —
    el mismo criterio que el scope del archivo de documentos.
    """
    raw = str(request.query_params.get('scope') or '').strip().lower()
    if not raw:
        return 'active'
    return raw if raw in _SCOPES else None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_panel_projects(request):
    """Full project listing for the module: rows plus header meta.

    Query params:
        - ``client_profile_id``: optional positive profile ID; filters before
          serialization so a proposal's selector loads only its client's projects.
        - ``scope``: compatibility selector for legacy consumers. The panel
          requests ``all`` and filters by ``current_state`` from the shared
          project catalog.
    """
    scope = _scope_or_none(request)
    if scope is None:
        return error_response(
            "scope debe ser 'active', 'archived' o 'all'.",
            code='invalid_scope',
        )

    qs = _annotated_queryset()
    if 'client_profile_id' in request.query_params:
        try:
            client_profile_id = int(request.query_params['client_profile_id'])
            if client_profile_id < 1:
                raise ValueError
        except (TypeError, ValueError):
            return error_response('Selecciona un cliente válido.', code='invalid_client_profile')
        qs = qs.filter(client__profile__pk=client_profile_id)
    if scope == 'active':
        qs = qs.exclude(status=Project.STATUS_ARCHIVED)
    elif scope == 'archived':
        qs = qs.filter(status=Project.STATUS_ARCHIVED)

    total = Project.objects.count()
    archived = Project.objects.filter(status=Project.STATUS_ARCHIVED).count()
    state_counts = {
        row['current_state_id']: row['total']
        for row in Project.objects.exclude(current_state__isnull=True)
        .values('current_state_id')
        .annotate(total=Count('id'))
    }
    catalog = DocumentState.objects.filter(
        catalog='projects',
        is_active=True,
        merged_into__isnull=True,
    ).select_related('group').order_by('group__order', 'order', 'name')
    return Response({
        'results': PanelProjectSerializer(qs, many=True).data,
        'meta': {
            'total': total,
            'active': total - archived,
            'archived': archived,
            'by_state': [
                {
                    'state_id': state.pk,
                    'name': state.name,
                    'description': state.description,
                    'color': state.color,
                    'system_key': state.system_key,
                    'operational_effect': state.operational_effect,
                    'operational_effect_help': state.operational_effect_help,
                    'count': state_counts.get(state.pk, 0),
                }
                for state in catalog
            ],
            'review_required': Project.objects.filter(
                state_review_required=True,
            ).count(),
            'clients_without_projects': _clients_without_projects_count(),
            'records_without_project': _records_without_project_count(),
        },
    })


def _annotated_row(project_id):
    """The listing-format row for one project — what every mutation answers."""
    return PanelProjectSerializer(_annotated_queryset().get(pk=project_id)).data


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_panel_project(request):
    if 'status' in request.data:
        return Response({
            'status': [
                'El estado legado no se acepta. Usa state_id para elegir '
                'un estado del catálogo de proyectos.'
            ],
        }, status=status.HTTP_400_BAD_REQUEST)
    serializer = CreatePanelProjectSerializer(
        data=request.data,
        context={'request': request},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    project = serializer.save()
    project_service.log_project_event(
        project, project_service.Action.CREATED, {}, request.user,
    )
    logger.info(
        'Panel project %s created for client profile %s',
        project.pk, serializer.client_profile.pk,
    )
    return Response(_annotated_row(project.pk), status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_panel_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if 'client_profile_id' in request.data or 'client' in request.data:
        return error_response(
            'El cliente de un proyecto no se puede cambiar desde el panel.',
            code='client_immutable',
        )
    if 'status' in request.data or 'state_id' in request.data:
        return error_response(
            'Cambia el estado desde el selector para revisar sus consecuencias.',
            code='project_state_transition_required',
            hint='Usa Cambiar estado en las acciones del proyecto.',
        )
    serializer = UpdatePanelProjectSerializer(
        project, data=request.data, partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    snapshot = project_service.project_snapshot(project)
    serializer.save()
    project_service.log_project_event(
        project, project_service.Action.UPDATED, snapshot, request.user,
    )
    return Response(_annotated_row(project.pk))


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def archive_panel_project(request, project_id):
    return error_response(
        'Archivado fue reemplazado por el ciclo administrable del proyecto.',
        code='project_archive_replaced',
        hint='Usa Cambiar estado y elige Dado de baja si corresponde.',
        status=status.HTTP_410_GONE,
    )


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def unarchive_panel_project(request, project_id):
    return error_response(
        'Restaurar fue reemplazado por una transición con histórico.',
        code='project_archive_replaced',
        hint='Usa Cambiar estado y elige el estado real del proyecto.',
        status=status.HTTP_410_GONE,
    )


def _archived_assign_error():
    return error_response(
        'El proyecto está en un estado terminal y no recibe registros nuevos.',
        code='project_terminal',
        hint='Cámbialo a un estado operativo antes de asignar registros.',
    )


def _project_is_terminal(project):
    state = getattr(project, 'current_state', None)
    return bool(state and state.operational_effect in (
        DocumentState.OperationalEffect.COMPLETED,
        DocumentState.OperationalEffect.DECOMMISSIONED,
    ))


def _unlinked_payload(project):
    """The visible plan: every assignable record, labelled for a human.

    Hostings lean on ``display_label`` (client — project — domain fallback);
    incomes carry concept plus kind and period so two same-concept rows stay
    distinguishable in the confirmation list.
    """
    hostings = [
        {'id': record.pk, 'label': record.display_label}
        for record in _unlinked_qs(HostingRecord, project)
    ]
    incomes = [
        {
            'id': record.pk,
            'label': record.concept,
            'kind_label': record.get_kind_display(),
            'period_label': month_label(record.period_date),
        }
        for record in _unlinked_qs(IncomeRecord, project)
    ]
    documents = [
        {
            'id': record.pk,
            'label': record.title,
            'type_label': record.document_type.name if record.document_type_id else '',
            # Issued cuentas show their number: it is how the operator knows
            # them, and the visible hint that this one is a fill, not an edit.
            'number': record.public_number,
        }
        for record in _unlinked_documents_qs(project).select_related('document_type')
    ]
    return {
        'client': PanelProjectSerializer().get_client(project),
        'hostings': hostings,
        'incomes': incomes,
        'documents': documents,
        'total': len(hostings) + len(incomes) + len(documents),
    }


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_project_unlinked_records(request, project_id):
    """Preview for the assign flow: the client's records without a project.

    This is the list the operator confirms against — the apply endpoint
    receives these ids back, so nothing is ever assigned sight unseen.
    """
    project = get_object_or_404(Project, pk=project_id)
    if _project_is_terminal(project):
        return _archived_assign_error()
    return Response(_unlinked_payload(project))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def assign_project_unlinked_records(request, project_id):
    """Assign this project to the confirmed subset of its client's
    unlinked records.

    Explicit ids: what was confirmed is what runs. Ids that no longer exist
    → 409 ``records_not_found``; ids that stopped being assignable (they
    gained a project, or belong to another client) → 409 ``records_changed``.
    Both run before the service, so its atomic block never opens on a stale
    plan — the same contract as the accounting bulk-assign.
    """
    project = get_object_or_404(Project, pk=project_id)
    if _project_is_terminal(project):
        return _archived_assign_error()

    serializer = ProjectAssignUnlinkedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    hosting_ids = serializer.validated_data['hosting_ids']
    income_ids = serializer.validated_data['income_ids']
    document_ids = serializer.validated_data['document_ids']

    # Document is deliberately not in ENTITY_MODELS (it never enters the
    # generic accounting pipeline), so its existence check lives here.
    missing_documents = sorted(
        set(document_ids)
        - set(
            Document.objects
            .filter(pk__in=document_ids).values_list('pk', flat=True),
        ),
    )
    missing = (
        accounting_service.missing_record_ids(EntityType.HOSTING, hosting_ids)
        + accounting_service.missing_record_ids(EntityType.INCOME, income_ids)
        + missing_documents
    )
    if missing:
        count = len(missing)
        verb = 'existe' if count == 1 else 'existen'
        return error_response(
            f'{count} de los registros seleccionados ya no {verb}.',
            code='records_not_found',
            hint='La lista se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'missing_ids': missing},
        )

    changed = sorted(
        (
            set(hosting_ids)
            - set(_unlinked_qs(HostingRecord, project)
                  .filter(pk__in=hosting_ids).values_list('pk', flat=True))
        )
        | (
            set(income_ids)
            - set(_unlinked_qs(IncomeRecord, project)
                  .filter(pk__in=income_ids).values_list('pk', flat=True))
        )
        | (
            set(document_ids)
            - set(_unlinked_documents_qs(project)
                  .filter(pk__in=document_ids).values_list('pk', flat=True))
        )
    )
    if changed:
        count = len(changed)
        noun = 'registro' if count == 1 else 'registros'
        return error_response(
            f'{count} {noun} de la lista ya no se pueden asignar '
            '(ganaron proyecto o cambiaron de cliente).',
            code='records_changed',
            hint='La lista se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'changed_ids': changed},
        )

    assigned_hostings = accounting_service.bulk_assign_project(
        EntityType.HOSTING, hosting_ids, project, request.user,
    ) if hosting_ids else []
    assigned_incomes = accounting_service.bulk_assign_project(
        EntityType.INCOME, income_ids, project, request.user,
    ) if income_ids else []
    assigned_documents = accounting_service.assign_project_to_documents(
        document_ids, project, request.user,
    ) if document_ids else []
    logger.info(
        'Panel project %s assigned to %s hostings, %s incomes and %s documents',
        project.pk, len(assigned_hostings), len(assigned_incomes),
        len(assigned_documents),
    )
    # The cascade also rewrites the liquid children of an assigned expected
    # income; without them in the response the panel would map-replace the
    # parent and keep a stale child row. The counts stay parents-only — they
    # answer for the plan the operator confirmed.
    expected_pks = [
        record.pk for record in assigned_incomes
        if record.kind == IncomeRecord.Kind.EXPECTED
    ]
    income_rows = IncomeRecord.objects.filter(
        Q(pk__in=[record.pk for record in assigned_incomes])
        | Q(expected_income_id__in=expected_pks),
    )
    return Response({
        'assigned_hostings': len(assigned_hostings),
        'assigned_incomes': len(assigned_incomes),
        'assigned_documents': len(assigned_documents),
        # Full rows, not just counts: an accounting tab open in the SPA
        # rebuilds from these instead of showing the stale "—" project cell.
        # Bounded by construction — only the confirmed preview ids run.
        'hostings': HostingRecordSerializer(assigned_hostings, many=True).data,
        'incomes': IncomeRecordSerializer(income_rows, many=True).data,
        'documents': DocumentListSerializer(assigned_documents, many=True).data,
        'project': _annotated_row(project.pk),
    })


def _terminal_change_client_error():
    return error_response(
        'Un proyecto cerrado no puede cambiar de cliente.',
        code='project_terminal',
        hint='Confirma primero un estado operativo y vuelve a intentar.',
    )


def _resolve_target_profile(project, raw_profile_id):
    """(profile, error_response) for the change-client destination."""
    try:
        profile_id = int(raw_profile_id)
    except (TypeError, ValueError):
        return None, error_response(
            'Indica el cliente destino.', code='client_not_found',
        )
    profile = UserProfile.objects.clients().filter(pk=profile_id).first()
    if profile is None:
        return None, error_response(
            'Ese cliente no existe o no es un perfil de cliente.',
            code='client_not_found',
        )
    if project.client_id == profile.user_id:
        return None, error_response(
            'El proyecto ya pertenece a ese cliente.', code='same_client',
        )
    return profile, None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def preview_project_client_change(request, project_id):
    """Impact preview of moving a project to another client.

    Nothing here writes: the operator sees every record the cascade will
    touch — and the ones it refuses to touch (issued cuentas, incomes with
    an active cuenta) — before choosing a mode.
    """
    project = get_object_or_404(Project, pk=project_id)
    if _project_is_terminal(project):
        return _terminal_change_client_error()
    profile, error = _resolve_target_profile(
        project, request.query_params.get('client_profile_id'),
    )
    if error:
        return error
    return Response(project_service.change_client_preview(project, profile))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def change_project_client(request, project_id):
    """Move the project to another client, cascading per the chosen mode.

    The generic update keeps refusing ``client`` (``client_immutable``):
    this endpoint is the only path, so an ownership change is always
    explicit, previewed and audited. The hosting/income ids are the
    staleness token — same PA-51 contract: the plan that was shown is the
    plan that runs, or nothing runs (both checks fire before the service,
    so its atomic block never opens on a stale preview).
    """
    project = get_object_or_404(Project, pk=project_id)
    if _project_is_terminal(project):
        return _terminal_change_client_error()

    serializer = ProjectChangeClientSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    mode = serializer.validated_data['mode']
    if mode not in project_service.MODES:
        return error_response(
            "Elige qué hacer con los registros: 'move' (mover al nuevo "
            "cliente) o 'detach' (desvincular del proyecto).",
            code='invalid_mode',
        )
    profile, error = _resolve_target_profile(
        project, serializer.validated_data['client_profile_id'],
    )
    if error:
        return error

    current_hostings = set(
        HostingRecord.objects.filter(project=project)
        .values_list('pk', flat=True),
    )
    current_incomes = set(
        IncomeRecord.objects.filter(project=project)
        .values_list('pk', flat=True),
    )
    current_communications = set(
        project.communication_threads.values_list('pk', flat=True),
    )
    sent_hostings = set(serializer.validated_data['hosting_ids'])
    sent_incomes = set(serializer.validated_data['income_ids'])
    sent_communications = set(
        serializer.validated_data['communication_thread_ids'],
    )
    missing = sorted(
        (sent_hostings - current_hostings)
        | (sent_incomes - current_incomes)
        | (sent_communications - current_communications),
    )
    if missing:
        count = len(missing)
        noun = 'registro' if count == 1 else 'registros'
        verb = 'está' if count == 1 else 'están'
        return error_response(
            f'{count} {noun} del plan ya no {verb} vinculados al proyecto.',
            code='records_not_found',
            hint='La vista previa se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'missing_ids': missing},
        )
    changed = sorted(
        (current_hostings - sent_hostings)
        | (current_incomes - sent_incomes)
        | (current_communications - sent_communications),
    )
    if changed:
        count = len(changed)
        noun = 'registro' if count == 1 else 'registros'
        verb = 'vinculó' if count == 1 else 'vincularon'
        return error_response(
            f'{count} {noun} se {verb} al proyecto después de la vista previa.',
            code='records_changed',
            hint='La vista previa se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'changed_ids': changed},
        )

    result = project_service.change_client_apply(
        project, profile, mode, request.user,
    )
    logger.info(
        'Panel project %s changed client to profile %s (mode=%s)',
        project.pk, profile.pk, mode,
    )
    return Response({'project': _annotated_row(project.pk), **result})
