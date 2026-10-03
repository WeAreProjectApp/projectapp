"""
Admin endpoints for managing proposal clients (UserProfile, role=client).

These power the new ``/panel/clients`` page, the autocomplete in the proposal
create/edit form, and the orphan-cleanup workflow. They live alongside the
proposal admin views in ``content`` because they share the same auth context
(Django session + ``IsAdminUser``) and URL prefix as the rest of the panel.

Endpoints
---------
- ``GET    /api/proposals/client-profiles/``               list (search, orphans, limit)
- ``GET    /api/proposals/client-profiles/search/?q=``     paged autocomplete
- ``GET    /api/proposals/client-profiles/status-counts/`` per-status counts
- ``GET    /api/proposals/client-profiles/<id>/``          detail with nested proposals
- ``POST   /api/proposals/client-profiles/create/``        standalone create
- ``PATCH  /api/proposals/client-profiles/<id>/update/``   update + cascade snapshots
- ``DELETE /api/proposals/client-profiles/<id>/delete/``   orphan-only delete
- ``GET    /api/proposals/client-profiles/<id>/archive-preview/`` cascade impact
- ``POST   /api/proposals/client-profiles/<id>/archive/``  archive + cascade
- ``POST   /api/proposals/client-profiles/<id>/unarchive/`` bring the client back
"""

import logging

from django.db.models import (
    CharField, Count, DateTimeField, Exists, IntegerField, Max, OuterRef, Q,
    Subquery, Sum, Value,
)
from django.db.models.functions import Coalesce, Concat, Lower, NullIf, Trim
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import Project, UserProfile
from accounts.serializers import ProjectListSerializer
from accounts.services import client_archive_service, proposal_client_service
from accounts.services.billing_code import (
    billing_code_error,
    normalize_billing_code,
)
from content.models import (
    BusinessProposal, CommunicationThread, Document, DocumentFolder, EmailLog,
    HostingRecord, IncomeRecord, WebAppDiagnostic,
)
from content.serializers.accounting import (
    HostingRecordSerializer,
    IncomeRecordSerializer,
    money_str,
)
from content.serializers.proposal import ProposalListSerializer
from content.services import accounting_service
from content.services.project_state_service import ProjectStateError
from content.serializers.document import ClientDocumentRowSerializer
from content.serializers.proposal_clients import (
    ClientBillingFieldsSerializer,
    ProposalClientSearchSerializer,
    ProposalClientSerializer,
)
from content.serializers.diagnostic import DiagnosticListSerializer

logger = logging.getLogger(__name__)

CLIENT_SEARCH_PAGE_SIZE = 20


def _bounded_non_negative_int(raw_value, *, default, maximum=None):
    """Parse a query integer without letting malformed paging break search."""
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    value = max(0, value)
    return min(value, maximum) if maximum is not None else value


def _base_queryset():
    """Return a queryset of client profiles with the standard annotations."""
    return (
        UserProfile.objects.clients()
        .annotate(
            proposals_count=Count('proposals', distinct=True),
            projects_count=Count('user__projects', distinct=True),
            diagnostics_count=Count('web_app_diagnostics', distinct=True),
            last_proposal_at=Max('proposals__last_activity_at'),
            accepted_count=Count(
                'proposals',
                filter=Q(proposals__status__in=['accepted', 'finished']),
                distinct=True,
            ),
            last_status=Subquery(
                BusinessProposal.objects
                .filter(client=OuterRef('pk'))
                .order_by('-last_activity_at')
                .values('status')[:1]
            ),
            last_sent_at=Max('proposals__sent_at'),
            # Subquery, not a fourth Count(distinct=True): three reverse
            # joins already fan out here, and a fourth multiplies the rows
            # every aggregate above has to de-duplicate.
            incomes_count=Coalesce(
                Subquery(
                    IncomeRecord.objects
                    .filter(client=OuterRef('pk'))
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            hostings_count=Coalesce(
                Subquery(
                    HostingRecord.objects
                    .filter(client=OuterRef('pk'))
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # Feeds the "Con hosting cobrado" preset. 'Cobrado' is the same
            # `is_active` the hosting row already renders as "Vigente", so the
            # count here reconciles with what the Hostings tab shows.
            active_hostings_count=Coalesce(
                Subquery(
                    HostingRecord.objects
                    .filter(client=OuterRef('pk'), is_active=True)
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # Feeds the "Con proyecto activo" preset. `projects_count` above
            # counts every status, so an archived-only client would pass it;
            # Project.client points at the User, not at this profile.
            active_projects_count=Coalesce(
                Subquery(
                    Project.objects
                    .filter(
                        client=OuterRef('user_id'),
                        status=Project.STATUS_ACTIVE,
                    )
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # Feeds the "Con diagnóstico facturado" subfilter, which reads the
            # MONEY rather than the entity: a diagnostic billed without its
            # WebAppDiagnostic ever being created is still billed, and asking
            # for both would hide exactly the rows worth chasing. `lost` is
            # written off, so it never counts; legacy rows carry origin='' and
            # simply do not match.
            diagnostic_incomes_count=Coalesce(
                Subquery(
                    IncomeRecord.objects
                    .filter(
                        client=OuterRef('pk'),
                        origin=IncomeRecord.Origin.DIAGNOSTIC,
                    )
                    .exclude(kind=IncomeRecord.Kind.LOST)
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # The commercially valuable cut: a diagnostic no proposal ever
            # followed. Two correlations, one level each — the inner NOT EXISTS
            # binds to the diagnostic row, the outer Subquery to the client;
            # WebAppDiagnostic carries client_id itself, which is what keeps
            # this at OuterRef(...) instead of OuterRef(OuterRef(...)).
            #
            # ~Exists and not __in: BusinessProposal.client is nullable, so one
            # legacy row with a NULL client would make a NOT IN return nothing
            # at all. Anchored on the send rather than on created_at, because
            # created_at is when we opened the draft — a proposal written while
            # the diagnostic still sat unsent cannot be its outcome.
            diagnostics_without_proposal_count=Coalesce(
                Subquery(
                    WebAppDiagnostic.objects
                    .filter(client=OuterRef('pk'))
                    .exclude(status=WebAppDiagnostic.Status.DRAFT)
                    .filter(~Exists(
                        BusinessProposal.objects.filter(
                            client_id=OuterRef('client_id'),
                            created_at__gt=Coalesce(
                                OuterRef('initial_sent_at'),
                                OuterRef('created_at'),
                            ),
                        )
                    ))
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # The Emails module counts contact, so all three read the rows
            # addressed to the client. The internal notices about their
            # records are in the modal, marked as such, but a digest that
            # reached the team is not contact with them.
            emails_sent_count=Coalesce(
                Subquery(
                    EmailLog.objects
                    .filter(
                        client=OuterRef('pk'),
                        audience=EmailLog.Audience.CLIENT,
                        delivery_role=EmailLog.DeliveryRole.PRIMARY,
                    )
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            emails_failed_count=Coalesce(
                Subquery(
                    EmailLog.objects
                    .filter(
                        client=OuterRef('pk'),
                        audience=EmailLog.Audience.CLIENT,
                        status=EmailLog.Status.FAILED,
                        delivery_role=EmailLog.DeliveryRole.PRIMARY,
                    )
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # Top-1 rather than Max(): with the (client, audience, sent_at)
            # index this is a backwards scan that stops at the first row, and
            # it carries no GROUP BY. `last_proposal_at` above gets to use
            # Max() because `proposals` is already joined for proposals_count;
            # nothing joins email_logs.
            last_email_at=Subquery(
                EmailLog.objects
                .filter(
                    client=OuterRef('pk'),
                    audience=EmailLog.Audience.CLIENT,
                    delivery_role=EmailLog.DeliveryRole.PRIMARY,
                )
                .order_by('-sent_at')
                .values('sent_at')[:1],
                output_field=DateTimeField(),
            ),
            # The Documents module counts what the manager's list shows for
            # the client: active documents only — archiving is that module's
            # own visibility axis, so the pill reconciles with the list the
            # jump lands on. Document.client_user points at the User.
            documents_count=Coalesce(
                Subquery(
                    Document.objects
                    .filter(client_user=OuterRef('user_id'), is_archived=False)
                    .order_by()
                    .values('client_user')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # "A medio asociar": del cliente pero sin proyecto — la lista de
            # revisión que deja la pasada retroactiva.
            documents_no_project_count=Coalesce(
                Subquery(
                    Document.objects
                    .filter(
                        client_user=OuterRef('user_id'),
                        is_archived=False,
                        project__isnull=True,
                    )
                    .order_by()
                    .values('client_user')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            # "Con carpeta": las carpetas que dicen ser de este cliente. Se
            # cuenta la relación de la carpeta, no las carpetas donde tiene
            # documentos — que una carpeta sea suya es ahora un dato, no una
            # inferencia por el nombre.
            document_folders_count=Coalesce(
                Subquery(
                    DocumentFolder.objects
                    .filter(client_user=OuterRef('user_id'), is_archived=False)
                    .order_by()
                    .values('client_user')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            last_document_at=Subquery(
                Document.objects
                .filter(client_user=OuterRef('user_id'), is_archived=False)
                .order_by('-created_at')
                .values('created_at')[:1],
                output_field=DateTimeField(),
            ),
            # Communications is a separate product module, but these three
            # summaries make the relationship navigable from the client row.
            communications_count=Coalesce(
                Subquery(
                    CommunicationThread.objects
                    .filter(client=OuterRef('pk'))
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            open_communications_count=Coalesce(
                Subquery(
                    CommunicationThread.objects
                    .filter(
                        client=OuterRef('pk'),
                        status=CommunicationThread.Status.OPEN,
                    )
                    .order_by()
                    .values('client')
                    .annotate(total=Count('id'))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            last_communication_at=Subquery(
                CommunicationThread.objects
                .filter(client=OuterRef('pk'))
                .order_by('-last_activity_at')
                .values('last_activity_at')[:1],
                output_field=DateTimeField(),
            ),
        )
    )


def _get_profile_or_404(client_id):
    return _base_queryset().filter(pk=client_id).first()


def _parse_bool(raw):
    """Parse a permissive boolean query param. ``None`` means 'unspecified'."""
    if raw is None:
        return None
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _billing_code_taken(code, *, exclude_pk=None):
    """Whether another profile already holds ``code`` (the column is unique)."""
    taken = UserProfile.objects.filter(billing_code=code)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    return taken.exists()


def _validated_billing_fields(request_data):
    """(nit, billing_code, error_response) for a create payload.

    Checked up front so a duplicate code answers with a 400 the panel can show
    instead of the IntegrityError the unique column would otherwise raise.
    """
    nit = (request_data.get('nit') or '').strip()
    code = normalize_billing_code(request_data.get('billing_code'))
    if code:
        error = billing_code_error(code)
        if error:
            return nit, code, Response(
                {'error': 'invalid_billing_code', 'message': error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _billing_code_taken(code):
            return nit, code, Response(
                {
                    'error': 'billing_code_taken',
                    'message': 'Ese código de facturación ya está en uso.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    return nit, code, None


# ---------------------------------------------------------------------------
# List + search
# ---------------------------------------------------------------------------

# The orphan predicate: no proposals, projects, diagnostics, incomes,
# hostings or communication threads. Matches ``is_orphan`` and the delete guard.
_ORPHAN_PREDICATE = {
    'proposals_count': 0, 'projects_count': 0, 'diagnostics_count': 0,
    'incomes_count': 0, 'hostings_count': 0, 'communications_count': 0,
}


def _apply_search(qs, search):
    """Case-insensitive match on email, first/last name and company."""
    if not search:
        return qs
    return qs.filter(
        Q(user__email__icontains=search)
        | Q(user__first_name__icontains=search)
        | Q(user__last_name__icontains=search)
        | Q(company_name__icontains=search)
    )


def _apply_status(qs, *, orphans, archived):
    """
    Client-status cut, shared by the list and its counts so the number in the
    selector can never disagree with the rows the same selection returns.

    ``orphans`` is tri-state (None = no cut). ``archived`` is exclusive:
    archived clients are hidden everywhere except their own tab, which is what
    makes the four options add up to the whole table.
    """
    if orphans is True:
        qs = qs.filter(**_ORPHAN_PREDICATE)
    elif orphans is False:
        qs = qs.exclude(**_ORPHAN_PREDICATE)
    return qs.filter(archived_at__isnull=not archived)


def _archived_param(request):
    """Read the archived cut, honouring the pre-rename ``inactive`` spelling.

    The panel was shipped with ``?inactive=1`` and the word only changed for
    the operator's vocabulary, so the old spelling stays valid: a bookmarked
    URL or a saved tab must not silently return the active list instead.
    """
    for key in ('archived', 'inactive'):
        raw = request.query_params.get(key)
        if raw is not None:
            return _parse_bool(raw) is True
    return False


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_proposal_clients(request):
    """
    Return all client profiles with annotated proposal counts.

    Query params:
        - ``search``: case-insensitive match on email, first/last name, company.
        - ``orphans``: ``true`` returns only profiles with 0 proposals AND
          0 projects AND 0 diagnostics AND 0 incomes AND 0 hostings AND
          0 communication threads
          (matches ``is_orphan`` and the delete guard). ``false`` returns
          the inverse. Omit to include all.
        - ``without_projects``: ``true`` returns only clients with zero
          platform projects (a strictly weaker predicate than ``orphans``);
          ``false`` returns the inverse. Feeds the Projects module indicator.
        - ``archived``: ``true`` returns only archived clients.
          Omitted/``false`` excludes them (panel default). ``inactive`` is
          still accepted as the pre-rename spelling.
        - ``limit``: max rows to return (default 100, hard cap 500).
    """
    qs = _apply_search(_base_queryset(), (request.query_params.get('search') or '').strip())

    qs = _apply_status(
        qs,
        orphans=_parse_bool(request.query_params.get('orphans')),
        archived=_archived_param(request),
    )

    without_projects = _parse_bool(request.query_params.get('without_projects'))
    if without_projects is True:
        qs = qs.filter(projects_count=0)
    elif without_projects is False:
        qs = qs.filter(projects_count__gt=0)

    try:
        limit = min(int(request.query_params.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100

    qs = qs.prefetch_related('proposals').order_by('-last_proposal_at', '-updated_at')[:limit]
    return Response(ProposalClientSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def proposal_client_status_counts(request):
    """
    Match count per client-status option, honouring the same ``search``.

    /panel/clients cuts by status on the server, so it only ever holds the rows
    of the selected one; without this the selector could not label the options
    it is not showing. Counting here (instead of over the loaded rows, like the
    module subfilters do) also keeps the numbers honest past the list's 500-row
    cap.
    """
    qs = _apply_search(_base_queryset(), (request.query_params.get('search') or '').strip())

    def count(**kwargs):
        return _apply_status(qs, **kwargs).count()

    return Response({
        'all': count(orphans=None, archived=False),
        'active': count(orphans=False, archived=False),
        'orphans': count(orphans=True, archived=False),
        'archived': count(orphans=None, archived=True),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def search_proposal_clients(request):
    """Lightweight, progressively pageable autocomplete for client pickers.

    The payload intentionally stays an array for backwards compatibility. The
    complete filtered count travels in ``X-Total-Count`` so the frontend can
    request the next slice without guessing whether another page exists.
    ``order=name|-name`` keeps every page on the same stable alphabetical
    contract; absent or unknown values preserve the historical A-Z default.
    """
    query = (request.query_params.get('q') or '').strip()
    requested_order = (
        request.query_params.get('order') or 'name'
    ).strip().lower()
    name_order = (
        '-_display_name_sort'
        if requested_order == '-name'
        else '_display_name_sort'
    )
    limit = _bounded_non_negative_int(
        request.query_params.get('limit'),
        default=CLIENT_SEARCH_PAGE_SIZE,
        maximum=CLIENT_SEARCH_PAGE_SIZE,
    ) or CLIENT_SEARCH_PAGE_SIZE
    offset = _bounded_non_negative_int(
        request.query_params.get('offset'),
        default=0,
    )
    qs = UserProfile.objects.clients()
    # Archived clients stay out of every picker by default. Leaving them in is
    # how a filed-away client keeps collecting brand-new proposals, incomes and
    # hostings: the operator types three letters, the old name comes up, and
    # nothing on the row says it was archived. ``include_archived`` is for the
    # flows that legitimately need them — reassigning a folder or a thread to a
    # client that was already put away.
    if _parse_bool(request.query_params.get('include_archived')) is not True:
        qs = qs.filter(archived_at__isnull=True)
    if query:
        qs = qs.filter(
            Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(company_name__icontains=query)
        )
    qs = qs.annotate(
        _display_name_sort=Lower(Coalesce(
            NullIf(
                Trim(Concat(
                    'user__first_name', Value(' '), 'user__last_name',
                )),
                Value(''),
            ),
            NullIf(Trim('company_name'), Value('')),
            NullIf(Trim('user__email'), Value('')),
            Value('Cliente'),
            output_field=CharField(),
        )),
    ).order_by(name_order, 'pk')
    total = qs.count()
    rows = qs[offset:offset + limit]
    response = Response(ProposalClientSearchSerializer(rows, many=True).data)
    response['X-Total-Count'] = str(total)
    return response


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_proposal_client(request, client_id):
    """Return a client with everything that belongs to them nested:
    proposals, platform projects, diagnostics, accounting hostings and
    incomes — the one surface that answers "todo sobre este cliente"."""
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )
    payload = ProposalClientSerializer(profile).data
    proposals = (
        profile.proposals
        .select_related('client__user')
        .order_by('-created_at')
    )
    payload['proposals'] = ProposalListSerializer(proposals, many=True).data
    projects = profile.user.projects.select_related('client__profile').order_by('-created_at')
    payload['projects'] = ProjectListSerializer(projects, many=True).data
    diagnostics = profile.web_app_diagnostics.select_related('client__user').order_by('-created_at')
    payload['diagnostics'] = DiagnosticListSerializer(diagnostics, many=True).data

    # select_related + the list annotations keep this per-row-query free:
    # the serializers fall back to one query per row for the client display
    # name and the collection-account flags otherwise.
    hostings = (
        profile.hosting_records
        .select_related('client__user')
        .order_by('-is_active', 'client_name')
    )
    payload['hostings'] = HostingRecordSerializer(hostings, many=True).data
    # What the hostings of this client cost per month, active ones only —
    # the number the per-client view exists to answer.
    payload['hostings_monthly_total'] = money_str(
        hostings.filter(is_active=True).aggregate(
            total=Sum('monthly_value'),
        )['total'] or 0,
    )

    incomes = (
        profile.income_records
        .select_related('client__user')
        .annotate(
            paid_amount=accounting_service.paid_amount_subquery(),
            **accounting_service.collection_account_subqueries(),
        )
        .order_by('-period_date')
    )
    payload['incomes'] = IncomeRecordSerializer(incomes, many=True).data

    # Los últimos 5 alcanzan para la ficha; "Ver todos" salta al módulo de
    # Documentos ya filtrado por el cliente, que es donde se trabaja en serio.
    documents = (
        profile.user.client_documents
        .filter(is_archived=False)
        .select_related('project', 'folder')
        .order_by('-created_at')
    )
    payload['documents'] = ClientDocumentRowSerializer(
        documents[:5], many=True,
    ).data
    payload['documents_total'] = documents.count()
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_proposal_client(request):
    """
    Standalone client creation (no proposal yet, no invitation email).

    Body: ``{name, email?, phone?, company?, nit?, cedula?, address?, billing_code?}``. ``email``
    is optional — when omitted, a placeholder is generated. The billing pair
    matches the edit form field for field, so a client can be filed complete in
    one step instead of being created and immediately edited.
    """
    name = (request.data.get('name') or '').strip()
    email = (request.data.get('email') or '').strip()
    phone = (request.data.get('phone') or '').strip()
    company = (request.data.get('company') or '').strip()

    if not name and not email and not company:
        return Response(
            {'error': 'name_or_email_required',
             'message': 'Debes proporcionar al menos un nombre, email o empresa.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    billing_serializer = ClientBillingFieldsSerializer(data=request.data)
    billing_serializer.is_valid(raise_exception=True)
    billing_data = billing_serializer.validated_data
    nit, billing_code, error_response = _validated_billing_fields({
        'nit': billing_data.get('nit', ''),
        'billing_code': request.data.get('billing_code'),
    })
    if error_response is not None:
        return error_response

    try:
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name=name, email=email, phone=phone, company=company,
            nit=nit, cedula=billing_data.get('cedula', ''),
            address=billing_data.get('address', ''), billing_code=billing_code,
        )
    except ValueError as exc:
        return Response(
            {'error': 'invalid_client_data', 'message': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile = _get_profile_or_404(profile.pk)
    return Response(
        ProposalClientSerializer(profile).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_proposal_client(request, client_id):
    """Update the client profile + cascade snapshots to all linked proposals."""
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )

    # Billing identity fields live on the profile only (no proposal cascade).
    billing_serializer = ClientBillingFieldsSerializer(data=request.data)
    billing_serializer.is_valid(raise_exception=True)
    payload = dict(billing_serializer.validated_data)
    if 'billing_code' in request.data:
        code = normalize_billing_code(request.data.get('billing_code'))
        error = billing_code_error(code) if code else None
        if error:
            return Response(
                {'error': 'invalid_billing_code', 'message': error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if code and _billing_code_taken(code, exclude_pk=profile.pk):
            return Response(
                {
                    'error': 'billing_code_taken',
                    'message': 'Ese código de facturación ya está en uso.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload['billing_code'] = code or ''
    for key in ('name', 'email', 'phone', 'company'):
        if key in request.data:
            payload[key] = request.data[key]
    if 'is_archived' in request.data:
        # Archiving suspends the client's projects and cancels their future
        # billing. That has to be previewed, so it does not ride along with an
        # ordinary identity save — same rule the projects module applies to
        # ``status``/``state_id``.
        return Response(
            {
                'error': 'client_archive_transition_required',
                'message': (
                    'Archiva el cliente desde su propia acción para revisar '
                    'las consecuencias sobre sus proyectos.'
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not payload:
        return Response(
            ProposalClientSerializer(profile).data, status=status.HTTP_200_OK,
        )

    try:
        proposal_client_service.update_client_profile(profile, **payload)
    except ValueError as exc:
        return Response(
            {'error': 'update_conflict', 'message': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile = _get_profile_or_404(client_id)
    return Response(ProposalClientSerializer(profile).data)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_proposal_client(request, client_id):
    """
    Delete a client (and the underlying ``User``) only if it has zero
    proposals and zero platform projects. Returns 400 with a machine-readable
    error code otherwise.
    """
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )

    try:
        proposal_client_service.delete_orphan_client(profile)
    except ValueError as exc:
        # Service raises ``ValueError('client_has_proposals:N')`` etc.
        code, _, count = str(exc).partition(':')
        return Response(
            {'error': code, 'count': int(count) if count.isdigit() else None},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Archive (client) + project cascade
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def preview_client_archive(request, client_id):
    """What archiving this client would do to its projects. Writes nothing.

    The operator sees every project the cascade moves and what it costs before
    confirming, because suspending a project cancels its future incomes and
    archives its future hosting charges, and none of that comes back.
    """
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )
    try:
        preview = client_archive_service.archive_client_preview(profile)
    except client_archive_service.ClientArchiveError as exc:
        return Response(
            {'error': exc.code, 'message': exc.message},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(preview)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def archive_proposal_client(request, client_id):
    """Archive the client and suspend the projects named in ``transitions``.

    ``transitions`` echoes the preview the operator actually saw — one
    ``impact_token`` per project. A mismatch is a 409, not a silent re-preview:
    the confirmation would otherwise cover numbers nobody read.
    """
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )

    raw = request.data.get('transitions')
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return Response(
            {
                'error': 'invalid_transitions',
                'message': 'transitions debe ser una lista.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    transitions = []
    for item in raw:
        if not isinstance(item, dict):
            return Response(
                {
                    'error': 'invalid_transitions',
                    'message': 'Cada transición debe traer project_id e '
                               'impact_token.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            project_id = int(item.get('project_id'))
        except (TypeError, ValueError):
            return Response(
                {
                    'error': 'invalid_transitions',
                    'message': 'project_id inválido.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        transitions.append({
            'project_id': project_id,
            'impact_token': item.get('impact_token') or '',
        })

    try:
        result = client_archive_service.archive_client(
            profile, transitions=transitions, actor=request.user,
        )
    except client_archive_service.ClientArchiveError as exc:
        return Response(
            {'error': exc.code, 'message': exc.message},
            status=status.HTTP_409_CONFLICT,
        )
    except ProjectStateError as exc:
        # A stale token or a blocker raised inside the per-project transition.
        return Response(
            {'error': exc.code, 'message': str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    profile = _get_profile_or_404(client_id)
    return Response({
        'client': ProposalClientSerializer(profile).data,
        'suspended_projects': result['suspended_projects'],
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def unarchive_proposal_client(request, client_id):
    """Bring the client back, leaving its projects suspended.

    Reactivating a project restores its label but not the incomes the cascade
    cancelled, so it stays an explicit per-project decision. The response names
    the ones still parked so the UI can say it out loud.
    """
    profile = _get_profile_or_404(client_id)
    if profile is None:
        return Response(
            {'error': 'client_not_found'}, status=status.HTTP_404_NOT_FOUND,
        )
    try:
        result = client_archive_service.unarchive_client(
            profile, actor=request.user,
        )
    except client_archive_service.ClientArchiveError as exc:
        return Response(
            {'error': exc.code, 'message': exc.message},
            status=status.HTTP_409_CONFLICT,
        )

    profile = _get_profile_or_404(client_id)
    return Response({
        'client': ProposalClientSerializer(profile).data,
        'still_suspended': result['still_suspended'],
    })
