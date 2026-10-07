"""Resource lifecycle shared by Platform HTTP views and administrative MCP tools."""
import mimetypes
from pathlib import PurePosixPath

from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import (
    Deliverable,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableFile,
    DeliverableVersion,
    Notification,
)
from accounts.serializers import (
    CreateDeliverableClientFolderSerializer,
    CreateDeliverableClientUploadSerializer,
    CreateDeliverableFileSerializer,
    CreateDeliverableSerializer,
    DeliverableClientFolderSerializer,
    DeliverableClientUploadSerializer,
    DeliverableDetailSerializer,
    DeliverableFileSerializer,
    DeliverableListSerializer,
    UpdateDeliverableSerializer,
    UploadNewVersionSerializer,
)
from accounts.services.archive import archive_record, unarchive_record
from accounts.services.notifications import notify_project_client
from accounts.services.platform_resource_operations import (
    is_resource_admin,
    perform,
    require_resource_admin,
)
from accounts.services.platform_resource_operations import (
    project_for_resource_actor as project_for_actor,
)


def _validate(serializer_type, data, **kwargs):
    serializer = serializer_type(data=data, **kwargs)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _resource(project, actor, resource_id, *, editable=False, request=None):
    resource = Deliverable.objects.select_related('uploaded_by', 'business_proposal').filter(
        project=project, pk=resource_id,
    ).first()
    if resource is None:
        raise NotFound('Recurso no encontrado.')
    if editable and resource.is_archived:
        raise ValidationError('El recurso está archivado.')
    if resource.is_archived and not is_resource_admin(actor, request):
        raise NotFound('Recurso no encontrado.')
    return resource


def _data(resource, request=None, *, detail=False):
    serializer = DeliverableDetailSerializer if detail else DeliverableListSerializer
    if detail:
        resource._detail_versions = list(resource.versions.select_related('uploaded_by').all())
    return dict(serializer(resource, context={'request': request}).data)


def list_resources(project_id, actor, *, include_archived=False, category=None, request=None):
    project = project_for_actor(project_id, actor, request=request)
    rows = Deliverable.objects.filter(project=project).select_related('uploaded_by').annotate(
        _versions_count=Count('versions'),
    ).order_by('category', '-updated_at')
    if not (is_resource_admin(actor, request) and include_archived):
        rows = rows.filter(is_archived=False)
    if category:
        rows = rows.filter(category=category)
    return list(DeliverableListSerializer(rows, many=True, context={'request': request}).data)


def get_resource(project_id, actor, resource_id, *, request=None):
    project = project_for_actor(project_id, actor, request=request)
    return _data(_resource(project, actor, resource_id, request=request), request, detail=True)


def create_resource(project_id, actor, data, *, request=None, **operation):
    values = _validate(CreateDeliverableSerializer, data)
    category = values['category']
    if not is_resource_admin(actor, request) and category in Deliverable.ADMIN_ONLY_CATEGORIES:
        raise PermissionDenied('Esta categoría solo puede ser subida por el administrador.')

    def change(project):
        resource = Deliverable.objects.create(project=project, uploaded_by=actor,
            title=values['title'], description=values['description'], category=category,
            file=values['file'], current_version=1)
        values['file'].seek(0)
        DeliverableVersion.objects.create(deliverable=resource, file=values['file'],
                                          version_number=1, uploaded_by=actor)
        notify_project_client(project, Notification.TYPE_DELIVERABLE_UPLOADED,
            f'Nuevo entregable: {resource.title}', message=f'Se subió un archivo en {project.name}.',
            related_object_type='deliverable', related_object_id=resource.pk,
            exclude_user=actor, deliverable=resource)
        return _data(resource, request)

    return perform(project_id, actor, 'resource:create', values, change, request=request, **operation)


def update_resource(project_id, actor, resource_id, data, *, request=None, **operation):
    require_resource_admin(actor, request)
    values = _validate(UpdateDeliverableSerializer, data)

    def change(project):
        resource = _resource(project, actor, resource_id, request=request)
        if 'is_archived' in values:
            resource.updated_at = timezone.now()
            (archive_record if values['is_archived'] else unarchive_record)(
                resource, extra_update_fields=('updated_at',))
        changed = [name for name in ('title', 'description', 'category') if name in values]
        for name in changed:
            setattr(resource, name, values[name])
        if changed:
            resource.updated_at = timezone.now()
            resource.save(update_fields=[*changed, 'updated_at'])
        return _data(resource, request, detail=True)

    return perform(project_id, actor, f'resource:{resource_id}:update', values, change, request=request, **operation)


def upload_version(project_id, actor, resource_id, data, *, request=None, **operation):
    require_resource_admin(actor, request)

    def change(project):
        resource = _resource(project, actor, resource_id, editable=True, request=request)
        values = _validate(UploadNewVersionSerializer, data, context={'deliverable': resource})
        number = resource.current_version + 1
        DeliverableVersion.objects.create(deliverable=resource, file=values['file'],
                                          version_number=number, uploaded_by=actor)
        values['file'].seek(0)
        resource.file = values['file']
        resource.current_version = number
        resource.save(update_fields=['file', 'current_version', 'updated_at'])
        notify_project_client(project, Notification.TYPE_DELIVERABLE_NEW_VERSION,
            f'Nueva versión: {resource.title} v{number}', message=f'Se actualizó un entregable en {project.name}.',
            related_object_type='deliverable', related_object_id=resource.pk,
            exclude_user=actor, deliverable=resource)
        return _data(resource, request, detail=True)

    return perform(project_id, actor, f'resource:{resource_id}:version', data, change, request=request, **operation)


def list_attachments(project_id, actor, resource_id, *, request=None):
    project = project_for_actor(project_id, actor, request=request)
    resource = _resource(project, actor, resource_id, request=request)
    return list(DeliverableFileSerializer(resource.attachment_files.select_related('uploaded_by'),
                                         many=True, context={'request': request}).data)


def upload_attachment(project_id, actor, resource_id, data, *, request=None, **operation):
    require_resource_admin(actor, request)
    values = _validate(CreateDeliverableFileSerializer, data)

    def change(project):
        resource = _resource(project, actor, resource_id, editable=True, request=request)
        row = DeliverableFile.objects.create(deliverable=resource, uploaded_by=actor, **values)
        return dict(DeliverableFileSerializer(row, context={'request': request}).data)

    return perform(project_id, actor, f'resource:{resource_id}:attachment', values, change, request=request, **operation)


def list_folders(project_id, actor, resource_id, *, request=None):
    project = project_for_actor(project_id, actor, request=request)
    return list(DeliverableClientFolderSerializer(_resource(project, actor, resource_id, request=request).client_folders.all(), many=True).data)


def create_folder(project_id, actor, resource_id, data, *, request=None, **operation):
    values = _validate(CreateDeliverableClientFolderSerializer, data)

    def change(project):
        row = DeliverableClientFolder.objects.create(
            deliverable=_resource(project, actor, resource_id, editable=True, request=request), created_by=actor, **values)
        return dict(DeliverableClientFolderSerializer(row).data)

    return perform(project_id, actor, f'resource:{resource_id}:folder-create', values, change, request=request, **operation)


def change_folder(project_id, actor, resource_id, folder_id, data, *, delete=False, request=None, **operation):
    values = {} if delete else _validate(CreateDeliverableClientFolderSerializer, data, partial=True)

    def change(project):
        resource = _resource(project, actor, resource_id, request=request)
        row = resource.client_folders.filter(pk=folder_id).first()
        if row is None:
            raise NotFound('Carpeta no encontrada.')
        if delete:
            row.delete()
            return {'deleted': True, 'folder_id': folder_id}
        for name, value in values.items():
            setattr(row, name, value)
        if values:
            row.save(update_fields=list(values))
        return dict(DeliverableClientFolderSerializer(row).data)

    return perform(project_id, actor, f'resource:{resource_id}:folder:{folder_id}:{delete}', values, change, request=request, **operation)


def list_client_files(project_id, actor, resource_id, *, request=None):
    project = project_for_actor(project_id, actor, request=request)
    resource = _resource(project, actor, resource_id, request=request)
    return list(DeliverableClientUploadSerializer(resource.client_uploads.select_related('uploaded_by', 'folder'),
                                                 many=True, context={'request': request}).data)


def upload_client_file(project_id, actor, resource_id, data, *, request=None, **operation):
    def change(project):
        resource = _resource(project, actor, resource_id, editable=True, request=request)
        values = _validate(CreateDeliverableClientUploadSerializer, data, context={'deliverable': resource})
        row = DeliverableClientUpload.objects.create(deliverable=resource, uploaded_by=actor, **values)
        return dict(DeliverableClientUploadSerializer(row, context={'request': request}).data)

    return perform(project_id, actor, f'resource:{resource_id}:client-file', data, change, request=request, **operation)


def open_file(project_id, actor, resource_id, *, kind='current', file_id=None, request=None):
    """Authorize the parent and selected child before opening either namespace."""
    project = project_for_actor(project_id, actor, request=request)
    resource = _resource(project, actor, resource_id, request=request)
    if kind == 'current':
        if file_id is not None:
            raise ValidationError('El archivo actual no recibe file_id.')
        row = resource
    else:
        relation = {'version': resource.versions, 'attachment': resource.attachment_files,
                    'client_upload': resource.client_uploads}.get(kind)
        if relation is None:
            raise ValidationError('Tipo de archivo desconocido.')
        row = relation.filter(pk=file_id).first()
    if row is None or not row.file:
        raise NotFound('Archivo no encontrado.')
    try:
        source = row.file.open('rb')
    except (OSError, ValueError) as exc:
        raise NotFound('Archivo no disponible.') from exc
    filename = PurePosixPath(row.file.name).name
    return source, filename, mimetypes.guess_type(filename)[0] or 'application/octet-stream'


def read_file(project_id, actor, resource_id, *, kind='current', file_id=None, request=None):
    source, filename, content_type = open_file(project_id, actor, resource_id,
        kind=kind, file_id=file_id, request=request)
    with source:
        body = source.read(25 * 1024 * 1024 + 1)
    if len(body) > 25 * 1024 * 1024:
        raise ValidationError('El archivo supera 25 MB.')
    return body, filename, content_type
