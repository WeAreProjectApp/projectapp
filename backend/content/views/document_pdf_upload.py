"""Panel endpoints reused verbatim by the Documents MCP binary adapters."""
import json

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import Document
from content.serializers.document import DocumentCreateUpdateSerializer, DocumentDetailSerializer
from content.services.uploaded_pdf_service import (
    PDF_COMPOSITION_FIELDS, create_pdf_document, replace_pdf_document,
)


class PdfUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class PdfReplacementSerializer(PdfUploadSerializer):
    expected_version = serializers.IntegerField(min_value=1)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_document_from_pdf(request):
    allowed = set(DocumentCreateUpdateSerializer().fields) | {'file'}
    unknown = set(request.data) - allowed
    if unknown:
        raise serializers.ValidationError({key: 'Campo desconocido.' for key in unknown})
    if len(request.FILES.getlist('file')) != 1:
        raise serializers.ValidationError({'file': 'Adjunta exactamente un archivo PDF.'})
    upload = PdfUploadSerializer(data=request.data)
    upload.is_valid(raise_exception=True)
    forbidden = PDF_COMPOSITION_FIELDS.intersection(request.data)
    if forbidden:
        raise serializers.ValidationError({key: 'Esta opción no se aplica a un PDF subido.' for key in forbidden})
    data = {key: request.data[key] for key in request.data if key != 'file'}
    for key in ('client_custom_notes', 'text_formats', 'tag_ids'):
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except ValueError as exc:
                raise serializers.ValidationError({key: 'Debe ser JSON válido.'}) from exc
    metadata = DocumentCreateUpdateSerializer(data=data)
    metadata.is_valid(raise_exception=True)
    document = create_pdf_document(metadata, upload.validated_data['file'], actor=request.user)
    return Response(DocumentDetailSerializer(document).data, status=201)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def replace_document_pdf(request, document_id):
    get_object_or_404(Document, pk=document_id)
    upload = PdfReplacementSerializer(data=request.data)
    upload.is_valid(raise_exception=True)
    unknown = set(request.data) - {'file', 'expected_version'}
    if unknown:
        raise serializers.ValidationError({key: 'Campo desconocido.' for key in unknown})
    document = replace_pdf_document(
        document_id, upload.validated_data['file'],
        expected_version=upload.validated_data['expected_version'], actor=request.user,
    )
    return Response(DocumentDetailSerializer(document).data)
