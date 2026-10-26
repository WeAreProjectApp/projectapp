"""Staff/session endpoints; all writes delegate to the filing service."""
from rest_framework.response import Response
from . import folder_services as filing
from .folder_serializers import FolderSerializer, FolderWriteSerializer, MoveLinkSerializer, RevisionSerializer, ReorderSerializer
from .services import SecureLinkError
from .views import admin_api, _invalid, _service_error, _link


@admin_api(['GET', 'POST'])
def folders(request):
    if request.method == 'GET':
        from .queries import folder_index
        return Response(folder_index())
    serializer = FolderWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid(serializer.errors)
    if 'name' not in serializer.validated_data:
        return _invalid({'name': ['El nombre es obligatorio.']})
    data = dict(serializer.validated_data)
    data.pop('expected_updated_at', None)
    try:
        row = filing.save_folder(data=data, actor=request.user)
    except SecureLinkError as exc:
        return _service_error(exc)
    return Response(FolderSerializer(row).data, status=201)


@admin_api(['GET', 'PATCH', 'DELETE'])
def folder_detail(request, pk):
    try:
        row = filing.folder_for(pk)
        if request.method == 'GET':
            return Response(FolderSerializer(row).data)
        serializer = FolderWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer.errors)
        data = dict(serializer.validated_data)
        expected = data.pop('expected_updated_at', None)
        if request.method == 'DELETE':
            filing.delete_folder(row, expected_updated_at=expected)
            return Response(status=204)
        row = filing.save_folder(data=data, folder=row, actor=request.user, expected_updated_at=expected)
        return Response(FolderSerializer(row).data)
    except SecureLinkError as exc:
        return _service_error(exc)


@admin_api(['POST'])
def folder_archive(request, pk, restore=False):
    serializer = RevisionSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid(serializer.errors)
    try:
        result = filing.archive_folder(filing.folder_for(pk), restore=restore, actor=request.user, **serializer.validated_data)
        return Response(result)
    except SecureLinkError as exc:
        return _service_error(exc)


@admin_api(['POST'])
def folder_reorder(request):
    serializer = ReorderSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid(serializer.errors)
    try:
        filing.reorder_folders(**serializer.validated_data)
        return Response({'success': True})
    except SecureLinkError as exc:
        return _service_error(exc)


@admin_api(['POST'])
def link_move(request, pk):
    from .serializers import SecureLinkSerializer
    serializer = MoveLinkSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid(serializer.errors)
    try:
        row = filing.move_link(_link(pk), actor=request.user, **serializer.validated_data)
        return Response(SecureLinkSerializer(row).data)
    except SecureLinkError as exc:
        return _service_error(exc)
