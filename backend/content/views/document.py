import copy
import json
import logging

from django.contrib.auth import get_user_model
from django.db.models import (
    Count, Exists, OuterRef, Prefetch,
)
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.api_errors import error_response
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentNote,
    DocumentStateEpisode,
    EmailLog,
    EmailLogTarget,
)
from content.serializers.document import (
    DocumentBrowseSerializer,
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentCreateUpdateSerializer,
    DocumentFromMarkdownSerializer,
)
from content.services import document_archive_service
from content.services.collection_account_service import (
    CollectionAccountError,
    delete_collection_account,
    is_collection_account,
)
from content.services.contract_mirror_service import (
    CONTRACT_MIRROR_CODE,
    CONTRACT_MIRROR_MESSAGE,
    is_contract_mirror,
    mirror_pdf,
)
from content.services.document_content import build_content_json, resolve_blocks
from content.services.document_navigation_service import build_document_navigation
from content.services.document_query_service import (
    DocumentQueryError,
    build_document_list_queryset,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_type_utils import get_markdown_document_type
from content.utils import safe_slug

logger = logging.getLogger(__name__)

_ARCHIVE_ORDER = {'recent': '-archived_at', 'oldest': 'archived_at'}

_SCOPES = ('active', 'archived', 'all')

_SEARCH_MAX_LENGTH = 200


def wants_archived(request):
    """True cuando el caller pide el scope archivado (`?archived=1`)."""
    raw = request.query_params.get('archived')
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')


def archive_scope(request):
    """Scope pedido: 'active' (default), 'archived' o 'all'. None si es inválido.

    `?archived=1` se conserva como alias heredado del store del panel y de la
    batería de tests que llegó con el archivado; si llegan los dos, manda
    `scope`. El parámetro selecciona datos, así que un valor inválido responde
    400 — igual que `folder` y `tags`, y a diferencia de `order`, que sólo los
    presenta.
    """
    raw = str(request.query_params.get('scope') or '').strip().lower()
    if not raw:
        return 'archived' if wants_archived(request) else 'active'
    return raw if raw in _SCOPES else None


def apply_archive_scope(queryset, scope):
    """Filtra por `is_archived`; 'all' no filtra y deja ver el estado mixto."""
    if scope == 'all':
        return queryset
    return queryset.filter(is_archived=(scope == 'archived'))


def search_term(request):
    """Texto de búsqueda ya normalizado; cadena vacía cuando no se pidió.

    Un `search` en blanco no es un error sino un no-op: a diferencia de un
    `folder` malformado, no hay ninguna intención que malinterpretar.
    """
    return str(request.query_params.get('search') or '').strip()[:_SEARCH_MAX_LENGTH]


def date_order(request):
    """Sentido de fecha solicitado; cualquier valor inválido cae a recent.

    A diferencia de `folder`/`tags`, que seleccionan datos y por eso responden
    400, `order` sólo los presenta: un valor raro no justifica romper la vista.
    """
    raw = str(request.query_params.get('order') or '').strip().lower()
    return 'oldest' if raw == 'oldest' else 'recent'


def archived_order_field(request):
    """Campo legado para ordenar carpetas archivadas con el sentido común."""
    return _ARCHIVE_ORDER[date_order(request)]


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_documents(request):
    """List all documents, optionally filtered by folder, tags and/or search.

    Por defecto sólo devuelve documentos activos; `?scope=archived` devuelve
    únicamente los archivados, ordenados por fecha de archivado, y `?scope=all`
    devuelve los dos estados mezclados — cada fila trae `is_archived`, que es lo
    que permite marcarla en una lista mixta.
    """
    scope = archive_scope(request)
    if scope is None:
        return Response(
            {'scope': 'El estado solicitado no es válido. Usa active, archived o all.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        documents = build_document_list_queryset(
            request.query_params,
            scope=scope,
            order=date_order(request),
            search_max_length=_SEARCH_MAX_LENGTH,
        )
    except DocumentQueryError as exc:
        return Response(
            {exc.field: exc.message}, status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = DocumentListSerializer(documents, many=True)
    return Response(serializer.data)


def _positive_page_value(request, field, default):
    raw = request.query_params.get(field)
    if raw in (None, ''):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def browse_documents(request):
    """Return one server-owned page for the interactive document manager."""
    scope = archive_scope(request)
    if scope is None:
        return Response(
            {'scope': 'El estado solicitado no es válido. Usa active, archived o all.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    page = _positive_page_value(request, 'page', 1)
    page_size = _positive_page_value(request, 'page_size', 10)
    if page is None:
        return Response(
            {'page': 'La página debe ser un entero positivo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if page_size not in (10, 12):
        return Response(
            {'page_size': 'El tamaño de página debe ser 10 o 12.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        documents = build_document_list_queryset(
            request.query_params,
            scope=scope,
            order=date_order(request),
            search_max_length=_SEARCH_MAX_LENGTH,
            resolve_root=True,
        )
    except DocumentQueryError as exc:
        return Response(
            {exc.field: exc.message}, status=status.HTTP_400_BAD_REQUEST,
        )

    count = documents.count()
    total_pages = max(1, (count + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    rows = DocumentBrowseSerializer(documents[start:start + page_size], many=True)
    return Response({
        'results': rows.data,
        'count': count,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    })


def _system_managed_folder_target_error(raw_folder_id):
    if raw_folder_id in (None, '', 'null'):
        return None
    try:
        folder = DocumentFolder.objects.filter(pk=int(raw_folder_id)).first()
    except (TypeError, ValueError):
        return None
    if folder is None or not folder.is_system_managed:
        return None
    return error_response(
        'Esta carpeta pertenece al archivado automático y sólo recibe '
        'documentos generados por el sistema.',
        code='system_managed_folder',
        hint='Elige una carpeta manual o deja el documento sin carpeta.',
        status=status.HTTP_409_CONFLICT,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_document(request):
    """Create a document from direct JSON input."""
    managed = _system_managed_folder_target_error(request.data.get('folder_id'))
    if managed:
        return managed
    serializer = DocumentCreateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    document = serializer.save(created_by=request.user, updated_by=request.user)
    if not document.document_type_id:
        document.document_type = get_markdown_document_type()
        document.save(update_fields=['document_type'])

    # If markdown was provided but no JSON, parse it
    if document.content_markdown and not document.content_json:
        document.content_json = build_content_json(document)
        document.save(update_fields=['content_json'])

    detail = DocumentDetailSerializer(document)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_document_from_markdown(request):
    """Create a document from markdown text."""
    managed = _system_managed_folder_target_error(request.data.get('folder_id'))
    if managed:
        return managed
    serializer = DocumentFromMarkdownSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    markdown_text = data['markdown']

    document = Document(
        title=data['title'],
        document_type=get_markdown_document_type(),
        folder=data.get('folder_id'),
        client_name=data.get('client_name', ''),
        client_email_subject=data.get('client_email_subject', ''),
        client_email_body=data.get('client_email_body', ''),
        client_whatsapp_message=data.get('client_whatsapp_message', ''),
        client_custom_notes=data.get('client_custom_notes', []),
        client_user=data.get('client_user'),
        project=data.get('project'),
        language=data.get('language', 'es'),
        cover_type=data.get('cover_type', 'generic'),
        template_style=data.get('template_style', 'professional'),
        include_portada=data.get('include_portada', True),
        include_subportada=data.get('include_subportada', True),
        include_contraportada=data.get('include_contraportada', True),
        content_markdown=markdown_text,
        created_by=request.user,
        updated_by=request.user,
    )
    document.content_json = build_content_json(document, markdown_text)
    document.save()

    tag_ids = data.get('tag_ids')
    if tag_ids:
        document.tags.set(tag_ids)

    detail = DocumentDetailSerializer(document)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_document_markdown(request):
    """Create a document from an uploaded .md file."""
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return Response(
            {'file': 'No se adjuntó ningún archivo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    managed = _system_managed_folder_target_error(request.data.get('folder_id'))
    if managed:
        return managed

    # Read file content
    try:
        markdown_text = uploaded_file.read().decode('utf-8')
    except UnicodeDecodeError:
        return Response(
            {'file': 'El archivo debe ser un texto válido en formato UTF-8.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    title = request.data.get('title', uploaded_file.name.rsplit('.', 1)[0])
    client_name = request.data.get('client_name', '')
    client_email_subject = request.data.get('client_email_subject', '')
    client_email_body = request.data.get('client_email_body', '')
    client_whatsapp_message = request.data.get('client_whatsapp_message', '')
    client_custom_notes = request.data.get('client_custom_notes', [])
    if isinstance(client_custom_notes, str):
        try:
            client_custom_notes = json.loads(client_custom_notes)
        except json.JSONDecodeError:
            # Let the serializer return the same field-level validation error
            # used by JSON requests instead of inventing a multipart contract.
            pass
    language = request.data.get('language', 'es')
    cover_type = request.data.get('cover_type', 'generic')
    template_style = request.data.get('template_style', 'professional')

    # Multipart uploads do not pass through the regular create endpoint, but
    # their text metadata must follow the same validation contract. In
    # particular, this prevents an oversized subject from reaching the DB.
    metadata_serializer = DocumentCreateUpdateSerializer(data={
        'title': title,
        'client_name': client_name,
        'client_email_subject': client_email_subject,
        'client_email_body': client_email_body,
        'client_whatsapp_message': client_whatsapp_message,
        'client_custom_notes': client_custom_notes,
        'language': language,
        'cover_type': cover_type,
        'template_style': template_style,
    })
    if not metadata_serializer.is_valid():
        return Response(
            metadata_serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )
    metadata = metadata_serializer.validated_data

    def _to_bool(value, default=True):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() not in ('false', '0', '')
        return default if value is None else bool(value)

    include_portada = _to_bool(request.data.get('include_portada'), default=True)
    include_subportada = _to_bool(request.data.get('include_subportada'), default=True)
    include_contraportada = _to_bool(request.data.get('include_contraportada'), default=True)

    folder_id = request.data.get('folder_id') or None
    folder = None
    if folder_id not in (None, '', 'null'):
        from content.models import DocumentFolder
        folder = DocumentFolder.objects.filter(pk=folder_id).first()

    # La guarda va en la vista y no en un serializer porque este endpoint no
    # pasa por ninguno: recibe multipart y arma el documento a mano.
    try:
        document_archive_service.ensure_active_target(folder)
    except document_archive_service.DocumentArchiveError as exc:
        return Response({'folder_id': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    document = Document(
        title=metadata['title'],
        document_type=get_markdown_document_type(),
        folder=folder,
        client_name=metadata.get('client_name', ''),
        client_email_subject=metadata.get('client_email_subject', ''),
        client_email_body=metadata.get('client_email_body', ''),
        client_whatsapp_message=metadata.get('client_whatsapp_message', ''),
        client_custom_notes=metadata.get('client_custom_notes', []),
        language=metadata.get('language', 'es'),
        cover_type=metadata.get('cover_type', 'generic'),
        template_style=metadata.get('template_style', 'professional'),
        include_portada=include_portada,
        include_subportada=include_subportada,
        include_contraportada=include_contraportada,
        content_markdown=markdown_text,
        created_by=request.user,
        updated_by=request.user,
    )
    document.content_json = build_content_json(document, markdown_text)
    document.save()

    tag_ids_raw = request.data.get('tag_ids')
    if tag_ids_raw:
        if isinstance(tag_ids_raw, str):
            try:
                tag_id_list = [int(t) for t in tag_ids_raw.split(',') if t.strip()]
            except ValueError:
                tag_id_list = []
        elif isinstance(tag_ids_raw, (list, tuple)):
            tag_id_list = [int(t) for t in tag_ids_raw if str(t).strip()]
        else:
            tag_id_list = []
        if tag_id_list:
            document.tags.set(tag_id_list)

    detail = DocumentDetailSerializer(document)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_document(request, document_id):
    """Get document detail."""
    document = get_object_or_404(
        Document.objects.annotate(
            thread_document_count=Count(
                'thread_item__thread__items', distinct=True,
            ),
        ).select_related(
            'document_type', 'folder', 'project', 'client_user__profile',
            'thread_item__thread', 'collection_account', 'contract_template',
        ).prefetch_related(
            Prefetch(
                'document_notes',
                queryset=DocumentNote.objects.filter(
                    deleted_at__isnull=True,
                ).select_related('created_by', 'resolved_by', 'deleted_by'),
                to_attr='_active_document_notes',
            ),
            'state_episodes__state__group',
        ),
        pk=document_id,
    )
    serializer = DocumentDetailSerializer(document)
    return Response(serializer.data)


def _locked_collection_account_error(document):
    """400 when a cuenta de cobro already left draft.

    Draft cuentas are provisional and stay editable/deletable here; once
    issued (or paid/cancelled) the document is a fact — the only path for a
    mistake is anular y reemitir from the cuentas module, never rewriting
    the record the number was assigned to.
    """
    is_cuenta = (
        document.document_type
        and document.document_type.code == COLLECTION_ACCOUNT
    )
    if not is_cuenta:
        return None
    if document.commercial_status == Document.CommercialStatus.DRAFT:
        return None
    return error_response(
        'Esta cuenta de cobro ya fue emitida y no se puede modificar ni '
        'eliminar desde Documentos.',
        code='collection_account_locked',
        hint='Anúlala y emite una nueva desde Contabilidad → Cuentas de cobro.',
    )


def _generated_snapshot_read_only_error(document):
    if not document.is_generated_snapshot:
        return None
    return error_response(
        'Esta versión fue generada por el sistema y conserva exactamente el '
        'PDF enviado al cliente.',
        code='generated_snapshot_read_only',
        hint='Puedes descargarla, archivarla y agregar observaciones, pero no modificarla.',
        status=status.HTTP_409_CONFLICT,
    )


def _contract_mirror_read_only_error(document):
    """409 for the Document-manager window onto the one contract."""
    if not is_contract_mirror(document):
        return None
    response = error_response(
        CONTRACT_MIRROR_MESSAGE,
        code=CONTRACT_MIRROR_CODE,
        hint='Descárgalo en PDF o en Markdown desde este documento.',
        status=status.HTTP_409_CONFLICT,
    )
    # The MCP panel bridge only relays `detail`.
    response.data['detail'] = CONTRACT_MIRROR_MESSAGE
    return response


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_document(request, document_id):
    """Update a document."""
    document = get_object_or_404(Document, pk=document_id)
    mirror = _contract_mirror_read_only_error(document)
    if mirror:
        return mirror
    generated = _generated_snapshot_read_only_error(document)
    if generated:
        return generated
    locked = _locked_collection_account_error(document)
    if locked:
        return locked
    managed = _system_managed_folder_target_error(request.data.get('folder_id'))
    if managed:
        return managed
    serializer = DocumentCreateUpdateSerializer(
        document, data=request.data, partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save(updated_by=request.user)

    # Re-parse markdown if it changed
    if 'content_markdown' in request.data and document.content_markdown:
        document.content_json = build_content_json(document)
        document.save(update_fields=['content_json'])

    detail = DocumentDetailSerializer(document)
    return Response(detail.data)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_document(request, document_id):
    """Delete a document.

    Los archivados siguen siendo borrables: archivar es el paso intermedio,
    eliminar sigue disponible para la limpieza final.
    """
    document = get_object_or_404(Document, pk=document_id)
    mirror = _contract_mirror_read_only_error(document)
    if mirror:
        return mirror
    generated = _generated_snapshot_read_only_error(document)
    if generated:
        return generated
    locked = _locked_collection_account_error(document)
    if locked:
        return locked
    if hasattr(document, 'thread_item'):
        return error_response(
            'Este documento pertenece a un hilo y no se puede eliminar todavía.',
            code='document_used_in_thread',
            hint='Retíralo del hilo y vuelve a intentar la eliminación.',
            status=status.HTTP_409_CONFLICT,
        )
    if document.email_attachment_snapshots.exists():
        return Response(
            {
                'detail': (
                    'Este documento forma parte del histórico de correos y '
                    'debe conservarse. Puedes archivarlo en lugar de eliminarlo.'
                ),
                'code': 'document_used_in_email_history',
            },
            status=status.HTTP_409_CONFLICT,
        )
    # A draft cuenta reaching this far is still a cuenta de cobro: route it
    # through the accounting service so it leaves the same audit row a delete
    # from the Cuentas de cobro tab would. Deleting it here used to be the one
    # way to make one disappear with no trace in the historial.
    if is_collection_account(document):
        try:
            delete_collection_account(document, acting_user=request.user)
        except CollectionAccountError as exc:
            # Unreachable through the lock above today, but a 500 is the wrong
            # way to say "this cuenta is not deletable".
            return error_response(str(exc))
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        document.delete()
    except ProtectedError:
        return Response(
            {
                'detail': (
                    'Este documento está referenciado en una comunicación. '
                    'Retira la referencia antes de eliminarlo.'
                ),
                'code': 'document_used_in_communication',
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def document_email_usage(request, document_id):
    """Return primary deliveries that retained this exact document."""
    from content.models import EmailAttachmentSnapshot, EmailLog

    document = get_object_or_404(Document, pk=document_id)
    attachments = list(
        EmailAttachmentSnapshot.objects.filter(
            source_document=document,
        ).select_related('snapshot').order_by('position', 'id')
    )
    attachments_by_snapshot = {}
    for attachment in attachments:
        attachments_by_snapshot.setdefault(attachment.snapshot_id, []).append(
            attachment,
        )
    logs = EmailLog.objects.filter(
        snapshot_id__in=attachments_by_snapshot,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    ).order_by('-sent_at', '-id')
    from content.services.email_log_service import (
        attach_delivery_recipients,
        delivery_recipient_payloads,
        representative_delivery_queryset,
    )
    logs = attach_delivery_recipients(representative_delivery_queryset(logs))
    rows = [
        {
            'email_log_id': log.pk,
            'recipient': log.recipient,
            'subject': log.subject,
            'status': log.status,
            'sent_at': log.sent_at,
            'attachments': [
                {
                    'id': attachment.pk,
                    'filename': attachment.filename,
                    'size_bytes': attachment.size_bytes,
                }
                for attachment in attachments_by_snapshot[log.snapshot_id]
            ],
            **delivery_recipient_payloads(log),
        }
        for log in logs
    ]
    return Response({
        'document_id': document.pk,
        'document_title': document.title,
        'count': len(rows),
        'results': rows,
    })


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def archive_document(request, document_id):
    """Saca un documento de la vista principal sin destruirlo."""
    document = get_object_or_404(Document, pk=document_id)
    mirror = _contract_mirror_read_only_error(document)
    if mirror:
        return mirror
    document_archive_service.archive_document(document)
    return Response(DocumentListSerializer(document).data)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def unarchive_document(request, document_id):
    """Devuelve un documento archivado a la vista principal.

    Reabre además la cadena de carpetas que lo contiene, y la reporta en
    `restored_chain` para que la UI pueda decir qué carpeta volvió con él. Si su
    carpeta fue eliminada mientras tanto, reaparece en «Sin carpeta».

    Las claves extra van al lado de los campos del documento y no en un
    envelope: el store devuelve `response.data` tal cual a la página.
    """
    document = get_object_or_404(Document, pk=document_id)
    result = document_archive_service.unarchive_document(document)
    return Response({
        **DocumentListSerializer(document).data,
        'restored_chain': [
            {'id': folder.id, 'name': folder.name}
            for folder in result['restored_chain']
        ],
        'moved_to_root': result['moved_to_root'],
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def document_counts(request):
    """Contadores autoritativos del panel lateral. No acepta filtros a propósito."""
    return Response(document_archive_service.panel_counts())


@api_view(['GET'])
@permission_classes([IsAdminUser])
def document_navigation(request):
    """Project/client sidebar facets, independent from transient list filters."""
    return Response(build_document_navigation())


@api_view(['POST'])
@permission_classes([IsAdminUser])
def duplicate_document(request, document_id):
    """Duplicate a document.

    La copia hereda la carpeta sólo si sigue activa: el duplicado nace sin
    archivar, y dejarlo dentro de una carpeta archivada lo volvería invisible
    en las dos vistas del panel.
    """
    document = get_object_or_404(Document, pk=document_id)
    mirror = _contract_mirror_read_only_error(document)
    if mirror:
        return mirror
    generated = _generated_snapshot_read_only_error(document)
    if generated:
        return generated
    if document.document_type and document.document_type.code == COLLECTION_ACCOUNT:
        return Response(
            {'detail': 'Las cuentas de cobro no se pueden duplicar desde el panel.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    doc_type = document.document_type or get_markdown_document_type()
    folder = document.folder if document.folder and not document.folder.is_archived else None
    new_document = Document.objects.create(
        title=f'{document.title} (copia)',
        document_type=doc_type,
        client_name=document.client_name,
        client_user=document.client_user,
        project=document.project,
        language=document.language,
        cover_type=document.cover_type,
        include_portada=document.include_portada,
        include_subportada=document.include_subportada,
        include_contraportada=document.include_contraportada,
        # Va con las casillas y no aparte: las cuatro deciden cómo sale el PDF,
        # y una copia que cambia de estilo sola no es una copia.
        template_style=document.template_style,
        folder=folder,
        status=Document.Status.DRAFT,
        content_markdown=document.content_markdown,
        content_json=copy.deepcopy(document.content_json),
        # A communication draft belongs to one concrete delivery. Copying it
        # into another document risks sending stale client-facing text.
        client_email_subject='',
        client_email_body='',
        client_whatsapp_message='',
        client_custom_notes=[],
        created_by=request.user,
        updated_by=request.user,
    )

    detail = DocumentDetailSerializer(new_document)
    return Response(detail.data, status=status.HTTP_201_CREATED)


# sameorigin porque la previsualización del panel embebe `?inline=1` en un
# visor: el DENY por defecto del middleware dejaría el visor en blanco.
@xframe_options_sameorigin
@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_document_pdf(request, document_id):
    """Generate the document PDF, as a download or inline for the previewer.

    El PDF se arma SIEMPRE con la configuración guardada del documento
    (`include_portada`/`include_subportada`/`include_contraportada`): esta vista
    no acepta banderas por request a propósito, para que lo previsualizado y lo
    descargado sean el mismo archivo. El panel avisa de los cambios sin guardar
    antes de llegar acá.
    """
    document = get_object_or_404(Document, pk=document_id)

    if is_contract_mirror(document):
        # Rendered live from the one contract: the same draft the client
        # downloads from the proposal's legal view.
        pdf_bytes = mirror_pdf()
        if not pdf_bytes:
            return Response(
                {'detail': 'El contrato vigente no está disponible en este momento.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            not request.query_params.get('inline'),
            f'{safe_slug(document.title)}.pdf',
        )
        return response

    if is_collection_account(document):
        from content.services.collection_account_snapshot_service import (
            CollectionAccountSnapshotError,
            stored_collection_account_pdf,
        )

        try:
            pdf_bytes = stored_collection_account_pdf(document)
        except CollectionAccountSnapshotError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        filename = f'{safe_slug(document.public_number or document.title)}.pdf'
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            not request.query_params.get('inline'),
            filename,
        )
        return response

    if document.generated_file:
        try:
            with document.generated_file.open('rb') as stored_pdf:
                pdf_bytes = stored_pdf.read()
        except (OSError, ValueError):
            logger.exception(
                'Stored generated document %s could not be read', document.pk,
            )
            return Response(
                {'detail': 'El PDF archivado no está disponible.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        filename = f'{safe_slug(document.title)}.pdf'
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            not request.query_params.get('inline'),
            filename,
        )
        return response

    # `resolve_blocks` y no `content_json['blocks']`: un documento cuyo writer
    # se saltó el parseo sigue teniendo el markdown, y ése es el contenido real.
    if not resolve_blocks(document):
        return Response(
            {'detail': 'El documento no tiene contenido para generar el PDF.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from content.services.document_pdf_service import DocumentPdfService  # noqa: E402
    requested = request.query_params.get('template')
    valid = {'professional', 'friendly'}
    style = requested if requested in valid else document.template_style
    pdf_bytes = DocumentPdfService.generate(document, template_style=style)

    if not pdf_bytes:
        return Response(
            {'detail': 'No se pudo generar el PDF.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    filename = f'{safe_slug(document.title)}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    # `?inline=1` deja que el panel lo embeba en un visor en vez de bajarlo:
    # previsualizar no debería llenar la carpeta de descargas. El default sigue
    # siendo `attachment`, así que ningún caller existente cambia.
    as_attachment = not request.query_params.get('inline')
    response['Content-Disposition'] = content_disposition_header(
        as_attachment, filename,
    )
    return response


@api_view(['GET'])
@permission_classes([IsAdminUser])
def suggest_folder_client(request):
    """Cliente mayoritario de una carpeta, para prellenar el form de crear.

    La carpeta ya está diciendo de quién es: si la mayoría estricta de sus
    documentos activos vinculados pertenece a un cliente (y son al menos dos),
    ése es el default propuesto. Una carpeta inexistente o sin señal devuelve
    sugerencia nula — la sugerencia nunca es un error, sólo un prellenado.
    """
    try:
        folder_id = int(request.query_params.get('folder'))
    except (TypeError, ValueError):
        return Response(
            {'folder': 'El identificador de carpeta no es válido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    docs = Document.objects.filter(folder_id=folder_id, is_archived=False)
    ranking = list(
        docs.filter(client_user__isnull=False)
        .values('client_user')
        .annotate(total=Count('id'))
        .order_by('-total'),
    )
    linked_total = sum(row['total'] for row in ranking)

    client_id = None
    client_display_name = None
    if ranking:
        top = ranking[0]
        if top['total'] >= 2 and top['total'] * 2 > linked_total:
            user = get_user_model().objects.filter(pk=top['client_user']).first()
            profile = getattr(user, 'profile', None) if user else None
            if profile is not None:
                from accounts.services.proposal_client_service import (
                    build_client_display_name,
                )
                client_id = profile.id
                client_display_name = build_client_display_name(profile)

    return Response({
        'client': client_id,
        'client_display_name': client_display_name,
        'linked_documents': linked_total,
        'folder_documents': docs.count(),
    })
