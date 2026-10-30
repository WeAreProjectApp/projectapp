"""Private PDF persistence shared by Panel and MCP, including rollback compensation."""
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import subprocess
import sys
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import APIException, ValidationError

from content.models import Document
from content.services.entity_history import cleanup_rollback_files, history_operation, retain_file_on_rollback
from content.services.document_type_utils import get_markdown_document_type

MAX_PDF_BYTES = 25 * 1024 * 1024
PDF_COMPOSITION_FIELDS = {
    'content_markdown', 'content_json', 'include_portada', 'include_subportada',
    'include_contraportada', 'template_style', 'cover_type',
}
_artifacts = ContextVar('uploaded_pdf_artifacts', default=None)


class PdfTooLarge(APIException):
    status_code = 413
    default_detail = 'El PDF no puede superar 25 MiB.'
    default_code = 'pdf_too_large'


class PdfVersionConflict(APIException):
    status_code = 409
    default_detail = 'El PDF o su asociación cambió. Recarga el documento antes de reemplazarlo.'
    default_code = 'pdf_version_conflict'


class PdfProtected(APIException):
    status_code = 409
    default_detail = 'Este PDF sustenta evidencia publicada o firmada y no admite reemplazos.'
    default_code = 'pdf_protected'


@contextmanager
def pdf_artifact_scope():
    """Compensate a savepoint failure even when the outer MCP call catches it."""
    parent = _artifacts.get()
    files = parent if parent is not None else []
    start = len(files)
    token = _artifacts.set(files)
    try:
        yield
    except BaseException:
        cleanup_rollback_files([(storage, name) for storage, name, owner in files[start:]
                                if owner is None or not owner.committed])
        del files[start:]
        raise
    finally:
        _artifacts.reset(token)


def pdf_bridge_artifacts(function):
    @wraps(function)
    def wrapped(operation, *args, **kwargs):
        if operation['name'] not in {'create_document_from_pdf', 'replace_document_pdf'}:
            return function(operation, *args, **kwargs)
        with pdf_artifact_scope():
            return function(operation, *args, **kwargs)
    return wrapped


def _probe(data, *, extract=False):
    command = [sys.executable, '-m', 'content.services.uploaded_pdf_probe']
    if extract:
        command.append('--extract')
    result = subprocess.run(
        command, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=5, check=True, cwd=Path(__file__).resolve().parents[2],
    )
    return json.loads(result.stdout)


def inspect_upload(upload):
    if not upload or Path(upload.name).suffix.lower() != '.pdf':
        raise ValidationError({'file': 'Selecciona un archivo .pdf.'})
    if upload.size > MAX_PDF_BYTES:
        raise PdfTooLarge()
    data = upload.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise PdfTooLarge()
    if not data or not data[:1024].lstrip().startswith(b'%PDF-'):
        raise ValidationError({'file': 'El contenido del archivo no es PDF.'})
    try:
        validated = _probe(data)
    except (subprocess.SubprocessError, ValueError) as exc:
        raise ValidationError({'file': 'No se pudo validar el PDF dentro de los límites de procesamiento.'}) from exc
    if not validated.get('valid'):
        raise ValidationError({'file': validated.get('error', 'El PDF no es válido.')})
    try:
        inspected = _probe(data, extract=True)
        if 'error' in inspected:
            inspected = {'text': '', 'status': 'unavailable'}
    except (subprocess.SubprocessError, ValueError):
        inspected = {'text': '', 'status': 'unavailable'}
    return data, inspected


def pdf_metadata(document):
    return {
        'filename': document.pdf_filename, 'size': document.pdf_size,
        'sha256': document.pdf_sha256, 'version': document.pdf_version,
        'text_status': document.pdf_text_status,
    } if document.content_format == 'pdf' else None


def _evidence_documents():
    return Document.objects.filter(
        Q(delivery_contracts__signature_evidence__isnull=False)
        | Q(delivery_amendments__signature_evidence__isnull=False)
        | Q(delivery_links__snapshots__isnull=False),
    )


def with_pdf_protection(queryset):
    """Batch the protection flag for callers that expose capabilities per row."""
    return queryset.annotate(_pdf_protected=Exists(_evidence_documents().filter(pk=OuterRef('pk'))))


def pdf_is_protected(document):
    if document.content_format != 'pdf':
        return False
    if document.requires_signature or document.signed_at:
        return True
    protected = getattr(document, '_pdf_protected', None)
    return protected if protected is not None else _evidence_documents().filter(pk=document.pk).exists()


def _assign_pdf(document, data, inspected, filename):
    document.content_format = 'pdf'
    document.pdf_filename = Path(filename).name[:255]
    document.pdf_size = len(data)
    document.pdf_sha256 = hashlib.sha256(data).hexdigest()
    document.pdf_version += 1
    document.pdf_search_text = inspected['text']
    document.pdf_text_status = inspected['status']
    document.uploaded_pdf.save(f'{uuid.uuid4().hex}.pdf', ContentFile(data), save=False)
    artifact = (document.uploaded_pdf.storage, document.uploaded_pdf.name)
    owner = retain_file_on_rollback(*artifact)
    files = _artifacts.get()
    if files is not None:
        files.append((*artifact, owner))


def create_pdf_document(serializer, upload, *, actor):
    data, inspected = inspect_upload(upload)
    with pdf_artifact_scope(), history_operation(actor=actor, source='service'), transaction.atomic():
        document = Document()
        _assign_pdf(document, data, inspected, upload.name)
        return serializer.save(
            document_type=get_markdown_document_type(), content_format='pdf',
            uploaded_pdf=document.uploaded_pdf.name, pdf_filename=document.pdf_filename,
            pdf_size=document.pdf_size, pdf_sha256=document.pdf_sha256,
            pdf_version=document.pdf_version, pdf_search_text=document.pdf_search_text,
            pdf_text_status=document.pdf_text_status, created_by=actor, updated_by=actor,
            cover_type='none', include_portada=False, include_subportada=False,
            include_contraportada=False,
        )


def _project_ids(document):
    from accounts.models import Project
    return set(Project.objects.filter(
        Q(pk=document.project_id) | Q(delivery_contracts__document_id=document.pk)
        | Q(delivery_contracts__amendments__document_id=document.pk)
        | Q(delivery_documents__document_id=document.pk),
    ).values_list('pk', flat=True))


def lock_pdf_document(document_id, *, extra_project_ids=()):
    """Serialize PDF metadata and bytes with publication/signing project locks."""
    from accounts.models import Project

    before = Document.objects.get(pk=document_id)
    project_ids = _project_ids(before) | {pk for pk in extra_project_ids if pk is not None}
    list(Project.objects.select_for_update().filter(pk__in=project_ids).order_by('pk'))
    document = Document.objects.select_for_update().get(pk=document_id)
    if document.project_id != before.project_id or not _project_ids(document) <= project_ids:
        raise PdfVersionConflict()
    return document


def replace_pdf_document(document_id, upload, *, expected_version, actor):
    from content.services.document_write_service import movement_blockers

    data, inspected = inspect_upload(upload)
    with pdf_artifact_scope(), history_operation(actor=actor, source='service'), transaction.atomic():
        document = lock_pdf_document(document_id)
        if document.content_format != 'pdf':
            raise ValidationError({'detail': 'Este documento no es un PDF subido.'})
        if movement_blockers(document) or pdf_is_protected(document):
            raise PdfProtected()
        if document.pdf_version != expected_version:
            raise PdfVersionConflict()
        _assign_pdf(document, data, inspected, upload.name)
        document.updated_by = actor
        document.save(update_fields=[
            'uploaded_pdf', 'pdf_filename', 'pdf_size', 'pdf_sha256', 'pdf_version',
            'pdf_search_text', 'pdf_text_status', 'updated_by', 'updated_at',
        ])
        return document
