"""Only transactional writer of the private alliance contract and its mirror."""
import hashlib
import logging
import re

from django.db import transaction
from django.utils import timezone

from content.models import BuildingWithUsContract, BuildingWithUsContractMirror, BuildingWithUsContractRevision, Document, DocumentFolder
from content.services.building_with_us_content import BuildingWithUsError
from content.services.contract_template_service import _diff_summary
from content.services.contract_template_validation import ContractTemplateError, apply_patches, markdown_diff
from content.services.document_note_service import create_note
from content.services.document_pdf_service import DocumentPdfService
from content.services.document_type_utils import get_markdown_document_type
from content.services.document_write_service import document_etag
from content.services.pdf_utils import add_watermark_to_pdf

logger = logging.getLogger(__name__)
CONTRACT_TITLE = 'Contrato de alianza comercial — Building with Us'
MIRROR_POINTER = (
    f'# {CONTRACT_TITLE}\n\nEste documento muestra en vivo el contrato vigente de Building with Us. '
    'Se edita desde el MCP «Building with Us».'
)
INITIALIZATION_NOTE = 'Inicialización del espejo contractual de sólo lectura.'
PENDING_DECISIONS_V1 = """Inventario de decisiones pendientes para revisión de la versión inicial.

PA-174:
1. ¿Hitos comunes o por proyecto? V1 adopta un esquema común de referencia ajustable por proyecto en Anexo B (cláusula 7).
2. ¿Qué ocurre al abandonar a mitad de camino según el modelo? V1 aplica pérdida de participación al salir o abandonar antes del éxito en todos los modelos (cláusula 14).
3. ¿Quién conserva el producto y el código al terminar? V1 reconoce desarrollos según participación consolidada, activos preexistentes propios y reasignación por incumplimiento (cláusula 11).
4. ¿Quién paga hosting, mantenimiento y soporte en producción? V1 usa primero ingresos del PRODUCTO y luego aportes proporcionales a la participación bajo presupuesto acordado (cláusula 12).
5. ¿Habrá exclusividad? V1 exige exclusividad del ALIADO durante la alianza y doce meses después; PROJECTAPP no atiende un competidor directo con un producto sustancialmente similar durante la vigencia (cláusula 13).
6. ¿Los modelos conviven o se elige uno por caso? V1 permite que convivan en el programa y elige uno por alianza; cambiar exige otrosí (cláusula 2).
7. ¿La cuota mensual es fija o depende del tamaño? V1 usa una referencia y fija el importe efectivo según el alcance (cláusula 2).
8. ¿Qué es público? Decidido: ninguna cifra pública; los valores sólo están en el contrato y sus Condiciones particulares (cláusula 2).

PA-175:
9. ¿Quién declara un hito y resuelve desacuerdos? V1 adopta comité con un representante por parte, acta firmada y mecanismo de controversias (cláusulas 7 y 20).
10. ¿Cómo se mide el compromiso esperado? V1 usa pagos oportunos, validaciones en cinco días hábiles y presupuesto propio de ventas ejecutado con reporte mensual (cláusula 6).
11. ¿Sobre qué recae la participación? V1 la define sobre derechos económicos del PRODUCTO: ingresos netos y valor de venta o licenciamiento, sin participación societaria (cláusula 8).
12. ¿Cómo queda la propiedad intelectual y el código al terminar? V1 conserva los activos preexistentes, reconoce participación consolidada y licencia de componentes para el PRODUCTO (cláusula 11).
13. ¿Cómo se pacta la salida? V1 permite aviso escrito de treinta días; salida del ALIADO antes del éxito pierde participación y salida sin causa de PROJECTAPP conserva lo consolidado con código y licencia (cláusula 14).
14. ¿Cuál es la relación con el contrato de desarrollo? V1 mantiene objetos, pagos y obligaciones independientes; no hay modificación tácita ni compensación sin acuerdo (cláusula 17).

Borrador para revisión del operador y de un asesor jurídico antes de usarlo con un aliado."""


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _load(*, lock=False):
    try:
        return BuildingWithUsContract.load(lock=lock)
    except BuildingWithUsContract.DoesNotExist as exc:
        raise BuildingWithUsError('El contrato no está configurado.', code='NOT_FOUND') from exc


def contract_etag(revision):
    return _hash(f'bwu:contract:{revision.pk}:{revision.version}:{_hash(revision.markdown)}')


def _mirror(contract, *, lock=False):
    queryset = BuildingWithUsContractMirror.objects.filter(contract=contract)
    if lock:
        # Lock only the mirror here; the Document is locked separately afterwards.
        return queryset.select_for_update().first()
    return queryset.select_related('document__folder', 'revision').first()


def resource_etags(arguments=None):
    contract = _load()
    mirror = _mirror(contract)
    resources = {'contract': contract_etag(contract.current_revision), 'mirror': 'none'}
    if mirror:
        identity = (
            f'{mirror.pk}:{mirror.document_id}:{mirror.document.folder_id}:{mirror.revision_id}:'
            f'{mirror.synced_at.isoformat()}:{document_etag(mirror.document)}'
        )
        resources['mirror'] = _hash(identity)
    if isinstance(arguments, dict) and 'folder_id' in arguments:
        folder = _folder(arguments['folder_id'])
        resources['folder'] = _hash(
            f'{folder.pk}:{folder.name}:{folder.parent_id}:{folder.is_archived}:'
            f'{folder.client_user_id}:{folder.project_id}:{folder.updated_at.isoformat()}'
        ) if folder else 'none'
    return resources


def validate_markdown(markdown):
    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 250000:
        raise BuildingWithUsError('markdown debe ser texto no vacío de hasta 250000 caracteres.')
    first = next(line for line in markdown.splitlines() if line.strip())
    if not first.startswith('# '):
        raise BuildingWithUsError('La primera línea no vacía debe ser un título de nivel uno (# ).')
    if re.search(r'\{[a-z_][a-z0-9_]*\}', markdown):
        raise BuildingWithUsError('Usa XXX-XXX-XXX para los espacios por completar; no se admiten placeholders.',
                                  code='PLACEHOLDER_NOT_SUPPORTED')
    return markdown


def _allowed_folder(folder):
    if not folder or folder.is_archived or folder.client_user_id or folder.project_id or folder.system_key:
        return False
    from content.services.contract_mirror_service import pinned_mirror_folder

    pinned, _source = pinned_mirror_folder()
    return folder.pk == pinned.pk if pinned else folder.name == 'Contratos'


def _folder(folder_id, *, lock=False):
    if type(folder_id) is not int or folder_id < 1:
        raise BuildingWithUsError('folder_id debe ser un entero positivo.', code='FOLDER_NOT_ALLOWED')
    queryset = DocumentFolder.objects.select_for_update() if lock else DocumentFolder.objects
    return queryset.filter(pk=folder_id).first()


def _mirror_status(contract, mirror):
    document = mirror.document if mirror else None
    folder = document.folder if document and document.folder_id else None
    synchronized = bool(mirror and mirror.revision_id == contract.current_revision_id
                        and mirror.pdf_content and bytes(mirror.pdf_content).startswith(b'%PDF-')
                        and not document.is_archived and _allowed_folder(folder))
    return {
        'status': 'synchronized' if synchronized else 'out_of_sync' if mirror else 'not_initialized',
        'document_id': document.pk if document else None,
        'title': document.title if document else CONTRACT_TITLE,
        'folder_id': folder.pk if folder else None,
        'folder_path': ' › '.join([*[row.name for row in folder.get_ancestors()], folder.name]) if folder else None,
        'version': mirror.revision.version if mirror else None,
        'last_synced_at': mirror.synced_at.isoformat() if mirror else None,
    }


def mirror_status():
    contract = _load()
    return _mirror_status(contract, _mirror(contract))


def read_contract():
    contract = _load()
    revision = contract.current_revision
    return {
        'markdown': revision.markdown, 'version': revision.version, 'version_id': revision.pk,
        'updated_at': contract.updated_at.isoformat(), 'author': revision.author_label,
        'change_note': revision.change_note, 'etag': contract_etag(revision),
        'mirror': _mirror_status(contract, _mirror(contract)),
    }


def list_versions(*, offset=0, limit=20, include_content=False):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50 or type(include_content) is not bool:
        raise BuildingWithUsError('Usa offset >= 0, limit entre 1 y 50 e include_content booleano.')
    queryset = BuildingWithUsContractRevision.objects.select_related('restored_from')
    versions = []
    for row in queryset[offset:offset + limit]:
        item = {
            'version_id': row.pk, 'version': row.version, 'author': row.author_label,
            'created_at': row.created_at.isoformat(), 'change_note': row.change_note,
            'restored_from_version_id': row.restored_from_id,
            'restored_from_version': row.restored_from.version if row.restored_from_id else None,
        }
        if include_content:
            item['markdown'] = row.markdown
        versions.append(item)
    return {'total': queryset.count(), 'versions': versions}


def prepare_update(arguments, *, restore=False, require_match=False):
    allowed = {'version_id' if restore else 'markdown', 'if_match', 'change_note'}
    if not restore:
        allowed.add('patches')
    if not isinstance(arguments, dict) or set(arguments) - allowed:
        raise BuildingWithUsError('Hay argumentos desconocidos.')
    sources = [key for key in ('markdown', 'patches', 'version_id') if key in arguments]
    if len(sources) != 1 or (restore and sources != ['version_id']):
        raise BuildingWithUsError('Indica exactamente markdown o patches; para restaurar usa version_id.')
    contract = _load()
    current = contract.current_revision
    etag = contract_etag(current)
    if require_match and not arguments.get('if_match'):
        raise BuildingWithUsError('if_match es obligatorio.', code='PRECONDITION_REQUIRED')
    if 'if_match' in arguments and arguments['if_match'] != etag:
        raise BuildingWithUsError('El contrato cambió; vuelve a leerlo.', code='STALE_VERSION', details={'current_etag': etag})
    note = arguments.get('change_note', '')
    if not isinstance(note, str) or len(note.strip()) > 4000 or (require_match and not note.strip()):
        raise BuildingWithUsError('change_note debe explicar el cambio (entre 1 y 4000 caracteres).')
    if restore:
        version_id = arguments['version_id']
        if type(version_id) is not int or version_id < 1:
            raise BuildingWithUsError('version_id debe ser un entero positivo.')
        revision = BuildingWithUsContractRevision.objects.filter(pk=version_id).first()
        if revision is None:
            raise BuildingWithUsError('La versión no existe.', code='NOT_FOUND')
        markdown = revision.markdown
    elif 'markdown' in arguments:
        markdown = arguments['markdown']
    else:
        try:
            markdown = apply_patches(current.markdown, arguments['patches'])
        except ContractTemplateError as exc:
            raise BuildingWithUsError(str(exc), code=exc.code, details=exc.details) from exc
    validate_markdown(markdown)
    mirror = _mirror(contract)
    if require_match and mirror is None:
        raise BuildingWithUsError('Inicializa primero el espejo en Contratos.', code='MIRROR_NOT_INITIALIZED')
    return {
        'changed': markdown != current.markdown, 'markdown': markdown,
        'diff': markdown_diff(current.markdown, markdown, 'building-with-us'), 'placeholders': [],
        'document_to_sync': {'document_id': mirror.document_id if mirror else None, 'status': 'ready' if mirror else 'missing'},
        'resource_etags': resource_etags(),
    }


def render_pdf(markdown, document=None):
    """The Gestor's markdown renderer, including the saved cover/style choices."""
    options = {key: getattr(document, key) for key in (
        'include_portada', 'include_subportada', 'include_contraportada', 'template_style',
    )} if document else {}
    pdf = DocumentPdfService.generate_from_markdown(title=CONTRACT_TITLE, markdown_text=markdown, language='es', **options)
    if not pdf or not pdf.startswith(b'%PDF-'):
        raise ValueError('El renderizador no produjo un PDF.')
    pdf = add_watermark_to_pdf(pdf)
    if not pdf or not pdf.startswith(b'%PDF-'):
        raise ValueError('El PDF con marca de agua no es válido.')
    return pdf


def _sync_error(exc, *, stage, document_id=None):
    logger.exception('Building with Us mirror synchronization failed document_id=%s stage=%s', document_id, stage)
    return BuildingWithUsError('No se sincronizó el espejo; no se aplicó ningún cambio.', code='MIRROR_SYNC_FAILED',
                               details={'stage': stage, 'applied': False})


def _synchronize(contract, revision, mirror, *, actor, note, diff):
    stage = 'pdf'
    try:
        pdf = render_pdf(revision.markdown, mirror.document)
        stage = 'mirror'
        mirror.revision = revision
        mirror.pdf_content = pdf
        mirror.synced_at = timezone.now()
        mirror.save()
        mirror.document.save(update_fields=['updated_at'])
        stage = 'private_note'
        create_note(mirror.document, actor=actor, title=f'Contrato Building with Us — versión {revision.version}',
                    content=f'Versión {revision.version}\nFecha: {mirror.synced_at.isoformat()}\n{note}\n\n{_diff_summary(diff)}')
    except Exception as exc:
        raise _sync_error(exc, stage=stage, document_id=mirror.document_id) from exc


@transaction.atomic
def apply_update(arguments, *, actor, credential=None, restore=False, expected_etags=None):
    contract = _load(lock=True)
    mirror = _mirror(contract, lock=True)
    if mirror:
        mirror.document = Document.objects.select_for_update().get(pk=mirror.document_id)
    if expected_etags is not None and expected_etags != resource_etags():
        raise BuildingWithUsError('El contrato o su espejo cambió desde la vista previa.', code='STALE_VERSION')
    prepared = prepare_update(arguments, restore=restore, require_match=True)
    if mirror.document.is_archived or not _allowed_folder(mirror.document.folder):
        raise BuildingWithUsError('El espejo debe permanecer activo en una carpeta interna Contratos.',
                                  code='MIRROR_SYNC_FAILED', details={'stage': 'mirror', 'applied': False})
    if not prepared['changed']:
        return {'applied': True, 'changed': False}
    revision = BuildingWithUsContractRevision.objects.create(
        version=contract.current_revision.version + 1, markdown=prepared['markdown'], author=actor, credential=credential,
        author_label=actor.get_username() if actor else 'Consola', change_note=arguments['change_note'].strip(),
        restored_from_id=arguments['version_id'] if restore else None,
    )
    contract.current_revision = revision
    contract.save(update_fields=['current_revision', 'updated_at'])
    _synchronize(contract, revision, mirror, actor=actor, note=revision.change_note, diff=prepared['diff'])
    return {'applied': True, 'changed': True, 'version': revision.version, 'version_id': revision.pk,
            'etag': contract_etag(revision), 'mirror': _mirror_status(contract, mirror)}


def _initialization_outcome(contract, mirror, folder):
    if mirror is None:
        return 'create'
    return 'noop' if mirror.document.folder_id == folder.pk and _mirror_status(contract, mirror)['status'] == 'synchronized' else 'resync'


def prepare_initialization(folder_id):
    """Validate and describe explicit initialization without creating a document."""
    folder = _folder(folder_id)
    if not _allowed_folder(folder):
        raise BuildingWithUsError('Elige una carpeta interna, activa y manual llamada Contratos.', code='FOLDER_NOT_ALLOWED')
    contract = _load()
    mirror = _mirror(contract)
    return {'outcome': _initialization_outcome(contract, mirror, folder), 'folder_id': folder.pk,
            'mirror': _mirror_status(contract, mirror), 'resource_etags': resource_etags({'folder_id': folder_id})}


@transaction.atomic
def initialize_mirror(folder_id, *, actor, expected_etags=None):
    contract = _load(lock=True)
    mirror = _mirror(contract, lock=True)
    if mirror:
        mirror.document = Document.objects.select_for_update().get(pk=mirror.document_id)
    folder = _folder(folder_id, lock=True)
    if expected_etags is not None and expected_etags != resource_etags({'folder_id': folder_id}):
        raise BuildingWithUsError('El contrato, su espejo o la carpeta cambió desde la vista previa.', code='STALE_VERSION')
    if not _allowed_folder(folder):
        raise BuildingWithUsError('Elige una carpeta interna, activa y manual llamada Contratos.', code='FOLDER_NOT_ALLOWED')
    outcome = _initialization_outcome(contract, mirror, folder)
    if outcome == 'noop':
        return {'outcome': outcome, 'mirror': _mirror_status(contract, mirror)}
    if mirror is None:
        document = Document.objects.create(
            document_type=get_markdown_document_type(), title=CONTRACT_TITLE, folder=folder,
            language='es', is_client_visible=False, content_markdown=MIRROR_POINTER, created_by=actor,
        )
        mirror = BuildingWithUsContractMirror(contract=contract, document=document, revision=contract.current_revision,
                                            synced_at=timezone.now())
    else:
        document = mirror.document
        document.folder = folder
        document.title = CONTRACT_TITLE
        document.is_client_visible = False
        document.is_archived = False
        document.archived_at = None
        document.archived_via_folder = None
        document.save(update_fields=['folder', 'title', 'is_client_visible', 'is_archived', 'archived_at', 'archived_via_folder', 'updated_at'])
    _synchronize(contract, contract.current_revision, mirror, actor=actor, note=INITIALIZATION_NOTE, diff='')
    if outcome == 'create':
        try:
            create_note(document, actor=actor, title='Inventario de decisiones pendientes (v1)', content=PENDING_DECISIONS_V1)
        except Exception as exc:
            raise _sync_error(exc, stage='private_note', document_id=document.pk) from exc
    return {'outcome': outcome, 'mirror': _mirror_status(contract, mirror)}


def current_pdf():
    """Serve a synchronized artifact, or render the current text without writing."""
    contract = _load()
    mirror = _mirror(contract)
    if _mirror_status(contract, mirror)['status'] == 'synchronized':
        return bytes(mirror.pdf_content), contract.current_revision.version
    try:
        return render_pdf(contract.current_revision.markdown, mirror.document if mirror else None), contract.current_revision.version
    except Exception as exc:
        raise BuildingWithUsError('El PDF vigente no está disponible.', code='PDF_RENDER_FAILED') from exc
