"""JWT downloads for the exact file belonging to an authorized resource."""
from django.http import FileResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.services import platform_resources


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def platform_resource_file(request, project_id, resource_id, kind):
    """Keep role and project ownership in the shared REST/MCP resource service."""
    file_id = request.query_params.get('file_id')
    if kind not in ('current', 'version', 'attachment', 'client_upload'):
        raise ValidationError('Tipo de archivo desconocido.')
    if kind == 'current':
        if file_id is not None:
            raise ValidationError('El archivo actual no recibe file_id.')
    else:
        if file_id is None or not file_id.isascii() or not file_id.isdecimal() or len(file_id) > 19:
            raise ValidationError({'file_id': 'Indica un identificador de archivo válido.'})
        file_id = int(file_id)
        if file_id < 1 or file_id > 2 ** 63 - 1:
            raise ValidationError({'file_id': 'Indica un identificador de archivo válido.'})
    source, filename, content_type = platform_resources.open_file(
        project_id, request.user, resource_id, kind=kind, file_id=file_id, request=request)
    response = FileResponse(source, as_attachment=True, filename=filename, content_type=content_type)
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
