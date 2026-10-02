"""
JWT API views for the client-facing document portal (platform).

A client sees the documents linked to them (main contract flagged with
``requires_signature`` plus its annexes), can view/download each PDF, validate
their email via OTP, and sign the main document once their email is verified.
Every milestone (first login, email validated, signed) notifies the team.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import VerificationCode
from accounts.serializers import DocumentSignSerializer, EmailVerifyConfirmSerializer
from accounts.serializers_documents import ClientDocumentSerializer
from accounts.services.verification import create_and_send_otp, validate_otp
from content.models import Document
from content.services.document_pdf_service import DocumentPdfService
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.utils import get_client_ip

logger = logging.getLogger(__name__)


def _is_platform_admin(request):
    profile = getattr(request.user, 'profile', None)
    return profile is not None and profile.is_admin


def _visible_docs_qs(request):
    """One inherited authorization gate for global list, detail, PDF and signing."""
    from accounts.services.delivery_documents import PortalDocumentIndex
    qs = Document.objects.exclude(
        document_type__code=COLLECTION_ACCOUNT,
    ).select_related('document_type', 'project', 'client_user', 'signed_by')
    if _is_platform_admin(request):
        return qs.filter(is_archived=False, is_client_visible=True)
    qs = qs.filter(
        Q(is_archived=False) | Q(delivery_links__snapshots__isnull=False)
        | Q(delivery_contracts__signature_evidence__isnull=False)
        | Q(delivery_amendments__signature_evidence__isnull=False),
    )
    qs = qs.filter(Q(client_user=request.user) | Q(project__client=request.user)).filter(
        Q(is_client_visible=True) | Q(delivery_links__isnull=False)
        | Q(delivery_contracts__client_visible=True) | Q(delivery_amendments__client_visible=True),
    ).distinct()
    documents = list(qs)
    index = PortalDocumentIndex(request.user, documents)
    request._delivery_portal_index = index
    visible_ids = [doc.pk for doc in documents if index.visible(doc)]
    return qs.filter(pk__in=visible_ids)


def _portal_document_data(request, doc):
    from accounts.services.delivery_documents import snapshot_for_document
    data = ClientDocumentSerializer(doc).data
    index = getattr(request, '_delivery_portal_index', None)
    snapshot = index.snapshot(doc) if index is not None else snapshot_for_document(request.user, doc)
    if snapshot:
        data['title'] = snapshot.title
    return data


def _ordered_docs(qs):
    """Main signable document(s) first, then annexes by creation order."""
    return qs.order_by('-requires_signature', 'created_at')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_document_list_view(request):
    """List the client's portal documents plus their email-verification state."""
    docs = _ordered_docs(_visible_docs_qs(request))
    profile = getattr(request.user, 'profile', None)
    return Response({
        'email': request.user.email or '',
        'email_verified': bool(profile and profile.email_verified),
        'documents': [_portal_document_data(request, doc) for doc in docs],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_document_detail_view(request, doc_uuid):
    doc = _visible_docs_qs(request).filter(uuid=doc_uuid).first()
    if not doc:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(_portal_document_data(request, doc))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_document_pdf_view(request, doc_uuid):
    doc = _visible_docs_qs(request).filter(uuid=doc_uuid).first()
    if not doc:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.services.delivery_documents import snapshot_for_document
    index = getattr(request, '_delivery_portal_index', None)
    snapshot = index.snapshot(doc) if index is not None else snapshot_for_document(request.user, doc)
    if snapshot:
        try:
            with snapshot.file.open('rb') as source:
                pdf_bytes = source.read()
        except (OSError, ValueError):
            return Response({'detail': 'Evidencia no disponible.'}, status=status.HTTP_404_NOT_FOUND)
    elif doc.generated_file:
        try:
            with doc.generated_file.open('rb') as source:
                pdf_bytes = source.read()
        except (OSError, ValueError):
            return Response({'detail': 'Documento no disponible.'}, status=status.HTTP_404_NOT_FOUND)
    else:
        pdf_bytes = DocumentPdfService.generate(doc)
    if not pdf_bytes:
        return Response(
            {'detail': 'Failed to generate PDF.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    filename = slugify(snapshot.title if snapshot else doc.title) or 'document'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def client_document_sign_view(request, doc_uuid):
    """Client accepts/signs a document (click-to-accept). Requires a verified email."""
    if request.auth and request.auth.get('impersonated_by'):
        return Response(
            {'detail': 'Inicia sesión con tu propia cuenta de cliente para firmar.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    doc = _visible_docs_qs(request).filter(uuid=doc_uuid).first()
    if not doc:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.services.delivery_access import is_admin
    if is_admin(request.user):
        return Response({'detail': 'La firma corresponde al cliente propietario.'}, status=status.HTTP_403_FORBIDDEN)

    if not doc.requires_signature:
        return Response(
            {'detail': 'Este documento no requiere firma.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.email_verified):
        return Response(
            {'detail': 'Debes validar tu correo electrónico antes de firmar.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if doc.signed_at is not None:
        # Idempotent: already signed.
        return Response(_portal_document_data(request, doc))

    serializer = DocumentSignSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    from accounts.models import DeliveryWorkspace, Project
    from accounts.services.delivery_documents import artifact_scope, capture_document_portal_signatures
    # Project lock first, as in authoring/publication; the source document lock
    # makes two simultaneous signature clicks produce one immutable fact.
    with artifact_scope(), transaction.atomic():
        projects = list(Project.objects.select_for_update().filter(
            Q(delivery_contracts__document=doc) | Q(delivery_contracts__amendments__document=doc),
        ).order_by('id').distinct())
        doc = _visible_docs_qs(request).select_for_update().get(pk=doc.pk)
        if doc.signed_at is not None:
            return Response(_portal_document_data(request, doc))
        default_name = f'{request.user.first_name} {request.user.last_name}'.strip()
        doc.signed_at = timezone.now()
        doc.signed_by = request.user
        doc.signature_name = serializer.validated_data.get('signature_name') or default_name or request.user.email
        doc.signature_ip = get_client_ip(request)
        doc.signature_user_agent = request.META.get('HTTP_USER_AGENT', '')
        doc.save(update_fields=[
            'signed_at', 'signed_by', 'signature_name',
            'signature_ip', 'signature_user_agent', 'updated_at',
        ])
        capture_document_portal_signatures(doc, request.user)
        for project in projects:
            workspace, _ = DeliveryWorkspace.objects.get_or_create(project=project)
            workspace.version += 1
            workspace.save(update_fields=['version'])

    from accounts.tasks import notify_team_document_signed_task

    notify_team_document_signed_task(doc.id)

    return Response(_portal_document_data(request, doc))


# ==========================================================================
# Email validation (OTP) — confirm ownership of the account email
# ==========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def email_verify_request_view(request):
    """Send an OTP code to the authenticated client's current email."""
    profile = getattr(request.user, 'profile', None)
    if profile and profile.email_verified:
        return Response({'detail': 'Tu correo ya está validado.', 'email_verified': True})
    if not request.user.email:
        return Response(
            {'detail': 'No tienes un correo configurado. Contacta al administrador.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    create_and_send_otp(request.user, purpose=VerificationCode.PURPOSE_EMAIL_VALIDATION)
    return Response({'detail': 'Código enviado a tu correo.', 'email': request.user.email})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def email_verify_confirm_view(request):
    """Validate the OTP and mark the client's email as verified."""
    profile = getattr(request.user, 'profile', None)
    if profile and profile.email_verified:
        return Response({'detail': 'Tu correo ya está validado.', 'email_verified': True})

    serializer = EmailVerifyConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    success, error_msg = validate_otp(
        request.user,
        serializer.validated_data['code'],
        purpose=VerificationCode.PURPOSE_EMAIL_VALIDATION,
    )
    if not success:
        return Response({'detail': error_msg}, status=status.HTTP_400_BAD_REQUEST)

    profile.email_verified = True
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=['email_verified', 'email_verified_at'])

    from accounts.tasks import notify_team_email_validated_task

    notify_team_email_validated_task(request.user.id)

    return Response({'detail': 'Correo validado correctamente.', 'email_verified': True})
