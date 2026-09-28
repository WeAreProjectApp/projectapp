from django.conf import settings
from django.core import signing
from django.core.files import File
from tempfile import TemporaryFile
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from content.mcp.upload_tools import (
    DEFAULT_MAX_UPLOAD_BYTES,
    DOWNLOAD_SIGNING_SALT,
    SIGNING_SALT,
    UPLOAD_TTL_MINUTES,
    VIDEO_UPLOAD_TTL_MINUTES,
    max_upload_bytes,
)
from content.models import McpUpload


@csrf_exempt  # The timestamped signature is the request credential.
@require_http_methods(['PUT'])
@transaction.atomic
def mcp_signed_upload(request, upload_id, signature):
    try:
        signed = signing.loads(
            signature,
            salt=SIGNING_SALT,
            max_age=VIDEO_UPLOAD_TTL_MINUTES * 60,
        )
    except signing.BadSignature:
        return JsonResponse({'detail': 'Firma de upload inválida.'}, status=404)
    if signed.get('upload_id') != str(upload_id):
        return JsonResponse({'detail': 'Firma de upload inválida.'}, status=404)
    try:
        upload = McpUpload.objects.select_for_update().select_related('credential').get(
            pk=upload_id,
            credential_id=signed.get('credential_id'),
        )
    except McpUpload.DoesNotExist:
        return JsonResponse({'detail': 'Upload no encontrado.'}, status=404)
    if (
        upload.status != McpUpload.STATUS_PENDING
        or upload.expires_at <= timezone.now()
        or not upload.credential.is_usable
    ):
        return JsonResponse({'detail': 'Upload no disponible.'}, status=409)
    max_bytes = max_upload_bytes(upload.content_type)
    content_length = request.META.get('CONTENT_LENGTH')
    try:
        declared_length = int(content_length) if content_length else 0
    except ValueError:
        declared_length = 0
    if declared_length > min(max_bytes, upload.expected_size):
        return JsonResponse({'detail': 'El archivo excede el tamaño declarado.'}, status=413)
    request_content_type = request.headers.get('Content-Type', '').split(';', 1)[0].lower()
    if request_content_type and request_content_type != upload.content_type:
        return JsonResponse({'detail': 'El Content-Type no coincide.'}, status=400)
    if upload.file or upload.received_size:
        return JsonResponse({'detail': 'El upload ya recibió contenido.'}, status=409)
    received = 0
    with TemporaryFile() as target:
        while True:
            chunk = request.read(min(1024 * 1024, upload.expected_size - received + 1))
            if not chunk:
                break
            received += len(chunk)
            if received > min(max_bytes, upload.expected_size):
                return JsonResponse({'detail': 'El archivo excede el tamaño declarado.'}, status=413)
            target.write(chunk)
        if received != upload.expected_size:
            return JsonResponse({'detail': 'El tamaño recibido no coincide.', 'received': received}, status=400)
        target.seek(0)
        upload.file.save(upload.filename, File(target), save=False)
    upload.received_size = received
    upload.next_chunk_index = 1
    upload.save(update_fields=[
        'file', 'received_size', 'next_chunk_index', 'updated_at',
    ])
    return JsonResponse({
        'asset_id': str(upload.id),
        'received_size': upload.received_size,
    })


@require_http_methods(['GET'])
def mcp_signed_asset(request, asset_id, signature):
    try:
        signed = signing.loads(
            signature,
            salt=DOWNLOAD_SIGNING_SALT,
            max_age=UPLOAD_TTL_MINUTES * 60,
        )
    except signing.BadSignature:
        return JsonResponse({'detail': 'Firma de asset inválida.'}, status=404)
    if signed.get('asset_id') != str(asset_id):
        return JsonResponse({'detail': 'Firma de asset inválida.'}, status=404)
    try:
        asset = McpUpload.objects.select_related('credential').get(
            pk=asset_id,
            credential_id=signed.get('credential_id'),
            status__in=[McpUpload.STATUS_COMPLETE, McpUpload.STATUS_CONSUMED],
        )
    except McpUpload.DoesNotExist:
        return JsonResponse({'detail': 'Asset no encontrado.'}, status=404)
    if (
        asset.expires_at <= timezone.now()
        or not asset.credential.is_usable
        or not asset.file
    ):
        return JsonResponse({'detail': 'Asset no disponible.'}, status=410)
    return FileResponse(
        asset.file.open('rb'),
        as_attachment=True,
        filename=asset.filename,
        content_type=asset.content_type,
    )
