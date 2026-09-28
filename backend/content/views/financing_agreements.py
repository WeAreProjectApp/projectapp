"""Session-authenticated admin API for financing addenda."""

from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import Project, UserProfile
from content.models import (
    AccountingSettings,
    BusinessProposal,
    FinancingAgreement,
    FinancingAgreementTemplate,
    FinancingPolicyRevision,
)
from content.serializers.financing import (
    FinancingAgreementDetailSerializer,
    FinancingAgreementListSerializer,
    FinancingAgreementTemplateSerializer,
    FinancingAgreementWriteSerializer,
    FinancingPolicyRevisionSerializer,
    FinancingPolicyWriteSerializer,
)
from content.services.financing_agreement_pdf_service import FinancingAgreementPdfService
from content.services.financing_agreement_service import (
    KNOWN_PLACEHOLDERS,
    FinancingAgreementTransitionError,
    FinancingAgreementValidationError,
    apply_current_policy,
    archive_agreement,
    cancel_agreement,
    complete_agreement,
    create_agreement,
    create_second_cycle,
    mark_ready,
    register_signed_pdf,
    reopen_draft,
    restore_agreement,
    update_draft,
)
from content.services.financing_policy_service import (
    FinancingPolicyValidationError,
    create_policy_revision,
)
from content.services.frontend_build import schedule_rebuild_after_publish


def _error_response(exc):
    if isinstance(
        exc,
        (FinancingAgreementValidationError, FinancingPolicyValidationError),
    ):
        payload = dict(exc.errors)
        payload['code'] = exc.code
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'detail': exc.detail, 'code': exc.code},
        status=status.HTTP_409_CONFLICT,
    )


def _agreement_queryset():
    return FinancingAgreement.objects.select_related(
        'client', 'client__user', 'source_proposal', 'source_project', 'template',
        'policy_revision', 'policy_revision__created_by',
        'previous_agreement', 'second_cycle', 'ready_by', 'activated_by', 'completed_by',
        'cancelled_by', 'second_cycle_approved_by',
    )


def _detail_agreement(agreement_id):
    return get_object_or_404(
        _agreement_queryset().prefetch_related('events', 'events__actor'),
        pk=agreement_id,
    )


def _parse_nonnegative_int(raw_value, default, maximum):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return min(max(value, 0), maximum)


def _serializer_context():
    current = FinancingPolicyRevision.get_current()
    return {'current_policy_id': current.pk if current else None}


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def financing_settings(request):
    if request.method == 'POST':
        serializer = FinancingPolicyWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            create_policy_revision(serializer.validated_data, actor=request.user)
        except FinancingPolicyValidationError as exc:
            return _error_response(exc)
        # The public Partnership Program is prerendered with the current policy.
        schedule_rebuild_after_publish(reason='partnership-program')

    current = FinancingPolicyRevision.get_current()
    history = FinancingPolicyRevision.objects.select_related('created_by')[:25]
    accounting = AccountingSettings.load()
    return Response({
        'current': (
            FinancingPolicyRevisionSerializer(current).data if current else None
        ),
        'history': FinancingPolicyRevisionSerializer(history, many=True).data,
        'usd_exchange_rate': accounting.usd_exchange_rate,
        'fixed_terms': {
            'ordinary_interest_percent': 0,
            'modalities': [
                {
                    'key': FinancingAgreement.Modality.FIVE_YEAR,
                    'years': 5,
                    'financing_cycles': 2,
                    'monthly_hours_package': True,
                },
                {
                    'key': FinancingAgreement.Modality.THREE_YEAR,
                    'years': 3,
                    'financing_cycles': 1,
                    'monthly_hours_package': False,
                },
            ],
        },
    }, status=(
        status.HTTP_201_CREATED
        if request.method == 'POST'
        else status.HTTP_200_OK
    ))


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def financing_agreement_list(request):
    if request.method == 'POST':
        serializer = FinancingAgreementWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            agreement = create_agreement(serializer.validated_data, actor=request.user)
        except (FinancingAgreementValidationError, FinancingAgreementTransitionError) as exc:
            return _error_response(exc)
        return Response(
            FinancingAgreementDetailSerializer(
                _detail_agreement(agreement.pk),
                context=_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    queryset = _agreement_queryset()
    archived = request.query_params.get('archived', 'false').lower()
    if archived == 'true':
        queryset = queryset.filter(is_archived=True)
    elif archived != 'all':
        queryset = queryset.filter(is_archived=False)

    search = request.query_params.get('q', '').strip()
    if search:
        queryset = queryset.filter(
            Q(number__icontains=search)
            | Q(client_full_name__icontains=search)
            | Q(client_company__icontains=search)
            | Q(project_name__icontains=search)
            | Q(original_contract_reference__icontains=search)
        )
    for field, values in (
        ('status', set(FinancingAgreement.Status.values)),
        ('modality', set(FinancingAgreement.Modality.values)),
    ):
        value = request.query_params.get(field)
        if value:
            if value not in values:
                return Response(
                    {field: ['Usa una opción válida.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(**{field: value})
    cycle = request.query_params.get('cycle')
    if cycle:
        if cycle not in ('1', '2'):
            return Response(
                {'cycle': ['Usa 1 o 2.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(cycle_number=int(cycle))

    count = queryset.count()
    limit = _parse_nonnegative_int(request.query_params.get('limit'), 25, 100) or 25
    offset = _parse_nonnegative_int(request.query_params.get('offset'), 0, 1_000_000)
    rows = queryset.order_by('-created_at', '-id')[offset:offset + limit]
    status_counts = {
        row['status']: row['count']
        for row in FinancingAgreement.objects.filter(is_archived=False)
        .values('status')
        .annotate(count=Count('id'))
    }
    return Response({
        'count': count,
        'limit': limit,
        'offset': offset,
        'results': FinancingAgreementListSerializer(
            rows,
            many=True,
            context=_serializer_context(),
        ).data,
        'stats': {
            'total_active_records': FinancingAgreement.objects.filter(
                is_archived=False,
            ).count(),
            'archived': FinancingAgreement.objects.filter(is_archived=True).count(),
            'by_status': status_counts,
        },
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def financing_agreement_detail(request, agreement_id):
    agreement = _detail_agreement(agreement_id)
    if request.method == 'PATCH':
        serializer = FinancingAgreementWriteSerializer(
            instance=agreement,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            agreement = update_draft(
                agreement,
                serializer.validated_data,
                actor=request.user,
            )
        except (FinancingAgreementValidationError, FinancingAgreementTransitionError) as exc:
            return _error_response(exc)
        agreement = _detail_agreement(agreement.pk)
    return Response(FinancingAgreementDetailSerializer(
        agreement,
        context=_serializer_context(),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def financing_agreement_action(request, agreement_id, action):
    agreement = _detail_agreement(agreement_id)
    try:
        if action == 'mark-ready':
            result = mark_ready(agreement, actor=request.user)
        elif action == 'reopen':
            result = reopen_draft(agreement, actor=request.user)
        elif action == 'upload-signed':
            result = register_signed_pdf(
                agreement,
                request.FILES.get('signed_document'),
                actor=request.user,
            )
        elif action == 'complete':
            result = complete_agreement(
                agreement,
                actor=request.user,
                note=request.data.get('completion_note'),
            )
        elif action == 'cancel':
            result = cancel_agreement(
                agreement,
                actor=request.user,
                reason=request.data.get('cancellation_reason'),
            )
        elif action == 'archive':
            result = archive_agreement(agreement, actor=request.user)
        elif action == 'restore':
            result = restore_agreement(agreement, actor=request.user)
        elif action == 'create-second-cycle':
            result = create_second_cycle(agreement, actor=request.user)
            return Response(
                FinancingAgreementDetailSerializer(
                    _detail_agreement(result.pk),
                    context=_serializer_context(),
                ).data,
                status=status.HTTP_201_CREATED,
            )
        elif action == 'apply-current-policy':
            result = apply_current_policy(agreement, actor=request.user)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
    except (FinancingAgreementValidationError, FinancingAgreementTransitionError) as exc:
        return _error_response(exc)
    return Response(
        FinancingAgreementDetailSerializer(
            _detail_agreement(result.pk),
            context=_serializer_context(),
        ).data,
    )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def financing_agreement_draft_pdf(request, agreement_id):
    agreement = _detail_agreement(agreement_id)
    try:
        pdf_bytes = FinancingAgreementPdfService.build_draft(agreement)
    except FinancingAgreementValidationError as exc:
        return _error_response(exc)
    safe_client = slugify(agreement.client_full_name) or 'cliente'
    safe_number = agreement.number or 'borrador'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Borrador_Otrosi_Financiacion_'
        f'{safe_number}_{safe_client}.pdf"'
    )
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
@permission_classes([IsAdminUser])
def financing_agreement_signed_pdf(request, agreement_id):
    agreement = _detail_agreement(agreement_id)
    if not agreement.signed_document:
        return Response(
            {'detail': 'Este otrosí no tiene un PDF firmado registrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    agreement.signed_document.open('rb')
    response = FileResponse(
        agreement.signed_document.file,
        as_attachment=True,
        filename=(
            f'Otrosi_Financiacion_{agreement.number or agreement.uuid}_'
            f'{slugify(agreement.client_full_name) or "cliente"}.pdf'
        ),
        content_type='application/pdf',
    )
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
@permission_classes([IsAdminUser])
def financing_agreement_templates(request):
    templates = FinancingAgreementTemplate.objects.filter(is_active=True)
    return Response({
        'results': FinancingAgreementTemplateSerializer(templates, many=True).data,
        'known_placeholders': sorted(KNOWN_PLACEHOLDERS),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def financing_client_context(request):
    client_id = request.query_params.get('client_id')
    client = get_object_or_404(
        UserProfile.objects.clients().filter(archived_at__isnull=True),
        pk=client_id,
    )
    proposals = BusinessProposal.objects.filter(client=client).order_by('-created_at')[:100]
    projects = Project.objects.filter(client=client.user).order_by('-updated_at')[:100]
    return Response({
        'client': {
            'id': client.id,
            'name': client.user.get_full_name() or client.company_name or client.user.email,
            'company': client.company_name,
            'email': '' if client.is_email_placeholder else client.user.email,
            'phone': client.phone,
            'id_type': 'NIT' if client.nit else ('C.C.' if client.cedula else ''),
            'id_number': client.nit or client.cedula,
        },
        'proposals': [
            {
                'id': proposal.id,
                'title': proposal.title,
                'status': proposal.status,
                'total_investment': proposal.total_investment,
                'currency': proposal.currency,
            }
            for proposal in proposals
        ],
        'projects': [
            {'id': project.id, 'name': project.name, 'status': project.status}
            for project in projects
        ],
    })
