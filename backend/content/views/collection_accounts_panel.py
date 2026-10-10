"""Panel (accounting) endpoints for collection accounts — superuser only.

The platform (JWT) side has its own per-project views in
accounts/collection_account_views.py; these serve the accounting
"Cuentas de cobro" monitor, its create/preview modal, and the hosting
"Enviar cuenta de cobro" action (session + CSRF).
"""
import re
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import UserProfile
from content.api_errors import error_response
from content.models import (
    AccountingChangeLog,
    Document,
    EmailLog,
    EmailLogTarget,
    HostingRecord,
    IncomeRecord,
)
from content.permissions import IsSuperUser
from content.serializers.collection_accounts_panel import (
    CollectionAccountCreateSerializer,
    CollectionAccountPanelDetailSerializer,
    CollectionAccountPanelListSerializer,
)
from content.services import (
    accounting_settlement_service,
    collection_account_create_service,
    collection_account_email_service,
    hosting_billing_service,
)
from content.services.collection_account_numbering import (
    peek_next_client_number,
)
from content.services.collection_account_pdf_service import (
    CollectionAccountPdfService,
)
from content.services.collection_account_preview_pdf import (
    load_preview_pdf,
    store_preview_pdf,
)
from content.services.collection_account_service import (
    CollectionAccountError,
    delete_collection_account,
    get_default_issuer,
    mark_collection_account_cancelled,
    mark_collection_account_paid,
)
from content.services.collection_account_snapshot_service import (
    CollectionAccountSnapshotError,
    stored_collection_account_pdf,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT

# What a single URL path segment can carry without needing escaping.
_URL_UNSAFE_RE = re.compile(r'[^A-Za-z0-9._-]+')


def _base_qs():
    return (
        Document.objects.filter(document_type__code=COLLECTION_ACCOUNT)
        .select_related(
            'billing_context__contract', 'billing_context__amendment', 'billing_context__hosting',
            'collection_account', 'hosting_record', 'project', 'income_record',
        )
        .prefetch_related('items', 'payment_methods')
    )


def _with_delivery_flag(queryset):
    """Annotate "a client email for this cuenta left the system".

    What `can_delete` needs to answer per row. As an Exists subquery rather
    than the serializer's fallback query so a hundred-row listing stays one
    round trip; the FAILED exclusion keeps the same meaning as
    ``collection_account_was_delivered``.
    """
    delivered = EmailLogTarget.objects.filter(
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=OuterRef('pk'),
    ).exclude(email_log__status=EmailLog.Status.FAILED)
    return queryset.annotate(was_delivered=Exists(delivered))


def _get_document(doc_id):
    return get_object_or_404(_base_qs(), pk=doc_id)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def send_hosting_collection_account(request, record_id):
    from accounts.serializers_billing_context import HostingAccountEmissionSerializer
    context_serializer = HostingAccountEmissionSerializer(data=request.data)
    context_serializer.is_valid(raise_exception=True)
    hosting = get_object_or_404(HostingRecord, pk=record_id)
    try:
        result = hosting_billing_service.send_hosting_collection_account(
            hosting, acting_user=request.user, hosting_payment_id=context_serializer.validated_data.get('hosting_payment_id'),
        )
    except hosting_billing_service.HostingBillingError as exc:
        return error_response(str(exc))
    document = _get_document(result['document'].pk)
    return Response(
        {
            'document': CollectionAccountPanelDetailSerializer(document).data,
            'email_sent': result['email_sent'],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_collection_account_view(request):
    """Create + issue + email a cuenta de cobro from an income."""
    serializer = CollectionAccountCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        document = collection_account_create_service.create_income_collection_account(
            serializer.validated_data, acting_user=request.user,
        )
    except CollectionAccountError as exc:
        return error_response(str(exc))
    # Re-read: the in-memory document caches the pre-issue extension via
    # the reverse one-to-one descriptor (same reason as the hosting flow).
    document = _get_document(document.pk)
    email_sent = collection_account_email_service.send_collection_account_email(
        document,
    )
    return Response(
        {
            'document': CollectionAccountPanelDetailSerializer(document).data,
            'email_sent': email_sent,
        },
        status=status.HTTP_201_CREATED,
    )


def _preview_pdf_url(token, filename):
    """URL whose last segment is the consecutivo, e.g. .../PA-ACME-001.pdf.

    Belt and braces: the response's own Content-Disposition is what names the
    download, but this is what a viewer falls back to when it ignores the
    header. The segment is sanitised because the consecutivo can be typed by
    hand and a '/' would fit in no single path segment (the header still gets
    the exact name, straight from the cache).
    """
    return reverse(
        'collection-account-preview-pdf',
        kwargs={
            'token': token,
            'filename': _URL_UNSAFE_RE.sub('-', filename),
        },
    )


@api_view(['POST'])
@permission_classes([IsSuperUser])
def preview_collection_account_view(request):
    """The real create pipeline minus the send, rolled back.

    Runs create + issue + email build + PDF inside a forced-rollback
    transaction, so the preview is byte-identical to what the confirm step
    will send while persisting nothing — no Document rows, no EmailLog and
    no consecutivo consumed (the sequence increment rolls back too).
    """
    serializer = CollectionAccountCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            document = (
                collection_account_create_service.create_income_collection_account(
                    serializer.validated_data,
                    acting_user=request.user,
                    persist_snapshot=False,
                )
            )
            document = _get_document(document.pk)
            email = collection_account_email_service.build_collection_account_email(
                document,
            )
            pdf_bytes = CollectionAccountPdfService.generate(document)
            pdf_name = f'{document.public_number or document.pk}.pdf'
            payload = {
                'subject': email['subject'],
                'html_body': email['html_body'],
                'public_number': document.public_number,
                'total': str(document.total),
                'subtotal': str(document.total - document.tax_total),
                'tax_total': str(document.tax_total),
                'vat_rate': str(document.collection_account.vat_rate) if document.collection_account.vat_rate is not None else None,
                'income_total': str(document.income_record.total_amount),
                'due_date': (
                    document.due_date.isoformat() if document.due_date else None
                ),
                'customer_email': document.collection_account.customer_email,
                # Read from the rolled-back issue too, so the panel's last
                # notice names what the confirm step will really emit.
                'issue_date': (
                    document.issue_date.isoformat() if document.issue_date else None
                ),
                'customer_name': document.collection_account.customer_name,
                'project_name': (
                    document.project.name if document.project_id
                    else document.collection_account.customer_project_name
                ),
                'billing_concept': (
                    document.collection_account.billing_concept or document.title
                ),
            }
            transaction.set_rollback(True)
    except CollectionAccountError as exc:
        return error_response(str(exc))
    # Outside the atomic block on purpose: the cache is not transactional, and
    # stashing the bytes inside a transaction that is about to roll back reads
    # as if the write were part of it.
    payload['pdf_url'] = (
        _preview_pdf_url(store_preview_pdf(pdf_bytes, pdf_name), pdf_name)
        if pdf_bytes else None
    )
    return Response(payload)


@xframe_options_sameorigin
@api_view(['GET'])
@permission_classes([IsSuperUser])
def collection_account_preview_pdf_view(request, token, filename):
    """Serve a previewed (never persisted) PDF so the viewer can name it.

    `inline` rather than `attachment`: this URL is what the modal embeds, and
    the operator downloads from the viewer's own button or the modal's.

    Without the sameorigin exemption the site-wide X-Frame-Options: DENY
    (middleware default, no setting overrides it) reaches this response and
    the browser refuses to render the PDF inside the modal's <embed>.
    """
    entry = load_preview_pdf(token)
    if entry is None:
        return error_response(
            'La previsualización expiró. Genérala de nuevo.', status=404,
        )
    response = HttpResponse(entry['pdf'], content_type='application/pdf')
    # The cached name, not the URL segment: the segment is caller-supplied.
    response['Content-Disposition'] = content_disposition_header(
        False, entry['filename'],
    )
    return response


@api_view(['GET'])
@permission_classes([IsSuperUser])
def collection_account_next_number_view(request):
    """Suggested per-client consecutivo — never consumes the counter."""
    client_profile_id = request.query_params.get('client_profile_id', '')
    if not client_profile_id.isdigit():
        return error_response("El parámetro 'client_profile_id' es obligatorio.")
    profile = UserProfile.objects.filter(pk=int(client_profile_id)).first()
    if profile is None:
        return error_response('El cliente seleccionado no existe.', status=404)
    try:
        issuer = get_default_issuer()
    except CollectionAccountError as exc:
        return error_response(str(exc))
    code, suggested = peek_next_client_number(profile, issuer)
    return Response({
        'suggested_number': suggested,
        'billing_code': code,
        'issuer_city': issuer.city or '',
    })


@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_collection_accounts(request):
    qs = _base_qs().order_by('-created_at')
    params = request.query_params

    commercial_status = params.get('commercial_status')
    if commercial_status:
        qs = qs.filter(commercial_status=commercial_status)
    origin = params.get('origin')
    # Mirrors get_origin()'s precedence so the four origins stay a partition.
    # Since a cuenta now inherits its origin record's project, a bare
    # project__isnull=False would also match every income- and hosting-driven
    # row and double-count them.
    if origin == 'hosting':
        qs = qs.filter(hosting_record__isnull=False)
    elif origin == 'income':
        qs = qs.filter(
            hosting_record__isnull=True, income_record__isnull=False,
        )
    elif origin == 'project':
        qs = qs.filter(
            hosting_record__isnull=True,
            income_record__isnull=True,
            project__isnull=False,
        )
    elif origin == 'other':
        qs = qs.filter(
            hosting_record__isnull=True,
            project__isnull=True,
            income_record__isnull=True,
        )
    for param, lookup in (
        ('date_from', 'issue_date__gte'),
        ('date_to', 'issue_date__lte'),
    ):
        value = params.get(param)
        if value:
            try:
                qs = qs.filter(**{lookup: date.fromisoformat(value)})
            except ValueError:
                return error_response(
                    f"El parámetro '{param}' debe ser una fecha AAAA-MM-DD.",
                )
    search = (params.get('q') or '').strip()
    if search:
        qs = qs.filter(
            Q(public_number__icontains=search)
            | Q(title__icontains=search)
            | Q(collection_account__customer_name__icontains=search),
        )

    totals = qs.aggregate(
        draft_count=Count('id', filter=Q(commercial_status='draft')),
        issued_count=Count('id', filter=Q(commercial_status='issued')),
        paid_count=Count('id', filter=Q(commercial_status='paid')),
        cancelled_count=Count('id', filter=Q(commercial_status='cancelled')),
        issued_total=Sum('total', filter=Q(commercial_status='issued')),
        paid_total=Sum('total', filter=Q(commercial_status='paid')),
    )
    two_places = Decimal('0.01')
    meta = {
        key: (
            str((value or Decimal('0')).quantize(two_places))
            if key.endswith('_total')
            else value or 0
        )
        for key, value in totals.items()
    }
    # Annotated only for the rows, never for the aggregate above: the counters
    # ask about status, and dragging an Exists subquery through the aggregate
    # buys nothing.
    serializer = CollectionAccountPanelListSerializer(
        _with_delivery_flag(qs), many=True,
    )
    return Response({'results': serializer.data, 'meta': meta})


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_collection_account(request, doc_id):
    document = _get_document(doc_id)
    return Response(CollectionAccountPanelDetailSerializer(document).data)


# sameorigin for the same reason as the preview view: the detail modal embeds
# `?inline=1` and the middleware's DENY default blanks the viewer otherwise.
@xframe_options_sameorigin
@api_view(['GET'])
@permission_classes([IsSuperUser])
def collection_account_pdf(request, doc_id):
    document = _get_document(doc_id)
    try:
        pdf_bytes = stored_collection_account_pdf(document)
    except CollectionAccountSnapshotError as exc:
        return error_response(str(exc), status=500)
    filename = f'{document.public_number or document.pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    # `?inline=1` lets the panel embed the document in a viewer instead of
    # downloading it — previewing a cuenta should not litter the operator's
    # Downloads folder. Default stays `attachment` so the download action and
    # every existing caller keep behaving exactly as before.
    #
    # Django's builder quotes and escapes: a manually typed consecutivo can
    # carry a `"` and hand-rolled interpolation would break the header.
    as_attachment = not request.query_params.get('inline')
    response['Content-Disposition'] = content_disposition_header(
        as_attachment, filename,
    )
    return response


@api_view(['POST'])
@permission_classes([IsSuperUser])
def resend_collection_account(request, doc_id):
    document = _get_document(doc_id)
    try:
        sent = hosting_billing_service.resend_collection_account_email(
            document, acting_user=request.user,
        )
    except hosting_billing_service.HostingBillingError as exc:
        return error_response(str(exc))
    if not sent:
        return error_response(
            'No se pudo enviar el correo; revisa los logs e inténtalo de nuevo.',
            status=502,
        )
    return Response({'email_sent': True})


@api_view(['POST'])
@permission_classes([IsSuperUser])
def mark_collection_account_paid_view(request, doc_id):
    document = _get_document(doc_id)
    # Guard here, not in the service: the settle flow's sync hook calls the
    # service directly and must never trip over its own precondition.
    income = document.income_record
    if (
        income is not None
        and income.kind == IncomeRecord.Kind.EXPECTED
        and accounting_settlement_service.income_payment_status(income) != 'paid'
    ):
        return error_response(
            'El ingreso vinculado aún tiene saldo pendiente. '
            'Liquídalo para marcar la cuenta como pagada.',
            status=409,
        )
    try:
        mark_collection_account_paid(document, acting_user=request.user)
    except CollectionAccountError as exc:
        return error_response(str(exc))
    return Response(CollectionAccountPanelDetailSerializer(document).data)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def cancel_collection_account_view(request, doc_id):
    document = _get_document(doc_id)
    try:
        mark_collection_account_cancelled(document, acting_user=request.user)
    except CollectionAccountError as exc:
        return error_response(str(exc))
    _resume_hosting_expiry_notices(document.hosting_record)
    return Response(CollectionAccountPanelDetailSerializer(document).data)


def _resume_hosting_expiry_notices(hosting):
    """Undo the "billing already requested" mute on the linked hosting.

    Both ways out of a live cuenta owe the hosting this: the flag is what
    silences the expiry cadence while a cuenta is pending, so a cuenta that
    stops being pending — annulled or deleted — must hand the reminders back.
    Without it the hosting goes quiet forever behind a cuenta nobody can see.
    """
    if hosting is not None and hosting.billing_requested_at is not None:
        HostingRecord.objects.filter(pk=hosting.pk).update(
            billing_requested_at=None,
        )


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_collection_account_view(request, doc_id):
    """Remove a cuenta created by mistake. Anular is the path for the rest."""
    document = _get_document(doc_id)
    # Captured before the delete: the FK is gone once the row is.
    hosting = document.hosting_record
    try:
        delete_collection_account(document, acting_user=request.user)
    except CollectionAccountError as exc:
        return error_response(str(exc))
    _resume_hosting_expiry_notices(hosting)
    return Response(status=status.HTTP_204_NO_CONTENT)
