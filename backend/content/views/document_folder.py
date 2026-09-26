from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import UserProfile

from content.api_errors import error_response
from content.models import DocumentFolder
from content.serializers.document_folder import (
    DocumentFolderChangeClientSerializer, DocumentFolderSerializer,
)
from content.services import (
    document_archive_service,
    document_folder_service,
    project_document_folder_service,
)
from content.views.document import (
    apply_archive_scope, archive_scope, archived_order_field, search_term,
)


def _system_managed_folder_error(folder):
    if folder is None or not folder.is_system_managed:
        return None
    return error_response(
        'Esta carpeta pertenece al archivado automático del sistema y su '
        'estructura no se puede modificar manualmente.',
        code='system_managed_folder',
        hint='Administra los documentos desde su flujo de origen.',
        status=status.HTTP_409_CONFLICT,
    )


def _managed_parent_error(request):
    if 'parent' not in request.data or request.data.get('parent') in (None, ''):
        return None
    try:
        parent_id = int(request.data['parent'])
    except (TypeError, ValueError):
        return None
    return _system_managed_folder_error(
        DocumentFolder.objects.filter(pk=parent_id).first(),
    )


def _annotated_folders(scope):
    """Carpetas del scope pedido, con los contadores activos y archivados.

    Se anotan los cuatro y el serializer elige: `document_count` sigue siendo
    relativo al estado de la carpeta (activa cuenta activos, archivada cuenta
    archivados), y `archived_document_count` es absoluto — es el que deja ver la
    carpeta ACTIVA que todavía guarda archivados, el estado mixto que produce
    una restauración por cadena.

    Compartido por la lista y por las respuestas de archive/unarchive para que
    el payload sea idéntico en ambos casos: el fallback `.count()` del
    serializer sólo entra cuando no hay annotation.
    """
    # distinct=True evita que el JOIN cruzado de las dos relaciones inversas
    # (documents + children) multiplique los conteos entre sí; el `filter=`
    # acota el estado pero no elimina ese cruce. Los cuatro agregados reusan los
    # mismos dos JOINs, así que el riesgo no crece con ellos.
    # El serializer lee `client_user.profile` y `project.name` en cada fila:
    # sin el select_related el panel lateral paga tres consultas por carpeta.
    queryset = DocumentFolder.objects.select_related(
        'client_user__profile', 'project',
        'managed_project__current_state', 'managed_client__profile',
    )
    return apply_archive_scope(queryset, scope).annotate(
        active_document_count=Count(
            'documents', filter=Q(documents__is_archived=False), distinct=True,
        ),
        archived_document_count=Count(
            'documents', filter=Q(documents__is_archived=True), distinct=True,
        ),
        active_children_count=Count(
            'children', filter=Q(children__is_archived=False), distinct=True,
        ),
        archived_children_count=Count(
            'children', filter=Q(children__is_archived=True), distinct=True,
        ),
    )


def _folder_payload(folder, scope):
    """Serializa una carpeta con los contadores anotados de su scope."""
    annotated = _annotated_folders(scope).filter(pk=folder.pk).first() or folder
    return DocumentFolderSerializer(annotated).data


def _managed_folder_error(folder):
    if not folder.managed_project_id:
        return None
    return error_response(
        'La raíz del proyecto se administra automáticamente. Renombra o '
        'cambia el proyecto desde el módulo Proyectos.',
        code='managed_project_folder',
        status=status.HTTP_409_CONFLICT,
    )


def _managed_client_folder_error(folder):
    """Protege la carpeta madre de un cliente de dejar de serlo.

    NO se aplica en el PATCH de actualización: renombrarla es legítimo (a
    diferencia de la raíz de proyecto, cuyo nombre lo dicta el módulo
    Proyectos), y el serializer ya bloquea ahí lo que sí importa — cambiarle el
    dueño o el padre. Acá se cubren las operaciones que la harían desaparecer o
    cambiar de cliente en bloque.
    """
    if not folder.managed_client_id:
        return None
    return error_response(
        'Esta carpeta es el espacio documental del cliente. Quita esa marca '
        'antes de moverla, archivarla o reasignarla.',
        code='managed_client_folder',
        status=status.HTTP_409_CONFLICT,
    )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_document_folders(request):
    """Lista carpetas por estado, opcionalmente filtradas por nombre.

    La búsqueda devuelve coincidencias planas, sin rellenar con los ancestros:
    la página ya pinta un listado plano mientras hay consulta activa.
    """
    scope = archive_scope(request)
    if scope is None:
        return Response(
            {'scope': 'El estado solicitado no es válido. Usa active, archived o all.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    folders = _annotated_folders(scope)

    search = search_term(request)
    if search:
        folders = folders.filter(name__icontains=search)

    if scope == 'archived':
        folders = folders.order_by(archived_order_field(request), 'order', 'name')
    serializer = DocumentFolderSerializer(folders, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def project_folder_readiness(request):
    """Explain whether an empty Projects folder section is real or repairable."""
    return Response(project_document_folder_service.project_folder_readiness())


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_document_folder(request):
    managed = _managed_parent_error(request)
    if managed:
        return managed
    serializer = DocumentFolderSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


def _changes_client(folder, request):
    """¿El PATCH le pone a la carpeta un dueño distinto del que tiene?

    Incluye la primera asignación —poner cliente a una carpeta que ya guarda
    doce documentos es justo el caso donde importa decidir qué pasa con ellos—
    pero NO el vaciado: la cascada existe para elegir a quién pasa el
    contenido, y «a nadie» no es un destino que ese endpoint pueda expresar.
    Quitarle el dueño a la carpeta la deja sin él y no toca lo que guarda.
    """
    if 'client' not in request.data:
        return False
    sent = request.data.get('client')
    if sent in (None, ''):
        return False
    current_id = getattr(folder.client_user, 'profile', None)
    current_id = current_id.pk if current_id else None
    return int(sent) != current_id


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_document_folder(request, folder_id):
    """Edita la carpeta. Cambiar de cliente con contenido va por la cascada.

    Basta mirar los hijos DIRECTOS: si la rama guarda algo, o cuelga del propio
    folder o cuelga de una subcarpeta suya, así que una de las dos existe.
    """
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _system_managed_folder_error(folder)
        or _managed_parent_error(request)
        # Dirigida, no total: a la raíz de cliente SÍ se le puede cambiar el
        # nombre —lo pone el operador, no un módulo externo—, pero no el dueño
        # ni el padre. El serializer repite la regla para los callers que no
        # pasan por acá (MCP); acá se atiende para responder 409 con `code`,
        # como el resto de las guardas del gestor, y no un 400 de validación.
        or (
            _managed_client_folder_error(folder)
            if {'parent', 'client'}.intersection(request.data)
            else None
        )
    )
    if managed:
        return managed
    if _changes_client(folder, request) and (
        folder.documents.exists() or folder.children.exists()
    ):
        return error_response(
            'La carpeta tiene contenido: el cambio de cliente se hace desde '
            '«Cambiar cliente…», que primero muestra a qué afecta.',
            code='folder_has_content',
            hint='Usa el endpoint change-client para elegir si se propaga.',
            status=status.HTTP_409_CONFLICT,
        )
    serializer = DocumentFolderSerializer(folder, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_document_folder(request, folder_id):
    """Elimina una carpeta vacía.

    Los conteos NO excluyen lo archivado a propósito: contenido es contenido.
    Si excluyéramos los archivados, borrar una carpeta archivada dejaría a sus
    documentos archivados en la raíz (folder es SET_NULL) sin avisar. Para
    sacar de la vista una carpeta con contenido está archivar, no borrar.
    """
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _managed_client_folder_error(folder)
        or _system_managed_folder_error(folder)
    )
    if managed:
        return managed
    document_count = folder.documents.count()
    if document_count:
        return Response(
            {
                'detail': (
                    f'La carpeta tiene {document_count} documento(s). '
                    'Muévelos o elimínalos antes de borrarla.'
                ),
                'document_count': document_count,
            },
            status=status.HTTP_409_CONFLICT,
        )
    children_count = folder.children.count()
    if children_count:
        return Response(
            {
                'detail': (
                    f'La carpeta tiene {children_count} subcarpeta(s). '
                    'Muévelas o elimínalas antes de borrarla.'
                ),
                'children_count': children_count,
            },
            status=status.HTTP_409_CONFLICT,
        )
    folder.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def archive_document_folder(request, folder_id):
    """Archiva la carpeta y, en cascada, su contenido.

    A diferencia de eliminar, esto SÍ está permitido con contenido: no destruye
    nada. Devuelve cuánto arrastró para que la UI lo pueda reportar.
    """
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _managed_client_folder_error(folder)
        or _system_managed_folder_error(folder)
    )
    if managed:
        return managed
    try:
        counts = document_archive_service.archive_folder(folder)
    except document_archive_service.DocumentArchiveError as exc:
        # `detail` too: the MCP panel bridge only relays that key.
        return Response(
            {'error': str(exc), 'detail': str(exc), 'code': 'folder_archive_refused'},
            status=status.HTTP_409_CONFLICT,
        )
    return Response({
        'folder': _folder_payload(folder, scope='archived'),
        'archived_folders': counts['folders'],
        'archived_documents': counts['documents'],
    })


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def unarchive_document_folder(request, folder_id):
    """Restaura la carpeta, lo que su archivado arrastró, y su cadena de ancestros.

    Antes esto respondía 409 cuando el padre seguía archivado, y con eso una
    subcarpeta arrastrada por la cascada no tenía forma de volver. Ahora la
    cadena se reabre sola y viaja en `restored_chain` para que la UI la nombre;
    `restored_folders`/`restored_documents` siguen contando sólo la cascada
    propia.
    """
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _managed_client_folder_error(folder)
        or _system_managed_folder_error(folder)
    )
    if managed:
        return managed
    counts = document_archive_service.unarchive_folder(folder)
    return Response({
        'folder': _folder_payload(folder, scope='active'),
        'restored_folders': counts['folders'],
        'restored_documents': counts['documents'],
        'restored_chain': [
            {'id': ancestor.id, 'name': ancestor.name}
            for ancestor in counts['restored_chain']
        ],
        'moved_to_root': counts['moved_to_root'],
    })


def _resolve_target_profile(folder, raw_profile_id):
    """(profile, error_response) para el destino del cambio de cliente."""
    try:
        profile_id = int(raw_profile_id)
    except (TypeError, ValueError):
        return None, error_response(
            'Indica el cliente destino.', code='client_not_found',
        )
    profile = UserProfile.objects.clients().filter(pk=profile_id).first()
    if profile is None:
        return None, error_response(
            'Ese cliente no existe o no es un perfil de cliente.',
            code='client_not_found',
        )
    if folder.client_user_id == profile.user_id:
        return None, error_response(
            'La carpeta ya pertenece a ese cliente.', code='same_client',
        )
    return profile, None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def preview_document_folder_client_change(request, folder_id):
    """Impacto de mover la carpeta a otro cliente. No escribe nada."""
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _managed_client_folder_error(folder)
        or _system_managed_folder_error(folder)
    )
    if managed:
        return managed
    profile, error = _resolve_target_profile(
        folder, request.query_params.get('client_profile_id'),
    )
    if error:
        return error
    return Response(
        document_folder_service.change_client_preview(folder, profile),
    )


def _staleness_error(sent, current, *, subject):
    """409 si el plan confirmado ya no es el que hay. Mismo contrato PA-51."""
    missing = sorted(sent - current)
    if missing:
        count = len(missing)
        noun = 'elemento' if count == 1 else 'elementos'
        verb = 'está' if count == 1 else 'están'
        return error_response(
            f'{count} {noun} del plan ya no {verb} en la carpeta.',
            code='records_not_found',
            hint='La vista previa se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'missing_ids': missing},
        )
    changed = sorted(current - sent)
    if changed:
        count = len(changed)
        noun = f'{subject}' if count == 1 else f'{subject}s'
        verb = 'entró' if count == 1 else 'entraron'
        return error_response(
            f'{count} {noun} {verb} a la carpeta después de la vista previa.',
            code='records_changed',
            hint='La vista previa se actualizó. Revísala y vuelve a intentarlo.',
            status=status.HTTP_409_CONFLICT,
            errors={'changed_ids': changed},
        )
    return None


@api_view(['POST'])
@permission_classes([IsAdminUser])
def change_document_folder_client(request, folder_id):
    """Mueve la carpeta a otro cliente, con la cascada del modo elegido.

    El PATCH genérico se niega con `folder_has_content`: éste es el único
    camino, así que un cambio de dueño siempre es explícito, previsto y
    auditado. Los ids viajan como token — ambos chequeos corren ANTES del
    servicio, así que su bloque atómico nunca se abre sobre un plan viejo.
    """
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    managed = (
        _managed_folder_error(folder)
        or _managed_client_folder_error(folder)
        or _system_managed_folder_error(folder)
    )
    if managed:
        return managed

    serializer = DocumentFolderChangeClientSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    mode = serializer.validated_data['mode']
    if mode not in document_folder_service.MODES:
        return error_response(
            "Elige qué hacer con el contenido: 'propagate' (seguir a la "
            "carpeta) o 'folder_only' (sólo la carpeta).",
            code='invalid_mode',
        )
    profile, error = _resolve_target_profile(
        folder, serializer.validated_data['client_profile_id'],
    )
    if error:
        return error

    plan = document_folder_service.linked_sets(folder)
    error = _staleness_error(
        set(serializer.validated_data['document_ids']),
        {document.pk for document in plan['documents_move']},
        subject='documento',
    )
    if error:
        return error
    error = _staleness_error(
        set(serializer.validated_data['folder_ids']),
        {child.pk for child in plan['folders_move']},
        subject='subcarpeta',
    )
    if error:
        return error

    result = document_folder_service.change_client_apply(
        folder, profile, mode, request.user,
    )
    return Response({
        'folder': _folder_payload(
            folder, scope='archived' if folder.is_archived else 'active',
        ),
        **result,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reorder_document_folders(request):
    ids = request.data.get('ids', [])
    if not isinstance(ids, list):
        return Response({'ids': 'Debe ser una lista.'}, status=status.HTTP_400_BAD_REQUEST)
    folders = list(DocumentFolder.objects.filter(pk__in=ids))
    system_managed = next(
        (folder for folder in folders if folder.is_system_managed),
        None,
    )
    managed = _system_managed_folder_error(system_managed)
    if managed:
        return managed

    # Las raíces gestionadas —de proyecto y de cliente— se ordenan por el nombre
    # de la entidad que representan y no participan del orden manual. Ignorarlas
    # mantiene compatible el payload de clientes antiguos que todavía envían
    # todas las raíces juntas.
    folders_by_id = {
        folder.id: folder
        for folder in folders
        if not folder.managed_project_id and not folder.managed_client_id
    }
    for order, folder_id in enumerate(ids):
        if folder_id in folders_by_id:
            folders_by_id[folder_id].order = order
    DocumentFolder.objects.bulk_update(folders_by_id.values(), ['order'])
    return Response({'status': 'ok'})
