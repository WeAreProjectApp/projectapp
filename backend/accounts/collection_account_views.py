"""
JWT API views for collection accounts (platform).
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Project
from accounts.permissions import IsAdminRole
from accounts.serializers_collection_accounts import (
    CollectionAccountCreateSerializer,
    CollectionAccountDetailSerializer,
    CollectionAccountListSerializer,
    CollectionAccountUpdateSerializer,
)
from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    DocumentPaymentMethod,
    IssuerProfile,
)
from content.services.collection_account_service import (
    CollectionAccountError,
    assert_draft_for_mutation,
    issue_collection_account,
    mark_collection_account_cancelled,
    mark_collection_account_paid,
    recalculate_document_totals,
)
from content.services.collection_account_numbering import client_number_allocator
from content.services.collection_account_snapshot_service import (
    CollectionAccountSnapshotError,
    discard_stored_collection_account_pdf,
    persist_collection_account_pdf,
    stored_collection_account_pdf,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_type_utils import get_collection_account_document_type


def _get_project_or_403(request, project_id):
    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin
    try:
        proj = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return None, Response(
            {'detail': 'Project not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not is_admin and proj.client_id != request.user.id:
        return None, Response(
            {'detail': 'You do not have access to this project.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return proj, None


def _base_collection_qs():
    # Sin filtro `is_archived`: archivar es orden interno del panel. La plata
    # que se debe no puede desaparecerle al cliente porque un admin ordenó una
    # carpeta; para retirar una cuenta está `commercial_status`.
    return Document.objects.filter(
        document_type__code=COLLECTION_ACCOUNT,
    ).select_related(
        'document_type', 'project', 'client_user', 'issuer',
    ).prefetch_related(
        'items', 'payment_methods', 'collection_account',
    )


def _visible_qs_for_user(request):
    qs = _base_collection_qs()
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return qs
    return qs.filter(
        Q(client_user=request.user) | Q(project__client=request.user),
    ).exclude(commercial_status=Document.CommercialStatus.DRAFT)


def _is_platform_admin(request):
    profile = getattr(request.user, 'profile', None)
    return profile is not None and profile.is_admin


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def collection_account_list_create_view(request):
    if request.method == 'GET':
        qs = _visible_qs_for_user(request)
        if _is_platform_admin(request):
            pid = request.query_params.get('project_id')
            if pid:
                qs = qs.filter(project_id=pid)
            cid = request.query_params.get('client_user_id')
            if cid:
                qs = qs.filter(client_user_id=cid)
            st = request.query_params.get('commercial_status')
            if st:
                qs = qs.filter(commercial_status=st)
        data = CollectionAccountListSerializer(
            qs.order_by('-created_at'),
            many=True,
        ).data
        return Response(data)

    if not _is_platform_admin(request):
        return Response(
            {'detail': 'Only administrators can create collection accounts.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    ser = CollectionAccountCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    data = ser.validated_data
    project_id = data.get('project_id')
    client_user_id = data.get('client_user_id')
    if project_id and not client_user_id:
        try:
            proj = Project.objects.get(pk=project_id)
            client_user_id = proj.client_id
        except Project.DoesNotExist:
            return Response(
                {'project_id': 'Invalid project.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    doc = Document.objects.create(
        title=data['title'],
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.DRAFT,
        project_id=project_id,
        deliverable_id=data.get('deliverable_id'),
        client_user_id=client_user_id,
        currency=data.get('currency', 'COP'),
        city=data.get('city', ''),
        discount_total=data.get('discount_total', Decimal('0')),
        notes=data.get('notes', ''),
        terms_and_conditions=data.get('terms_and_conditions', ''),
        created_by=request.user,
        updated_by=request.user,
    )
    DocumentCollectionAccount.objects.create(
        document=doc,
        vat_rate=data.get('vat_rate', Decimal('19')),
        billing_concept=data.get('billing_concept', ''),
        payment_term_type=data['payment_term_type'],
        payment_term_days=data.get('payment_term_days'),
        support_reference=data.get('support_reference', ''),
    )
    doc = _base_collection_qs().get(pk=doc.pk)
    return Response(
        CollectionAccountDetailSerializer(doc).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_collection_account_list_view(request, project_id):
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err
    qs = _visible_qs_for_user(request).filter(project_id=project_id)
    did = request.query_params.get('deliverable_id')
    if did:
        qs = qs.filter(deliverable_id=did)
    data = CollectionAccountListSerializer(
        qs.order_by('-created_at'),
        many=True,
    ).data
    return Response(data)


def _detail_queryset_for_request(request):
    if _is_platform_admin(request):
        return _base_collection_qs()
    return _visible_qs_for_user(request)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def collection_account_detail_view(request, account_id):
    doc = _detail_queryset_for_request(request).filter(pk=account_id).first()
    if not doc:
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(CollectionAccountDetailSerializer(doc).data)

    if not _is_platform_admin(request):
        return Response(
            {'detail': 'Only administrators can update collection accounts.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        assert_draft_for_mutation(doc)
    except CollectionAccountError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    ser = CollectionAccountUpdateSerializer(data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    payload = ser.validated_data

    # Draft moves of client/project alter per-client figures like any
    # reassignment; the diff-and-log at the end makes them reconstructable.
    from content.services import accounting_service
    audit_snapshot = accounting_service.snapshot_values(
        doc, accounting_service.EntityType.COLLECTION_ACCOUNT,
    )

    if 'title' in payload:
        doc.title = payload['title']
    if 'project_id' in payload:
        doc.project_id = payload['project_id']
    if 'client_user_id' in payload:
        doc.client_user_id = payload['client_user_id']
    if 'currency' in payload:
        doc.currency = payload['currency']
    if 'city' in payload:
        doc.city = payload['city']
    if 'discount_total' in payload:
        doc.discount_total = payload['discount_total']
    if 'due_date' in payload:
        doc.due_date = payload['due_date']
    if 'notes' in payload:
        doc.notes = payload['notes']
    if 'terms_and_conditions' in payload:
        doc.terms_and_conditions = payload['terms_and_conditions']
    doc.updated_by = request.user

    ext = getattr(doc, 'collection_account', None)
    if ext is None:
        ext = DocumentCollectionAccount.objects.create(document=doc)
    if 'vat_rate' in payload:
        ext.vat_rate = payload['vat_rate']
    if 'billing_concept' in payload:
        ext.billing_concept = payload['billing_concept']
    if 'payment_term_type' in payload:
        ext.payment_term_type = payload['payment_term_type']
    if 'payment_term_days' in payload:
        ext.payment_term_days = payload['payment_term_days']
    if 'support_reference' in payload:
        ext.support_reference = payload['support_reference']
    if 'observations' in payload:
        ext.observations = payload['observations']
    ext.save()

    if 'items' in payload:
        doc.items.all().delete()
        for idx, row in enumerate(payload['items']):
            qty = row.get('quantity', Decimal('1'))
            up = row.get('unit_price', Decimal('0'))
            da = row.get('discount_amount', Decimal('0'))
            tax = row.get('tax_amount', Decimal('0'))
            lt = row.get('line_total')
            if lt is None:
                lt = qty * up - da + tax
            DocumentItem.objects.create(
                document=doc,
                position=row.get('position', idx),
                item_type=row.get('item_type', DocumentItem.ItemType.SERVICE),
                description=row['description'],
                quantity=qty,
                unit_price=up,
                discount_amount=da,
                tax_amount=tax,
                line_total=lt,
                period_start=row.get('period_start'),
                period_end=row.get('period_end'),
                reference_type=row.get('reference_type', ''),
                reference_id=row.get('reference_id'),
            )

    if 'payment_methods' in payload:
        doc.payment_methods.all().delete()
        for row in payload['payment_methods']:
            DocumentPaymentMethod.objects.create(
                document=doc,
                payment_method_type=row.get(
                    'payment_method_type',
                    DocumentPaymentMethod.MethodType.BANK_TRANSFER,
                ),
                bank_name=row.get('bank_name', ''),
                account_type=row.get('account_type', ''),
                account_number=row.get('account_number', ''),
                account_holder_name=row.get('account_holder_name', ''),
                account_holder_identification=row.get('account_holder_identification', ''),
                payment_instructions=row.get('payment_instructions', ''),
                is_primary=row.get('is_primary', False),
            )

    if ext.vat_rate is not None and ('items' in payload or 'vat_rate' in payload):
        from content.services.accounting_vat import vat_breakdown, quantize_money
        for item in doc.items.all():
            base = quantize_money(item.quantity * item.unit_price - item.discount_amount)
            try:
                _, item.tax_amount, item.line_total = vat_breakdown(base, ext.vat_rate, 'before_vat')
            except ValueError as exc:
                # All draft financial writes are atomic, including replacement items.
                raise serializers.ValidationError({'items': str(exc)}) from exc
            item.save(update_fields=['tax_amount', 'line_total'])
    recalculate_document_totals(doc)
    doc.save()
    doc = _base_collection_qs().get(pk=doc.pk)
    accounting_service.log_entity_diff(
        accounting_service.EntityType.COLLECTION_ACCOUNT,
        doc, audit_snapshot, request.user,
    )
    return Response(CollectionAccountDetailSerializer(doc).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def collection_account_issue_view(request, account_id):
    doc = _base_collection_qs().filter(pk=account_id).first()
    if not doc:
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    issuer = IssuerProfile.objects.order_by('pk').first()
    if not issuer:
        return Response(
            {'detail': 'No issuer profile configured.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    stored = None
    try:
        with transaction.atomic():
            # Same series as the panel and hosting flows: one client, one
            # consecutivo, instead of a second numbering living in parallel.
            issue_collection_account(
                doc,
                issuer=issuer,
                acting_user=request.user,
                number_allocator=client_number_allocator(doc, issuer),
            )
            doc = _base_collection_qs().get(pk=doc.pk)
            stored = persist_collection_account_pdf(doc)
    except (CollectionAccountError, CollectionAccountSnapshotError) as e:
        discard_stored_collection_account_pdf(stored)
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        discard_stored_collection_account_pdf(stored)
        raise
    doc = _base_collection_qs().get(pk=doc.pk)
    return Response(CollectionAccountDetailSerializer(doc).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def collection_account_mark_paid_view(request, account_id):
    doc = _base_collection_qs().filter(pk=account_id).first()
    if not doc:
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        mark_collection_account_paid(doc, acting_user=request.user)
    except CollectionAccountError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    doc = _base_collection_qs().get(pk=doc.pk)
    return Response(CollectionAccountDetailSerializer(doc).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def collection_account_mark_cancelled_view(request, account_id):
    doc = _base_collection_qs().filter(pk=account_id).first()
    if not doc:
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        mark_collection_account_cancelled(doc, acting_user=request.user)
    except CollectionAccountError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    doc = _base_collection_qs().get(pk=doc.pk)
    return Response(CollectionAccountDetailSerializer(doc).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def collection_account_pdf_view(request, account_id):
    doc = _detail_queryset_for_request(request).filter(pk=account_id).first()
    if not doc:
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if doc.commercial_status == Document.CommercialStatus.DRAFT and not _is_platform_admin(request):
        return Response(
            {'detail': 'Not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        pdf_bytes = stored_collection_account_pdf(doc)
    except CollectionAccountSnapshotError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    from django.http import HttpResponse
    from django.utils.http import content_disposition_header

    from content.utils import safe_slug

    # The consecutivo is already filename-safe and is how both sides refer to
    # the document; slugify used to lowercase it into pa-mimittos-001, which
    # did not match the name the panel and the email attachment produce.
    filename = doc.public_number or safe_slug(doc.title, 'collection-account')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    # Django's builder quotes and escapes; a manually typed consecutivo can
    # carry a `"` that hand-rolled interpolation would let break the header.
    response['Content-Disposition'] = content_disposition_header(
        True, f'{filename}.pdf',
    )
    return response
